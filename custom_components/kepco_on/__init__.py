"""Config entry lifecycle for the KEPCO ON integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiohttp import ClientSession, CookieJar
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .api import KepcoOnClient
from .auth import KepcoOnAuth
from .const import (
    CONF_DISPLAY_NAME,
    CONF_SESSION_HANDOFF,
    CONF_USERNAME,
    CONFIG_ENTRY_VERSION,
    DEFAULT_TITLE,
    OPT_ENABLE_CO2_ESTIMATE,
    OPT_ENABLE_DETAILED_SENSORS,
    PLATFORMS,
)
from .coordinator import KepcoOnDataUpdateCoordinator
from .exceptions import (
    KepcoOnAuthError,
    KepcoOnConnectionError,
    KepcoOnNoCustomersError,
    KepcoOnProtocolError,
    KepcoOnRateLimitError,
    KepcoOnUnsupportedAccount,
)
from .models import customer_selection_title, strict_selected_stored_customers
from .repairs import async_clear_issue, async_create_issue
from .services import async_setup_services
from .session_store import KepcoOnSessionStore, session_from_payload

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class KepcoOnRuntimeData:
    """Runtime objects owned by one KEPCO ON config entry."""

    client: KepcoOnClient
    auth: KepcoOnAuth
    coordinator: KepcoOnDataUpdateCoordinator
    session_store: KepcoOnSessionStore
    session: ClientSession


type KepcoOnConfigEntry = ConfigEntry[KepcoOnRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict[str, object]) -> bool:
    """Set up KEPCO ON integration-level services."""
    del config
    await async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy sensor options and default presentation names."""
    if entry.version == CONFIG_ENTRY_VERSION:
        return True
    if entry.version not in {1, 2}:
        return False

    options = dict(entry.options)
    if entry.version == 1:
        options.pop(OPT_ENABLE_DETAILED_SENSORS, None)
        options.pop(OPT_ENABLE_CO2_ESTIMATE, None)

    title = entry.title
    if not entry.data.get(CONF_DISPLAY_NAME) and title == DEFAULT_TITLE:
        try:
            title = customer_selection_title(strict_selected_stored_customers(entry.data))
        except ValueError:
            title = DEFAULT_TITLE

    hass.config_entries.async_update_entry(
        entry,
        options=options,
        title=title,
        version=CONFIG_ENTRY_VERSION,
    )
    return True


async def _close_session(session: ClientSession) -> None:
    """Close a dedicated client session."""
    if not session.closed:
        await session.close()


def _clear_runtime_data(entry: ConfigEntry) -> None:
    """Clear runtime data without relying on generic ConfigEntry deletion internals."""
    object.__setattr__(entry, "runtime_data", None)


def _has_saved_password(entry: ConfigEntry) -> bool:
    """Return whether a config entry has a stored password."""
    password = entry.data.get(CONF_PASSWORD)
    return isinstance(password, str) and bool(password)


async def _consume_session_handoff(
    hass: HomeAssistant,
    entry: ConfigEntry,
    session_store: KepcoOnSessionStore,
) -> None:
    """Persist one-time session handoff data and scrub it from entry data."""
    handoff = entry.data.get(CONF_SESSION_HANDOFF)
    if handoff is None:
        return
    error: Exception | None = None
    try:
        if not isinstance(handoff, dict):
            raise ConfigEntryError("Invalid KEPCO ON session handoff")
        session = session_from_payload(handoff)
        await session_store.async_save(session)
    except Exception as err:
        error = err
    if error is not None:
        async_create_issue(hass, entry, "session_restore_failed")
        raise ConfigEntryError("Could not persist KEPCO ON session handoff") from None

    updated = dict(entry.data)
    updated.pop(CONF_SESSION_HANDOFF, None)
    hass.config_entries.async_update_entry(entry, data=updated)


async def _ensure_authenticated(
    hass: HomeAssistant,
    auth: KepcoOnAuth,
    entry: ConfigEntry,
) -> None:
    """Restore, validate, or relogin before client use."""
    try:
        restored = await auth.async_restore_session()
        valid = restored and await auth.async_validate_session()
    except KepcoOnProtocolError:
        async_create_issue(hass, entry, "session_restore_failed")
        raise ConfigEntryError("KEPCO ON session restore failed") from None
    if valid:
        return
    if not _has_saved_password(entry):
        raise ConfigEntryAuthFailed("KEPCO ON credentials must be reauthenticated")
    await auth.async_login(str(entry.data[CONF_USERNAME]), str(entry.data[CONF_PASSWORD]))


def _map_setup_error(err: Exception) -> Exception:
    """Map integration exceptions to Home Assistant setup exceptions."""
    if isinstance(err, ConfigEntryAuthFailed | ConfigEntryNotReady | ConfigEntryError):
        return err
    if isinstance(err, UpdateFailed):
        return ConfigEntryNotReady("KEPCO ON first refresh failed")
    if isinstance(err, KepcoOnAuthError):
        return ConfigEntryAuthFailed("KEPCO ON authentication failed")
    if isinstance(err, KepcoOnRateLimitError | KepcoOnConnectionError):
        return ConfigEntryNotReady("KEPCO ON is temporarily unavailable")
    if isinstance(err, KepcoOnProtocolError | KepcoOnUnsupportedAccount | KepcoOnNoCustomersError):
        return ConfigEntryError("KEPCO ON setup failed")
    return ConfigEntryError("KEPCO ON setup failed")


async def async_setup_entry(hass: HomeAssistant, entry: KepcoOnConfigEntry) -> bool:
    """Set up KEPCO ON from a config entry."""
    client_session = async_create_clientsession(
        hass,
        auto_cleanup=False,
        cookie_jar=CookieJar(),
    )
    setup_error: Exception | None = None
    runtime_assigned = False
    setup_phase = "session_handoff"
    try:
        session_store = KepcoOnSessionStore(hass, entry.entry_id)
        await _consume_session_handoff(hass, entry, session_store)
        setup_phase = "authenticate"
        auth = KepcoOnAuth(
            client_session,
            store=session_store,
            reauth_username=str(entry.data[CONF_USERNAME]),
            reauth_password=str(entry.data[CONF_PASSWORD]) if _has_saved_password(entry) else None,
        )
        await _ensure_authenticated(hass, auth, entry)
        client = KepcoOnClient(auth, clock=dt_util.now)
        setup_phase = "account"
        await client.async_get_account_type()
        setup_phase = "customers"
        customers = strict_selected_stored_customers(entry.data)
        coordinator = KepcoOnDataUpdateCoordinator(hass, entry, client, customers)
        runtime_data = KepcoOnRuntimeData(
            client=client,
            auth=auth,
            coordinator=coordinator,
            session_store=session_store,
            session=client_session,
        )
        setup_phase = "first_refresh"
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = runtime_data
        runtime_assigned = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        setup_error = err

    if setup_error is not None:
        if isinstance(setup_error, KepcoOnUnsupportedAccount):
            async_create_issue(hass, entry, "unsupported_account")
        elif isinstance(setup_error, KepcoOnProtocolError):
            if setup_phase in {"authenticate", "account"}:
                async_create_issue(hass, entry, "login_schema_changed")
            elif setup_phase == "customers":
                async_create_issue(hass, entry, "customer_schema_changed")
        if runtime_assigned:
            _clear_runtime_data(entry)
        await _close_session(client_session)
        mapped = _map_setup_error(setup_error)
        if mapped is setup_error:
            raise mapped
        mapped.__context__ = None
        mapped.__cause__ = None
        raise mapped from None

    for kind in (
        "login_schema_changed",
        "customer_schema_changed",
        "unsupported_account",
        "session_restore_failed",
    ):
        async_clear_issue(hass, entry, kind)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KepcoOnConfigEntry) -> bool:
    """Unload a KEPCO ON config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await _close_session(entry.runtime_data.session)
        _clear_runtime_data(entry)
    return unload_ok


__all__ = [
    "KepcoOnConfigEntry",
    "KepcoOnRuntimeData",
    "async_migrate_entry",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]
