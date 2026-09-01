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
from .const import CONF_SESSION_HANDOFF, CONF_USERNAME, PLATFORMS
from .coordinator import KepcoOnDataUpdateCoordinator
from .exceptions import (
    KepcoOnAuthError,
    KepcoOnConnectionError,
    KepcoOnNoCustomersError,
    KepcoOnProtocolError,
    KepcoOnRateLimitError,
    KepcoOnUnsupportedAccount,
)
from .models import strict_selected_stored_customers
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
        raise ConfigEntryError("Could not persist KEPCO ON session handoff") from None

    updated = dict(entry.data)
    updated.pop(CONF_SESSION_HANDOFF, None)
    hass.config_entries.async_update_entry(entry, data=updated)


async def _ensure_authenticated(auth: KepcoOnAuth, entry: ConfigEntry) -> None:
    """Restore, validate, or relogin before client use."""
    restored = await auth.async_restore_session()
    valid = restored and await auth.async_validate_session()
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
    try:
        session_store = KepcoOnSessionStore(hass, entry.entry_id)
        await _consume_session_handoff(hass, entry, session_store)
        auth = KepcoOnAuth(
            client_session,
            store=session_store,
            reauth_username=str(entry.data[CONF_USERNAME]),
            reauth_password=str(entry.data[CONF_PASSWORD]) if _has_saved_password(entry) else None,
        )
        await _ensure_authenticated(auth, entry)
        client = KepcoOnClient(auth, clock=dt_util.now)
        await client.async_get_account_type()
        customers = strict_selected_stored_customers(entry.data)
        coordinator = KepcoOnDataUpdateCoordinator(hass, entry, client, customers)
        runtime_data = KepcoOnRuntimeData(
            client=client,
            auth=auth,
            coordinator=coordinator,
            session_store=session_store,
            session=client_session,
        )
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = runtime_data
        runtime_assigned = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        setup_error = err

    if setup_error is not None:
        if runtime_assigned:
            _clear_runtime_data(entry)
        await _close_session(client_session)
        mapped = _map_setup_error(setup_error)
        if mapped is setup_error:
            raise mapped
        mapped.__context__ = None
        mapped.__cause__ = None
        raise mapped from None

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KepcoOnConfigEntry) -> bool:
    """Unload a KEPCO ON config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await _close_session(entry.runtime_data.session)
    return unload_ok


__all__ = [
    "KepcoOnConfigEntry",
    "KepcoOnRuntimeData",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]
