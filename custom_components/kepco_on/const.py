"""Constants for the KEPCO ON integration."""

from homeassistant.const import CONF_PASSWORD, Platform

DOMAIN = "kepco_on"
NAME = "KEPCO ON"
VERSION = "0.2.4"
CONFIG_ENTRY_VERSION = 3

BASE_URL = "https://online.kepco.co.kr"
PAGE_URL = "https://online.kepco.co.kr/MYM001D00"

ENDPOINT_LOGIN_INDI = "/cyb/me/login/indi/api"
ENDPOINT_FIRST_LOGIN_CHECK = "/me/login/firstLogin/check"
ENDPOINT_SESSION_CHECK = "/sessionCheck"
ENDPOINT_SSO_CHECK = "/ssoCheck"
ENDPOINT_IS_CORP = "/isCorp"
ENDPOINT_MYPAGE_CUST_NO_LIST = "/my/indi/info/myPageCustNoList"
ENDPOINT_CUST_NO_LIST = "/my/indi/info/custNoList"
ENDPOINT_APT_BILL_DETAIL = "/my/charge/pay/aptBillDetail"

POLLING_INTERVAL_HOURS = (1, 3, 6, 12, 24)
DEFAULT_POLLING_INTERVAL_HOURS = 6
DEFAULT_CO2_FACTOR_KG_PER_KWH = 0.459

PLATFORMS = (Platform.SENSOR,)

CONF_USERNAME = "username"
CONF_SAVE_PASSWORD = "save_password"
CONF_SELECTED_CUSTOMERS = "selected_customers"
CONF_ACCOUNT_UID_HASH = "account_uid_hash"
CONF_CUSTOMERS = "customers"
CONF_DISPLAY_NAME = "display_name"
CONF_SESSION_HANDOFF = "session_handoff"
# Task 6 must consume CONF_SESSION_HANDOFF into the private session Store and
# scrub it from entry data; until then HA redaction must treat it as sensitive.
SENSITIVE_CONFIG_DATA_KEYS = frozenset({CONF_PASSWORD, CONF_SESSION_HANDOFF})

DATA_STABLE_KEY = "stable_key"
DATA_APARTMENT_NAME = "apartment_name"
DATA_UNIT_LOCATION = "unit_location"
DATA_SELECTED_CUSTOMER_COUNT = "selected_customer_count"

OPT_POLLING_INTERVAL_HOURS = "polling_interval_hours"
OPT_ENABLE_DETAILED_SENSORS = "enable_detailed_sensors"
OPT_ENABLE_CO2_ESTIMATE = "enable_co2_estimate"
OPT_CO2_FACTOR_KG_PER_KWH = "co2_factor_kg_per_kwh"
OPT_HISTORY_MONTHS = "history_months"

DEFAULT_ENABLE_DETAILED_SENSORS = True
DEFAULT_ENABLE_CO2_ESTIMATE = True
DEFAULT_HISTORY_MONTHS = 13
MIN_HISTORY_MONTHS = 1
MAX_HISTORY_MONTHS = 36

ENTRY_MINOR_VERSION_DISPLAY_NAME = 1
ENTRY_MINOR_VERSION_LOGICAL_DEVICES = 2

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "kepco_on.session"

CANDIDATE_COOKIE_NAMES = frozenset({"JSESSIONID", "kepcoSSO"})
PERSISTED_COOKIE_ALLOWLIST = frozenset()
