"""Config flow for the KEPCO ON integration."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import voluptuous as vol
from aiohttp import CookieJar
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import KepcoOnClient
from .auth import KepcoOnAuth
from .const import (
    CONF_ACCOUNT_UID_HASH,
    CONF_CUSTOMERS,
    CONF_DISPLAY_NAME,
    CONF_SAVE_PASSWORD,
    CONF_SELECTED_CUSTOMERS,
    CONF_SESSION_HANDOFF,
    CONF_USERNAME,
    DATA_APARTMENT_NAME,
    DATA_CONTRACT_METHOD,
    DATA_CUSTOMER_NUMBER,
    DATA_DONG,
    DATA_HO,
    DATA_HOUSE_CONTRACT_NUMBER,
    DATA_IS_SUPPORTED,
    DATA_STABLE_KEY,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DOMAIN,
    OPT_CO2_FACTOR_KG_PER_KWH,
    OPT_ENABLE_CO2_ESTIMATE,
    OPT_ENABLE_DETAILED_SENSORS,
    OPT_HISTORY_MONTHS,
    OPT_POLLING_INTERVAL_HOURS,
    POLLING_INTERVAL_HOURS,
)
from .exceptions import (
    KepcoOnAuthError,
    KepcoOnConnectionError,
    KepcoOnMfaRequired,
    KepcoOnNoCustomersError,
    KepcoOnProtocolError,
    KepcoOnRateLimitError,
    KepcoOnUnsupportedAccount,
)
from .models import KepcoAccountSession, KepcoCustomer
from .session_store import session_to_payload

DEFAULT_TITLE = "한전ON"
DEFAULT_CO2_FACTOR = 0.459
DEFAULT_HISTORY_MONTHS = 12


class FlowSessionStore:
    """In-memory store for one config-flow login attempt."""

    def __init__(self) -> None:
        self.session: KepcoAccountSession | None = None

    async def async_load(self) -> KepcoAccountSession | None:
        """Return the captured session."""
        return self.session

    async def async_save(self, session: KepcoAccountSession) -> None:
        """Capture a session without writing persistent storage."""
        self.session = session

    async def async_clear(self) -> None:
        """Clear the captured session."""
        self.session = None


@dataclass(slots=True)
class PendingConfig:
    """State held between user and customer steps."""

    username: str
    password: str
    save_password: bool
    display_name: str
    account_uid_hash: str
    customers: tuple[KepcoCustomer, ...]
    session: KepcoAccountSession
    client_session: Any


def _account_uid_hash(user_id: str) -> str:
    return hashlib.sha256(f"kepco_on:{user_id.strip()}".encode()).hexdigest()


def _serialize_customer(customer: KepcoCustomer) -> dict[str, Any]:
    return {
        DATA_STABLE_KEY: customer.stable_key,
        DATA_APARTMENT_NAME: customer.apartment_name,
        DATA_DONG: customer.dong,
        DATA_HO: customer.ho,
        DATA_CONTRACT_METHOD: customer.contract_method,
        DATA_IS_SUPPORTED: customer.is_supported,
        DATA_CUSTOMER_NUMBER: customer.customer_number,
        DATA_HOUSE_CONTRACT_NUMBER: customer.house_contract_number,
    }


def _deserialize_customer(payload: Mapping[str, Any]) -> KepcoCustomer:
    return KepcoCustomer(
        stable_key=str(payload[DATA_STABLE_KEY]),
        apartment_name=str(payload[DATA_APARTMENT_NAME]),
        dong=str(payload[DATA_DONG]),
        ho=str(payload[DATA_HO]),
        contract_method=str(payload[DATA_CONTRACT_METHOD]),
        is_supported=bool(payload[DATA_IS_SUPPORTED]),
        _customer_number=str(payload[DATA_CUSTOMER_NUMBER]),
        _house_contract_number=str(payload[DATA_HOUSE_CONTRACT_NUMBER]),
    )


def _customer_label(customer: KepcoCustomer) -> str:
    return f"{customer.apartment_name} {customer.dong}동 {customer.ho}호"


def _customer_options(customers: tuple[KepcoCustomer, ...]) -> list[selector.SelectOptionDict]:
    return [
        selector.SelectOptionDict(value=customer.stable_key, label=_customer_label(customer))
        for customer in customers
    ]


def _customer_schema(
    customers: tuple[KepcoCustomer, ...],
    selected: list[str] | None = None,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SELECTED_CUSTOMERS, default=selected or []): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_customer_options(customers),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def _base_user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_SAVE_PASSWORD, default=False): bool,
            vol.Optional(CONF_DISPLAY_NAME, default=""): str,
        }
    )


def _map_error(err: Exception) -> str:
    if isinstance(err, KepcoOnMfaRequired):
        return "mfa_required"
    if isinstance(err, KepcoOnAuthError):
        return "invalid_auth"
    if isinstance(err, KepcoOnRateLimitError):
        return "rate_limited"
    if isinstance(err, KepcoOnConnectionError):
        return "cannot_connect"
    if isinstance(err, KepcoOnUnsupportedAccount):
        return "unsupported_account"
    if isinstance(err, KepcoOnNoCustomersError):
        return "no_customers"
    if isinstance(err, KepcoOnProtocolError):
        return "protocol_changed"
    return "unknown"


def _stored_customers(entry_data: Mapping[str, Any]) -> tuple[KepcoCustomer, ...] | None:
    try:
        customers = tuple(
            _deserialize_customer(cast("Mapping[str, Any]", payload))
            for payload in entry_data.get(CONF_CUSTOMERS, [])
        )
    except KeyError, TypeError, ValueError:
        return None
    if not customers:
        return None
    return customers


def _valid_selected(selected: object, available: set[str]) -> list[str] | None:
    if not isinstance(selected, list) or not selected:
        return None
    normalized = [str(value) for value in selected]
    if any(value not in available for value in normalized):
        return None
    return normalized


async def _close_session(client_session: Any | None) -> None:
    if client_session is not None and not getattr(client_session, "closed", False):
        await client_session.close()


class KepcoOnConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle KEPCO ON config, reauth, and reconfigure flows."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending: PendingConfig | None = None

    @callback
    def async_remove(self) -> None:
        """Close any pending dedicated login session when the flow is abandoned."""
        pending = self._pending
        self._pending = None
        if pending is not None:
            asyncio.get_running_loop().create_task(_close_session(pending.client_session))
        super().async_remove()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return KepcoOnOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user credential step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_base_user_schema())

        await _close_session(self._pending.client_session if self._pending else None)
        self._pending = None
        client_session = async_create_clientsession(
            self.hass,
            auto_cleanup=False,
            cookie_jar=CookieJar(),
        )
        try:
            store = FlowSessionStore()
            auth = KepcoOnAuth(client_session, store=store)
            session = await auth.async_login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            client = KepcoOnClient(auth)
            await client.async_get_account_type()
            customers = await client.async_get_customers()
            if not customers:
                raise KepcoOnNoCustomersError("No KEPCO ON apartment customers found")
            account_uid_hash = _account_uid_hash(session.user_id)
            await self.async_set_unique_id(account_uid_hash)
            self._abort_if_unique_id_configured()
        except AbortFlow as err:
            await _close_session(client_session)
            return self.async_abort(reason=err.reason)
        except Exception as err:
            await _close_session(client_session)
            return self.async_show_form(
                step_id="user",
                data_schema=_base_user_schema(),
                errors={"base": _map_error(err)},
            )

        self._pending = PendingConfig(
            username=str(user_input[CONF_USERNAME]).strip(),
            password=str(user_input[CONF_PASSWORD]),
            save_password=bool(user_input.get(CONF_SAVE_PASSWORD, False)),
            display_name=str(user_input.get(CONF_DISPLAY_NAME) or "").strip(),
            account_uid_hash=account_uid_hash,
            customers=tuple(customers),
            session=session,
            client_session=client_session,
        )
        return self.async_show_form(
            step_id="customer",
            data_schema=_customer_schema(tuple(customers), [customers[0].stable_key]),
        )

    async def async_step_customer(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select one or more customers after authentication."""
        if self._pending is None:
            return await self.async_step_user()
        available = {customer.stable_key for customer in self._pending.customers}
        if user_input is None:
            return self.async_show_form(
                step_id="customer",
                data_schema=_customer_schema(self._pending.customers),
            )
        selected = _valid_selected(user_input.get(CONF_SELECTED_CUSTOMERS), available)
        if selected is None:
            return self.async_show_form(
                step_id="customer",
                data_schema=_customer_schema(self._pending.customers),
                errors={"base": "invalid_selection"},
            )

        pending = self._pending
        data: dict[str, Any] = {
            CONF_USERNAME: pending.username,
            CONF_SAVE_PASSWORD: pending.save_password,
            CONF_ACCOUNT_UID_HASH: pending.account_uid_hash,
            CONF_CUSTOMERS: [_serialize_customer(customer) for customer in pending.customers],
            CONF_SELECTED_CUSTOMERS: selected,
            CONF_SESSION_HANDOFF: session_to_payload(pending.session),
        }
        if pending.display_name:
            data[CONF_DISPLAY_NAME] = pending.display_name
        if pending.save_password:
            data[CONF_PASSWORD] = pending.password
        title = pending.display_name or DEFAULT_TITLE
        await _close_session(pending.client_session)
        self._pending = None
        return self.async_create_entry(title=title, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm credentials for an existing config entry."""
        entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_PASSWORD): selector.TextSelector(
                            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                        )
                    }
                ),
            )
        client_session = async_create_clientsession(
            self.hass,
            auto_cleanup=False,
            cookie_jar=CookieJar(),
        )
        try:
            store = FlowSessionStore()
            username = str(entry.data[CONF_USERNAME])
            password = str(user_input[CONF_PASSWORD])
            auth = KepcoOnAuth(
                client_session,
                store=store,
                reauth_username=username,
                reauth_password=password,
            )
            session = await auth.async_login(username, password)
            account_uid_hash = _account_uid_hash(session.user_id)
            if account_uid_hash != entry.unique_id and account_uid_hash != entry.data.get(
                CONF_ACCOUNT_UID_HASH
            ):
                raise KepcoOnAuthError("Authenticated KEPCO ON account does not match entry")
            client = KepcoOnClient(auth)
            await client.async_get_account_type()
            customers = await client.async_get_customers()
            if not customers:
                raise KepcoOnNoCustomersError("No KEPCO ON apartment customers found")
        except Exception as err:
            await _close_session(client_session)
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_PASSWORD): selector.TextSelector(
                            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                        )
                    }
                ),
                errors={"base": _map_error(err)},
            )

        new_keys = {customer.stable_key for customer in customers}
        current = [str(value) for value in entry.data.get(CONF_SELECTED_CUSTOMERS, [])]
        preserved = [key for key in current if key in new_keys]
        if not preserved and customers:
            preserved = [customers[0].stable_key]
        data = dict(entry.data)
        data[CONF_ACCOUNT_UID_HASH] = account_uid_hash
        data[CONF_CUSTOMERS] = [_serialize_customer(customer) for customer in customers]
        data[CONF_SELECTED_CUSTOMERS] = preserved
        data[CONF_SESSION_HANDOFF] = session_to_payload(session)
        if data.get(CONF_SAVE_PASSWORD):
            data[CONF_PASSWORD] = str(user_input[CONF_PASSWORD])
        else:
            data.pop(CONF_PASSWORD, None)
        await _close_session(client_session)
        return self.async_update_reload_and_abort(
            entry,
            data=data,
            reason="reauth_successful",
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Update customer selection for an existing entry."""
        entry = self._get_reconfigure_entry()
        customers = _stored_customers(entry.data)
        if customers is None:
            return self.async_abort(reason="no_customers")
        current = [str(value) for value in entry.data.get(CONF_SELECTED_CUSTOMERS, [])]
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_customer_schema(customers, current),
            )
        selected = _valid_selected(
            user_input.get(CONF_SELECTED_CUSTOMERS),
            {customer.stable_key for customer in customers},
        )
        if selected is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_customer_schema(customers, current),
                errors={"base": "invalid_selection"},
            )
        return self.async_update_reload_and_abort(
            entry,
            data_updates={CONF_SELECTED_CUSTOMERS: selected},
            reason="reconfigure_successful",
        )


class KepcoOnOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle KEPCO ON options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        customers = _stored_customers(self._config_entry.data) or ()
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=self._schema(customers))

        options, error = self._validate_options(customers, user_input)
        if error is not None:
            return self.async_show_form(
                step_id="init",
                data_schema=self._schema(customers),
                errors={"base": error},
            )
        return self.async_create_entry(title=None, data=options)

    def _schema(self, customers: tuple[KepcoCustomer, ...]) -> vol.Schema:
        options = self._config_entry.options
        data = self._config_entry.data
        selected = list(options.get(CONF_SELECTED_CUSTOMERS, data.get(CONF_SELECTED_CUSTOMERS, [])))
        return vol.Schema(
            {
                vol.Required(
                    OPT_POLLING_INTERVAL_HOURS,
                    default=options.get(OPT_POLLING_INTERVAL_HOURS, DEFAULT_POLLING_INTERVAL_HOURS),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[str(value) for value in POLLING_INTERVAL_HOURS],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SELECTED_CUSTOMERS, default=selected): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_customer_options(customers),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    OPT_ENABLE_DETAILED_SENSORS,
                    default=options.get(OPT_ENABLE_DETAILED_SENSORS, False),
                ): bool,
                vol.Optional(
                    OPT_ENABLE_CO2_ESTIMATE,
                    default=options.get(OPT_ENABLE_CO2_ESTIMATE, False),
                ): bool,
                vol.Required(
                    OPT_CO2_FACTOR_KG_PER_KWH,
                    default=options.get(OPT_CO2_FACTOR_KG_PER_KWH, DEFAULT_CO2_FACTOR),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10,
                        step="any",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    OPT_HISTORY_MONTHS,
                    default=options.get(OPT_HISTORY_MONTHS, DEFAULT_HISTORY_MONTHS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=24,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    def _validate_options(
        self,
        customers: tuple[KepcoCustomer, ...],
        user_input: Mapping[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        selected = _valid_selected(
            user_input.get(CONF_SELECTED_CUSTOMERS),
            {customer.stable_key for customer in customers},
        )
        if selected is None:
            return {}, "invalid_selection"
        try:
            interval = int(
                user_input.get(OPT_POLLING_INTERVAL_HOURS, DEFAULT_POLLING_INTERVAL_HOURS)
            )
        except TypeError, ValueError:
            return {}, "unknown"
        if interval not in POLLING_INTERVAL_HOURS:
            return {}, "unknown"
        try:
            co2_factor = float(
                Decimal(str(user_input.get(OPT_CO2_FACTOR_KG_PER_KWH, DEFAULT_CO2_FACTOR)))
            )
        except InvalidOperation, ValueError:
            return {}, "invalid_co2_factor"
        if co2_factor <= 0 or co2_factor > 10:
            return {}, "invalid_co2_factor"
        try:
            history_months = int(user_input.get(OPT_HISTORY_MONTHS, DEFAULT_HISTORY_MONTHS))
        except TypeError, ValueError:
            return {}, "invalid_history_months"
        if not 1 <= history_months <= 24:
            return {}, "invalid_history_months"
        return (
            {
                OPT_POLLING_INTERVAL_HOURS: interval,
                CONF_SELECTED_CUSTOMERS: selected,
                OPT_ENABLE_DETAILED_SENSORS: bool(
                    user_input.get(OPT_ENABLE_DETAILED_SENSORS, False)
                ),
                OPT_ENABLE_CO2_ESTIMATE: bool(user_input.get(OPT_ENABLE_CO2_ESTIMATE, False)),
                OPT_CO2_FACTOR_KG_PER_KWH: co2_factor,
                OPT_HISTORY_MONTHS: history_months,
            },
            None,
        )


__all__ = ["KepcoOnConfigFlow", "KepcoOnOptionsFlow"]
