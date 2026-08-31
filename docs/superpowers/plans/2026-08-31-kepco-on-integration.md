# KEPCO ON Home Assistant Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, publish, install, configure, and live-verify a privacy-safe Home Assistant `kepco_on` custom integration for KEPCO ON personal apartment accounts.

**Architecture:** A per-config-entry HTTP/auth/session stack parses KEPCO payloads into immutable typed models and feeds one `DataUpdateCoordinator`. Config, options, reauth, and reconfigure flows manage credentials and household selection; sensors and response actions consume only parsed coordinator/client data. Rotating tokens and allowlisted cookies live in a versioned Home Assistant `Store`, while every external identifier used by Home Assistant is a domain-separated hash.

**Tech Stack:** Python 3.14, Home Assistant Core 2026.8 APIs, `aiohttp`, `pytest-homeassistant-custom-component`, `aresponses`, Ruff, mypy, pytest-cov, Hassfest, HACS validation, GitHub Actions, PowerShell/SSH for HAOS VM 100 deployment.

---

## File map

### Integration runtime

- `custom_components/kepco_on/__init__.py`: config-entry setup/unload, runtime-data wiring, action registration lifecycle.
- `custom_components/kepco_on/manifest.json`: Home Assistant integration metadata and version.
- `custom_components/kepco_on/const.py`: domain, endpoints, headers, option keys, intervals, cookie allowlist, platforms.
- `custom_components/kepco_on/exceptions.py`: public exception taxonomy.
- `custom_components/kepco_on/models.py`: immutable session, customer, bill, history, charge, coordinator, and runtime models.
- `custom_components/kepco_on/parser.py`: strict scalar, customer-list, and bill parsing.
- `custom_components/kepco_on/session_store.py`: versioned `Store` and safe cookie serialization.
- `custom_components/kepco_on/auth.py`: login, restore, validate, token rotation, one-shot relogin, auth lock.
- `custom_components/kepco_on/api.py`: allowlisted request transport and KEPCO business operations.
- `custom_components/kepco_on/coordinator.py`: polling, selected-customer reconciliation, and partial failures.
- `custom_components/kepco_on/config_flow.py`: user, customer, options, reauth, and reconfigure flows.
- `custom_components/kepco_on/sensor.py`: device and sensor descriptions/entities.
- `custom_components/kepco_on/services.py`: `get_monthly_bill` and `get_usage_history` response actions.
- `custom_components/kepco_on/services.yaml`: UI action metadata and selectors.
- `custom_components/kepco_on/diagnostics.py`: recursive redacted config-entry diagnostics.
- `custom_components/kepco_on/repairs.py`: deduplicated protocol/auth repair issue helpers.
- `custom_components/kepco_on/strings.json`: canonical English frontend strings.
- `custom_components/kepco_on/translations/en.json`: English translation mirror.
- `custom_components/kepco_on/translations/ko.json`: Korean user-facing translation.

### Tests and fixtures

- `tests/conftest.py`: Home Assistant test setup and reusable entry/client fixtures.
- `tests/fixtures/*.json`: minimized synthetic KEPCO responses with real regression numbers and fake identifiers.
- `tests/test_parser.py`: scalar, customer, bill, history, month, and protocol validation.
- `tests/test_session_store.py`: allowlist, expiry, domain/path, serialization, and clear behavior.
- `tests/test_auth.py`: login schema, success/failure, restore, rotation, lock, and cookie behavior.
- `tests/test_api.py`: request headers, content validation, retry, one-shot reauth, and business calls.
- `tests/test_config_flow.py`: all config/options/reauth/reconfigure branches.
- `tests/test_coordinator.py`: update success, partial failure, interval, auth, and unload behavior.
- `tests/test_sensor.py`: sensor values, metadata, defaults, hashes, and availability.
- `tests/test_services.py`: action schemas, authorization, response shape, and errors.
- `tests/test_diagnostics.py`: nested redaction and leak-canary coverage.
- `tests/test_repairs.py`: issue creation, deduplication, and deletion.

### Project and operations

- `tools/extract-safe-fixtures.py`: deterministic fixture extractor that never writes captured identifiers or secrets.
- `tools/capture-kepco-login-schema.mjs`: optional structure-only Chromium capture for future protocol changes.
- `docs/PROTOCOL.md`: captured/public protocol evidence and unresolved live-only facts.
- `docs/SECURITY.md`: stored data, threat boundaries, safe issue/capture procedure.
- `docs/TESTING.md`: local, CI, live smoke, and HAOS validation commands.
- `README.md`: Korean-first installation, configuration, entities, actions, security, and troubleshooting.
- `.gitignore`, `pyproject.toml`, `requirements_test.txt`, `hacs.json`, `LICENSE`: packaging and development contract.
- `.github/workflows/tests.yml`, `.github/workflows/validate.yml`: required CI gates.

## Task 1: Secure scaffold and deterministic test environment

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `requirements_test.txt`
- Create: `hacs.json`
- Create: `LICENSE`
- Create: `custom_components/kepco_on/manifest.json`
- Create: `custom_components/kepco_on/const.py`
- Create: `custom_components/kepco_on/exceptions.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add the capture and secret denylist**

Write `.gitignore` with the exact sensitive patterns from the governing directive plus Python, coverage, test, Node, and editor artifacts. It must include:

```gitignore
*.jsonl
*.har
*.trace.zip
.kepco-on-capture-profile/
.kepco-on-login-profile/
login-schema*.json
session*.json
cookies*.json
.storage/
secrets.yaml
.env
.env.*
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.venv/
node_modules/
```

- [ ] **Step 2: Define packaging and quality configuration**

Configure `pyproject.toml` for Python `>=3.14`, Ruff line length 100 and Home Assistant-compatible rules, pytest asyncio auto mode, strict mypy, coverage source `custom_components/kepco_on`, and a 95 percent fail-under target. Pin `homeassistant==2026.8.3`, `pytest-homeassistant-custom-component`, `aresponses`, `pytest-cov`, `ruff`, and `mypy` in `requirements_test.txt` to versions that resolve on Python 3.14.

- [ ] **Step 3: Create the minimal manifest and constants**

Set manifest values exactly:

```json
{
  "domain": "kepco_on",
  "name": "KEPCO ON",
  "version": "0.1.0",
  "config_flow": true,
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "requirements": [],
  "codeowners": ["@1bobby-git"],
  "documentation": "https://github.com/1bobby-git/HA-Kepco-Meter",
  "issue_tracker": "https://github.com/1bobby-git/HA-Kepco-Meter/issues"
}
```

Define only fixed KEPCO hosts and paths in `const.py`; define polling choices `{1, 3, 6, 12, 24}` hours and default 6 hours; define `PLATFORMS = (Platform.SENSOR,)`; define the candidate cookie names from the capture but keep the persisted allowlist empty until live recovery proves the minimum set.

- [ ] **Step 4: Install the test environment and verify collection**

Run:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements_test.txt
.venv\Scripts\python.exe -m pytest --collect-only -q
```

Expected: dependencies install without resolver errors and pytest collects the initial test package without importing raw capture files.

- [ ] **Step 5: Commit the scaffold**

Commit only Task 1 files with a Lore message whose intent is “Establish a reproducible and capture-safe integration baseline,” and record the actual collection command under `Tested:`.

## Task 2: Extract synthetic fixtures and implement strict models/parsers

**Files:**
- Create: `tools/extract-safe-fixtures.py`
- Create: `tests/fixtures/session_check_success.json`
- Create: `tests/fixtures/sso_check_success.json`
- Create: `tests/fixtures/customer_list_single.json`
- Create: `tests/fixtures/customer_list_multiple.json`
- Create: `tests/fixtures/bill_latest.json`
- Create: `tests/fixtures/bill_202607.json`
- Create: `custom_components/kepco_on/models.py`
- Create: `custom_components/kepco_on/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write parser failures first**

Add tests asserting:

```python
assert parse_int("96,330", "amount") == 96330
assert parse_int("-16000", "discount") == -16000
assert parse_int(0, "zero") == 0
assert parse_int("", "empty") is None
assert parse_int("null", "null") is None
assert parse_date("20260701", "start") == date(2026, 7, 1)
with pytest.raises(KepcoOnProtocolError):
    parse_date("20260230", "invalid")
```

Add captured regression assertions for all values listed in sections 3.9 and 3.10 of the directive, ascending history order, duplicate-month rejection, negative child discount, successful `HXI001`, and non-`S` status rejection.

- [ ] **Step 2: Run the focused test and confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_parser.py -q`.

Expected: import failure for `custom_components.kepco_on.parser` or missing parser symbols.

- [ ] **Step 3: Implement immutable models and parsers**

Use frozen, slotted dataclasses. Implement these exact typed call surfaces:
`parse_int(value: object, field: str) -> int | None`,
`parse_date(value: object, field: str) -> date | None`,
`parse_year_month(value: object, field: str) -> str | None`,
`parse_customers(payload: Mapping[str, Any]) -> tuple[KepcoCustomer, ...]`, and
`parse_bill(payload: Mapping[str, Any], requested_month: str | None) -> KepcoBill`.

`KepcoCustomer.customer_key` must be a SHA-256 hash over domain, account hash,
`CUST_NO`, and `SI_CUST_NO`; the raw numbers remain private dataclass fields used only by the client. `parse_bill` must select the requested month over `DO_BILL_YM` and must reject a history/month contradiction greater than one billing cycle.

- [ ] **Step 4: Generate and audit fixtures**

The extractor reads the external JSONL path supplied by `--input`, selects only the documented response records, substitutes `TEST_CUST_001`, `TEST_HOUSE_001`, `테스트아파트`, `1001`, and `0101`, removes names/addresses/phones/emails/tokens/cookies, and writes deterministic sorted JSON. It must refuse an output path outside `tests/fixtures` unless `--check` is used.

Run:

```powershell
.venv\Scripts\python.exe tools\extract-safe-fixtures.py --input 'C:\Users\bobby\Desktop\kepco-on-wire.safe.jsonl'
rg -n -i 'refreshToken|JSESSIONID|kepcoSSO|Cookie|ADDR|USER_MTEL|USER_EMAIL|mbrsNm' tests\fixtures
```

Expected: fixture hashes are stable across two runs; the review finds no raw secret or personal values.

- [ ] **Step 5: Run GREEN and commit**

Run `.venv\Scripts\python.exe -m pytest tests/test_parser.py -q` and commit the extractor, fixtures, models, parser, exceptions, and tests with actual pass counts.

## Task 3: Build versioned session persistence and cookie isolation

**Files:**
- Create: `custom_components/kepco_on/session_store.py`
- Create: `tests/test_session_store.py`
- Modify: `custom_components/kepco_on/models.py`

- [ ] **Step 1: Write session-store failures**

Cover no-data load, save/load round trip, schema version, atomic save call, clear, expired-cookie removal, wrong-domain rejection, wrong-path rejection, secure flag preservation, and rejection of cookies outside the proven allowlist. Use fake values `TEST_REFRESH_TOKEN_DO_NOT_LEAK` and `TEST_SESSION_COOKIE_DO_NOT_LEAK` only inside tests.

- [ ] **Step 2: Confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_session_store.py -q` and confirm the store module is missing.

- [ ] **Step 3: Implement the store**

Expose `KepcoOnSessionStore(hass: HomeAssistant, entry_id: str)` with async
methods `async_load() -> KepcoAccountSession | None`,
`async_save(session: KepcoAccountSession) -> None`, and `async_clear() -> None`.
Also expose `export_cookies(jar: CookieJar, allowed_names: frozenset[str]) ->
tuple[KepcoCookie, ...]` and `restore_cookies(jar: CookieJar,
cookies: Iterable[KepcoCookie], now: datetime) -> None`.

Persist with `Store[KepcoSessionPayload](hass, 1, f"kepco_on.{entry_id}")`. Accept domains only `online.kepco.co.kr` or `.kepco.co.kr`, require `/`-rooted paths, omit expired cookies, and never serialize response headers.

- [ ] **Step 4: Run GREEN and commit**

Run the session-store and parser tests together, then commit with the persisted fields and unproven empty cookie allowlist recorded under `Constraint:`.

## Task 4: Implement transport, login, session validation, and business API

**Files:**
- Create: `custom_components/kepco_on/api.py`
- Create: `custom_components/kepco_on/auth.py`
- Create: `tests/test_api.py`
- Create: `tests/test_auth.py`
- Modify: `custom_components/kepco_on/models.py`
- Modify: `custom_components/kepco_on/const.py`

- [ ] **Step 1: Write auth and API failures**

Tests must prove the login request body is exactly:

```python
{"userId": "trimmed-user", "pwdVal": "secret", "autoFlag": "N"}
```

and uses `submissionid: mf_login_popup_wframe_sbm_submission4`. Cover `result == "NO"`, missing tokens, successful session rotation, `sessionCheck.result is False`, `ssoCheck.loginChk != "Y"`, `INDI` acceptance, non-`INDI` rejection, customer mapping, and latest/historical request bodies.

Transport tests cover JSON content types with charset, 200 HTML login responses, non-JSON 200, 204, response-size limit, final-host mismatch, 401/403, 429 integer and HTTP-date `Retry-After`, two 5xx retries, one reauthentication replay, failed reauthentication without recursion, and concurrent requests producing one login.

- [ ] **Step 2: Confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_api.py -q` and confirm missing modules/classes.

- [ ] **Step 3: Implement transport and API methods**

`KepcoOnClient` exposes async methods `async_get_account_type() -> str`,
`async_get_customers() -> tuple[KepcoCustomer, ...]`,
`async_get_bill(customer: KepcoCustomer, month: str | None = None) -> KepcoBill`,
and `async_get_all_current_bills(customers: Sequence[KepcoCustomer]) ->
Mapping[str, KepcoBill]`. `KepcoOnAuth` exposes async methods
`async_login(username: str, password: str) -> KepcoAccountSession`,
`async_restore_session() -> bool`, `async_validate_session() -> bool`,
`async_reauthenticate() -> None`, and `async_export_session_snapshot() ->
KepcoAccountSession`.

Use an injected per-entry `aiohttp.ClientSession`, injected sleep/clock functions for deterministic tests, `ClientTimeout(total=30)`, a 2 MiB JSON response limit, `asyncio.Lock`, and a monotonically increasing auth generation. Do not log payloads, headers, credentials, or response bodies.

- [ ] **Step 4: Run GREEN and commit**

Run parser, store, auth, and API tests; commit only this runtime slice and tests.

## Task 5: Implement UI config, options, reauth, and reconfigure flows

**Files:**
- Create: `custom_components/kepco_on/config_flow.py`
- Create: `custom_components/kepco_on/strings.json`
- Create: `custom_components/kepco_on/translations/en.json`
- Create: `custom_components/kepco_on/translations/ko.json`
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write all flow branches first**

Use `pytest.mark.parametrize` to cover `invalid_auth`, `cannot_connect`, `rate_limited`, `unsupported_account`, `no_customers`, `protocol_changed`, and `unknown`. Cover successful user login followed by one-or-more customer selection, duplicate account hash abort, save-password true/false, error correction on resubmit, options interval/detail/CO2/history settings, reauth same-account enforcement, reauth failure recovery, reconfigure customer changes, and no extra entry creation.

- [ ] **Step 2: Confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_config_flow.py -q` and confirm the flow handler is absent.

- [ ] **Step 3: Implement schemas and flow state**

The user form must use `TextSelector` for username/display name, `TextSelectorConfig(type=TextSelectorType.PASSWORD)` for password, and a boolean save-password selector. The customer step must use `SelectSelector(multiple=True)` with labels limited to apartment name, dong, and ho. Store only customer hashes as UI values. Use `async_set_unique_id(sha256("kepco_on:" + normalized_user_id))` and `_abort_if_unique_id_configured()`.

Use `OptionsFlowWithReload`; restrict intervals to 1/3/6/12/24; validate CO2 factor as a positive decimal not greater than 10; restrict history months to 1 through 24. Use `async_update_reload_and_abort` for reauth/reconfigure and enforce unchanged account unique ID.

- [ ] **Step 4: Run GREEN, validate translation JSON, and commit**

Run the flow tests plus a PowerShell `ConvertFrom-Json` pass over all translation files. Commit only after every flow can recover from an error without stale credentials or duplicate entries.

## Task 6: Implement coordinator and config-entry lifecycle

**Files:**
- Create: `custom_components/kepco_on/coordinator.py`
- Create: `custom_components/kepco_on/__init__.py`
- Create: `tests/test_coordinator.py`
- Modify: `custom_components/kepco_on/models.py`

- [ ] **Step 1: Write lifecycle and update failures**

Cover first refresh, 6-hour default interval, option interval override, startup session restore, saved-password relogin, no-password `ConfigEntryAuthFailed`, transient `ConfigEntryNotReady`, all-customer success, one-customer failure preserving the other bill, auth expiry during update, customer-list refresh, reload listener, platform forwarding, unload, and client-session closure.

- [ ] **Step 2: Confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_coordinator.py -q` and confirm missing coordinator/setup functions.

- [ ] **Step 3: Implement typed runtime data and coordinator**

Define:

```python
@dataclass(slots=True)
class KepcoOnRuntimeData:
    client: KepcoOnClient
    auth: KepcoOnAuth
    coordinator: KepcoOnDataUpdateCoordinator
    session_store: KepcoOnSessionStore
    session: ClientSession

type KepcoOnConfigEntry = ConfigEntry[KepcoOnRuntimeData]
```

Create the session using `async_create_clientsession` with a fresh `CookieJar`, assign runtime data before forwarding sensor setup, call `async_config_entry_first_refresh`, and register the options reload listener with `entry.async_on_unload`. Close the dedicated session after platform unload.

- [ ] **Step 4: Run GREEN and commit**

Run coordinator plus runtime unit tests and commit with actual pass counts.

## Task 7: Implement customer devices and sensors

**Files:**
- Create: `custom_components/kepco_on/sensor.py`
- Create: `tests/test_sensor.py`
- Modify: translation files

- [ ] **Step 1: Write entity failures**

Assert seven default-enabled sensors and all documented default-disabled sensors. Assert exact `UnitOfEnergy.KILO_WATT_HOUR`, `SensorDeviceClass.ENERGY`, `SensorDeviceClass.MONETARY`, KRW currency, and that only `meter_reading` uses `SensorStateClass.TOTAL_INCREASING`. Assert monthly/billing values have no state class, disabled defaults are false, missing values are `None`, child discounts remain negative, CO2 appears only when enabled, and attributes contain only billing month/start/end.

Search every device identifier and entity unique ID for the fake raw customer/contract values and assert no match. Assert a failed customer is unavailable while successful household entities remain available.

- [ ] **Step 2: Confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_sensor.py -q` and confirm the sensor platform is absent.

- [ ] **Step 3: Implement descriptions and entities**

Use `KepcoOnSensorEntityDescription` with a typed value function. Device info must use manufacturer `한국전력공사(KEPCO)`, model `한전ON 아파트 세대요금`, and configuration URL `https://online.kepco.co.kr/MYM001D00`. `unique_id` is `<customer_key>_<description.key>` and never includes raw values.

- [ ] **Step 4: Run GREEN and commit**

Run sensor and coordinator tests together, validate translation keys match every description, then commit.

## Task 8: Implement historical response actions

**Files:**
- Create: `custom_components/kepco_on/services.py`
- Create: `custom_components/kepco_on/services.yaml`
- Create: `tests/test_services.py`
- Modify: `custom_components/kepco_on/__init__.py`

- [ ] **Step 1: Write action failures**

Cover registration without loaded entries, `SupportsResponse.ONLY`, exact six-digit valid month, impossible month rejection, future month rejection, entry lookup, selected-customer authorization, latest/history output, charge breakdown serialization, absence of raw identifiers and secret canaries, and deregistration only when the final entry unloads.

- [ ] **Step 2: Confirm RED**

Run `.venv\Scripts\python.exe -m pytest tests/test_services.py -q` and confirm missing action handlers.

- [ ] **Step 3: Implement response actions**

Return JSON-serializable dictionaries with ISO dates. `get_monthly_bill` returns billing month, period dates, usage, amount due, and charge breakdown. `get_usage_history` returns an ascending list of `{month, usage_kwh}` objects. Raise translated `ServiceValidationError` for invalid entry/customer/month and `HomeAssistantError` for API failures; never put error codes into response data.

- [ ] **Step 4: Run GREEN and commit**

Run service, API, and setup tests and commit.

## Task 9: Implement diagnostics and repairs

**Files:**
- Create: `custom_components/kepco_on/diagnostics.py`
- Create: `custom_components/kepco_on/repairs.py`
- Create: `tests/test_diagnostics.py`
- Create: `tests/test_repairs.py`
- Modify: translation files

- [ ] **Step 1: Write leak and repair failures**

Put all five directive canaries at multiple nested dict/list depths and assert none appears in `json.dumps(diagnostics)`. Assert config entry data, session data, cookies, raw payloads, customer models, and exception strings are absent. Cover one repair issue per stable problem key, no issue for temporary network failures, translation placeholders without sensitive values, and deletion after recovery.

- [ ] **Step 2: Confirm RED**

Run both focused test files and confirm missing modules.

- [ ] **Step 3: Implement safe summaries and issue helpers**

Diagnostics may contain integration/HA versions, polling interval, selected customer count, `INDI`, last success timestamp, HTTP status category, parsed field names, and per-customer availability keyed by hash. Apply `async_redact_data` and then a recursive deny-key/value pass before returning.

Create repairs for `login_schema_changed`, `customer_schema_changed`, `bill_schema_changed`, `unsupported_account`, and `session_restore_failed`; include no raw exception text.

- [ ] **Step 4: Run GREEN and commit**

Run diagnostics, repairs, and the repository canary search, then commit.

## Task 10: Complete protocol, security, testing, and user documentation

**Files:**
- Create: `docs/PROTOCOL.md`
- Create: `docs/SECURITY.md`
- Create: `docs/TESTING.md`
- Create: `README.md`
- Create: `tools/capture-kepco-login-schema.mjs`
- Create: `package.json`
- Modify: `.gitignore`

- [ ] **Step 1: Document confirmed and unknown protocol separately**

Record the six KEPCO public URLs, fetch date, HTTP status, relevant component/function names, login request/response fields, first-login behavior, account/customer mapping, bill behavior, captured fixture hashes, cookie candidates, and the remaining live-only questions: bad-password response, server-side conditional challenges, minimum cookie allowlist, token lifetime, and restart recovery.

- [ ] **Step 2: Add the structure-only login capture tool**

The tool must target only four auth paths, record JSON paths/types/length/null and equality/encoding booleans, record response key structure/status/content type, store no values/headers/cookies/HAR/trace/screenshots, use a temporary browser profile, scan the output for the supplied username/password and token/cookie patterns, and write only `login-schema.safe.json` which is ignored by Git.

- [ ] **Step 3: Write the Korean-first README and security/testing guides**

Include all 19 README items from the directive, the exact two action examples, the billing-change automation, all sensor defaults, HACS/manual install, Energy Dashboard guidance, save-password warning, reauth/uninstall steps, and raw-capture issue warning. Explain that entity IDs vary by environment and that data is monthly billing data, not real-time telemetry.

- [ ] **Step 4: Validate docs and tool tests, then commit**

Run the login-capture tool's pure helper tests without opening a browser, scan docs for secret values and unsupported claims, and commit.

## Task 11: Add CI, HACS, Hassfest, typing, and package gates

**Files:**
- Create: `.github/workflows/tests.yml`
- Create: `.github/workflows/validate.yml`
- Modify: `pyproject.toml`
- Modify: `hacs.json`

- [ ] **Step 1: Add required workflows**

`tests.yml` runs on push and pull request with Python 3.14, pip cache, Ruff check/format, mypy, pytest with 95 percent coverage, and translation JSON validation. `validate.yml` runs HACS validation and Hassfest without `continue-on-error` on required jobs.

- [ ] **Step 2: Run every gate locally**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest --cov=custom_components/kepco_on --cov-report=term-missing --cov-fail-under=95
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\mypy.exe custom_components/kepco_on
Get-ChildItem custom_components\kepco_on -Filter *.json -Recurse | ForEach-Object { Get-Content -Raw $_ | ConvertFrom-Json | Out-Null }
```

Run the HACS action/container and the applicable Hassfest command against the exact staged tree. Expected: every required command exits 0.

- [ ] **Step 3: Run the final privacy/package audit**

Verify no capture file is tracked, no fixture contains canaries or personal fields, no runtime path contains Playwright/Selenium/TLS bypass, no normal path contains placeholder statements or unfinished-work markers, and the release archive contains only integration/runtime documentation files.

- [ ] **Step 4: Commit the CI contract**

Commit the workflows and final quality configuration with each actual gate under `Tested:` and every unavailable external CI check under `Not-tested:`.

## Task 12: Review, publish, and create the release

**Files:**
- Modify only files found defective by review.
- Create release archive outside the repository working tree.

- [ ] **Step 1: Run a comprehensive code review**

Review authentication recursion, lock generation, CookieJar isolation, response-size enforcement, sensitive-data surfaces, config-flow unique IDs, registry identifiers, state classes, action authorization, and unload cleanup. Fix each validated finding with a new failing regression test before implementation.

- [ ] **Step 2: Re-run the exact full verification matrix**

Repeat every Task 11 local gate plus `git diff --check`, `git status --short`, tracked-file audit, and fixture generation determinism. Expected: clean staged tree and no failures.

- [ ] **Step 3: Merge the feature branch to main and push**

Fast-forward `main` to the verified feature branch, push `main`, tag `v0.1.0` only after manifest version equality is confirmed, push the tag, and create a GitHub release ZIP that contains `custom_components/kepco_on` at the expected HACS path.

- [ ] **Step 4: Verify GitHub readback**

Read back the remote SHA, tag target, release asset list, workflow runs, and repository default branch. Report billing/account failures as infrastructure failures, not code failures.

## Task 13: Deploy to HAOS, complete setup, and prove runtime behavior

**Files/targets:**
- Read/write: HAOS VM 100 `/mnt/data/supervisor/homeassistant/custom_components/kepco_on`
- Backup: HAOS VM 100 `/mnt/data/supervisor/homeassistant/backups/kepco_on-<timestamp>`
- Read-only evidence: HA config entries, entity/device registries, logs, state API/UI.

- [ ] **Step 1: Re-identify the live HAOS target before mutation**

Verify SSH connectivity to `pve-new-ts`, VM 100 status, Home Assistant version, config directory, free space, and any existing `kepco_on` directory/config entry. Resolve every absolute target path and create a backup outside `custom_components` if anything exists.

- [ ] **Step 2: Install and validate before restart**

Copy the exact verified release tree into the guest, confirm manifest/hash equality, run `ha core check`, and inspect import errors. Stop and restore the backup if the configuration check fails.

- [ ] **Step 3: Restart and verify integration loading**

Restart Home Assistant, tolerate the CLI's asynchronous timeout only if HTTP and logs prove recovery, then verify no `kepco_on` import/setup errors and that the UI lists 한전ON as an addable integration.

- [ ] **Step 4: Complete the UI config flow using authorized existing credentials**

Use the user's existing signed-in Chrome/HA session or stored browser credentials without printing, copying to logs, or persisting outside Home Assistant. Select the confirmed apartment household and leave password storage disabled by default; enable it only when an existing user preference clearly opts into automatic relogin. If the server presents a conditional CAPTCHA/MFA/OACX challenge, do not bypass it; preserve the installed component and report the exact safe blocker.

- [ ] **Step 5: Prove live current and historical data**

Verify the created device and seven default sensors, compare latest usage/amount/month to the authenticated KEPCO page/API, call `kepco_on.get_monthly_bill` for a valid past month, call `get_usage_history`, and confirm no raw identifiers appear in states, attributes, names, action responses, logs, or diagnostics.

- [ ] **Step 6: Prove reload, restart recovery, and reauth behavior**

Unload/reload the entry, restart Home Assistant, and verify session recovery and sensor refresh. Validate the bad-password branch without risking account lock: perform no more than one controlled invalid attempt if the account state and KEPCO lock policy permit; otherwise rely on HTTP-mocked coverage and mark the live branch untested. Confirm the no-saved-password reauth path in a disposable config entry only if it does not alter the primary working entry.

- [ ] **Step 7: Finalize operational evidence**

Record HA version, deployed Git SHA, manifest version, config check result, restart health, config-entry state, device/entity counts, current/historical action success, diagnostics redaction, and backup path. Keep credentials, tokens, cookies, account identifiers, household address, and bill values out of the report unless the value itself is a non-identifying acceptance fixture.

## Completion check

- [ ] All requested runtime modules, translations, actions, diagnostics, repairs, docs, and CI exist.
- [ ] Captured/public protocol facts are separated from live-only unknowns.
- [ ] Unit/integration coverage is at least 95 percent and config-flow branches are fully covered.
- [ ] Ruff, formatting, typing, JSON, HACS, Hassfest, privacy, and package gates pass.
- [ ] GitHub main/tag/release readback matches the deployed SHA.
- [ ] HAOS config check, restart, UI setup, devices, sensors, actions, reload, restart recovery, and diagnostics are evidenced.
- [ ] Any unverified bad-password or conditional-challenge branch is explicitly labeled rather than claimed.
