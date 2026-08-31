"""Constants for the KEPCO ON integration."""

from homeassistant.const import CONF_PASSWORD, Platform

DOMAIN = "kepco_on"
NAME = "KEPCO ON"
VERSION = "0.1.0"

BASE_URL = "https://online.kepco.co.kr"
PAGE_URL = "https://online.kepco.co.kr/MYM001D00"

ENDPOINT_LOGIN_INDI = "/cyb/me/login/indi/api"
ENDPOINT_FIRST_LOGIN_CHECK = "/me/login/firstLogin/check"
ENDPOINT_SESSION_CHECK = "/sessionCheck"
ENDPOINT_APT_BILL_DETAIL = "/my/charge/pay/aptBillDetail"

POLLING_INTERVAL_HOURS = (1, 3, 6, 12, 24)
DEFAULT_POLLING_INTERVAL_HOURS = 6

PLATFORMS = (Platform.SENSOR,)

CONF_USERNAME = "username"
CONF_SAVE_PASSWORD = "save_password"
CONF_SELECTED_CUSTOMERS = "selected_customers"

OPT_POLLING_INTERVAL_HOURS = "polling_interval_hours"
OPT_ENABLE_DETAILED_SENSORS = "enable_detailed_sensors"
OPT_ENABLE_CO2_ESTIMATE = "enable_co2_estimate"
OPT_CO2_FACTOR_KG_PER_KWH = "co2_factor_kg_per_kwh"
OPT_HISTORY_MONTHS = "history_months"

CANDIDATE_COOKIE_NAMES: frozenset[str] = frozenset({"JSESSIONID", "kepcoSSO"})
PERSISTED_COOKIE_ALLOWLIST: frozenset[str] = frozenset()

__all__ = [
    "BASE_URL",
    "CANDIDATE_COOKIE_NAMES",
    "CONF_PASSWORD",
    "CONF_SAVE_PASSWORD",
    "CONF_SELECTED_CUSTOMERS",
    "CONF_USERNAME",
    "DEFAULT_POLLING_INTERVAL_HOURS",
    "DOMAIN",
    "ENDPOINT_APT_BILL_DETAIL",
    "ENDPOINT_FIRST_LOGIN_CHECK",
    "ENDPOINT_LOGIN_INDI",
    "ENDPOINT_SESSION_CHECK",
    "NAME",
    "OPT_CO2_FACTOR_KG_PER_KWH",
    "OPT_ENABLE_CO2_ESTIMATE",
    "OPT_ENABLE_DETAILED_SENSORS",
    "OPT_HISTORY_MONTHS",
    "OPT_POLLING_INTERVAL_HOURS",
    "PAGE_URL",
    "PERSISTED_COOKIE_ALLOWLIST",
    "PLATFORMS",
    "POLLING_INTERVAL_HOURS",
    "VERSION",
]
