"""Align the test suite with the v0.3.10 session-persistence contract."""

from pathlib import Path


def replace_versions() -> None:
    """Update stale release-version expectations in Python tests."""
    for path in Path("tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace("0.3.9", "0.3.10")
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def update_fake_auth() -> None:
    """Keep the coordinator test double aligned with the production auth API."""
    path = Path("tests/test_coordinator.py")
    text = path.read_text(encoding="utf-8")
    if "    async def async_reauthenticate(self) -> None:" in text:
        return

    marker = (
        "    async def async_login(self, username: str, password: str) "
        "-> KepcoAccountSession:\n"
    )
    methods = '''    async def async_reset_session(self) -> None:
        await self.store.async_clear()

    async def async_reauthenticate(self) -> None:
        if self.reauth_username is None or self.reauth_password is None:
            raise RuntimeError("reauthentication credentials are missing")
        await self.async_login(self.reauth_username, self.reauth_password)

'''
    if marker not in text:
        raise RuntimeError("FakeAuth async_login marker not found")
    path.write_text(text.replace(marker, methods + marker, 1), encoding="utf-8")


def update_session_store_expectation() -> None:
    """Expect the default store to keep allowlisted first-party session cookies."""
    path = Path("tests/test_session_store.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "test_store_save_filters_disallowed_cookies_by_default",
        "test_store_save_persists_allowed_cookies_by_default",
        1,
    )
    old = '    assert MemoryStore.saved["cookies"] == []'
    new = '''    cookies = cast("list[dict[str, Any]]", MemoryStore.saved["cookies"])
    assert cookies == [
        {
            "name": "JSESSIONID",
            "value": COOKIE_SECRET,
            "domain": "online.kepco.co.kr",
            "path": "/",
            "secure": True,
            "expires": None,
            "host_only": True,
        }
    ]'''
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise RuntimeError("session-store persistence assertion not found")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    replace_versions()
    update_fake_auth()
    update_session_store_expectation()


if __name__ == "__main__":
    main()
