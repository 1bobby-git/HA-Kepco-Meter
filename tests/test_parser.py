"""Parser contract tests for sanitized KEPCO ON payload fixtures."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

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


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
    payload["dma_result"]["DO_BILL_YM"] = "202701"

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
