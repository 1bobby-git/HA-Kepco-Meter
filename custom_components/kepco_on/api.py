"""KEPCO ON transport and business API client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol, cast

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    ENDPOINT_APT_BILL_DETAIL,
    ENDPOINT_CUST_NO_LIST,
    ENDPOINT_IS_CORP,
    ENDPOINT_LOGIN_INDI,
    ENDPOINT_MYPAGE_CUST_NO_LIST,
    ENDPOINT_SESSION_CHECK,
    ENDPOINT_SSO_CHECK,
    PAGE_URL,
)
from .exceptions import (
    KepcoOnConnectionError,
    KepcoOnProtocolError,
    KepcoOnRateLimitError,
    KepcoOnSessionExpired,
    KepcoOnUnsupportedAccount,
)
from .models import KepcoBill, KepcoCustomer
from .parser import parse_bill, parse_customers, parse_year_month

JsonObject = dict[str, object]
SleepCallback = Callable[[float], Awaitable[None]]
ClockCallback = Callable[[], datetime]

ONLINE_HOST = "online.kepco.co.kr"
ORIGIN = "https://online.kepco.co.kr/"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TRANSIENT_STATUSES = frozenset({500, 502, 503})
MAX_RETRY_AFTER_SECONDS = 30.0
ALLOWED_PATHS = frozenset(
    {
        ENDPOINT_LOGIN_INDI,
        ENDPOINT_SESSION_CHECK,
        ENDPOINT_SSO_CHECK,
        ENDPOINT_IS_CORP,
        ENDPOINT_MYPAGE_CUST_NO_LIST,
        ENDPOINT_CUST_NO_LIST,
        ENDPOINT_APT_BILL_DETAIL,
    }
)


class KepcoAuthProvider(Protocol):
    """Private client/auth collaboration surface."""

    async def async_protected_request(
        self,
        path: str,
        payload: JsonObject | None,
        *,
        submission_id: str | None = None,
    ) -> JsonObject:
        """Run an authenticated KEPCO ON JSON request."""

    def account_uid_hash(self) -> str:
        """Return a stable one-way account identifier for customer keys."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _TemporaryHttpError(Exception):
    """Internal retry signal for transient KEPCO HTTP failures."""


def _safe_protocol_error(reason: str) -> KepcoOnProtocolError:
    return KepcoOnProtocolError(f"Unexpected KEPCO ON response: {reason}")


def _is_json_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return lowered == "application/json" or lowered.endswith("+json")


def _looks_like_login_markup(body: bytes) -> bool:
    prefix = body[:4096].decode("utf-8", errors="ignore").lower()
    return "<html" in prefix and ("login" in prefix or "로그인" in prefix)


def _parse_retry_after(value: str | None, clock: ClockCallback) -> float:
    if value is None:
        return 0.0
    stripped = value.strip()
    if stripped.isdigit():
        return min(float(int(stripped)), MAX_RETRY_AFTER_SECONDS)
    try:
        parsed = parsedate_to_datetime(stripped)
    except TypeError, ValueError:
        return 0.0
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)
    seconds = max(0.0, (parsed.astimezone(UTC) - clock().astimezone(UTC)).total_seconds())
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


async def _default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


class KepcoOnTransport:
    """Focused HTTP transport for the fixed KEPCO ON origin."""

    def __init__(
        self,
        session: ClientSession,
        *,
        sleep: SleepCallback = _default_sleep,
    ) -> None:
        self._session = session
        self._sleep = sleep

    async def async_prepare_login_session(self) -> None:
        """Load the fixed KEPCO page that establishes browser-session cookies."""
        try:
            async with self._session.get(
                PAGE_URL,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": ORIGIN,
                },
                timeout=ClientTimeout(total=30),
                allow_redirects=False,
            ) as response:
                if response.url.scheme != "https" or response.url.host != ONLINE_HOST:
                    raise _safe_protocol_error("login bootstrap host changed")
                if response.status != 200:
                    raise KepcoOnConnectionError("Could not initialize KEPCO ON login session")
                body = await response.content.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise _safe_protocol_error("login bootstrap response was too large")
        except KepcoOnConnectionError, KepcoOnProtocolError:
            raise
        except (TimeoutError, ClientError) as err:
            raise KepcoOnConnectionError("Could not initialize KEPCO ON login session") from err

    async def request_json(
        self,
        path: str,
        payload: JsonObject | None,
        *,
        refresh_token: str | None = None,
        submission_id: str | None = None,
        clock: ClockCallback = _utc_now,
    ) -> JsonObject:
        """POST JSON to an allowlisted KEPCO ON path and return a JSON object."""
        if path not in ALLOWED_PATHS:
            raise _safe_protocol_error("path is not allowlisted")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": PAGE_URL,
            "Origin": ORIGIN,
        }
        if refresh_token is not None:
            headers["refreshToken"] = refresh_token
        if submission_id is not None:
            headers["submissionid"] = submission_id

        for attempt in range(3):
            try:
                async with self._session.post(
                    f"{BASE_URL}{path}",
                    json=payload,
                    headers=headers,
                    timeout=ClientTimeout(total=30),
                    allow_redirects=False,
                ) as response:
                    return await self._handle_response(response, clock)
            except _TemporaryHttpError as err:
                if attempt == 2:
                    raise KepcoOnConnectionError(
                        "KEPCO ON returned a temporary HTTP error"
                    ) from err
                await self._sleep(float(2**attempt))
            except KepcoOnConnectionError:
                raise
            except KepcoOnSessionExpired:
                raise
            except KepcoOnProtocolError:
                raise
            except (TimeoutError, ClientError) as err:
                if attempt == 2:
                    raise KepcoOnConnectionError("Could not reach KEPCO ON") from err
                await self._sleep(float(2**attempt))

        raise KepcoOnConnectionError("Could not reach KEPCO ON")

    async def _handle_response(self, response: ClientResponse, clock: ClockCallback) -> JsonObject:
        if response.url.scheme != "https" or response.url.host != ONLINE_HOST:
            raise _safe_protocol_error("response host changed")

        if 300 <= response.status < 400:
            response.release()
            raise _safe_protocol_error("redirects are not allowed")
        if response.status in TRANSIENT_STATUSES:
            await response.content.read(MAX_RESPONSE_BYTES + 1)
            response.release()
            raise _TemporaryHttpError
        if response.status == 429:
            await self._sleep(_parse_retry_after(response.headers.get("Retry-After"), clock))
            raise KepcoOnRateLimitError("KEPCO ON rate limit was reached")
        if response.status in (401, 403):
            raise KepcoOnSessionExpired("KEPCO ON session expired")
        if response.status == 204:
            return {}
        if response.status >= 400:
            raise KepcoOnConnectionError("KEPCO ON returned an HTTP error")

        body = await response.content.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise _safe_protocol_error("response is too large")
        if _looks_like_login_markup(body):
            raise KepcoOnSessionExpired("KEPCO ON session expired")
        if not body.strip():
            return {}

        content_type = response.content_type
        stripped = body.lstrip()
        if not _is_json_content_type(content_type) and not stripped.startswith((b"{", b"[")):
            raise _safe_protocol_error("response is not JSON")
        parsed: object | None
        try:
            parsed = json.loads(body.decode(response.charset or "utf-8"))
        except UnicodeDecodeError:
            parsed = None
        except json.JSONDecodeError:
            parsed = None
        if parsed is None:
            raise _safe_protocol_error("response JSON is invalid")
        if not isinstance(parsed, dict):
            raise _safe_protocol_error("response JSON root is not an object")
        return cast("JsonObject", parsed)


class KepcoOnClient:
    """Business API wrapper for supported KEPCO ON individual accounts."""

    def __init__(
        self,
        auth: KepcoAuthProvider,
        *,
        clock: ClockCallback = dt_util.now,
    ) -> None:
        self._auth = auth
        self._clock = clock

    async def async_get_account_type(self) -> str:
        """Return the account type if it is a supported individual account."""
        payload = await self._auth.async_protected_request(ENDPOINT_IS_CORP, None)
        account_type = payload.get("userClNm")
        if account_type != "INDI":
            raise KepcoOnUnsupportedAccount("Only KEPCO ON individual accounts are supported")
        return "INDI"

    async def async_get_customers(self) -> tuple[KepcoCustomer, ...]:
        """Return supported apartment customers for the current account."""
        payload = await self._auth.async_protected_request(
            ENDPOINT_MYPAGE_CUST_NO_LIST,
            {
                "dma_search": {
                    "schYm": "",
                    "custNo": "",
                    "gubun": "",
                    "schChart": "12",
                    "CUST_NO": "",
                    "housCntrNo": "",
                    "yyyymm": "",
                    "searchType": "",
                    "dong": "",
                    "ho": "",
                    "months": "",
                    "chgYmd": "",
                }
            },
            submission_id="mf_wfm_layout_sbm_myPageCustList",
        )
        return parse_customers(payload, self._auth.account_uid_hash())

    async def async_get_bill(self, customer: KepcoCustomer, month: str | None = None) -> KepcoBill:
        """Return latest or requested-month bill detail for a customer."""
        requested_month = self._validated_month(month)
        payload = await self._auth.async_protected_request(
            ENDPOINT_APT_BILL_DETAIL,
            {
                "dma_search": {
                    "custNo": customer.customer_number,
                    "housCntrNo": customer.house_contract_number,
                    "yymm": requested_month or "",
                    "yyyymm": requested_month or "",
                    "searchType": "DETAIL",
                }
            },
            submission_id="mf_wfm_layout_sbm_search",
        )
        return parse_bill(payload, requested_month)

    async def async_get_all_current_bills(
        self, customers: Sequence[KepcoCustomer]
    ) -> Mapping[str, KepcoBill]:
        """Fetch current bills sequentially for all selected customers."""
        bills: dict[str, KepcoBill] = {}
        for customer in customers:
            bills[customer.stable_key] = await self.async_get_bill(customer)
        return bills

    def _validated_month(self, month: str | None) -> str | None:
        if month is None:
            return None
        parsed = parse_year_month(month, "month")
        if parsed is None:
            return None
        now = self._clock()
        current_month = f"{now.year}{now.month:02d}"
        if parsed > current_month:
            raise KepcoOnProtocolError("month must not be in the future")
        if parsed < "200001":
            raise KepcoOnProtocolError("month is outside supported range")
        return parsed


__all__ = ["MAX_RETRY_AFTER_SECONDS", "KepcoOnClient", "KepcoOnTransport"]
