"""Sensor platform for KEPCO ON selected customer bills."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KepcoOnConfigEntry
from .const import (
    DOMAIN,
    OPT_CO2_FACTOR_KG_PER_KWH,
    OPT_ENABLE_CO2_ESTIMATE,
    OPT_ENABLE_DETAILED_SENSORS,
    PAGE_URL,
)
from .coordinator import KepcoOnDataUpdateCoordinator
from .models import KepcoBill, KepcoCustomer

KepcoSensorValue = str | int | date | None


@dataclass(frozen=True, kw_only=True)
class KepcoSensorEntityDescription(SensorEntityDescription):
    """Describe one KEPCO ON sensor value."""

    value_fn: Callable[[KepcoBill, dict[str, Any]], KepcoSensorValue]


def _usage(field: str) -> Callable[[KepcoBill, dict[str, Any]], KepcoSensorValue]:
    """Return a bill usage accessor."""

    def value(bill: KepcoBill, options: dict[str, Any]) -> KepcoSensorValue:
        del options
        value = getattr(bill, field)
        if isinstance(value, str | int | date) or value is None:
            return value
        return None

    return value


def _charge(field: str) -> Callable[[KepcoBill, dict[str, Any]], KepcoSensorValue]:
    """Return a bill charge accessor."""

    def value(bill: KepcoBill, options: dict[str, Any]) -> KepcoSensorValue:
        del options
        value = getattr(bill.charge, field)
        if isinstance(value, str | int | date) or value is None:
            return value
        return None

    return value


def _co2_estimate(bill: KepcoBill, options: dict[str, Any]) -> int | None:
    """Return user-coefficient CO2 estimate in kg."""
    if bill.usage_kwh is None:
        return None
    factor = options.get(OPT_CO2_FACTOR_KG_PER_KWH)
    if factor is None:
        return None
    try:
        estimate = Decimal(bill.usage_kwh) * Decimal(str(factor))
    except InvalidOperation, ValueError:
        return None
    return round(estimate)


DEFAULT_SENSOR_DESCRIPTIONS: tuple[KepcoSensorEntityDescription, ...] = (
    KepcoSensorEntityDescription(
        key="monthly_usage",
        translation_key="monthly_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_usage("usage_kwh"),
    ),
    KepcoSensorEntityDescription(
        key="meter_reading",
        translation_key="meter_reading",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("current_meter_reading"),
    ),
    KepcoSensorEntityDescription(
        key="amount_due",
        translation_key="amount_due",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_usage("amount_krw"),
    ),
    KepcoSensorEntityDescription(
        key="previous_month_usage",
        translation_key="previous_month_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_usage("previous_usage_kwh"),
    ),
    KepcoSensorEntityDescription(
        key="last_year_same_month_usage",
        translation_key="last_year_same_month_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_usage("last_year_usage_kwh"),
    ),
    KepcoSensorEntityDescription(
        key="building_average_usage",
        translation_key="building_average_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_usage("building_average_kwh"),
    ),
    KepcoSensorEntityDescription(
        key="apartment_average_usage",
        translation_key="apartment_average_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_usage("apartment_average_kwh"),
    ),
)

DETAIL_SENSOR_DESCRIPTIONS: tuple[KepcoSensorEntityDescription, ...] = (
    KepcoSensorEntityDescription(
        key="previous_meter_reading",
        translation_key="previous_meter_reading",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_usage("previous_meter_reading"),
    ),
    KepcoSensorEntityDescription(
        key="billing_month",
        translation_key="billing_month",
        value_fn=_usage("bill_month"),
    ),
    KepcoSensorEntityDescription(
        key="usage_period_start",
        translation_key="usage_period_start",
        device_class=SensorDeviceClass.DATE,
        value_fn=_usage("period_start"),
    ),
    KepcoSensorEntityDescription(
        key="usage_period_end",
        translation_key="usage_period_end",
        device_class=SensorDeviceClass.DATE,
        value_fn=_usage("period_end"),
    ),
    KepcoSensorEntityDescription(
        key="meter_reading_day",
        translation_key="meter_reading_day",
        value_fn=_usage("meter_reading_day"),
    ),
    KepcoSensorEntityDescription(
        key="electricity_subtotal",
        translation_key="electricity_subtotal",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("subtotal_krw"),
    ),
    KepcoSensorEntityDescription(
        key="base_charge",
        translation_key="base_charge",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("base_krw"),
    ),
    KepcoSensorEntityDescription(
        key="energy_charge",
        translation_key="energy_charge",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("energy_krw"),
    ),
    KepcoSensorEntityDescription(
        key="climate_environment_charge",
        translation_key="climate_environment_charge",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("climate_krw"),
    ),
    KepcoSensorEntityDescription(
        key="fuel_adjustment_charge",
        translation_key="fuel_adjustment_charge",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("fuel_krw"),
    ),
    KepcoSensorEntityDescription(
        key="child_discount",
        translation_key="child_discount",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("child_discount_krw"),
    ),
    KepcoSensorEntityDescription(
        key="vat",
        translation_key="vat",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("vat_krw"),
    ),
    KepcoSensorEntityDescription(
        key="power_industry_fund",
        translation_key="power_industry_fund",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("fund_krw"),
    ),
    KepcoSensorEntityDescription(
        key="rounding_amount",
        translation_key="rounding_amount",
        native_unit_of_measurement="KRW",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=_charge("rounding_krw"),
    ),
)

CO2_SENSOR_DESCRIPTION = KepcoSensorEntityDescription(
    key="co2_estimate",
    translation_key="co2_estimate",
    native_unit_of_measurement="kg",
    value_fn=_co2_estimate,
)


def _description_with_enabled_default(
    description: KepcoSensorEntityDescription,
    enabled_default: bool,
) -> KepcoSensorEntityDescription:
    return KepcoSensorEntityDescription(
        key=description.key,
        translation_key=description.translation_key,
        native_unit_of_measurement=description.native_unit_of_measurement,
        device_class=description.device_class,
        state_class=description.state_class,
        entity_registry_enabled_default=enabled_default,
        value_fn=description.value_fn,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KepcoOnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEPCO ON bill sensors."""
    coordinator = entry.runtime_data.coordinator
    customers = coordinator.data.customers
    await _async_remove_stale_registry_entries(hass, entry, customers)
    detailed_enabled = bool(entry.options.get(OPT_ENABLE_DETAILED_SENSORS, False))
    options = dict(entry.options)

    entities: list[KepcoOnSensor] = []
    for customer in customers:
        for description in DEFAULT_SENSOR_DESCRIPTIONS:
            entities.append(KepcoOnSensor(coordinator, customer, description, options))
        for description in DETAIL_SENSOR_DESCRIPTIONS:
            entities.append(
                KepcoOnSensor(
                    coordinator,
                    customer,
                    _description_with_enabled_default(description, detailed_enabled),
                    options,
                )
            )
        if entry.options.get(OPT_ENABLE_CO2_ESTIMATE, False):
            entities.append(KepcoOnSensor(coordinator, customer, CO2_SENSOR_DESCRIPTION, options))

    async_add_entities(entities)


class KepcoOnSensor(CoordinatorEntity[KepcoOnDataUpdateCoordinator], SensorEntity):
    """Sensor backed by one selected customer's coordinator bill snapshot."""

    _attr_has_entity_name = True
    entity_description: KepcoSensorEntityDescription

    def __init__(
        self,
        coordinator: KepcoOnDataUpdateCoordinator,
        customer: KepcoCustomer,
        description: KepcoSensorEntityDescription,
        options: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.customer = customer
        self.entity_description = description
        self._options = options
        self._attr_unique_id = f"{customer.stable_key}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, customer.stable_key)},
            "manufacturer": "한국전력공사(KEPCO)",
            "model": "한전ON 아파트 세대요금",
            "configuration_url": PAGE_URL,
        }

    @property
    def available(self) -> bool:
        """Return if the customer bill is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        return (
            self.customer.stable_key in data.bills_by_customer_key
            and self.customer.stable_key not in data.errors_by_customer_key
        )

    @property
    def native_value(self) -> KepcoSensorValue:
        """Return the current native sensor value."""
        bill = self.coordinator.data.bills_by_customer_key.get(self.customer.stable_key)
        if bill is None or self.customer.stable_key in self.coordinator.data.errors_by_customer_key:
            return None
        return self.entity_description.value_fn(bill, self._options)

    @property
    def extra_state_attributes(self) -> dict[str, str | date]:
        """Return non-sensitive billing context attributes."""
        bill = self.coordinator.data.bills_by_customer_key.get(self.customer.stable_key)
        if bill is None:
            return {}
        attributes: dict[str, str | date] = {"billing_month": bill.bill_month}
        if bill.period_start is not None:
            attributes["usage_period_start"] = bill.period_start
        if bill.period_end is not None:
            attributes["usage_period_end"] = bill.period_end
        return attributes


async def _async_remove_stale_registry_entries(
    hass: HomeAssistant,
    entry: KepcoOnConfigEntry,
    customers: Iterable[KepcoCustomer],
) -> None:
    """Remove stale entities/devices for customers no longer selected."""
    selected_keys = {customer.stable_key for customer in customers}
    entity_registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if registry_entry.platform != DOMAIN:
            continue
        customer_key = _customer_key_from_unique_id(registry_entry.unique_id)
        if customer_key is None or customer_key in selected_keys:
            continue
        entity_registry.async_remove(registry_entry.entity_id)

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        customer_key = _customer_key_from_device_identifiers(device_entry.identifiers)
        if customer_key is None or customer_key in selected_keys:
            continue
        if set(device_entry.config_entries) == {entry.entry_id}:
            device_registry.async_remove_device(device_entry.id)


def _customer_key_from_unique_id(unique_id: str) -> str | None:
    for description in (
        *DEFAULT_SENSOR_DESCRIPTIONS,
        *DETAIL_SENSOR_DESCRIPTIONS,
        CO2_SENSOR_DESCRIPTION,
    ):
        suffix = f"_{description.key}"
        if unique_id.endswith(suffix):
            return unique_id[: -len(suffix)]
    return None


def _customer_key_from_device_identifiers(identifiers: set[tuple[str, str]]) -> str | None:
    for domain, identifier in identifiers:
        if domain == DOMAIN:
            return identifier
    return None


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: KepcoOnConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Return whether Home Assistant may remove a stale KEPCO ON device."""
    del hass
    selected_keys = {
        customer.stable_key for customer in config_entry.runtime_data.coordinator.data.customers
    }
    customer_key = _customer_key_from_device_identifiers(device_entry.identifiers)
    return customer_key not in selected_keys


__all__ = ["async_remove_config_entry_device", "async_setup_entry"]
