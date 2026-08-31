"""Authentication and session lifecycle for KEPCO ON."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from aiohttp import ClientSession, CookieJar

from .api import KepcoOnTransport
from .const import (
    ENDPOINT_LOGIN_INDI,
    ENDPOINT_SESSION_CHECK,
    ENDPOINT_SSO_CHECK,
    PERSISTED_COOKIE_ALLOWLIST,
)
from .exceptions import KepcoOnAuthError, KepcoOnProtocolError, KepcoOnSessionExpired
from .models import KepcoAccountSession
from .session_store import export_cookies, restore_cookies

JsonObject = dict[str, object]
ClockCallback = Callable[[], datetime]


class SessionStore(Protocol):
    """Small persistence protocol used by auth."""

    async def async_load(self) -> KepcoAccountSession | None:
        """Load a persisted session."""

    async def async_save(self, session: KepcoAccountSession) -> None:
        """Persist a session."""

    async def async_clear(self) -> None:
        """Clear a persisted session."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_str(payload: JsonObject, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise KepcoOnAuthError(f"KEPCO ON authentication response is missing {field}")
    return value


class KepcoOnAuth:
    """Owns KEPCO ON credentials, current session, and reauthentication."""

    def __init__(
        self,
        session: ClientSession,
        *,
        store: SessionStore,
        username: str,
        password: str | None,
        clock: ClockCallback = _utc_now,
    ) -> None:
        self._transport = KepcoOnTransport(session)
        if not isinstance(session.cookie_jar, CookieJar):
            raise KepcoOnProtocolError("KEPCO ON auth requires an aiohttp CookieJar")
        self._cookie_jar = session.cookie_jar
        self._store = store
        self._username = username.strip()
        self._password = password
        self._clock = clock
        self._current_session: KepcoAccountSession | None = None
        self._generation = 0
        self._auth_lock = asyncio.Lock()

    @property
    def current_session(self) -> KepcoAccountSession | None:
        """Return the current account session."""
        return self._current_session

    async def async_login(self) -> KepcoAccountSession:
        """Authenticate with saved credentials and persist the session."""
        async with self._auth_lock:
            return await self._async_login_unlocked()

    async def async_restore_session(self) -> bool:
        """Restore persisted session state and allowed cookies."""
        session = await self._store.async_load()
        if session is None:
            return False
        restore_cookies(
            self._cookie_jar,
            session.cookies,
            PERSISTED_COOKIE_ALLOWLIST,
            now=self._clock(),
        )
        self._current_session = session
        return True

    async def async_validate_session(self) -> KepcoAccountSession:
        """Validate and rotate the current session tokens."""
        session = self._require_current_session()
        payload = await self._transport.request_json(
            ENDPOINT_SESSION_CHECK,
            {
                "refreshToken": session.refresh_token,
                "userId": session.user_id,
                "mbrsNm": session.member_name,
            },
            refresh_token=session.refresh_token,
        )
        if payload.get("result") is not True:
            raise KepcoOnSessionExpired("KEPCO ON session expired")
        updated = self._session_from_validation(payload, session)
        await self._save_current_session(updated)
        return updated

    async def async_reauthenticate(self) -> KepcoAccountSession:
        """Reauthenticate with the configured password."""
        async with self._auth_lock:
            return await self._async_reauthenticate_unlocked()

    def async_export_session_snapshot(self) -> KepcoAccountSession | None:
        """Return the current session snapshot without exposing credentials."""
        return self._current_session

    async def async_sso_check(self) -> str:
        """Run the captured SSO check when explicitly needed by validation."""
        session = self._require_current_session()
        if session.user_mng_seqno is None:
            raise KepcoOnProtocolError("KEPCO ON session is missing user sequence")
        payload = await self._transport.request_json(
            ENDPOINT_SSO_CHECK,
            {
                "userId": session.user_id,
                "userMngSeqno": session.user_mng_seqno,
                "name": session.member_name,
                "autoLogin": "Y",
            },
            refresh_token=session.refresh_token,
        )
        if payload.get("loginChk") != "Y":
            raise KepcoOnSessionExpired("KEPCO ON SSO session expired")
        refresh_token = payload.get("refreshToken")
        return (
            refresh_token
            if isinstance(refresh_token, str) and refresh_token
            else session.refresh_token
        )

    async def async_protected_request(
        self,
        path: str,
        payload: JsonObject | None,
        *,
        submission_id: str | None = None,
    ) -> JsonObject:
        """Run a protected request with one relogin and one replay on expiry."""
        session = self._require_current_session()
        generation = self._generation
        try:
            return await self._transport.request_json(
                path,
                payload,
                refresh_token=session.refresh_token,
                submission_id=submission_id,
            )
        except KepcoOnSessionExpired:
            async with self._auth_lock:
                if self._generation == generation:
                    await self._async_reauthenticate_unlocked()
            replay_session = self._require_current_session()
            return await self._transport.request_json(
                path,
                payload,
                refresh_token=replay_session.refresh_token,
                submission_id=submission_id,
            )

    def account_uid_hash(self) -> str:
        """Return a stable one-way account hash for customer key derivation."""
        session = self._require_current_session()
        return sha256(
            f"kepco_on:account:v1\0{session.user_id}\0{session.member_name}".encode()
        ).hexdigest()

    async def _async_reauthenticate_unlocked(self) -> KepcoAccountSession:
        if not self._password:
            raise KepcoOnAuthError("KEPCO ON password is required to reauthenticate")
        return await self._async_login_unlocked()

    async def _async_login_unlocked(self) -> KepcoAccountSession:
        if not self._password:
            raise KepcoOnAuthError("KEPCO ON password is required to authenticate")
        payload = await self._transport.request_json(
            ENDPOINT_LOGIN_INDI,
            {"userId": self._username, "pwdVal": self._password, "autoFlag": "N"},
            submission_id="mf_login_popup_wframe_sbm_submission4",
        )
        if payload.get("result") == "NO":
            raise KepcoOnAuthError("KEPCO ON authentication failed")
        session = KepcoAccountSession(
            refresh_token=_require_str(payload, "refreshToken"),
            token=self._optional_str(payload, "token"),
            user_id=_require_str(payload, "userId"),
            member_name=_require_str(payload, "mbrsNm"),
            user_mng_seqno=self._optional_str(payload, "userMngSeqno"),
            cookies=export_cookies(
                self._cookie_jar,
                PERSISTED_COOKIE_ALLOWLIST,
                now=self._clock(),
            ),
            updated_at=self._clock(),
        )
        await self._save_current_session(session)
        return session

    async def _save_current_session(self, session: KepcoAccountSession) -> None:
        self._current_session = session
        self._generation += 1
        await self._store.async_save(session)

    def _session_from_validation(
        self, payload: JsonObject, previous: KepcoAccountSession
    ) -> KepcoAccountSession:
        return KepcoAccountSession(
            refresh_token=_require_str(payload, "refreshToken"),
            token=self._optional_str(payload, "token"),
            user_id=_require_str(payload, "userId"),
            member_name=_require_str(payload, "mbrsNm"),
            user_mng_seqno=self._optional_str(payload, "userMngSeqno") or previous.user_mng_seqno,
            cookies=export_cookies(
                self._cookie_jar,
                PERSISTED_COOKIE_ALLOWLIST,
                now=self._clock(),
            ),
            updated_at=self._clock(),
        )

    def _require_current_session(self) -> KepcoAccountSession:
        if self._current_session is None:
            raise KepcoOnSessionExpired("KEPCO ON session is not available")
        return self._current_session

    @staticmethod
    def _optional_str(payload: JsonObject, field: str) -> str | None:
        value = payload.get(field)
        if value is None:
            return None
        if not isinstance(value, str):
            raise KepcoOnAuthError(f"KEPCO ON authentication response field {field} is invalid")
        return value or None


__all__ = ["KepcoOnAuth"]
