"""Strict parsers for sanitized KEPCO ON response payloads."""

from __future__ import annotations

import re
from datetime import date
from hashlib import sha256

from .exceptions import KepcoOnNoCustomersError, KepcoOnProtocolError
from .models import (
    KepcoBill,
    KepcoChargeBreakdown,
    KepcoCustomer,
    KepcoUsageHistoryPoint,
)

SUPPORTED_APARTMENT_CONTRACT = "아파트(단일계약)"
ASCII_INTEGER_PATTERN = re.compile(r"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)")
ASCII_DATE_PATTERN = re.compile(r"[0-9]{8}")
ASCII_YEAR_MONTH_PATTERN = re.compile(r"[0-9]{6}")


def parse_int(value: object, field_name: str) -> int | None:
    """Parse KEPCO integer fields while preserving negative discounts."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise KepcoOnProtocolError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "" or normalized.lower() == "null":
            return None
        if not ASCII_INTEGER_PATTERN.fullmatch(normalized):
            raise KepcoOnProtocolError(f"{field_name} must be an integer")
        normalized = normalized.replace(",", "")
        try:
            return int(normalized)
        except ValueError as err:
            raise KepcoOnProtocolError(f"{field_name} must be an integer") from err
    raise KepcoOnProtocolError(f"{field_name} must be an integer")


def parse_date(value: object, field_name: str) -> date | None:
    """Parse strict YYYYMMDD dates."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise KepcoOnProtocolError(f"{field_name} must be a YYYYMMDD string")
    normalized = value.strip()
    if normalized == "" or normalized.lower() == "null":
        return None
    if not ASCII_DATE_PATTERN.fullmatch(normalized):
        raise KepcoOnProtocolError(f"{field_name} must be a YYYYMMDD string")
    try:
        return date(int(normalized[0:4]), int(normalized[4:6]), int(normalized[6:8]))
    except ValueError as err:
        raise KepcoOnProtocolError(f"{field_name} must be a valid date") from err


def parse_year_month(value: object, field_name: str) -> str | None:
    """Parse strict YYYYMM month strings."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise KepcoOnProtocolError(f"{field_name} must be a YYYYMM string")
    normalized = value.strip()
    if normalized == "" or normalized.lower() == "null":
        return None
    if not ASCII_YEAR_MONTH_PATTERN.fullmatch(normalized):
        raise KepcoOnProtocolError(f"{field_name} must be a YYYYMM string")
    month = int(normalized[4:6])
    if month < 1 or month > 12:
        raise KepcoOnProtocolError(f"{field_name} must contain a valid month")
    return normalized


def parse_customers(payload: dict[str, object], account_uid_hash: str) -> tuple[KepcoCustomer, ...]:
    """Parse apartment contracts from either KEPCO customer-list response shape."""
    rows = _customer_rows(payload)
    if not rows:
        raise KepcoOnNoCustomersError("KEPCO ON account has no customer contracts")

    customers: list[KepcoCustomer] = []
    for index, row in enumerate(rows):
        contract_method = _optional_str(row, "cntrMthdCd") or ""
        customer_number = _required_str(row, "CUST_NO")
        house_contract_number = _required_str(row, "SI_CUST_NO")
        stable_key = _stable_customer_key(account_uid_hash, customer_number, house_contract_number)
        customers.append(
            KepcoCustomer(
                stable_key=stable_key,
                apartment_name=_required_any_key(row, ("APT_NAME", "APT_NM")),
                dong=_required_any_key(row, ("APT_DONGNO", "DONG_NO")),
                ho=_required_any_key(row, ("APT_HONO", "HO_NO")),
                contract_method=contract_method,
                is_supported=contract_method == SUPPORTED_APARTMENT_CONTRACT,
                _customer_number=customer_number,
                _house_contract_number=house_contract_number,
            )
        )
        if not customers[index].is_supported:
            raise KepcoOnProtocolError("Only apartment single-contract customers are supported")
    return tuple(customers)


def parse_bill(payload: dict[str, object], requested_month: str | None) -> KepcoBill:
    """Parse a KEPCO apartment bill detail response."""
    result = _result_payload(payload)
    _raise_for_bill_status(payload, result)

    response_bill_month = parse_year_month(
        _first_present(result, payload, "DO_BILL_YM", "BILL_YM", "MR_YM"), "DO_BILL_YM"
    )
    effective_month = (
        parse_year_month(requested_month, "requested_month")
        if requested_month
        else response_bill_month
    )
    if effective_month is None:
        raise KepcoOnProtocolError("bill month is missing")

    history = _parse_history(payload)
    _validate_history_consistency(history, effective_month, response_bill_month)

    return KepcoBill(
        bill_month=effective_month,
        response_bill_month=response_bill_month,
        period_start=parse_date(
            _field(result, payload, "DO_FROM_MMDD", "USE_STRT_YMD"), "period_start"
        ),
        period_end=parse_date(_field(result, payload, "DO_TO_MMDD", "USE_END_YMD"), "period_end"),
        usage_kwh=parse_int(_field(result, payload, "DO_KWH", "USE_QTY"), "usage_kwh"),
        previous_usage_kwh=parse_int(
            _field(result, payload, "DO_BEF_KWH", "BF_USE_QTY"), "previous_usage_kwh"
        ),
        last_year_usage_kwh=parse_int(
            _field(result, payload, "DO_LAST_YEAR_KWH", "BFYY_USE_QTY"), "last_year_usage_kwh"
        ),
        building_average_kwh=parse_int(
            _field(result, payload, "DO_APT_HOUS_USKI_AVG", "BLDG_AVG_USE_QTY"),
            "building_average_kwh",
        ),
        apartment_average_kwh=parse_int(
            _field(result, payload, "DO_APT_TOT_USKI_AVG", "APT_AVG_USE_QTY"),
            "apartment_average_kwh",
        ),
        current_meter_reading=parse_int(
            _field(result, payload, "DO_WHM_MTR_ALW", "PRESENT_MR_VAL"), "current_meter_reading"
        ),
        previous_meter_reading=parse_int(
            _field(result, payload, "DO_BEF_MTR_ALW", "BF_MR_VAL"), "previous_meter_reading"
        ),
        amount_krw=parse_int(_field(result, payload, "DO_PRE_REQ_BILL", "BILL_AMT"), "amount_krw"),
        charge=KepcoChargeBreakdown(
            subtotal_krw=parse_int(_field(result, payload, "DO_PRE_BILL", "ELEC_AMT"), "subtotal"),
            base_krw=parse_int(_field(result, payload, "DO_PRE_BASE_BILL", "BASE_AMT"), "base"),
            energy_krw=parse_int(_field(result, payload, "DO_PRE_KWHBILL", "KWH_AMT"), "energy"),
            climate_krw=parse_int(
                _field(result, payload, "DO_PRE_CLMT_ENVRN_BILL", "CLIMATE_AMT"), "climate"
            ),
            fuel_krw=parse_int(
                _field(result, payload, "DO_PRE_FUEL_COST_ADJ_BILL", "FUEL_AMT"), "fuel"
            ),
            child_discount_krw=parse_int(
                _field(result, payload, "DO_PRE_CHILD_DC_BILL", "CHILD_DC_AMT"), "child_discount"
            ),
            vat_krw=parse_int(_field(result, payload, "DO_PRE_BILL_VAT", "VAT"), "vat"),
            fund_krw=parse_int(_field(result, payload, "DO_PRE_PUBCHGE", "FUND_AMT"), "fund"),
            rounding_krw=parse_int(
                _field(result, payload, "DO_PRE_REQ_BILLODD", "CUT_AMT"), "rounding"
            ),
        ),
        history=history,
    )


def _customer_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    for key in ("dlt_appendList", "dlt_myPageAppendList"):
        rows = payload.get(key)
        if rows is None:
            continue
        if not isinstance(rows, list):
            raise KepcoOnProtocolError(f"{key} must be a list")
        parsed: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise KepcoOnProtocolError(f"{key} entries must be objects")
            parsed.append(row)
        return parsed
    raise KepcoOnProtocolError("customer list is missing")


def _result_payload(payload: dict[str, object]) -> dict[str, object]:
    result = payload.get("dma_result")
    if result is None:
        return payload
    if not isinstance(result, dict):
        raise KepcoOnProtocolError("dma_result must be an object")
    return result


def _raise_for_bill_status(payload: dict[str, object], result: dict[str, object]) -> None:
    rs_msg = payload.get("rsMsg")
    if not isinstance(rs_msg, dict) or rs_msg.get("statusCode") != "S":
        raise KepcoOnProtocolError("KEPCO ON bill status is not successful")


def _parse_history(payload: dict[str, object]) -> tuple[KepcoUsageHistoryPoint, ...]:
    raw_history = payload.get("history")
    if raw_history is None:
        raw_history = payload.get("dlt_chrtList")
    if raw_history is None:
        return ()
    if not isinstance(raw_history, list):
        raise KepcoOnProtocolError("bill history must be a list")

    history: list[KepcoUsageHistoryPoint] = []
    previous_month: str | None = None
    seen: set[str] = set()
    for item in raw_history:
        if not isinstance(item, dict):
            raise KepcoOnProtocolError("bill history entries must be objects")
        month = parse_year_month(
            _first_present(item, {}, "DO_CHRT_REQ_YM", "BILL_YM"), "history_month"
        )
        if month is None:
            raise KepcoOnProtocolError("history month is missing")
        if month in seen:
            raise KepcoOnProtocolError("bill history contains duplicate months")
        if previous_month is not None and month <= previous_month:
            raise KepcoOnProtocolError("bill history must be sorted ascending")
        seen.add(month)
        previous_month = month
        history.append(
            KepcoUsageHistoryPoint(
                month=month,
                usage_kwh=parse_int(
                    _first_present(item, {}, "DO_CHRT_KWH", "USE_QTY"), "history_usage"
                ),
                amount_krw=parse_int(
                    _first_present(item, {}, "DO_CHRT_AFTR_MNY", "BILL_AMT"), "history_amount"
                ),
            )
        )
    return tuple(history)


def _validate_history_consistency(
    history: tuple[KepcoUsageHistoryPoint, ...],
    effective_month: str,
    response_month: str | None,
) -> None:
    if not history:
        return
    last_history_month = history[-1].month
    if (
        response_month
        and response_month != effective_month
        and response_month != _next_month(effective_month)
    ):
        raise KepcoOnProtocolError("bill response month does not match requested month")
    if last_history_month == effective_month:
        return
    raise KepcoOnProtocolError("bill history month range does not match bill month")


def _next_month(month: str) -> str:
    year = int(month[:4])
    month_number = int(month[4:])
    if month_number == 12:
        return f"{year + 1}01"
    return f"{year}{month_number + 1:02d}"


def _stable_customer_key(
    account_uid_hash: str,
    customer_number: str,
    house_contract_number: str,
) -> str:
    return sha256(
        f"kepco_on:customer:v1\0{account_uid_hash}\0{customer_number}\0{house_contract_number}".encode()
    ).hexdigest()


def _required_str(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise KepcoOnProtocolError(f"{key} is missing")
    return value.strip()


def _optional_str(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise KepcoOnProtocolError(f"{key} must be a string")
    value = value.strip()
    return value or None


def _required_any_key(row: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _optional_str(row, key)
        if value is not None:
            return value
    raise KepcoOnProtocolError(f"{'/'.join(keys)} is missing")


def _field(
    primary: dict[str, object],
    fallback: dict[str, object],
    primary_key: str,
    fallback_key: str,
) -> object:
    if primary_key in primary:
        return primary[primary_key]
    return fallback.get(fallback_key)


def _first_present(
    primary: dict[str, object],
    fallback: dict[str, object],
    *keys: str,
) -> object:
    for key in keys:
        if key in primary:
            return primary[key]
        if key in fallback:
            return fallback[key]
    return None


__all__ = [
    "parse_bill",
    "parse_customers",
    "parse_date",
    "parse_int",
    "parse_year_month",
]
