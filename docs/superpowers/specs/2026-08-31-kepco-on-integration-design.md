# KEPCO ON Home Assistant Integration Design

Date: 2026-08-31
Status: Approved by the user-provided governing directive
Domain: `kepco_on`
Display name: 한전ON / KEPCO ON

## Goal and scope

Build an installable Home Assistant custom integration for KEPCO ON personal
accounts (`INDI`) with apartment single-contract household billing. Users must
be able to authenticate in the Home Assistant UI, select one or more households,
poll billing data, use reauthentication and reconfiguration flows, retrieve
historical bills through response actions, download redacted diagnostics, and
unload or remove the integration cleanly.

The first release exposes inspection and billing data, not real-time smart-meter
telemetry. Corporate accounts, electrical-contractor accounts, browser-only
certificate login, OACX simple authentication, and Power Planner real-time data
are out of scope.

## Evidence baseline

The design is grounded in these sources:

- `kepco-on-endpoints.txt`, SHA-256
  `9ab036e15bd80e018a923cf9ca9250067cf3b2a911248d88ad2a8fdff940558b`.
- `kepco-on-wire.safe.jsonl`, SHA-256
  `cdd9f5f7443781e2986484cd030e5b95d9d89ae764a5ee2e759d144c2459620a`.
- KEPCO ON public WebSquare definitions fetched on 2026-08-31:
  `MEM001D01.xml`, `MYM001D00.xml`, `commonAPI.js`, `commonGlobal.js`,
  `commonScope.js`, and `commonUtil.js`.
- Home Assistant developer documentation current on 2026-08-31 for manifests,
  typed config-entry runtime data, config/options/reauth/reconfigure flows,
  data coordinators, action response data, diagnostics, repairs, and sensors.

The safe wire capture remains outside Git. Only minimized, synthetic fixtures
derived from its non-identifying response structure and regression numbers may
be committed.

## Confirmed KEPCO protocol

ID/password login posts JSON to `/cyb/me/login/indi/api` with the data-map fields
`userId`, `pwdVal`, and `autoFlag`. The client trims `userId`, binds the entered
password directly to `pwdVal`, and defaults `autoFlag` to `"N"`. No password
encryption, CAPTCHA, MFA, or OACX field is added by the public ID-login path.
OACX is a separate optional login path and will not be reproduced.

The login response map contains `result`, `errorCode`, `errorMessage`, `token`,
`refreshToken`, `userId`, `mbrsNm`, `movePage`, `serviceMode`, `pwdUpdFlag`,
`frstLoginTF`, and `pwdUp`. `result == "NO"` is authentication failure. A
successful login provides the values required by `/sessionCheck` and protected
XHRs. `/me/login/firstLogin/check` reuses the same login data map, but it is not
required for billing and will not be called unless live verification proves it
is necessary.

For apartment/officetel rows, KEPCO's page maps list response fields as follows:

- `CUST_NO` becomes bill request `custNo`.
- `SI_CUST_NO` becomes bill request `housCntrNo`.

Protected requests use the `refreshToken` header and the account's isolated
cookie jar. The client will reproduce only proven headers and will not copy
browser fingerprint headers.

The bill endpoint is `/my/charge/pay/aptBillDetail`. Latest-month requests send
empty `yymm` and `yyyymm`; historical requests send the same validated `YYYYMM`
in both fields. `rsMsg.statusCode == "S"` is the primary application-success
condition. `DO_ERR_CODE == "HXI001"` is accepted when the status is successful.
When a month was requested, that month is the effective billing month even if
the server repeats a different `DO_BILL_YM`.

## Architecture

The integration uses these boundaries:

- `KepcoOnAuth`: login, session restore and validation, one-shot relogin,
  cookie snapshot import/export, token rotation, and auth concurrency control.
- `KepcoOnClient`: allowlisted JSON requests, retry/rate-limit handling,
  account type, customer list, current bill, and historical bill operations.
- `KepcoOnSessionStore`: versioned Home Assistant `Store` persistence for the
  minimum rotating session state.
- Typed immutable models and parsers: normalize KEPCO dictionaries once and
  prevent entities from reading raw payloads.
- `KepcoOnDataUpdateCoordinator`: one poll per entry, sequential household
  retrieval, partial-customer failure isolation, and reauth signaling.
- Config flow: login and customer selection; options flow for polling and
  optional sensors; reauth for credentials; reconfigure for required customer
  bindings.
- Sensor platform: one device per selected household with hashed identifiers
  and declaration-driven entities.
- Integration actions: `get_monthly_bill` and `get_usage_history`, registered
  with response data and strict customer/month validation.
- Diagnostics and repairs: safe summaries only, never raw KEPCO payloads.

Each config entry owns a dedicated `aiohttp.ClientSession` and `CookieJar` so
accounts cannot share cookies. Runtime objects are stored in typed
`ConfigEntry.runtime_data`. The session is closed during unload.

## Authentication and persistence

Config-entry data stores the normalized username, the optional password only
when the user enables password storage, the account hash, selected synthetic
customer keys, and the minimum API identifiers required for selected customers.
The account and customer hashes use SHA-256 domain-separated inputs; raw KEPCO
identifiers are never used as Home Assistant unique IDs.

The versioned session store contains the refresh token, optional token, minimum
session identity fields required by `/sessionCheck`, and an allowlisted cookie
snapshot. Candidate cookies are persisted only after live session-recovery
evidence. Expired cookies and cookies outside KEPCO domains are rejected.

Startup restores and validates a session. If invalid and a saved password is
available, authentication is attempted once under an async lock. Without a
saved password, Home Assistant raises `ConfigEntryAuthFailed` and starts reauth.
Each protected request may trigger at most one relogin and one replay.

## Data and entity model

The parser produces a `KepcoBill` with dates, effective and server billing
months, meter readings, usage comparisons, charge breakdown, ordered history,
and protocol warnings. Numbers accept integers or comma-formatted integer
strings while preserving negative discounts. Empty strings, JSON null, and the
literal `"null"` normalize to `None`. Invalid non-empty numbers and dates are
protocol errors.

Default-enabled sensors are monthly usage, cumulative meter reading, amount due,
previous-month usage, previous-year usage, building average, and apartment
average. Only the cumulative meter-reading sensor uses `total_increasing`.
Monthly comparison and billing values have no state class. Detailed charge,
date, and previous-meter sensors are disabled by default. The derived CO2 sensor
exists only when enabled and is explicitly labeled as a user-configured estimate.

Entity attributes are limited to billing month and usage-period dates. History
is returned by actions rather than copied into every entity's recorder state.

## Network and error handling

Only constant KEPCO paths may be requested. Requests have a 30-second total
timeout, a response-size limit, strict JSON/login-HTML detection, and final-host
validation. HTTP 401/403 or proven login content means session expiry. HTTP 429
raises a rate-limit error and honors `Retry-After`. HTTP 500/502/503 receives at
most two bounded exponential-backoff retries. Other network failures are wrapped
without sensitive values.

Temporary connection failures map to `ConfigEntryNotReady` or coordinator
`UpdateFailed`; invalid authentication maps to `ConfigEntryAuthFailed`; account
types other than `INDI` are rejected in the flow. A per-customer failure leaves
successful household data available and marks only the failed household's
entities unavailable.

## Security and privacy

The integration never disables TLS verification, accepts a user-supplied host,
logs request or response bodies, or embeds browser automation. Passwords,
tokens, cookies, customer and contract numbers, names, addresses, phones, and
emails are excluded from logs, diagnostics, entity states, attributes, device
identifiers, and fixture data.

Diagnostics contain integration and Home Assistant versions, interval, selected
customer count, account type, timestamps, status categories, parsed field names,
and entity availability. Redaction is recursive and covered by secret-canary
tests. Protocol repairs are deduplicated and contain only translated safe error
categories.

## Verification strategy

Development follows test-first slices. Parser fixtures cover the captured
latest bill and the `202607` requested-month discrepancy. API tests cover JSON
validation, auth expiry, one-shot replay, rate limits, bounded retries, token
rotation, and auth locking. Flow tests cover login, customer selection,
duplicates, error recovery, options, reauth, and reconfigure. Coordinator and
entity tests cover partial failures, unload, intervals, device/entity hashes,
classes, units, and defaults. Diagnostics tests use explicit leak canaries.

Before release, run pytest with coverage, Ruff lint and format checks, strict
typing, translation JSON validation, HACS validation, the applicable Hassfest
checks, repository secret scans, and a package-content audit.

## Live deployment and acceptance

Deployment targets the user's existing HAOS instance only after its current
version, VM/host path, and config directory are re-verified. Back up any existing
`custom_components/kepco_on` directory outside `custom_components`, copy the
verified integration, run Home Assistant configuration checks, restart, and
confirm the integration loads without errors.

Completion requires UI flow setup, correct household devices and sensors,
latest and historical data, unload/reload, restart session recovery, reauth
behavior, and redacted diagnostics. Live credential-dependent checks use the
user's existing authorized browser/HA environment without exposing credentials.
If a server-side conditional CAPTCHA, MFA, or bot gate appears, the integration
must surface that limitation and must not bypass it.

