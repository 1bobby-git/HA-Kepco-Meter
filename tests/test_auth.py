"""Authentication/session contract tests for KEPCO ON."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import pytest
from aiohttp import ClientSession, web
from aresponses import Response, ResponsesMockServer
from custom_components.kepco_on.auth import KepcoOnAuth
from custom_components.kepco_on.exceptions import (
    KepcoOnAuthError,
    KepcoOnSessionExpired,
)
from custom_components.kepco_on.models import KepcoAccountSession

HOST = "online.kepco.co.kr"
USERNAME_SECRET = " USERNAME_SECRET_CANARY "
PASSWORD_SECRET = "PASSWORD_SECRET_CANARY"
REFRESH_SECRET = "REFRESH_SECRET_CANARY"


class MemorySessionStore:
    """In-memory auth store with save/load counters."""

    def __init__(self, session: KepcoAccountSession | None = None) -> None:
        self.session = session
        self.saved: list[KepcoAccountSession] = []
        self.loads = 0

    async def async_load(self) -> KepcoAccountSession | None:
        self.loads += 1
        return self.session

    async def async_save(self, session: KepcoAccountSession) -> None:
        self.session = session
        self.saved.append(session)

    async def async_clear(self) -> None:
        self.session = None


class FailingSessionStore(MemorySessionStore):
    """Store that records attempted saves but fails before persisting."""

    async def async_save(self, session: KepcoAccountSession) -> None:
        self.saved.append(session)
        raise KepcoOnAuthError("STORE_FAILURE_CANARY")


def json_response(payload: Mapping[str, object], *, status: int = 200) -> Response:
    return Response(
        text=json.dumps(payload),
        status=status,
        content_type="application/json",
        charset="UTF-8",
    )


async def request_json(request: web.Request) -> dict[str, object]:
    return cast("dict[str, object]", json.loads((await request.read()).decode()))


def make_session(refresh_token: str = REFRESH_SECRET) -> KepcoAccountSession:
    return KepcoAccountSession(
        refresh_token=refresh_token,
        token="TOKEN_SECRET_CANARY",
        user_id="USER_ID_SECRET_CANARY",
        member_name="MEMBER_NAME_SECRET_CANARY",
        user_mng_seqno="SEQ_SECRET_CANARY",
        updated_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def assert_no_secret(text: str) -> None:
    for value in (
        USERNAME_SECRET.strip(),
        PASSWORD_SECRET,
        REFRESH_SECRET,
        "TOKEN_SECRET_CANARY",
        "USER_ID_SECRET_CANARY",
        "MEMBER_NAME_SECRET_CANARY",
    ):
        assert value not in text


@asynccontextmanager
async def auth_context(
    server: ResponsesMockServer,
    store: MemorySessionStore,
    *,
    reauth_username: str | None = USERNAME_SECRET,
    reauth_password: str | None = PASSWORD_SECRET,
) -> AsyncIterator[KepcoOnAuth]:
    await server.__aenter__()
    session = ClientSession()
    try:
        yield KepcoOnAuth(
            session,
            store=store,
            reauth_username=reauth_username,
            reauth_password=reauth_password,
            clock=lambda: datetime(2026, 9, 1, tzinfo=UTC),
        )
    finally:
        await session.close()
        await server.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_login_posts_exact_body_headers_and_saves_session() -> None:
    captured: dict[str, object] = {}

    async def route(request: web.Request) -> Response:
        captured["path"] = request.path
        captured["body"] = await request_json(request)
        captured["headers"] = dict(request.headers)
        return json_response(
            {
                "result": "YES",
                "token": "TOKEN_SECRET_CANARY",
                "refreshToken": REFRESH_SECRET,
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        )

    server = ResponsesMockServer()
    server.add(HOST, "/cyb/me/login/indi/api", "post", response=route)
    store = MemorySessionStore()
    async with auth_context(server, store) as auth:
        session = await auth.async_login(USERNAME_SECRET, PASSWORD_SECRET)

    headers = cast("dict[str, str]", captured["headers"])
    assert captured["path"] == "/cyb/me/login/indi/api"
    assert captured["body"] == {
        "userId": USERNAME_SECRET.strip(),
        "pwdVal": PASSWORD_SECRET,
        "autoFlag": "N",
    }
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json; charset=UTF-8"
    assert headers["Referer"] == "https://online.kepco.co.kr/MYM001D00"
    assert headers["submissionid"] == "mf_login_popup_wframe_sbm_submission4"
    assert session.refresh_token == REFRESH_SECRET
    assert store.saved == [session]


@pytest.mark.asyncio
async def test_login_result_no_and_missing_tokens_raise_safe_auth_error() -> None:
    for payload in (
        {"result": "NO", "errorCode": "BAD", "errorMessage": PASSWORD_SECRET},
        {"result": "YES", "refreshToken": REFRESH_SECRET, "userId": "user"},
    ):
        server = ResponsesMockServer()
        server.add(HOST, "/cyb/me/login/indi/api", "post", response=json_response(payload))
        async with auth_context(server, MemorySessionStore()) as auth:
            with pytest.raises(KepcoOnAuthError) as raised:
                await auth.async_login(USERNAME_SECRET, PASSWORD_SECRET)
            assert_no_secret(str(raised.value))


@pytest.mark.asyncio
async def test_login_rejects_empty_one_off_credentials_before_request() -> None:
    server = ResponsesMockServer()
    store = MemorySessionStore()
    async with auth_context(server, store, reauth_username=None, reauth_password=None) as auth:
        for username, password in ((" ", PASSWORD_SECRET), ("user", ""), ("user", " ")):
            with pytest.raises(KepcoOnAuthError) as raised:
                await auth.async_login(username, password)
            assert_no_secret(str(raised.value))

    assert store.saved == []


@pytest.mark.asyncio
async def test_one_off_login_does_not_retain_password_for_reauthenticate() -> None:
    server = ResponsesMockServer()
    server.add(
        HOST,
        "/cyb/me/login/indi/api",
        "post",
        response=json_response(
            {
                "result": "YES",
                "token": "TOKEN_SECRET_CANARY",
                "refreshToken": REFRESH_SECRET,
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        ),
    )
    store = MemorySessionStore()
    async with auth_context(server, store, reauth_username=None, reauth_password=None) as auth:
        await auth.async_login(USERNAME_SECRET, PASSWORD_SECRET)
        with pytest.raises(KepcoOnAuthError):
            await auth.async_reauthenticate()


@pytest.mark.asyncio
async def test_restore_loads_store_and_restores_current_session() -> None:
    store = MemorySessionStore(make_session())
    server = ResponsesMockServer()
    async with auth_context(server, store) as auth:
        assert await auth.async_restore_session() is True
        assert auth.current_session == store.session
        assert store.loads == 1


@pytest.mark.asyncio
async def test_validate_session_false_raises_expired_without_saving() -> None:
    server = ResponsesMockServer()
    server.add(HOST, "/sessionCheck", "post", response=json_response({"result": False}))
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        assert await auth.async_validate_session() is False
        assert len(store.saved) == 0


@pytest.mark.asyncio
async def test_validate_session_rotates_tokens_and_saves() -> None:
    captured: dict[str, object] = {}

    async def route(request: web.Request) -> Response:
        captured["body"] = await request_json(request)
        captured["headers"] = dict(request.headers)
        return json_response(
            {
                "result": True,
                "userMngSeqno": "SEQ_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        )

    server = ResponsesMockServer()
    server.add(HOST, "/sessionCheck", "post", response=route)
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        restored = await auth.async_restore_session()
        assert restored is True
        validated = await auth.async_validate_session()

    assert captured["body"] == {
        "refreshToken": REFRESH_SECRET,
        "userId": "USER_ID_SECRET_CANARY",
        "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
    }
    assert cast("dict[str, str]", captured["headers"])["refreshToken"] == REFRESH_SECRET
    assert validated is True
    assert auth.current_session is not None
    assert auth.current_session.refresh_token == "REFRESH_ROTATED"
    assert auth.current_session.token == "TOKEN_ROTATED"
    assert auth.current_session.user_mng_seqno == "SEQ_ROTATED"
    assert store.saved[-1] == auth.current_session


@pytest.mark.asyncio
async def test_reauthenticate_requires_saved_password() -> None:
    async with auth_context(
        ResponsesMockServer(),
        MemorySessionStore(make_session()),
        reauth_username=USERNAME_SECRET,
        reauth_password=None,
    ) as auth:
        with pytest.raises(KepcoOnAuthError):
            await auth.async_reauthenticate()


@pytest.mark.asyncio
async def test_reauthenticate_uses_configured_credentials_and_returns_none() -> None:
    captured: dict[str, object] = {}

    async def route(request: web.Request) -> Response:
        captured["body"] = await request_json(request)
        return json_response(
            {
                "result": "YES",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        )

    server = ResponsesMockServer()
    server.add(HOST, "/cyb/me/login/indi/api", "post", response=route)
    store = MemorySessionStore(make_session())
    async with auth_context(
        server,
        store,
        reauth_username=" SAVED_USER ",
        reauth_password="SAVED_PASSWORD",
    ) as auth:
        await auth.async_reauthenticate()

    assert captured["body"] == {
        "userId": "SAVED_USER",
        "pwdVal": "SAVED_PASSWORD",
        "autoFlag": "N",
    }
    assert store.saved[-1].refresh_token == "REFRESH_ROTATED"


@pytest.mark.asyncio
async def test_protected_request_reauthenticates_once_and_replays_once() -> None:
    server = ResponsesMockServer()
    server.add(
        HOST,
        "/my/indi/info/myPageCustNoList",
        "post",
        response=json_response({"expired": True}, status=401),
    )
    server.add(
        HOST,
        "/cyb/me/login/indi/api",
        "post",
        response=json_response(
            {
                "result": "YES",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        ),
    )
    server.add(
        HOST,
        "/my/indi/info/myPageCustNoList",
        "post",
        response=json_response({"dlt_myPageAppendList": []}),
    )
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        result = await auth.async_protected_request(
            "/my/indi/info/myPageCustNoList",
            {"dma_search": {}},
            submission_id="mf_wfm_layout_sbm_myPageCustList",
        )

    assert result == {"dlt_myPageAppendList": []}
    assert [saved.refresh_token for saved in store.saved] == ["REFRESH_ROTATED"]


@pytest.mark.asyncio
async def test_protected_request_does_not_recurse_after_replay_expiration() -> None:
    server = ResponsesMockServer()
    server.add(HOST, "/sessionCheck", "post", response=json_response({"expired": True}, status=401))
    server.add(
        HOST,
        "/cyb/me/login/indi/api",
        "post",
        response=json_response(
            {
                "result": "YES",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        ),
    )
    server.add(HOST, "/sessionCheck", "post", response=json_response({"expired": True}, status=401))
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        with pytest.raises(KepcoOnSessionExpired):
            await auth.async_protected_request("/sessionCheck", {})


@pytest.mark.asyncio
async def test_concurrent_expired_requests_share_one_relogin_generation() -> None:
    login_calls = 0
    protected_calls = 0

    async def protected_route(request: web.Request) -> Response:
        nonlocal protected_calls
        protected_calls += 1
        if protected_calls <= 2:
            return json_response({"expired": True}, status=401)
        return json_response({"ok": protected_calls})

    async def login_route(request: web.Request) -> Response:
        nonlocal login_calls
        del request
        login_calls += 1
        await asyncio.sleep(0)
        return json_response(
            {
                "result": "YES",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        )

    server = ResponsesMockServer()
    server.add(HOST, "/sessionCheck", "post", response=protected_route, repeat=4)
    server.add(HOST, "/cyb/me/login/indi/api", "post", response=login_route)
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        results = await asyncio.gather(
            auth.async_protected_request("/sessionCheck", {}),
            auth.async_protected_request("/sessionCheck", {}),
        )

    assert login_calls == 1
    assert sorted(cast("int", result["ok"]) for result in results) == [3, 4]


@pytest.mark.asyncio
async def test_export_session_snapshot_hides_password_and_is_copy() -> None:
    store = MemorySessionStore(make_session())
    async with auth_context(ResponsesMockServer(), store) as auth:
        await auth.async_restore_session()
        snapshot = await auth.async_export_session_snapshot()

    rendered = repr(snapshot)
    assert PASSWORD_SECRET not in rendered
    assert snapshot == store.session


@pytest.mark.asyncio
async def test_export_session_snapshot_raises_when_no_session() -> None:
    async with auth_context(ResponsesMockServer(), MemorySessionStore()) as auth:
        with pytest.raises(KepcoOnSessionExpired):
            await auth.async_export_session_snapshot()


@pytest.mark.asyncio
async def test_sso_check_non_y_raises_if_fallback_is_used() -> None:
    server = ResponsesMockServer()
    server.add(HOST, "/ssoCheck", "post", response=json_response({"loginChk": "N"}))
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        with pytest.raises(KepcoOnSessionExpired):
            await auth.async_sso_check()


@pytest.mark.asyncio
async def test_sso_check_posts_exact_contract_and_rotates_refresh_token() -> None:
    captured: dict[str, object] = {}

    async def route(request: web.Request) -> Response:
        captured["path"] = request.path
        captured["body"] = await request_json(request)
        captured["headers"] = dict(request.headers)
        return json_response({"loginChk": "Y", "refreshToken": "REFRESH_SSO_ROTATED"})

    server = ResponsesMockServer()
    server.add(HOST, "/ssoCheck", "post", response=route)
    store = MemorySessionStore(make_session())
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        refresh_token = await auth.async_sso_check()

    headers = cast("dict[str, str]", captured["headers"])
    assert captured["path"] == "/ssoCheck"
    assert captured["body"] == {
        "userId": "USER_ID_SECRET_CANARY",
        "userMngSeqno": "SEQ_SECRET_CANARY",
        "name": "MEMBER_NAME_SECRET_CANARY",
        "autoLogin": "Y",
    }
    assert headers["refreshToken"] == REFRESH_SECRET
    assert headers["Referer"] == "https://online.kepco.co.kr/MYM001D00"
    assert headers["Origin"] == "https://online.kepco.co.kr/"
    assert "submissionid" not in {key.lower() for key in headers}
    assert refresh_token == "REFRESH_SSO_ROTATED"
    assert store.saved[-1].refresh_token == "REFRESH_SSO_ROTATED"


@pytest.mark.asyncio
async def test_login_store_failure_preserves_old_generation_and_hides_secret() -> None:
    old_session = make_session("OLD_REFRESH")
    server = ResponsesMockServer()
    server.add(
        HOST,
        "/cyb/me/login/indi/api",
        "post",
        response=json_response(
            {
                "result": "YES",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        ),
    )
    store = FailingSessionStore(old_session)
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        generation = auth._generation
        with pytest.raises(KepcoOnAuthError) as raised:
            await auth.async_login(USERNAME_SECRET, PASSWORD_SECRET)
        assert "STORE_FAILURE_CANARY" in str(raised.value)
        assert PASSWORD_SECRET not in str(raised.value)
        assert auth.current_session == old_session
        assert auth._generation == generation


@pytest.mark.asyncio
async def test_validate_store_failure_preserves_old_session_and_generation() -> None:
    old_session = make_session("OLD_REFRESH")
    server = ResponsesMockServer()
    server.add(
        HOST,
        "/sessionCheck",
        "post",
        response=json_response(
            {
                "result": True,
                "userMngSeqno": "SEQ_ROTATED",
                "userId": "USER_ID_SECRET_CANARY",
                "token": "TOKEN_ROTATED",
                "refreshToken": "REFRESH_ROTATED",
                "mbrsNm": "MEMBER_NAME_SECRET_CANARY",
            }
        ),
    )
    store = FailingSessionStore(old_session)
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        generation = auth._generation
        with pytest.raises(KepcoOnAuthError):
            await auth.async_validate_session()
        assert auth.current_session == old_session
        assert auth._generation == generation


@pytest.mark.asyncio
async def test_sso_store_failure_preserves_old_session_and_generation() -> None:
    old_session = make_session("OLD_REFRESH")
    server = ResponsesMockServer()
    server.add(
        HOST,
        "/ssoCheck",
        "post",
        response=json_response({"loginChk": "Y", "refreshToken": "REFRESH_SSO_ROTATED"}),
    )
    store = FailingSessionStore(old_session)
    async with auth_context(server, store) as auth:
        await auth.async_restore_session()
        generation = auth._generation
        with pytest.raises(KepcoOnAuthError):
            await auth.async_sso_check()
        assert auth.current_session == old_session
        assert auth._generation == generation
