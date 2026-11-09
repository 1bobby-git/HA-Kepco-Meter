"""Field-level isolation of optional KEPCO ON bill fields (v0.4.3)."""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
from custom_components.kepco_on.exceptions import KepcoOnProtocolError
from custom_components.kepco_on.models import KepcoBill, KepcoChargeBreakdown
from custom_components.kepco_on.parser import parse_bill, parse_house_bill

from .test_sensor import by_key, setup_entities

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CANARY = "PRIVATE_VALUE_CANARY_7"

OPTIONAL_BILL_FIELDS = [
    ("DO_FROM_MMDD", "period_start"),
    ("DO_TO_MMDD", "period_end"),
    ("DO_KWH", "usage_kwh"),
    ("DO_TP_RSD_KWH", "household_usage_kwh"),
    ("DO_TP_CMNUS_KWH", "common_usage_kwh"),
    ("DO_BEF_KWH", "previous_usage_kwh"),
    ("DO_LAST_YEAR_KWH", "last_year_usage_kwh"),
    ("DO_APT_HOUS_USKI_AVG", "building_average_kwh"),
    ("DO_APT_TOT_USKI_AVG", "apartment_average_kwh"),
    ("DO_WHM_MTR_ALW", "current_meter_reading"),
    ("DO_BEF_MTR_ALW", "previous_meter_reading"),
    ("DO_GUMCHM_DD", "meter_reading_day"),
    ("DO_PRE_REQ_BILL", "amount_krw"),
    ("DO_PRE_BILL", "charge.subtotal_krw"),
    ("DO_PRE_BASE_BILL", "charge.base_krw"),
    ("DO_PRE_KWHBILL", "charge.energy_krw"),
    ("DO_PRE_CLMT_ENVRN_BILL", "charge.climate_krw"),
    ("DO_PRE_FUEL_COST_ADJ_BILL", "charge.fuel_krw"),
    ("DO_PRE_CHILD_DC_BILL", "charge.child_discount_krw"),
    ("DO_PRE_BILL_VAT", "charge.vat_krw"),
    ("DO_PRE_PUBCHGE", "charge.fund_krw"),
    ("DO_PRE_REQ_BILLODD", "charge.rounding_krw"),
]


def load_fixture(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def with_field(field: str, value: object) -> dict[str, Any]:
    payload = load_fixture("bill_latest.json")
    payload["dma_result"][field] = value
    return payload


def none_for(*names: str) -> dict[str, Any]:
    """Return replace() keyword arguments that clear the named fields."""
    return dict.fromkeys(names)


def without(bill: KepcoBill, field: str) -> KepcoBill:
    """Return the bill with one parsed field cleared and marked invalid."""
    if field.startswith("charge."):
        charge = dataclasses.replace(bill.charge, **none_for(field.removeprefix("charge.")))
        cleared = dataclasses.replace(bill, charge=charge)
    else:
        cleared = dataclasses.replace(bill, **none_for(field))
    return dataclasses.replace(cleared, invalid_fields=frozenset({field}))


@pytest.mark.parametrize(("source_key", "field"), OPTIONAL_BILL_FIELDS)
def test_malformed_optional_bill_field_clears_only_that_field(
    source_key: str, field: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="custom_components.kepco_on.parser")
    baseline = parse_bill(load_fixture("bill_latest.json"), None)
    assert baseline.invalid_fields == frozenset()

    parsed = parse_bill(with_field(source_key, CANARY), None)

    assert parsed == without(baseline, field)
    assert "1 optional field(s)" in caplog.text
    assert field in caplog.text
    assert CANARY not in caplog.text


@pytest.mark.parametrize(
    ("source_key", "field", "attribute"),
    [
        ("DO_CHRT_KWH", "history.usage_kwh", "usage_kwh"),
        ("DO_CHRT_AFTR_MNY", "history.amount_krw", "amount_krw"),
    ],
)
def test_malformed_history_value_clears_only_that_month(
    source_key: str, field: str, attribute: str
) -> None:
    baseline = parse_bill(load_fixture("bill_latest.json"), None)
    payload = load_fixture("bill_latest.json")
    payload["dlt_chrtList"][-2][source_key] = CANARY

    parsed = parse_bill(payload, None)

    history = list(baseline.history)
    history[-2] = dataclasses.replace(history[-2], **none_for(attribute))
    assert parsed == dataclasses.replace(
        baseline, history=tuple(history), invalid_fields=frozenset({field})
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["dma_result"].__setitem__("DO_BILL_YM", CANARY),
        lambda payload: payload["dlt_chrtList"][0].__setitem__("DO_CHRT_REQ_YM", CANARY),
        lambda payload: payload.__setitem__("dlt_chrtList", CANARY),
        lambda payload: payload.__setitem__("rsMsg", {"statusCode": "F"}),
    ],
    ids=["bill_month", "history_month", "history_shape", "status"],
)
def test_required_bill_fields_still_fail_closed(mutate: Any) -> None:
    payload = load_fixture("bill_latest.json")
    mutate(payload)

    with pytest.raises(KepcoOnProtocolError) as raised:
        parse_bill(payload, None)

    assert CANARY not in str(raised.value)


def house_payload() -> dict[str, Any]:
    payload = load_fixture("house_main_chart.json")
    payload["dlt_chart"].append({"jojYmFilter": "202508", "kwh": "512", "afterMny": "120000"})
    return payload


def house_row(payload: dict[str, Any], month: str) -> dict[str, Any]:
    return next(row for row in payload["dlt_chart"] if row["jojYmFilter"] == month)


@pytest.mark.parametrize(
    ("month", "source_key", "expected_invalid", "cleared"),
    [
        ("202608", "kwh", {"usage_kwh", "history.usage_kwh"}, {"usage_kwh"}),
        ("202608", "afterMny", {"amount_krw", "history.amount_krw"}, {"amount_krw"}),
        ("202607", "kwh", {"previous_usage_kwh", "history.usage_kwh"}, {"previous_usage_kwh"}),
        ("202508", "kwh", {"last_year_usage_kwh", "history.usage_kwh"}, {"last_year_usage_kwh"}),
        ("202606", "afterMny", {"history.amount_krw"}, set()),
    ],
)
def test_malformed_house_value_clears_only_dependent_fields(
    month: str, source_key: str, expected_invalid: set[str], cleared: set[str]
) -> None:
    baseline = parse_house_bill(house_payload())
    payload = house_payload()
    house_row(payload, month)[source_key] = CANARY

    parsed = parse_house_bill(payload)

    attribute = "usage_kwh" if source_key == "kwh" else "amount_krw"
    history = tuple(
        dataclasses.replace(point, **none_for(attribute)) if point.month == month else point
        for point in baseline.history
    )
    expected = dataclasses.replace(
        baseline,
        history=history,
        invalid_fields=frozenset(expected_invalid),
        **none_for(*cleared),
    )
    assert parsed == expected


@pytest.mark.parametrize(
    ("source_key", "changed_sensors"),
    [
        ("DO_TP_CMNUS_KWH", {"household_usage", "common_usage"}),
        ("DO_TP_RSD_KWH", {"household_usage", "common_usage"}),
        (
            "DO_KWH",
            {
                "monthly_usage",
                "neighbor_usage_comparison",
                "co2_estimate",
                "household_usage",
                "common_usage",
            },
        ),
        ("DO_BEF_KWH", {"previous_month_usage", "previous_month_co2_estimate"}),
        ("DO_PRE_BASE_BILL", {"base_charge"}),
        ("DO_GUMCHM_DD", {"meter_reading_day"}),
        ("DO_FROM_MMDD", {"usage_period_start"}),
    ],
)
async def test_only_sensors_using_a_malformed_field_become_unknown(
    source_key: str, changed_sensors: set[str]
) -> None:
    clean = by_key(
        await setup_entities(
            bills_by_customer_key={"cust-a": parse_bill(load_fixture("bill_latest.json"), None)}
        )
    )
    isolated = by_key(
        await setup_entities(
            bills_by_customer_key={"cust-a": parse_bill(with_field(source_key, CANARY), None)}
        )
    )

    changed = {key for key in clean if clean[key].native_value != isolated[key].native_value}
    assert changed == changed_sensors
    assert all(isolated[key].native_value is None for key in changed_sensors)
    # Unknown, not unavailable: the rest of the bill is still valid.
    assert all(entity.available for entity in isolated.values())


@pytest.mark.parametrize(
    ("unreadable_key", "reported_key", "unknown_sensor", "kept_sensor"),
    [
        ("DO_TP_RSD_KWH", "DO_TP_CMNUS_KWH", "household_usage", "common_usage"),
        ("DO_TP_CMNUS_KWH", "DO_TP_RSD_KWH", "common_usage", "household_usage"),
    ],
)
async def test_unreadable_split_side_keeps_a_directly_reported_other_side(
    unreadable_key: str, reported_key: str, unknown_sensor: str, kept_sensor: str
) -> None:
    payload = with_field(unreadable_key, CANARY)
    payload["dma_result"][reported_key] = "100"

    entities = by_key(
        await setup_entities(bills_by_customer_key={"cust-a": parse_bill(payload, None)})
    )

    # The unreadable side is never derived from the total; a reported value stays.
    assert entities[unknown_sensor].native_value is None
    assert entities[kept_sensor].native_value == 100


async def test_coordinator_keeps_bill_with_malformed_optional_field_and_reports_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import custom_components.kepco_on.coordinator as coordinator_module
    from custom_components.kepco_on.coordinator import KepcoOnDataUpdateCoordinator

    from .test_coordinator import FakeClient, customer, make_entry

    created: list[str] = []
    cleared: list[str] = []
    monkeypatch.setattr(
        coordinator_module, "async_create_issue", lambda hass, entry, kind: created.append(kind)
    )
    monkeypatch.setattr(
        coordinator_module, "async_clear_issue", lambda hass, entry, kind: cleared.append(kind)
    )
    customers = (customer("key-1"), customer("key-2"))
    partial = KepcoBill(
        bill_month="202608",
        usage_kwh=321,
        charge=KepcoChargeBreakdown(base_krw=None),
        invalid_fields=frozenset({"charge.base_krw"}),
    )
    FakeClient.bill_results = [KepcoBill(bill_month="202608", usage_kwh=111), partial]
    coordinator = KepcoOnDataUpdateCoordinator(
        cast("Any", Mock()),
        cast("Any", make_entry(customers=customers, selected=["key-1", "key-2"])),
        cast("Any", FakeClient(cast("Any", object()))),
        customers,
    )

    data = await coordinator._async_update_data()

    assert data.bills_by_customer_key["key-2"] == partial
    assert data.errors_by_customer_key == {}
    assert created == ["bill_schema_changed"]
    assert cleared == []

    FakeClient.bill_results = [
        KepcoBill(bill_month="202609", usage_kwh=111),
        KepcoBill(bill_month="202609", usage_kwh=222),
    ]
    await coordinator._async_update_data()

    assert cleared == ["bill_schema_changed"]
