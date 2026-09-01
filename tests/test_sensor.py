"""Sensor platform contract tests for KEPCO ON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from custom_components.kepco_on.const import (
    DOMAIN,
    OPT_CO2_FACTOR_KG_PER_KWH,
    OPT_ENABLE_CO2_ESTIMATE,
    OPT_ENABLE_DETAILED_SENSORS,
    PAGE_URL,
)
from custom_components.kepco_on.models import (
    KepcoBill,
    KepcoChargeBreakdown,
    KepcoCoordinatorData,
    KepcoCustomer,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

ROOT = Path(__file__).resolve().parents[1]
RAW_CUSTOMER_SECRET = "RAW_CUST_1234567890"
RAW_HOUSE_SECRET = "RAW_HOUSE_0987654321"
RAW_NAME_SECRET = "홍길동"


@dataclass(slots=True)
class FakeCoordinator:
    """Minimal coordinator surface read by CoordinatorEntity sensors."""

    data: KepcoCoordinatorData
    last_update_success: bool = True
    refresh_calls: int = 0
    listener_calls: list[object] | None = None

    def __post_init__(self) -> None:
        self.listener_calls = []

    def async_add_listener(self, listener: object, context: object = None) -> object:
        assert self.listener_calls is not None
        self.listener_calls.append((listener, context))

        def remove_listener() -> None:
            return None

        return remove_listener

    async def async_request_refresh(self) -> None:
        self.refresh_calls += 1


class FakeEntityRegistry:
    """Entity registry fake for stale cleanup assertions."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.entries = entries
        self.removed: list[str] = []
        self.updated: list[tuple[str, RegistryEntryDisabler | None]] = []

    def async_remove(self, entity_id: str) -> None:
        self.removed.append(entity_id)

    def async_update_entity(
        self,
        entity_id: str,
        *,
        disabled_by: RegistryEntryDisabler | None,
    ) -> None:
        self.updated.append((entity_id, disabled_by))


class FakeDeviceRegistry:
    """Device registry fake for stale cleanup assertions."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.entries = entries
        self.removed: list[str] = []

    def async_remove_device(self, device_id: str) -> None:
        self.removed.append(device_id)


class FakeHass:
    """Hashable HA stand-in for registry singleton helpers."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}


def customer(stable_key: str, *, apartment: str = "푸른아파트") -> KepcoCustomer:
    """Return a privacy-canary customer."""
    return KepcoCustomer(
        stable_key=stable_key,
        apartment_name=apartment,
        dong="101",
        ho="1001",
        contract_method="아파트(단일계약)",
        is_supported=True,
        _customer_number=f"{RAW_CUSTOMER_SECRET}_{stable_key}",
        _house_contract_number=f"{RAW_HOUSE_SECRET}_{stable_key}",
    )


def bill(
    *,
    usage_kwh: int | None = 573,
    amount_krw: int | None = 96330,
    child_discount_krw: int | None = -16000,
    building_average_kwh: int | None = 363,
    apartment_average_kwh: int | None = 284,
) -> KepcoBill:
    """Return a synthetic bill with every sensor-backed field populated."""
    return KepcoBill(
        bill_month="202608",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        usage_kwh=usage_kwh,
        previous_usage_kwh=406,
        last_year_usage_kwh=612,
        building_average_kwh=building_average_kwh,
        apartment_average_kwh=apartment_average_kwh,
        current_meter_reading=23139,
        previous_meter_reading=22566,
        meter_reading_day="01",
        amount_krw=amount_krw,
        charge=KepcoChargeBreakdown(
            subtotal_krw=85484,
            base_krw=6060,
            energy_krw=87402,
            climate_krw=5157,
            fuel_krw=2865,
            child_discount_krw=child_discount_krw,
            vat_krw=8548,
            fund_krw=2300,
            rounding_krw=2,
        ),
    )


def entry(
    *,
    coordinator: FakeCoordinator,
    options: dict[str, Any] | None = None,
    entry_id: str = "entry-1",
) -> SimpleNamespace:
    """Return a typed-runtime config-entry stand-in."""
    return SimpleNamespace(
        entry_id=entry_id,
        options=options or {},
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )


async def setup_entities(
    *,
    customers: tuple[KepcoCustomer, ...] = (customer("cust-a"),),
    bills_by_customer_key: dict[str, KepcoBill] | None = None,
    errors_by_customer_key: dict[str, str] | None = None,
    options: dict[str, Any] | None = None,
    use_real_registry_cleanup: bool = False,
) -> list[Any]:
    """Set up sensor entities and return the collected entity list."""
    from custom_components.kepco_on import sensor as sensor_module

    data = KepcoCoordinatorData(
        customers=customers,
        bills_by_customer_key=bills_by_customer_key
        if bills_by_customer_key is not None
        else {customers[0].stable_key: bill()},
        errors_by_customer_key=errors_by_customer_key or {},
    )
    coordinator = FakeCoordinator(data)
    config_entry = entry(coordinator=coordinator, options=options)
    entities: list[Any] = []

    sensor_any = cast("Any", sensor_module)
    add_entities = cast("Any", entities.extend)
    if use_real_registry_cleanup:
        await sensor_module.async_setup_entry(
            cast("Any", FakeHass()), cast("Any", config_entry), add_entities
        )
        return entities

    entity_registry = FakeEntityRegistry([])
    device_registry = FakeDeviceRegistry([])
    original_entity_get = sensor_any.er.async_get
    original_entity_entries = sensor_any.er.async_entries_for_config_entry
    original_device_get = sensor_any.dr.async_get
    original_device_entries = sensor_any.dr.async_entries_for_config_entry
    sensor_any.er.async_get = lambda hass: entity_registry
    sensor_any.er.async_entries_for_config_entry = lambda reg, entry_id: reg.entries
    sensor_any.dr.async_get = lambda hass: device_registry
    sensor_any.dr.async_entries_for_config_entry = lambda reg, entry_id: reg.entries
    try:
        await sensor_module.async_setup_entry(
            cast("Any", FakeHass()), cast("Any", config_entry), add_entities
        )
    finally:
        sensor_any.er.async_get = original_entity_get
        sensor_any.er.async_entries_for_config_entry = original_entity_entries
        sensor_any.dr.async_get = original_device_get
        sensor_any.dr.async_entries_for_config_entry = original_device_entries

    return entities


def entity_entry(
    entity_id: str,
    unique_id: str,
    *,
    platform: str = DOMAIN,
    config_entry_id: str = "entry-1",
    disabled_by: RegistryEntryDisabler | None = None,
) -> SimpleNamespace:
    """Return a registry entry fake."""
    return SimpleNamespace(
        entity_id=entity_id,
        unique_id=unique_id,
        platform=platform,
        config_entry_id=config_entry_id,
        disabled_by=disabled_by,
    )


def by_key(entities: list[Any]) -> dict[str, Any]:
    """Return entities keyed by sensor description key."""
    return {entity.entity_description.key: entity for entity in entities}


@pytest.mark.asyncio
async def test_default_sensors_have_exact_count_metadata_values_and_privacy() -> None:
    entities = await setup_entities()
    sensors = by_key(entities)

    assert set(sensors) == {
        "monthly_usage",
        "meter_reading",
        "amount_due",
        "previous_month_usage",
        "last_year_same_month_usage",
        "neighbor_usage_comparison",
        "building_average_usage",
        "apartment_average_usage",
        "previous_meter_reading",
        "billing_month",
        "usage_period_start",
        "usage_period_end",
        "meter_reading_day",
        "electricity_subtotal",
        "base_charge",
        "energy_charge",
        "climate_environment_charge",
        "fuel_adjustment_charge",
        "child_discount",
        "vat",
        "power_industry_fund",
        "rounding_amount",
    }
    assert len(entities) == 22

    default_enabled = {
        "monthly_usage",
        "meter_reading",
        "amount_due",
        "previous_month_usage",
        "last_year_same_month_usage",
        "neighbor_usage_comparison",
        "building_average_usage",
        "apartment_average_usage",
    }
    for key, entity in sensors.items():
        assert entity.has_entity_name is True
        assert entity.translation_key == key
        assert entity.unique_id == f"cust-a_{key}"
        assert entity.entity_description.entity_registry_enabled_default is (key in default_enabled)
        assert entity.device_info == {
            "identifiers": {(DOMAIN, "cust-a")},
            "name": "한전ON 전기요금 101동 1001호",
            "manufacturer": "한국전력공사(KEPCO)",
            "model": "한전ON 아파트 세대요금",
            "configuration_url": PAGE_URL,
        }
        rendered = repr(entity.device_info) + repr(entity.unique_id) + repr(entity.native_value)
        assert RAW_CUSTOMER_SECRET not in rendered
        assert RAW_HOUSE_SECRET not in rendered
        assert RAW_NAME_SECRET not in rendered

    assert sensors["monthly_usage"].native_value == 573
    assert sensors["monthly_usage"].native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
    assert sensors["monthly_usage"].device_class == SensorDeviceClass.ENERGY
    assert sensors["monthly_usage"].state_class is None
    assert sensors["meter_reading"].native_value == 23139
    assert sensors["meter_reading"].state_class == SensorStateClass.TOTAL_INCREASING
    assert sensors["amount_due"].native_value == 96330
    assert sensors["amount_due"].native_unit_of_measurement == "KRW"
    assert sensors["amount_due"].device_class == SensorDeviceClass.MONETARY
    assert sensors["amount_due"].state_class is None
    assert sensors["previous_month_usage"].state_class is None
    assert sensors["last_year_same_month_usage"].state_class is None
    assert sensors["neighbor_usage_comparison"].native_value == 573
    assert (
        sensors["neighbor_usage_comparison"].native_unit_of_measurement
        == UnitOfEnergy.KILO_WATT_HOUR
    )
    assert sensors["neighbor_usage_comparison"].device_class == SensorDeviceClass.ENERGY
    assert sensors["neighbor_usage_comparison"].state_class is None
    assert sensors["neighbor_usage_comparison"].extra_state_attributes == {
        "billing_month": "202608",
        "usage_period_start": date(2026, 7, 1),
        "usage_period_end": date(2026, 7, 31),
        "same_building_average_kwh": 363,
        "apartment_average_kwh": 284,
    }
    rendered = repr(sensors["neighbor_usage_comparison"].extra_state_attributes)
    assert RAW_CUSTOMER_SECRET not in rendered
    assert RAW_HOUSE_SECRET not in rendered
    assert RAW_NAME_SECRET not in rendered
    assert sensors["building_average_usage"].state_class is None
    assert sensors["apartment_average_usage"].state_class is None
    assert sensors["usage_period_start"].device_class == SensorDeviceClass.DATE
    assert sensors["usage_period_start"].native_value == date(2026, 7, 1)
    assert sensors["usage_period_end"].device_class == SensorDeviceClass.DATE
    assert sensors["meter_reading_day"].native_value == "01"
    assert sensors["child_discount"].native_value == -16000
    assert sensors["child_discount"].native_unit_of_measurement == "KRW"
    assert sensors["child_discount"].device_class == SensorDeviceClass.MONETARY


@pytest.mark.asyncio
async def test_detailed_option_enables_disabled_entities_only_at_creation() -> None:
    entities = await setup_entities(options={OPT_ENABLE_DETAILED_SENSORS: True})

    assert all(entity.entity_description.entity_registry_enabled_default for entity in entities)


@pytest.mark.asyncio
async def test_attributes_only_include_non_null_billing_context() -> None:
    sensors = by_key(await setup_entities())

    assert sensors["monthly_usage"].extra_state_attributes == {
        "billing_month": "202608",
        "usage_period_start": date(2026, 7, 1),
        "usage_period_end": date(2026, 7, 31),
    }

    missing = by_key(
        await setup_entities(
            bills_by_customer_key={
                "cust-a": KepcoBill(
                    bill_month="202608",
                    usage_kwh=None,
                    amount_krw=None,
                )
            }
        )
    )
    assert missing["monthly_usage"].native_value is None
    assert missing["monthly_usage"].extra_state_attributes == {"billing_month": "202608"}


@pytest.mark.asyncio
async def test_neighbor_usage_comparison_keeps_usage_when_neighbor_averages_missing() -> None:
    sensors = by_key(
        await setup_entities(
            bills_by_customer_key={
                "cust-a": bill(building_average_kwh=None, apartment_average_kwh=None)
            }
        )
    )

    assert sensors["neighbor_usage_comparison"].native_value == 573
    assert sensors["neighbor_usage_comparison"].extra_state_attributes == {
        "billing_month": "202608",
        "usage_period_start": date(2026, 7, 1),
        "usage_period_end": date(2026, 7, 31),
        "same_building_average_kwh": None,
        "apartment_average_kwh": None,
    }


@pytest.mark.asyncio
async def test_multiple_customers_and_partial_failure_availability_are_isolated() -> None:
    customers = (customer("cust-a"), customer("cust-b"))
    entities = await setup_entities(
        customers=customers,
        bills_by_customer_key={"cust-a": bill()},
        errors_by_customer_key={"cust-b": "protocol_error"},
    )
    successful = [entity for entity in entities if entity.unique_id.startswith("cust-a_")]
    failed = [entity for entity in entities if entity.unique_id.startswith("cust-b_")]

    assert len(successful) == 22
    assert len(failed) == 22
    assert {entity.available for entity in successful} == {True}
    assert {entity.available for entity in failed} == {False}
    assert {entity.native_value for entity in failed} == {None}


@pytest.mark.asyncio
async def test_multiple_customer_device_names_are_distinct_and_privacy_safe() -> None:
    customers = (
        customer("cust-a"),
        KepcoCustomer(
            stable_key="cust-b",
            apartment_name="비밀아파트",
            dong="202",
            ho="0304",
            contract_method="아파트(단일계약)",
            is_supported=True,
            _customer_number=f"{RAW_CUSTOMER_SECRET}_b",
            _house_contract_number=f"{RAW_HOUSE_SECRET}_b",
        ),
    )
    entities = await setup_entities(
        customers=customers,
        bills_by_customer_key={"cust-a": bill(), "cust-b": bill()},
    )
    device_names = {
        entity.device_info["name"]
        for entity in entities
        if entity.entity_description.key == "monthly_usage"
    }

    assert device_names == {
        "한전ON 전기요금 101동 1001호",
        "한전ON 전기요금 202동 0304호",
    }
    rendered = repr([entity.device_info for entity in entities])
    assert RAW_CUSTOMER_SECRET not in rendered
    assert RAW_HOUSE_SECRET not in rendered
    assert RAW_NAME_SECRET not in rendered


@pytest.mark.asyncio
async def test_co2_sensor_is_optional_estimated_and_decimal_rounded() -> None:
    assert "co2_estimate" not in by_key(await setup_entities())

    sensors = by_key(
        await setup_entities(
            options={
                OPT_ENABLE_CO2_ESTIMATE: True,
                OPT_CO2_FACTOR_KG_PER_KWH: "0.459",
            }
        )
    )
    assert sensors["co2_estimate"].native_value == 263
    assert sensors["co2_estimate"].native_unit_of_measurement == "kg CO₂"
    assert sensors["co2_estimate"].translation_key == "co2_estimate"
    assert sensors["co2_estimate"].entity_description.entity_registry_enabled_default is True
    assert sensors["co2_estimate"].state_class is None

    missing_usage = by_key(
        await setup_entities(
            bills_by_customer_key={"cust-a": bill(usage_kwh=None)},
            options={OPT_ENABLE_CO2_ESTIMATE: True, OPT_CO2_FACTOR_KG_PER_KWH: 0.459},
        )
    )
    assert missing_usage["co2_estimate"].native_value is None

    missing_factor = by_key(await setup_entities(options={OPT_ENABLE_CO2_ESTIMATE: True}))
    assert missing_factor["co2_estimate"].native_value is None


@pytest.mark.asyncio
async def test_setup_removes_only_stale_entities_and_solely_owned_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.kepco_on import sensor as sensor_module

    sensor_any = cast("Any", sensor_module)
    entity_registry = FakeEntityRegistry(
        [
            entity_entry(
                entity_id="sensor.stale_monthly_usage",
                unique_id="stale_monthly_usage",
            ),
            entity_entry(
                entity_id="sensor.cust_a_monthly_usage",
                unique_id="cust-a_monthly_usage",
            ),
            entity_entry(
                entity_id="sensor.other_domain",
                unique_id="stale_monthly_usage",
                platform="other",
            ),
        ]
    )
    device_registry = FakeDeviceRegistry(
        [
            SimpleNamespace(
                id="device-stale",
                identifiers={(DOMAIN, "stale")},
                config_entries={"entry-1"},
            ),
            SimpleNamespace(
                id="device-shared",
                identifiers={(DOMAIN, "stale")},
                config_entries={"entry-1", "entry-2"},
            ),
            SimpleNamespace(
                id="device-selected",
                identifiers={(DOMAIN, "cust-a")},
                config_entries={"entry-1"},
            ),
        ]
    )
    monkeypatch.setattr(sensor_any.er, "async_get", lambda hass: entity_registry)
    monkeypatch.setattr(
        sensor_any.er, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )
    monkeypatch.setattr(sensor_any.dr, "async_get", lambda hass: device_registry)
    monkeypatch.setattr(
        sensor_any.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )

    await setup_entities(use_real_registry_cleanup=True)

    assert entity_registry.removed == ["sensor.stale_monthly_usage"]
    assert device_registry.removed == ["device-stale"]


@pytest.mark.asyncio
async def test_setup_option_true_reenables_only_integration_disabled_detailed_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.kepco_on import sensor as sensor_module

    sensor_any = cast("Any", sensor_module)
    entity_registry = FakeEntityRegistry(
        [
            entity_entry(
                "sensor.cust_a_previous_meter_reading",
                "cust-a_previous_meter_reading",
                disabled_by=RegistryEntryDisabler.INTEGRATION,
            ),
            entity_entry(
                "sensor.cust_a_base_charge",
                "cust-a_base_charge",
                disabled_by=RegistryEntryDisabler.USER,
            ),
            entity_entry(
                "sensor.cust_a_monthly_usage",
                "cust-a_monthly_usage",
                disabled_by=RegistryEntryDisabler.INTEGRATION,
            ),
            entity_entry(
                "sensor.other_platform_previous_meter_reading",
                "cust-a_previous_meter_reading",
                platform="other",
                disabled_by=RegistryEntryDisabler.INTEGRATION,
            ),
            entity_entry(
                "sensor.other_entry_previous_meter_reading",
                "cust-a_previous_meter_reading",
                config_entry_id="entry-2",
                disabled_by=RegistryEntryDisabler.INTEGRATION,
            ),
        ]
    )
    device_registry = FakeDeviceRegistry([])
    monkeypatch.setattr(sensor_any.er, "async_get", lambda hass: entity_registry)
    monkeypatch.setattr(
        sensor_any.er, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )
    monkeypatch.setattr(sensor_any.dr, "async_get", lambda hass: device_registry)
    monkeypatch.setattr(
        sensor_any.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )

    await setup_entities(
        options={OPT_ENABLE_DETAILED_SENSORS: True},
        use_real_registry_cleanup=True,
    )

    assert entity_registry.updated == [("sensor.cust_a_previous_meter_reading", None)]
    assert entity_registry.removed == []


@pytest.mark.asyncio
async def test_setup_option_false_keeps_manual_detailed_registry_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.kepco_on import sensor as sensor_module

    sensor_any = cast("Any", sensor_module)
    entity_registry = FakeEntityRegistry(
        [
            entity_entry("sensor.cust_a_base_charge", "cust-a_base_charge"),
            entity_entry(
                "sensor.cust_a_vat",
                "cust-a_vat",
                disabled_by=RegistryEntryDisabler.USER,
            ),
        ]
    )
    device_registry = FakeDeviceRegistry([])
    monkeypatch.setattr(sensor_any.er, "async_get", lambda hass: entity_registry)
    monkeypatch.setattr(
        sensor_any.er, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )
    monkeypatch.setattr(sensor_any.dr, "async_get", lambda hass: device_registry)
    monkeypatch.setattr(
        sensor_any.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )

    await setup_entities(use_real_registry_cleanup=True)

    assert entity_registry.updated == []
    assert entity_registry.removed == []


@pytest.mark.asyncio
async def test_setup_co2_toggle_off_removes_only_this_entry_co2_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.kepco_on import sensor as sensor_module

    sensor_any = cast("Any", sensor_module)
    entity_registry = FakeEntityRegistry(
        [
            entity_entry("sensor.cust_a_co2_estimate", "cust-a_co2_estimate"),
            entity_entry("sensor.cust_a_monthly_usage", "cust-a_monthly_usage"),
            entity_entry("sensor.cust_a_base_charge", "cust-a_base_charge"),
            entity_entry(
                "sensor.other_entry_co2_estimate",
                "cust-a_co2_estimate",
                config_entry_id="entry-2",
            ),
            entity_entry(
                "sensor.other_platform_co2_estimate",
                "cust-a_co2_estimate",
                platform="other",
            ),
        ]
    )
    device_registry = FakeDeviceRegistry([])
    monkeypatch.setattr(sensor_any.er, "async_get", lambda hass: entity_registry)
    monkeypatch.setattr(
        sensor_any.er, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )
    monkeypatch.setattr(sensor_any.dr, "async_get", lambda hass: device_registry)
    monkeypatch.setattr(
        sensor_any.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )

    entities = await setup_entities(
        options={OPT_ENABLE_CO2_ESTIMATE: False},
        use_real_registry_cleanup=True,
    )

    assert entity_registry.removed == ["sensor.cust_a_co2_estimate"]
    assert "co2_estimate" not in by_key(entities)


@pytest.mark.asyncio
async def test_setup_co2_toggle_on_keeps_registry_and_creates_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.kepco_on import sensor as sensor_module

    sensor_any = cast("Any", sensor_module)
    entity_registry = FakeEntityRegistry(
        [entity_entry("sensor.cust_a_co2_estimate", "cust-a_co2_estimate")]
    )
    device_registry = FakeDeviceRegistry([])
    monkeypatch.setattr(sensor_any.er, "async_get", lambda hass: entity_registry)
    monkeypatch.setattr(
        sensor_any.er, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )
    monkeypatch.setattr(sensor_any.dr, "async_get", lambda hass: device_registry)
    monkeypatch.setattr(
        sensor_any.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )

    entities = await setup_entities(
        options={OPT_ENABLE_CO2_ESTIMATE: True, OPT_CO2_FACTOR_KG_PER_KWH: "0.459"},
        use_real_registry_cleanup=True,
    )

    assert entity_registry.removed == []
    assert by_key(entities)["co2_estimate"].native_value == 263


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("co2_enabled", "expected_removed"),
    [
        (False, ["sensor.selected_co2", "sensor.stale_co2"]),
        (True, ["sensor.stale_co2"]),
    ],
)
async def test_setup_co2_cleanup_removes_stale_customer_before_option_handling(
    monkeypatch: pytest.MonkeyPatch,
    co2_enabled: bool,
    expected_removed: list[str],
) -> None:
    from custom_components.kepco_on import sensor as sensor_module

    sensor_any = cast("Any", sensor_module)
    entity_registry = FakeEntityRegistry(
        [
            entity_entry("sensor.selected_co2", "cust-a_co2_estimate"),
            entity_entry("sensor.stale_co2", "stale_co2_estimate"),
            entity_entry("sensor.selected_monthly", "cust-a_monthly_usage"),
            entity_entry("sensor.stale_monthly", "stale_monthly_usage"),
            entity_entry(
                "sensor.other_entry_stale_co2",
                "stale_co2_estimate",
                config_entry_id="entry-2",
            ),
            entity_entry(
                "sensor.other_platform_stale_co2",
                "stale_co2_estimate",
                platform="other",
            ),
        ]
    )
    device_registry = FakeDeviceRegistry([])
    monkeypatch.setattr(sensor_any.er, "async_get", lambda hass: entity_registry)
    monkeypatch.setattr(
        sensor_any.er, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )
    monkeypatch.setattr(sensor_any.dr, "async_get", lambda hass: device_registry)
    monkeypatch.setattr(
        sensor_any.dr, "async_entries_for_config_entry", lambda reg, entry_id: reg.entries
    )

    await setup_entities(
        options={OPT_ENABLE_CO2_ESTIMATE: co2_enabled},
        use_real_registry_cleanup=True,
    )

    assert entity_registry.removed == [*expected_removed, "sensor.stale_monthly"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identifiers", "expected"),
    [
        ({(DOMAIN, "cust-a")}, False),
        ({(DOMAIN, "stale")}, True),
        ({("other_domain", "stale")}, False),
        (set(), False),
        ({("other_domain", "stale"), (DOMAIN, "cust-a")}, False),
        ({("other_domain", "stale"), (DOMAIN, "stale")}, True),
        ({(DOMAIN,)}, False),
        ({(DOMAIN, "stale", "extra")}, False),
    ],
)
async def test_async_remove_config_entry_device_only_removes_stale_kepco_customer_devices(
    identifiers: set[tuple[str, ...]], expected: bool
) -> None:
    from custom_components.kepco_on.sensor import async_remove_config_entry_device

    coordinator = FakeCoordinator(
        KepcoCoordinatorData(customers=(customer("cust-a"),), bills_by_customer_key={})
    )
    config_entry = entry(coordinator=coordinator)

    result = await async_remove_config_entry_device(
        cast("Any", object()),
        cast("Any", config_entry),
        cast("Any", SimpleNamespace(identifiers=identifiers, config_entries={"entry-1"})),
    )

    assert result is expected


def test_entity_translations_have_json_parity() -> None:
    strings = json.loads(
        (ROOT / "custom_components/kepco_on/strings.json").read_text(encoding="utf-8")
    )
    english = json.loads(
        (ROOT / "custom_components/kepco_on/translations/en.json").read_text(encoding="utf-8")
    )
    korean = json.loads(
        (ROOT / "custom_components/kepco_on/translations/ko.json").read_text(encoding="utf-8")
    )

    expected_keys = {
        "monthly_usage",
        "meter_reading",
        "amount_due",
        "previous_month_usage",
        "last_year_same_month_usage",
        "building_average_usage",
        "apartment_average_usage",
        "previous_meter_reading",
        "billing_month",
        "usage_period_start",
        "usage_period_end",
        "meter_reading_day",
        "electricity_subtotal",
        "base_charge",
        "energy_charge",
        "climate_environment_charge",
        "fuel_adjustment_charge",
        "child_discount",
        "vat",
        "power_industry_fund",
        "rounding_amount",
        "co2_estimate",
        "neighbor_usage_comparison",
    }

    assert english["entity"] == strings["entity"]
    assert set(strings["entity"]["sensor"]) == expected_keys
    assert set(korean["entity"]["sensor"]) == expected_keys
    assert strings["entity"]["sensor"]["neighbor_usage_comparison"] == {
        "name": "Neighbor electricity usage comparison"
    }
    assert english["entity"]["sensor"]["neighbor_usage_comparison"] == {
        "name": "Neighbor electricity usage comparison"
    }
    assert korean["entity"]["sensor"]["neighbor_usage_comparison"] == {
        "name": "이웃 전기사용량 비교"
    }
    assert korean["entity"]["sensor"]["co2_estimate"] == {"name": "온실가스 배출량"}
    for language in (strings, english, korean):
        for key in expected_keys:
            sensor_translation = language["entity"]["sensor"][key]
            assert set(sensor_translation) == {"name"}
            assert sensor_translation["name"]
