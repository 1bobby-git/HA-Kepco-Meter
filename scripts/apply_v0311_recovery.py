"""Apply the v0.3.11 legacy-session recovery patch once."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"expected text not found in {path}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def patch_setup_lifecycle() -> None:
    path = "custom_components/kepco_on/__init__.py"
    text = read(path)

    text = text.replace(
        "    KepcoOnRateLimitError,\n    KepcoOnUnsupportedAccount,\n)",
        "    KepcoOnRateLimitError,\n    KepcoOnSessionExpired,\n    KepcoOnUnsupportedAccount,\n)",
        1,
    )

    old_restore = """    if restored:
        try:
            valid = await auth.async_validate_session()
"""
    new_restore = """    if restored:
        restored_session = getattr(auth, "current_session", None)
        if restored_session is not None and not restored_session.cookies:
            if not has_saved_password:
                async_create_issue(hass, entry, "session_restore_failed")
                raise ConfigEntryAuthFailed(
                    "KEPCO ON legacy session requires reauthentication"
                ) from None
            _LOGGER.warning(
                "Restored legacy KEPCO ON session has no persisted cookies; "
                "reauthenticating cleanly"
            )
            await auth.async_reset_session()
            await auth.async_reauthenticate()
            return
        try:
            valid = await auth.async_validate_session()
"""
    if old_restore not in text:
        raise RuntimeError("restore-session insertion point not found")
    text = text.replace(old_restore, new_restore, 1)

    helper_marker = "\ndef _map_setup_error(err: Exception) -> Exception:\n"
    helper = '''
async def _ensure_supported_account(
    hass: HomeAssistant,
    auth: KepcoOnAuth,
    client: KepcoOnClient,
    entry: ConfigEntry,
) -> None:
    """Validate account type and recover one incomplete restored session."""
    try:
        await client.async_get_account_type()
        return
    except KepcoOnSessionExpired:
        if not _has_saved_password(entry):
            async_create_issue(hass, entry, "session_restore_failed")
            raise ConfigEntryAuthFailed(
                "KEPCO ON session requires reauthentication"
            ) from None

    _LOGGER.warning(
        "Restored KEPCO ON session was incomplete during account validation; "
        "reauthenticating cleanly"
    )
    await auth.async_reset_session()
    await auth.async_reauthenticate()
    try:
        await client.async_get_account_type()
    except KepcoOnSessionExpired:
        raise KepcoOnProtocolError(
            "KEPCO ON account response remained incomplete after reauthentication"
        ) from None

'''
    if helper_marker not in text:
        raise RuntimeError("setup helper insertion point not found")
    text = text.replace(helper_marker, "\n" + helper + "def _map_setup_error(err: Exception) -> Exception:\n", 1)

    old_account = '''        setup_phase = "account"
        await client.async_get_account_type()
'''
    new_account = '''        setup_phase = "account"
        await _ensure_supported_account(hass, auth, client, entry)
'''
    if old_account not in text:
        raise RuntimeError("account-validation call not found")
    text = text.replace(old_account, new_account, 1)

    old_error = """    if setup_error is not None:
        if isinstance(setup_error, KepcoOnUnsupportedAccount):
"""
    new_error = """    if setup_error is not None:
        _LOGGER.error(
            "KEPCO ON setup failed during %s (%s)",
            setup_phase,
            type(setup_error).__name__,
        )
        if isinstance(setup_error, KepcoOnUnsupportedAccount):
"""
    if old_error not in text:
        raise RuntimeError("safe setup error log insertion point not found")
    text = text.replace(old_error, new_error, 1)
    write(path, text)


def patch_account_response_classification() -> None:
    path = "custom_components/kepco_on/api.py"
    old = '''        account_type = payload.get("userClNm")
        if account_type != "INDI":
            raise KepcoOnUnsupportedAccount("Only KEPCO ON individual accounts are supported")
        return "INDI"
'''
    new = '''        account_type = payload.get("userClNm")
        if account_type is None or account_type == "":
            raise KepcoOnSessionExpired("KEPCO ON account session is incomplete")
        if not isinstance(account_type, str):
            raise KepcoOnProtocolError("KEPCO ON account type response is invalid")
        if account_type.strip().upper() != "INDI":
            raise KepcoOnUnsupportedAccount("Only KEPCO ON individual accounts are supported")
        return "INDI"
'''
    replace_once(path, old, new)


def patch_api_tests() -> None:
    path = "tests/test_api.py"
    marker = '''
@pytest.mark.asyncio
async def test_client_get_customers_uses_mypage_endpoint_body_and_parser() -> None:
'''
    tests = '''
@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"result": False}, {"userClNm": ""}])
async def test_client_get_account_type_treats_incomplete_response_as_expired(
    payload: dict[str, object],
) -> None:
    class Auth:
        async def async_protected_request(
            self,
            path: str,
            request_payload: dict[str, object] | None,
            *,
            submission_id: str | None = None,
        ) -> dict[str, object]:
            assert path == "/isCorp"
            assert request_payload is None
            assert submission_id is None
            return payload

        def account_uid_hash(self) -> str:
            return "HASH"

    client = KepcoOnClient(cast("Any", Auth()))

    with pytest.raises(KepcoOnSessionExpired):
        await client.async_get_account_type()


@pytest.mark.asyncio
async def test_client_get_account_type_rejects_invalid_type_shape() -> None:
    class Auth:
        async def async_protected_request(
            self,
            path: str,
            payload: dict[str, object] | None,
            *,
            submission_id: str | None = None,
        ) -> dict[str, object]:
            assert path == "/isCorp"
            assert payload is None
            assert submission_id is None
            return {"userClNm": True}

        def account_uid_hash(self) -> str:
            return "HASH"

    client = KepcoOnClient(cast("Any", Auth()))

    with pytest.raises(KepcoOnProtocolError):
        await client.async_get_account_type()

'''
    text = read(path)
    if marker not in text:
        raise RuntimeError("API test insertion point not found")
    write(path, text.replace(marker, "\n" + tests + marker.lstrip("\n"), 1))


def patch_setup_tests() -> None:
    path = "tests/test_coordinator.py"
    marker = '''
@pytest.mark.asyncio
async def test_setup_invalid_restore_without_saved_password_raises_auth_failed(
'''
    tests = '''
@pytest.mark.asyncio
async def test_setup_reauthenticates_legacy_session_without_cookies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import custom_components.kepco_on as init_module

    class LegacySessionAuth(FakeAuth):
        @property
        def current_session(self) -> KepcoAccountSession:
            return account_session()

    monkeypatch.setattr(init_module, "KepcoOnAuth", LegacySessionAuth)
    hass = FakeHass()
    entry = make_entry(save_password=True)
    FakeAuth.restore_results = [True]
    FakeAuth.login_results = [account_session()]

    assert await init_module.async_setup_entry(cast("Any", hass), cast("Any", entry)) is True

    assert FakeStore.instances[0].cleared is True
    assert FakeAuth.instances[0].login_calls == [("input-user", PASSWORD_SECRET)]


@pytest.mark.asyncio
async def test_setup_legacy_session_without_password_requests_reauthentication(
    monkeypatch: pytest.MonkeyPatch,
    reset_fakes: list[FakeSession],
) -> None:
    import custom_components.kepco_on as init_module

    class LegacySessionAuth(FakeAuth):
        @property
        def current_session(self) -> KepcoAccountSession:
            return account_session()

    monkeypatch.setattr(init_module, "KepcoOnAuth", LegacySessionAuth)
    hass = FakeHass()
    entry = make_entry()
    FakeAuth.restore_results = [True]

    with pytest.raises(ConfigEntryAuthFailed):
        await init_module.async_setup_entry(cast("Any", hass), cast("Any", entry))

    assert reset_fakes[0].closed is True


@pytest.mark.asyncio
async def test_setup_reauthenticates_when_account_response_is_incomplete() -> None:
    import custom_components.kepco_on as init_module

    hass = FakeHass()
    entry = make_entry(save_password=True)
    FakeAuth.restore_results = [True]
    FakeAuth.validate_results = [True]
    FakeAuth.login_results = [account_session()]
    FakeClient.account_results = [
        KepcoOnSessionExpired("incomplete restored account session"),
        "INDI",
    ]

    assert await init_module.async_setup_entry(cast("Any", hass), cast("Any", entry)) is True

    assert FakeStore.instances[0].cleared is True
    assert FakeAuth.instances[0].login_calls == [("input-user", PASSWORD_SECRET)]


@pytest.mark.asyncio
async def test_setup_incomplete_account_without_password_requests_reauthentication(
    reset_fakes: list[FakeSession],
) -> None:
    import custom_components.kepco_on as init_module

    hass = FakeHass()
    entry = make_entry()
    FakeAuth.restore_results = [True]
    FakeAuth.validate_results = [True]
    FakeClient.account_results = [KepcoOnSessionExpired("incomplete restored account session")]

    with pytest.raises(ConfigEntryAuthFailed):
        await init_module.async_setup_entry(cast("Any", hass), cast("Any", entry))

    assert reset_fakes[0].closed is True

'''
    text = read(path)
    if marker not in text:
        raise RuntimeError("setup test insertion point not found")
    write(path, text.replace(marker, "\n" + tests + marker.lstrip("\n"), 1))


def update_version_metadata() -> None:
    replace_once(
        "custom_components/kepco_on/const.py",
        'VERSION = "0.3.10"',
        'VERSION = "0.3.11"',
    )
    replace_once(
        "custom_components/kepco_on/manifest.json",
        '"version": "0.3.10"',
        '"version": "0.3.11"',
    )
    for path in (ROOT / "tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace("0.3.10", "0.3.11")
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def update_docs() -> None:
    changelog = read("CHANGELOG.md")
    entry = '''## 0.3.11 — 2026-09-11

- `v0.3.9`에서 만들어진 쿠키 없는 기존 세션을 `v0.3.10`이 토큰만으로 정상 복원한 뒤 계정 유형 확인에서 일반 설정 오류로 종료할 수 있던 업그레이드 회귀를 수정합니다.
- 저장 비밀번호가 있으면 쿠키 없는 레거시 세션을 폐기하고 한 번 자동 재로그인하여 `JSESSIONID`/`kepcoSSO`를 새로 수립합니다. 저장 비밀번호가 없으면 모호한 `KEPCO ON setup failed` 대신 Home Assistant 재인증 흐름을 시작합니다.
- 세션 확인 직후 `/isCorp` 응답에 계정 유형이 없는 경우를 법인 계정으로 오판하지 않고, 저장 비밀번호가 있으면 한 번만 깨끗한 재로그인 후 다시 검사합니다. 재로그인 후에도 응답이 불완전하면 프로토콜 변경 오류로 분리합니다.
- 초기화 실패 로그에 민감한 응답·토큰 없이 실패 단계와 예외 유형만 남겨 후속 진단이 가능하도록 개선합니다.

'''
    header = "# Changelog\n\n"
    if not changelog.startswith(header):
        raise RuntimeError("changelog header not found")
    write("CHANGELOG.md", header + entry + changelog[len(header) :])

    write(
        "RELEASE_NOTES.md",
        '''## 한전ON v0.3.11

- `v0.3.9`에서 업그레이드한 기존 항목에 인증 쿠키가 없는 경우 더 이상 일반 설정 오류로 중단하지 않습니다.
- `비밀번호 저장`이 켜져 있으면 쿠키 없는 레거시 세션을 자동으로 초기화하고 한 번 재로그인하여 새 세션을 저장합니다.
- 비밀번호가 저장되지 않은 항목은 `KEPCO ON setup failed` 대신 Home Assistant의 재인증 요청으로 전환됩니다. 통합을 삭제하거나 센서 기록을 다시 만들 필요가 없습니다.
- `/isCorp` 계정 유형 응답이 비어 있는 세션도 한 번 자동 복구하며, 실제 법인 계정은 기존처럼 지원하지 않습니다.
- 초기화 오류 로그에는 계정 정보나 토큰 없이 실패 단계와 예외 유형만 기록합니다.
- HACS에서 `v0.3.11`로 업데이트한 뒤 Home Assistant를 완전히 재시작하세요.
''',
    )

    readme = read("README.md")
    readme = readme.replace("- 버전: `v0.3.10`.", "- 버전: `v0.3.11`.", 1)
    old_upgrade = "`v0.3.10`에서는 한전ON 인증 쿠키를 제한적으로 영속화하고 최소 성공 세션 검증 응답을 정상 처리하며, 저장 비밀번호가 있는 경우 손상된 세션을 자동 재로그인으로 복구합니다. 업데이트 후 Home Assistant Core를 완전히 재시작하세요."
    new_upgrade = "`v0.3.10`에서는 한전ON 인증 쿠키를 제한적으로 영속화하고 최소 성공 세션 검증 응답을 정상 처리합니다. `v0.3.11`에서는 `v0.3.9`에서 넘어온 쿠키 없는 레거시 세션을 자동 재로그인하거나 Home Assistant 재인증 흐름으로 전환해 일반 설정 오류를 방지합니다. 업데이트 후 Home Assistant Core를 완전히 재시작하세요."
    if old_upgrade not in readme:
        raise RuntimeError("README upgrade note not found")
    readme = readme.replace(old_upgrade, new_upgrade, 1)
    old_troubleshooting = "- 세션 만료/복원 실패: `v0.3.10`부터 refresh token과 허용된 `JSESSIONID`/`kepcoSSO` 인증 쿠키를 함께 복원하고, 성공한 보호 요청에서 갱신된 쿠키를 다시 저장합니다. 한전 서버가 세션 자체를 만료한 경우에는 재인증이 필요하며, 비밀번호 저장을 켠 항목은 자동 재로그인을 시도합니다."
    new_troubleshooting = "- 세션 만료/복원 실패: `v0.3.11`은 refresh token과 허용된 `JSESSIONID`/`kepcoSSO` 인증 쿠키를 함께 복원합니다. `v0.3.9`에서 넘어온 쿠키 없는 세션은 비밀번호 저장 시 자동 재로그인하고, 비밀번호가 없으면 기존 항목을 유지한 채 재인증을 요청합니다."
    if old_troubleshooting not in readme:
        raise RuntimeError("README troubleshooting note not found")
    write("README.md", readme.replace(old_troubleshooting, new_troubleshooting, 1))


def main() -> None:
    patch_setup_lifecycle()
    patch_account_response_classification()
    patch_api_tests()
    patch_setup_tests()
    update_version_metadata()
    update_docs()


if __name__ == "__main__":
    main()
