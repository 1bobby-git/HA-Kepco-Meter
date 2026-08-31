#!/usr/bin/env python
"""Extract sanitized parser fixtures from the safe KEPCO ON wire capture."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

EXPECTED_CAPTURE_SHA256 = "cdd9f5f7443781e2986484cd030e5b95d9d89ae764a5ee2e759d144c2459620a"
EXPECTED_RECORD_COUNT = 611
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures"

ALLOWED_SYNTHETIC_CUSTOMER_KEYS = {
    "APT_DONGNO",
    "APT_HONO",
    "APT_NAME",
    "CUST_NO",
    "SI_CUST_NO",
    "cntrMthdCd",
}
SENSITIVE_EXACT_KEYS = {
    "access_token",
    "accesstoken",
    "addr",
    "address",
    "auth_token",
    "authtoken",
    "email",
    "emailaddress",
    "mbrsnm",
    "mobile",
    "name",
    "phone",
    "refreshtoken",
    "secret",
    "set-cookie",
    "token",
    "user_email_addr",
    "user_mtel",
    "userid",
    "usermngseqno",
}
SENSITIVE_KEY_PARTS = (
    "addr",
    "address",
    "cookie",
    "email",
    "mobile",
    "password",
    "phone",
    "secret",
    "token",
)

SYNTHETIC_CUSTOMERS = (
    {
        "APT_NAME": "테스트아파트",
        "APT_DONGNO": "1001",
        "APT_HONO": "0101",
        "CUST_NO": "TEST_CUST_001",
        "SI_CUST_NO": "TEST_HOUSE_001",
        "cntrMthdCd": "아파트(단일계약)",
    },
    {
        "APT_NAME": "테스트아파트 2",
        "APT_DONGNO": "1002",
        "APT_HONO": "0102",
        "CUST_NO": "TEST_CUST_002",
        "SI_CUST_NO": "TEST_HOUSE_002",
        "cntrMthdCd": "아파트(단일계약)",
    },
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    records = _read_capture(args.input)
    fixtures = _build_fixtures(records)
    _audit_fixtures(fixtures)

    if args.check:
        missing_or_changed = [
            name
            for name, payload in fixtures.items()
            if not _output_path(name).exists()
            or _render_json(payload) != _output_path(name).read_text(encoding="utf-8")
        ]
        if missing_or_changed:
            raise SystemExit(
                f"fixtures are not deterministic/current: {', '.join(missing_or_changed)}"
            )
        print(f"OK: {len(fixtures)} sanitized fixtures are current")
        return 0

    for name, payload in fixtures.items():
        path = _output_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_json(payload), encoding="utf-8")
    print(f"OK: wrote {len(fixtures)} sanitized fixtures")
    return 0


def _read_capture(path: Path) -> list[dict[str, Any]]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_CAPTURE_SHA256:
        raise SystemExit("input capture SHA256 does not match the expected safe capture")

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as capture:
        for line_number, line in enumerate(capture, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as err:
                raise SystemExit(f"invalid JSONL record at line {line_number}") from err
            if not isinstance(record, dict):
                raise SystemExit(f"record at line {line_number} is not an object")
            records.append(record)

    if len(records) != EXPECTED_RECORD_COUNT:
        raise SystemExit("input capture record count does not match the expected safe capture")
    return records


def _build_fixtures(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bodies = [_body(record) for record in records]
    session = _first_body(bodies, lambda body: {"result", "token", "refreshToken"} <= body.keys())
    sso = _first_body(bodies, lambda body: {"loginChk", "refreshToken"} <= body.keys())
    customer_single = _first_body(bodies, lambda body: isinstance(body.get("dlt_appendList"), list))
    customer_multiple = _first_body(
        bodies, lambda body: isinstance(body.get("dlt_myPageAppendList"), list)
    )
    latest_bill = _first_body(
        bodies,
        lambda body: (
            _bill_result(body).get("DO_FROM_MMDD") == "20260701"
            and _bill_result(body).get("DO_KWH") == "573"
            and _history_count(body) == 24
        ),
    )
    requested_bill = _first_body(
        bodies,
        lambda body: (
            _bill_result(body).get("DO_FROM_MMDD") == "20260601"
            and _bill_result(body).get("DO_KWH") == "406"
            and _history_count(body) == 24
        ),
    )

    return {
        "session_check_success.json": _sanitize_session(session),
        "sso_check_success.json": _sanitize_sso(sso),
        "customer_list_single.json": _sanitize_customers(customer_single, "dlt_appendList", 1),
        "customer_list_multiple.json": _sanitize_customers(
            customer_multiple, "dlt_myPageAppendList", 2
        ),
        "bill_latest.json": _sanitize_bill(latest_bill),
        "bill_202607.json": _sanitize_bill(requested_bill),
    }


def _body(record: dict[str, Any]) -> dict[str, Any] | None:
    body = record.get("body")
    if not isinstance(body, str):
        return None
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _first_body(
    bodies: Iterable[dict[str, Any] | None],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    for body in bodies:
        if body is not None and predicate(body):
            return body
    raise SystemExit("expected response structure was not found in safe capture")


def _bill_result(body: dict[str, Any]) -> dict[str, Any]:
    result = body.get("dma_result")
    return result if isinstance(result, dict) else {}


def _history_count(body: dict[str, Any]) -> int:
    history = body.get("dlt_chrtList")
    return len(history) if isinstance(history, list) else 0


def _sanitize_session(body: dict[str, Any]) -> dict[str, Any]:
    return {"result": body.get("result")}


def _sanitize_sso(body: dict[str, Any]) -> dict[str, Any]:
    return {"loginChk": body.get("loginChk")}


def _sanitize_customers(body: dict[str, Any], list_key: str, count: int) -> dict[str, Any]:
    sanitized = cast("dict[str, Any]", _strip_sensitive(deepcopy(body)))
    sanitized[list_key] = [dict(SYNTHETIC_CUSTOMERS[index]) for index in range(count)]
    return sanitized


def _sanitize_bill(body: dict[str, Any]) -> dict[str, Any]:
    sanitized = cast("dict[str, Any]", _strip_sensitive(deepcopy(body)))
    result = sanitized.get("dma_result")
    if isinstance(result, dict):
        result.pop("DO_CUSTNO", None)
    return sanitized


def _strip_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if _is_sensitive_key(key):
                continue
            output[key] = _strip_sensitive(_normalize_placeholder(item))
        return output
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return _normalize_placeholder(value)


def _audit_fixtures(fixtures: dict[str, dict[str, Any]]) -> None:
    rendered = json.dumps(fixtures, ensure_ascii=False, sort_keys=True)
    forbidden_text = (
        "[REDACTED]",
        "USER_MTEL",
        "USER_EMAIL_ADDR",
        "ADDR",
        "mbrsNm",
        "userMngSeqno",
        "directive",
        "canary",
    )
    for text in forbidden_text:
        if text in rendered:
            raise SystemExit("sanitized fixtures contain forbidden sensitive metadata")

    def walk(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if _is_sensitive_key(key):
                    raise SystemExit("sanitized fixtures contain a sensitive key")
                if key in {"CUST_NO", "SI_CUST_NO"} and not str(item).startswith("TEST_"):
                    raise SystemExit("customer identifiers must be synthetic")
                walk(item, (*path, key))
        elif isinstance(value, list):
            for item in value:
                walk(item, path)

    walk(fixtures)


def _is_sensitive_key(key: str) -> bool:
    if key in ALLOWED_SYNTHETIC_CUSTOMER_KEYS:
        return False
    normalized = key.replace("-", "_").lower()
    compact = normalized.replace("_", "")
    return (
        normalized in SENSITIVE_EXACT_KEYS
        or compact in SENSITIVE_EXACT_KEYS
        or any(part in normalized for part in SENSITIVE_KEY_PARTS)
    )


def _normalize_placeholder(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        return None
    return value


def _output_path(name: str) -> Path:
    path = FIXTURE_DIR / name
    resolved_fixture_dir = FIXTURE_DIR.resolve()
    resolved_path = path.resolve()
    if resolved_fixture_dir not in resolved_path.parents:
        raise SystemExit("refusing to write outside tests/fixtures")
    return path


def _render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
