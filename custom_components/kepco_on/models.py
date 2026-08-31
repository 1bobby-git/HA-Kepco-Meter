"""Typed immutable models for KEPCO ON parsed data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class KepcoCookie:
    """A persisted KEPCO ON cookie candidate."""

    name: str
    value: str = field(repr=False)
    domain: str = "online.kepco.co.kr"
    path: str = "/"
    secure: bool = True
    expires: int | None = None


@dataclass(frozen=True, slots=True)
class KepcoAccountSession:
    """Authenticated account session state safe for coordinator use."""

    refresh_token: str = field(repr=False)
    user_id: str = field(repr=False)
    member_name: str = field(repr=False)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    token: str | None = field(default=None, repr=False)
    user_mng_seqno: str | None = field(default=None, repr=False)
    cookies: tuple[KepcoCookie, ...] = ()

    def __post_init__(self) -> None:
        updated_at = self.updated_at
        if updated_at.tzinfo is None or updated_at.utcoffset() is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        object.__setattr__(self, "updated_at", updated_at.astimezone(UTC))
        object.__setattr__(self, "cookies", tuple(self.cookies))


@dataclass(frozen=True, slots=True)
class KepcoCustomer:
    """A selectable KEPCO apartment contract."""

    stable_key: str
    apartment_name: str
    dong: str
    ho: str
    contract_method: str
    is_supported: bool
    _customer_number: str = field(repr=False)
    _house_contract_number: str = field(repr=False)

    @property
    def customer_number(self) -> str:
        """Return the bill request customer number."""
        return self._customer_number

    @property
    def house_contract_number(self) -> str:
        """Return the apartment house contract number."""
        return self._house_contract_number


@dataclass(frozen=True, slots=True)
class KepcoUsageHistoryPoint:
    """One monthly usage/amount history point."""

    month: str
    usage_kwh: int | None = None
    amount_krw: int | None = None


@dataclass(frozen=True, slots=True)
class KepcoChargeBreakdown:
    """Bill charge components."""

    subtotal_krw: int | None = None
    base_krw: int | None = None
    energy_krw: int | None = None
    climate_krw: int | None = None
    fuel_krw: int | None = None
    child_discount_krw: int | None = None
    vat_krw: int | None = None
    fund_krw: int | None = None
    rounding_krw: int | None = None


@dataclass(frozen=True, slots=True)
class KepcoBill:
    """Parsed monthly apartment bill."""

    bill_month: str
    response_bill_month: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    usage_kwh: int | None = None
    previous_usage_kwh: int | None = None
    last_year_usage_kwh: int | None = None
    building_average_kwh: int | None = None
    apartment_average_kwh: int | None = None
    current_meter_reading: int | None = None
    previous_meter_reading: int | None = None
    amount_krw: int | None = None
    charge: KepcoChargeBreakdown = field(default_factory=KepcoChargeBreakdown)
    history: tuple[KepcoUsageHistoryPoint, ...] = ()


@dataclass(frozen=True, slots=True)
class KepcoCustomerUpdateResult:
    """Latest update result for one customer."""

    customer: KepcoCustomer
    bill: KepcoBill | None
    error: Exception | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class KepcoCoordinatorData:
    """Coordinator snapshot consumed by entities."""

    customers: tuple[KepcoCustomer, ...]
    bills_by_customer_key: Mapping[str, KepcoBill] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "bills_by_customer_key",
            MappingProxyType(dict(self.bills_by_customer_key)),
        )


__all__ = [
    "KepcoAccountSession",
    "KepcoBill",
    "KepcoChargeBreakdown",
    "KepcoCookie",
    "KepcoCoordinatorData",
    "KepcoCustomer",
    "KepcoCustomerUpdateResult",
    "KepcoUsageHistoryPoint",
]
