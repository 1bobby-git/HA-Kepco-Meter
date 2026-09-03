"""Constants for the KEPCO ON integration."""

from homeassistant.const import CONF_PASSWORD, Platform

DOMAIN = "kepco_on"
NAME = "KEPCO ON"
VERSION = "0.3.2"
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
ENDPOINT_MAIN_CHART = "/my/memo/mainChart"
ENDPOINT_POWER_PLANNER = "/my/memo/powerPlanner"

POLLING_INTERVAL_HOURS = (1, 3, 6, 12, 24)
DEFAULT_POLLING_INTERVAL_HOURS = 6
DEFAULT_CO2_FACTOR_KG_PER_KWH = 0.459
DEFAULT_HISTORY_MONTHS = 12
MIN_HISTORY_MONTHS = 1
MAX_HISTORY_MONTHS = 24

CONF_USERNAME = "username"
CONF_SAVE_PASSWORD = "save_password"
CONF_CUSTOMERS = "customers"
CONF_SELECTED_CUSTOMERS = "selected_customers"
CONF_DISPLAY_NAME = "display_name"

OPT_POLLING_INTERVAL_HOURS = "polling_interval_hours"
OPT_ENABLE_DETAILED_SENSORS = "enable_detailed_sensors"
OPT_ENABLE_CO2_ESTIMATE = "enable_co2_estimate"
OPT_CO2_FACTOR_KG_PER_KWH = "co2_factor_kg_per_kwh"
OPT_HISTORY_MONTHS = "history_months"

DATA_STABLE_KEY = "stable_key"
DATA_APARTMENT_NAME = "apartment_name"
DATA_DONG = "dong"
DATA_HO = "ho"
DATA_CONTRACT_METHOD = "contract_method"
DATA_IS_SUPPORTED = "is_supported"
DATA_CUSTOMER_NUMBER = "customer_number"
DATA_HOUSE_CONTRACT_NUMBER = "house_contract_number"

CANDIDATE_COOKIE_NAMES = frozenset({"JSESSIONID", "kepcoSSO"})
PERSISTED_COOKIE_ALLOWLIST = frozenset()

PLATFORMS = (Platform.SENSOR,)
