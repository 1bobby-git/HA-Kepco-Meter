"""Parser contract tests for sanitized KEPCO ON payload fixtures."""

from __future__ import annotations

import json
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Protocol, cast

import pytest
from custom_components.kepco_on.exceptions import KepcoOnNoCustomersError, KepcoOnProtocolError
from custom_components.kepco_on.parser import (
    parse_bill,
    parse_customers,
    parse_date,
    parse_int,
    parse_year_month,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class FixtureExtractor(Protocol):
    """Subset of the extractor module used by parser fixture tests."""

    def _strip_sensitive(self, value: JsonValue) -> JsonValue: ...

    def _audit_fixtures(self, fixtures: dict[str, dict[str, JsonValue]]) -> None: ...


def load_fixture(name: str) -> dict[str, object]:
    return cast("dict[str, object]", json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def load_extractor() -> FixtureExtractor:
    spec = spec_from_file_location("extract_safe_fixtures", ROOT / "tools/extract-safe-fixtures.py")
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast("FixtureExtractor", module)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("96,330", 96330),
        ("-16000", -16000),
        (0, 0),
        (None, None),
        ("", None),
        ("null", None),
    ],
)
def test_parse_int_accepts_kepco_number_shapes(value: object, expected: int | None) -> None:
    assert parse_int(value, "amount") == expected


def test_parse_int_rejects_nonempty_invalid_value() -> None:
    with pytest.raises(KepcoOnProtocolError):
        parse_int("not-a-number", "amount")


def test_parse_date_is_strict() -> None:
    assert parse_date("20260731", "period_end") == date(2026, 7, 31)

    with pytest.raises(KepcoOnProtocolError):
        parse_date("20260230", "period_end")


def test_parse_year_month_is_strict() -> None:
    assert parse_year_month("202607", "bill_month") == "202607"

    with pytest.raises(KepcoOnProtocolError):
        parse_year_month("202613", "bill_month")


def test_parse_customers_accepts_single_customer_append_list() -> None:
    customers = parse_customers(load_fixture("customer_list_single.json"), "ACCOUNT_HASH")

    assert len(customers) == 1
    customer = customers[0]
    assert customer.customer_number == "TEST_CUST_001"
    assert customer.house_contract_number == "TEST_HOUSE_001"
    assert customer.apartment_name == "테스트아파트"
    assert customer.dong == "1001"
    assert customer.ho == "0101"
    assert customer.contract_method == "아파트(단일계약)"
    assert customer.is_supported is True


def test_parse_customers_accepts_multiple_my_page_append_list() -> None:
    customers = parse_customers(load_fixture("customer_list_multiple.json"), "ACCOUNT_HASH")

    assert [customer.customer_number for customer in customers] == [
        "TEST_CUST_001",
        "TEST_CUST_002",
    ]
    assert {customer.stable_key for customer in customers} == {
        customer.stable_key for customer in customers
    }
    assert customers[0].stable_key != customers[1].stable_key


def test_parse_customers_rejects_empty_list() -> None:
    with pytest.raises(KepcoOnNoCustomersError):
        parse_customers({"dlt_appendList": []}, "ACCOUNT_HASH")


def test_parse_customer_repr_does_not_expose_raw_identifiers() -> None:
    customer = parse_customers(load_fixture("customer_list_single.json"), "ACCOUNT_HASH")[0]

    rendered = repr(customer)
    assert "TEST_CUST_001" not in rendered
    assert "TEST_HOUSE_001" not in rendered
    assert customer.stable_key
    assert "TEST_CUST_001" not in customer.stable_key
    assert "TEST_HOUSE_001" not in customer.stable_key


def test_customer_stable_key_is_full_domain_separated_sha256() -> None:
    customer = parse_customers(load_fixture("customer_list_single.json"), "ACCOUNT_HASH")[0]
    same_customer = parse_customers(load_fixture("customer_list_single.json"), "ACCOUNT_HASH")[0]
    other_account = parse_customers(
        load_fixture("customer_list_single.json"), "OTHER_ACCOUNT_HASH"
    )[0]

    assert len(customer.stable_key) == 64
    assert all(character in "0123456789abcdef" for character in customer.stable_key)
    assert customer.stable_key == same_customer.stable_key
    assert customer.stable_key != other_account.stable_key
    assert "ACCOUNT_HASH" not in customer.stable_key
    assert "TEST_CUST_001" not in customer.stable_key
    assert "TEST_HOUSE_001" not in customer.stable_key


def test_generated_fixtures_do_not_contain_bracketed_placeholders() -> None:
    for path in FIXTURES.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "[REDACTED]" not in text


def test_parse_latest_bill_extracts_all_governing_values() -> None:
    bill = parse_bill(load_fixture("bill_latest.json"), requested_month=None)

    assert bill.bill_month == "202608"
    assert bill.period_start == date(2026, 7, 1)
    assert bill.period_end == date(2026, 7, 31)
    assert bill.usage_kwh == 573
    assert bill.previous_usage_kwh == 406
    assert bill.last_year_usage_kwh == 612
    assert bill.building_average_kwh == 363
    assert bill.apartment_average_kwh == 284
    assert bill.current_meter_reading == 23139
    assert bill.previous_meter_reading == 22566
    assert bill.amount_krw == 96330
    assert bill.charge.subtotal_krw == 85484
    assert bill.charge.base_krw == 6060
    assert bill.charge.energy_krw == 87402
    assert bill.charge.climate_krw == 5157
    assert bill.charge.fuel_krw == 2865
    assert bill.charge.child_discount_krw == -16000
    assert bill.charge.vat_krw == 8548
    assert bill.charge.fund_krw == 2300
    assert bill.charge.rounding_krw == 2
    assert len(bill.history) == 24
    assert bill.history[0].month == "202409"
    assert bill.history[-1].month == "202608"


def test_parse_requested_bill_uses_requested_month_over_response_month() -> None:
    bill = parse_bill(load_fixture("bill_202607.json"), requested_month="202607")

    assert bill.bill_month == "202607"
    assert bill.response_bill_month == "202608"
    assert bill.period_start == date(2026, 6, 1)
    assert bill.period_end == date(2026, 6, 30)
    assert bill.usage_kwh == 406
    assert bill.previous_usage_kwh == 371
    assert bill.last_year_usage_kwh == 459
    assert bill.building_average_kwh == 248
    assert bill.apartment_average_kwh == 185
    assert bill.current_meter_reading == 22566
    assert bill.previous_meter_reading == 22160
    assert bill.amount_krw == 59720
    assert bill.charge.subtotal_krw == 52997
    assert bill.charge.base_krw == 6060
    assert bill.charge.energy_krw == 57253
    assert bill.charge.climate_krw == 3654
    assert bill.charge.fuel_krw == 2030
    assert bill.charge.child_discount_krw == -16000
    assert bill.charge.vat_krw == 5300
    assert bill.charge.fund_krw == 1430
    assert bill.charge.rounding_krw == 7
    assert bill.history[0].month == "202408"
    assert bill.history[-1].month == "202607"


def test_parse_bill_status_success_accepts_hxi001() -> None:
    bill = parse_bill({"status": "S", "DO_ERR_CODE": "HXI001", "DO_BILL_YM": "202608"}, None)

    assert bill.bill_month == "202608"


def test_parse_bill_rejects_non_success_status() -> None:
    with pytest.raises(KepcoOnProtocolError):
        parse_bill({"status": "F", "DO_ERR_CODE": "HXI001", "DO_BILL_YM": "202608"}, None)


def test_parse_bill_history_must_be_sorted_unique_and_valid() -> None:
    base = load_fixture("bill_latest.json")

    duplicate = dict(base)
    duplicate["history"] = [{"BILL_YM": "202607"}, {"BILL_YM": "202607"}]
    with pytest.raises(KepcoOnProtocolError):
        parse_bill(duplicate, None)

    unsorted = dict(base)
    unsorted["history"] = [{"BILL_YM": "202608"}, {"BILL_YM": "202607"}]
    with pytest.raises(KepcoOnProtocolError):
        parse_bill(unsorted, None)

    invalid = dict(base)
    invalid["history"] = [{"BILL_YM": "20260230"}]
    with pytest.raises(KepcoOnProtocolError):
        parse_bill(invalid, None)


def test_parse_bill_rejects_large_response_history_month_contradiction() -> None:
    payload = load_fixture("bill_202607.json")
    result = payload["dma_result"]
    assert isinstance(result, dict)
    result["DO_BILL_YM"] = "202701"

    with pytest.raises(KepcoOnProtocolError):
        parse_bill(payload, requested_month="202607")


def test_parse_bill_empty_values_are_none_and_comma_numbers_work() -> None:
    bill = parse_bill(
        {
            "status": "S",
            "DO_ERR_CODE": "HXI001",
            "DO_BILL_YM": "202608",
            "USE_QTY": "",
            "BILL_AMT": "96,330",
        },
        None,
    )

    assert bill.usage_kwh is None
    assert bill.amount_krw == 96330


def test_extractor_strips_nested_generic_personal_secret_keys() -> None:
    extractor = load_extractor()
    payload: dict[str, JsonValue] = {
        "safe": "kept",
        "emailAddress": "private@example.test",
        "nested": {
            "accessToken": "SECRET_ACCESS",
            "authToken": "SECRET_AUTH",
            "phone": "01000000000",
            "children": [
                {"mobile": "01011112222"},
                {"address": "private address"},
                {"name": "private name"},
            ],
        },
    }

    sanitized = extractor._strip_sensitive(payload)

    assert isinstance(sanitized, dict)
    assert sanitized == {"nested": {"children": [{}, {}, {}]}, "safe": "kept"}


def test_extractor_audit_rejects_nested_generic_personal_secret_keys() -> None:
    extractor = load_extractor()
    fixture: dict[str, dict[str, JsonValue]] = {
        "unsafe.json": {"nested": [{"accessToken": "SECRET_ACCESS"}]}
    }

    with pytest.raises(SystemExit):
        extractor._audit_fixtures(fixture)
