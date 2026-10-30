"""Regression coverage for Home Assistant's shared connector ownership."""

from pathlib import Path

import pytest
from aiohttp import CookieJar, TCPConnector
from custom_components.kepco_on import _close_session as close_runtime_session
from custom_components.kepco_on.config_flow import _close_session as close_flow_session
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, frame


@pytest.mark.parametrize("flow_session", [False, True], ids=["runtime", "config_flow"])
async def test_cleanup_preserves_shared_connector_and_other_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flow_session: bool,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    connector = TCPConnector()
    # Exercise the real HA session factory without starting network discovery.
    monkeypatch.setattr(aiohttp_client, "_async_get_connector", lambda *args: connector)
    # Isolate connector ownership from HA's platform-dependent warning reporter.
    monkeypatch.setattr(frame, "report_usage", lambda what: None)
    session = aiohttp_client.async_create_clientsession(
        hass, auto_cleanup=False, cookie_jar=CookieJar()
    )
    other_session = aiohttp_client.async_create_clientsession(
        hass, auto_cleanup=False, cookie_jar=CookieJar()
    )
    cleanup = close_flow_session if flow_session else close_runtime_session
    try:
        assert session.connector is other_session.connector is connector
        assert session.cookie_jar is not other_session.cookie_jar
        await cleanup(session)
        assert session.closed
        assert not connector.closed
        assert not other_session.closed

        # Repeated cleanup must leave the other session usable.
        await cleanup(session)
        assert not connector.closed
        assert not other_session.closed
    finally:
        session.detach()
        other_session.detach()
        await connector.close()
        await hass.async_stop(force=True)
