# KEPCO ON Neighbor Comparison and Unit Design

Date: 2026-09-01  
Status: Approved design, pending implementation  
Domain: `kepco_on`

## Goal

Add one Home Assistant sensor that mirrors KEPCO ON's official “이웃 전기사용량 비교” chart while preserving the existing billing sensors. Align usage, greenhouse-gas, and monetary units with the user's requested presentation and Home Assistant's unit contracts.

## Protocol evidence

The public KEPCO ON apartment bill definition at `/ui/my/charge/MYM053D50.xml` defines the comparison chart from three captured bill fields:

- Customer usage: `DO_KWH`
- Same-building household average: `DO_APT_HOUS_USKI_AVG`
- Whole-apartment average: `DO_APT_TOT_USKI_AVG`

The same definition labels the chart “이웃 전기사용량 비교” and its unit `kWh`. No new endpoint or speculative field is needed.

## Entity design

Create a default-enabled sensor description with key `neighbor_usage_comparison`.

- Name: `이웃 전기사용량 비교` / `Neighbor electricity usage comparison`
- Native state: the selected household's current monthly usage from `KepcoBill.usage_kwh`
- Native unit: `kWh`
- Device class: `energy`
- State class: none, because this is a monthly comparison value rather than a cumulative meter
- Extra attributes:
  - `same_building_average_kwh`: `KepcoBill.building_average_kwh`
  - `apartment_average_kwh`: `KepcoBill.apartment_average_kwh`

The attributes contain parsed integers or `None`; they never contain raw customer numbers, contract numbers, names, addresses, tokens, cookies, or response bodies.

The existing `monthly_usage`, `building_average_usage`, and `apartment_average_usage` sensors remain for backward compatibility. The new entity groups their meaning under the official KEPCO chart name without changing existing unique IDs.

## Unit policy

- Meter readings and all electricity-usage or comparison values use `UnitOfEnergy.KILO_WATT_HOUR` (`kWh`).
- The greenhouse-gas estimate uses the custom display unit `kg CO₂`. It remains an energy-derived estimate without `SensorDeviceClass.CO2`, because Home Assistant's CO₂ device class represents concentration in `ppm`, not emitted mass.
- Monetary sensors retain the ISO 4217 native unit `KRW` and `SensorDeviceClass.MONETARY`. Home Assistant localizes this to the won symbol (`₩`) in the Korean UI; using the literal unit `원` would violate the monetary device-class contract.

## Data flow

The coordinator continues to fetch and parse one bill per selected household. The new sensor reads only the existing typed `KepcoBill`; it does not add network calls, polling, storage, authentication state, or parser fallbacks.

The sensor's native state and attributes update together whenever the coordinator refreshes. If a source field is missing, only the corresponding value is `None`; other comparison values remain available.

## Options and migration

The comparison sensor is default enabled for new and existing entries. Existing entity registry identifiers are unchanged. The current “상세 센서 사용” and CO₂ options continue to control only their existing entity groups.

## Verification

Add regression coverage that proves:

- the new sensor exists once per selected household and is enabled by default;
- its state is customer monthly usage and its two attributes are the captured building/apartment averages;
- all three values are integers or `None` and use `kWh` semantics;
- the CO₂ unit is exactly `kg CO₂` and its current rounding behavior remains unchanged;
- every monetary description keeps `KRW` with the monetary device class;
- no existing unique ID or default sensor is removed;
- translation files and scaffold metadata remain aligned;
- full pytest coverage, Ruff, mypy, HACS validation, Hassfest, Node schema tests, and npm audit pass.

## Release

Ship the implementation in the next patch release. The manifest, Python project version, tag, GitHub Release, and release ZIP filename must match. HAOS must receive the exact release commit, pass config check, restart, and show the new comparison sensor plus `kg CO₂` display before completion is claimed.
