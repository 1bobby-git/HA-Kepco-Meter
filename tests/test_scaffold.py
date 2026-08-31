"""Scaffold contract tests for the KEPCO ON integration."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.kepco_on import const
from custom_components.kepco_on.exceptions import (
    KepcoOnAuthError,
    KepcoOnConnectionError,
    KepcoOnError,
    KepcoOnMfaRequired,
    KepcoOnNoCustomersError,
    KepcoOnPartialUpdateError,
    KepcoOnProtocolError,
    KepcoOnRateLimitError,
    KepcoOnSessionExpired,
    KepcoOnUnsupportedAccount,
)
from homeassistant.const import Platform

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_matches_integration_contract() -> None:
    manifest = json.loads((ROOT / "custom_components/kepco_on/manifest.json").read_text())

    assert manifest == {
        "domain": "kepco_on",
        "name": "KEPCO ON",
        "version": "0.1.0",
        "config_flow": True,
        "integration_type": "hub",
        "iot_class": "cloud_polling",
        "requirements": [],
        "codeowners": ["@1bobby-git"],
        "documentation": "https://github.com/1bobby-git/HA-Kepco-Meter",
        "issue_tracker": "https://github.com/1bobby-git/HA-Kepco-Meter/issues",
    }


def test_hacs_metadata_uses_supported_minimum_keys() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert hacs == {
        "name": "한전ON (KEPCO ON)",
        "content_in_root": False,
        "homeassistant": "2026.8.3",
    }


def test_gitignore_blocks_capture_and_secret_artifacts() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert gitignore == [
        "*.jsonl",
        "*.har",
        "*.trace.zip",
        ".kepco-on-capture-profile/",
        ".kepco-on-login-profile/",
        "login-schema*.json",
        "session*.json",
        "cookies*.json",
        ".storage/",
        "secrets.yaml",
        ".env",
        ".env.*",
        "__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "htmlcov/",
        ".venv/",
        "node_modules/",
    ]


def test_constants_are_fixed_and_capture_safe() -> None:
    assert const.DOMAIN == "kepco_on"
    assert const.NAME == "KEPCO ON"
    assert const.VERSION == "0.1.0"
    assert const.BASE_URL == "https://online.kepco.co.kr"
    assert const.PAGE_URL == "https://online.kepco.co.kr/MYM001D00"
    assert const.ENDPOINT_LOGIN_INDI == "/cyb/me/login/indi/api"
    assert const.ENDPOINT_FIRST_LOGIN_CHECK == "/me/login/firstLogin/check"
    assert const.ENDPOINT_SESSION_CHECK == "/sessionCheck"
    assert const.ENDPOINT_APT_BILL_DETAIL == "/my/charge/pay/aptBillDetail"
    assert const.POLLING_INTERVAL_HOURS == (1, 3, 6, 12, 24)
    assert const.DEFAULT_POLLING_INTERVAL_HOURS == 6
    assert const.PLATFORMS == (Platform.SENSOR,)
    assert frozenset({"JSESSIONID", "kepcoSSO"}) == const.CANDIDATE_COOKIE_NAMES
    assert frozenset() == const.PERSISTED_COOKIE_ALLOWLIST


def test_option_and_config_keys_are_stable() -> None:
    assert const.CONF_USERNAME == "username"
    assert const.CONF_SAVE_PASSWORD == "save_password"
    assert const.CONF_SELECTED_CUSTOMERS == "selected_customers"
    assert const.OPT_POLLING_INTERVAL_HOURS == "polling_interval_hours"
    assert const.OPT_ENABLE_DETAILED_SENSORS == "enable_detailed_sensors"
    assert const.OPT_ENABLE_CO2_ESTIMATE == "enable_co2_estimate"
    assert const.OPT_CO2_FACTOR_KG_PER_KWH == "co2_factor_kg_per_kwh"
    assert const.OPT_HISTORY_MONTHS == "history_months"


def test_exception_hierarchy_is_documented() -> None:
    assert issubclass(KepcoOnAuthError, KepcoOnError)
    assert issubclass(KepcoOnSessionExpired, KepcoOnAuthError)
    assert issubclass(KepcoOnMfaRequired, KepcoOnAuthError)
    assert issubclass(KepcoOnUnsupportedAccount, KepcoOnError)
    assert issubclass(KepcoOnNoCustomersError, KepcoOnError)
    assert issubclass(KepcoOnConnectionError, KepcoOnError)
    assert issubclass(KepcoOnRateLimitError, KepcoOnConnectionError)
    assert issubclass(KepcoOnProtocolError, KepcoOnError)
    assert issubclass(KepcoOnPartialUpdateError, KepcoOnError)
