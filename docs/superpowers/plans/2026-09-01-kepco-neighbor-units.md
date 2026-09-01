# KEPCO Neighbor Comparison and Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the official KEPCO neighbor-comparison sensor, display estimated emissions as `kg CO₂`, preserve Home Assistant-compliant KRW monetary sensors, and ship the verified work as `v0.1.1` to GitHub and HAOS.

**Architecture:** Reuse the existing typed `KepcoBill` values; no new request, parser field, or authentication behavior is introduced. Add one default-enabled sensor whose state is household monthly usage and whose safe attributes contain same-building and whole-apartment averages. Keep existing sensor IDs stable, update presentation metadata, then verify the exact release commit locally, in GitHub Actions, and on HAOS.

**Tech Stack:** Python 3.14, Home Assistant 2026.8.3 sensor/config-entry APIs, pytest, Ruff, mypy, JSON translations, HACS, Hassfest, GitHub CLI, PowerShell, HAOS VM 100.

---

## File map

- Modify `custom_components/kepco_on/sensor.py`: comparison description, comparison attributes, `kg CO₂` unit.
- Modify `tests/test_sensor.py`: sensor count/defaults/value/attribute/unit/privacy regression coverage.
- Modify `custom_components/kepco_on/strings.json`: English source translation for the comparison sensor.
- Modify `custom_components/kepco_on/translations/en.json`: English translation parity.
- Modify `custom_components/kepco_on/translations/ko.json`: Korean comparison name and greenhouse-gas name.
- Modify `custom_components/kepco_on/manifest.json`: release version `0.1.1`.
- Modify `custom_components/kepco_on/const.py`: runtime version `0.1.1` and derived User-Agent.
- Modify `pyproject.toml`: project version `0.1.1`.
- Modify `tests/test_scaffold.py`: expected release contract and constant.
- Modify `tests/test_ci_metadata.py`: manifest/pyproject version parity and final-version validation.
- Modify `README.md`: new entity, units, live setup, troubleshooting, restart/update guidance.
- Modify `docs/PROTOCOL.md`: verified WebSquare envelope, bootstrap, User-Agent, live response/runtime evidence.
- Modify `docs/TESTING.md`: completed live smoke evidence and remaining explicitly untested branches.

### Task 1: Add the comparison entity and unit behavior

**Files:**
- Modify: `tests/test_sensor.py`
- Modify: `custom_components/kepco_on/sensor.py`

- [ ] **Step 1: Write failing entity-contract tests**

Extend the synthetic bill helper so missing comparison values can be tested without building an unrelated bill object:

```python
def bill(
    *,
    usage_kwh: int | None = 573,
    amount_krw: int | None = 96330,
    child_discount_krw: int | None = -16000,
    building_average_kwh: int | None = 363,
    apartment_average_kwh: int | None = 284,
) -> KepcoBill:
    """Return a synthetic bill with every sensor-backed field populated."""
    return KepcoBill(
        bill_month="202608",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        usage_kwh=usage_kwh,
        previous_usage_kwh=406,
        last_year_usage_kwh=612,
        building_average_kwh=building_average_kwh,
        apartment_average_kwh=apartment_average_kwh,
        current_meter_reading=23139,
        previous_meter_reading=22566,
        meter_reading_day="01",
        amount_krw=amount_krw,
        charge=KepcoChargeBreakdown(
            subtotal_krw=85484,
            base_krw=6060,
            energy_krw=87402,
            climate_krw=5157,
            fuel_krw=2865,
            child_discount_krw=child_discount_krw,
            vat_krw=8548,
            fund_krw=2300,
            rounding_krw=2,
        ),
    )
```

Update the exact sensor-key and default-enabled assertions in `test_default_sensors_have_exact_count_metadata_values_and_privacy`:

```python
assert set(sensors) == {
    "monthly_usage",
    "neighbor_usage_comparison",
    "meter_reading",
    "amount_due",
    "previous_month_usage",
    "last_year_same_month_usage",
    "building_average_usage",
    "apartment_average_usage",
    "previous_meter_reading",
    "billing_month",
    "usage_period_start",
    "usage_period_end",
    "meter_reading_day",
    "electricity_subtotal",
    "base_charge",
    "energy_charge",
    "climate_environment_charge",
    "fuel_adjustment_charge",
    "child_discount",
    "vat",
    "power_industry_fund",
    "rounding_amount",
}
assert len(entities) == 22

default_enabled = {
    "monthly_usage",
    "neighbor_usage_comparison",
    "meter_reading",
    "amount_due",
    "previous_month_usage",
    "last_year_same_month_usage",
    "building_average_usage",
    "apartment_average_usage",
}

comparison = sensors["neighbor_usage_comparison"]
assert comparison.native_value == 573
assert comparison.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
assert comparison.device_class == SensorDeviceClass.ENERGY
assert comparison.state_class is None
assert comparison.extra_state_attributes == {
    "billing_month": "202608",
    "usage_period_start": date(2026, 7, 1),
    "usage_period_end": date(2026, 7, 31),
    "same_building_average_kwh": 363,
    "apartment_average_kwh": 284,
}
rendered_comparison = repr(comparison.extra_state_attributes)
assert RAW_CUSTOMER_SECRET not in rendered_comparison
assert RAW_HOUSE_SECRET not in rendered_comparison
assert RAW_NAME_SECRET not in rendered_comparison
```

Add a missing-value test:

```python
@pytest.mark.asyncio
async def test_neighbor_comparison_attributes_preserve_independent_missing_values() -> None:
    sensors = by_key(
        await setup_entities(
            bills_by_customer_key={
                "cust-a": bill(building_average_kwh=None, apartment_average_kwh=284)
            }
        )
    )

    assert sensors["neighbor_usage_comparison"].extra_state_attributes[
        "same_building_average_kwh"
    ] is None
    assert sensors["neighbor_usage_comparison"].extra_state_attributes[
        "apartment_average_kwh"
    ] == 284
```

Change the CO₂ unit assertion:

```python
assert sensors["co2_estimate"].native_unit_of_measurement == "kg CO₂"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
uv run --python 3.14 python -m pytest `
  tests/test_sensor.py::test_default_sensors_have_exact_count_metadata_values_and_privacy `
  tests/test_sensor.py::test_neighbor_comparison_attributes_preserve_independent_missing_values `
  tests/test_sensor.py::test_co2_sensor_is_optional_estimated_and_decimal_rounded -q
```

Expected: FAIL because `neighbor_usage_comparison` is absent and the CO₂ unit is still `kg`.

- [ ] **Step 3: Implement the minimal sensor contract**

Extend the description type in `sensor.py`:

```python
KepcoSensorAttributes = dict[str, int | None]


@dataclass(frozen=True, kw_only=True)
class KepcoSensorEntityDescription(SensorEntityDescription):
    """Describe one KEPCO ON sensor value."""

    value_fn: Callable[[KepcoBill, dict[str, Any]], KepcoSensorValue]
    attributes_fn: Callable[[KepcoBill], KepcoSensorAttributes] | None = None
```

Add the safe accessor:

```python
def _neighbor_comparison_attributes(bill: KepcoBill) -> KepcoSensorAttributes:
    return {
        "same_building_average_kwh": bill.building_average_kwh,
        "apartment_average_kwh": bill.apartment_average_kwh,
    }
```

Add this entry to `DEFAULT_SENSOR_DESCRIPTIONS` immediately after `monthly_usage`:

```python
KepcoSensorEntityDescription(
    key="neighbor_usage_comparison",
    translation_key="neighbor_usage_comparison",
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    device_class=SensorDeviceClass.ENERGY,
    value_fn=_usage("usage_kwh"),
    attributes_fn=_neighbor_comparison_attributes,
),
```

Preserve the attribute function when changing enabled defaults:

```python
return KepcoSensorEntityDescription(
    key=description.key,
    translation_key=description.translation_key,
    native_unit_of_measurement=description.native_unit_of_measurement,
    device_class=description.device_class,
    state_class=description.state_class,
    entity_registry_enabled_default=enabled_default,
    value_fn=description.value_fn,
    attributes_fn=description.attributes_fn,
)
```

Merge the attributes without exposing raw payload data:

```python
@property
def extra_state_attributes(self) -> dict[str, str | date | int | None]:
    bill = self.coordinator.data.bills_by_customer_key.get(self.customer.stable_key)
    if bill is None:
        return {}
    attributes: dict[str, str | date | int | None] = {
        "billing_month": bill.bill_month
    }
    if bill.period_start is not None:
        attributes["usage_period_start"] = bill.period_start
    if bill.period_end is not None:
        attributes["usage_period_end"] = bill.period_end
    if self.entity_description.attributes_fn is not None:
        attributes.update(self.entity_description.attributes_fn(bill))
    return attributes
```

Change the CO₂ description:

```python
native_unit_of_measurement="kg CO₂",
```

- [ ] **Step 4: Run focused and full sensor tests**

Run:

```powershell
uv run --python 3.14 python -m pytest tests/test_sensor.py -q
uv run --python 3.14 python -m ruff check custom_components/kepco_on/sensor.py tests/test_sensor.py
uv run --python 3.14 python -m mypy
```

Expected: all sensor tests pass; Ruff and mypy report no errors.

- [ ] **Step 5: Commit the entity slice**

```powershell
git add custom_components/kepco_on/sensor.py tests/test_sensor.py
git commit -m "Expose KEPCO neighbor comparison without new requests" `
  -m "Mirror the official three-value neighbor chart as one monthly kWh state with same-building and apartment-average attributes, and label estimated emissions as kg CO₂." `
  -m "Constraint: Existing sensor IDs and strict parsed integer values remain unchanged." `
  -m "Confidence: high" `
  -m "Scope-risk: narrow" `
  -m "Tested: full sensor tests; Ruff; mypy." `
  -m "Not-tested: HAOS rendering pending release deployment."
```

### Task 2: Add translation parity and official naming

**Files:**
- Modify: `tests/test_sensor.py`
- Modify: `custom_components/kepco_on/strings.json`
- Modify: `custom_components/kepco_on/translations/en.json`
- Modify: `custom_components/kepco_on/translations/ko.json`

- [ ] **Step 1: Write failing translation assertions**

Add `neighbor_usage_comparison` to `expected_keys` in `test_entity_translations_have_json_parity`, then assert exact labels:

```python
assert strings["entity"]["sensor"]["neighbor_usage_comparison"] == {
    "name": "Neighbor electricity usage comparison"
}
assert korean["entity"]["sensor"]["neighbor_usage_comparison"] == {
    "name": "이웃 전기사용량 비교"
}
assert korean["entity"]["sensor"]["co2_estimate"] == {
    "name": "온실가스 배출량"
}
```

- [ ] **Step 2: Run the translation test and verify RED**

Run:

```powershell
uv run --python 3.14 python -m pytest tests/test_sensor.py::test_entity_translations_have_json_parity -q
```

Expected: FAIL because the comparison translation is absent and the Korean CO₂ name is still the old estimate label.

- [ ] **Step 3: Update all translation resources**

Add to `strings.json` and `translations/en.json`:

```json
"neighbor_usage_comparison": {
  "name": "Neighbor electricity usage comparison"
}
```

Add to `translations/ko.json`:

```json
"neighbor_usage_comparison": {
  "name": "이웃 전기사용량 비교"
}
```

Change the Korean CO₂ name to:

```json
"co2_estimate": {
  "name": "온실가스 배출량"
}
```

- [ ] **Step 4: Validate translation parity and JSON**

Run:

```powershell
uv run --python 3.14 python -m pytest tests/test_sensor.py::test_entity_translations_have_json_parity -q
uv run --python 3.14 python -m json.tool custom_components/kepco_on/strings.json > $null
uv run --python 3.14 python -m json.tool custom_components/kepco_on/translations/en.json > $null
uv run --python 3.14 python -m json.tool custom_components/kepco_on/translations/ko.json > $null
```

Expected: test and all JSON parses pass.

- [ ] **Step 5: Commit translations**

```powershell
git add custom_components/kepco_on/strings.json `
  custom_components/kepco_on/translations/en.json `
  custom_components/kepco_on/translations/ko.json tests/test_sensor.py
git commit -m "Name KEPCO comparison and emissions sensors explicitly" `
  -m "Use KEPCO's official neighbor-comparison title and a mass-emissions Korean label while preserving translation parity." `
  -m "Constraint: Translation objects remain name-only for Hassfest." `
  -m "Confidence: high" `
  -m "Scope-risk: narrow" `
  -m "Tested: translation parity and JSON parse checks." `
  -m "Not-tested: HA frontend localization pending deployment."
```

### Task 3: Set patch-version metadata to 0.1.1

**Files:**
- Modify: `tests/test_scaffold.py`
- Modify: `tests/test_ci_metadata.py`
- Modify: `custom_components/kepco_on/manifest.json`
- Modify: `custom_components/kepco_on/const.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing version-parity tests**

In `test_scaffold.py`, change the exact manifest and constant expectations to `0.1.1`.

In `test_ci_metadata.py`, import `Version`:

```python
from packaging.version import Version
```

Replace the hard-coded manifest-only version assertion with:

```python
pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
release_version = Version(cast("str", manifest["version"]))

assert release_version == Version(cast("str", pyproject["project"]["version"]))
assert release_version == Version("0.1.1")
assert release_version.is_prerelease is False
assert release_version.is_devrelease is False
```

- [ ] **Step 2: Run metadata tests and verify RED**

Run:

```powershell
uv run --python 3.14 python -m pytest tests/test_scaffold.py tests/test_ci_metadata.py -q
```

Expected: FAIL because manifest, constant, and project version are `0.1.0`.

- [ ] **Step 3: Update all source versions**

Set:

```json
"version": "0.1.1"
```

in `manifest.json`, set:

```python
VERSION = "0.1.1"
```

in `const.py`, and set:

```toml
version = "0.1.1"
```

in `pyproject.toml`. The User-Agent remains derived from `VERSION`.

- [ ] **Step 4: Run metadata and static checks**

Run:

```powershell
uv run --python 3.14 python -m pytest tests/test_scaffold.py tests/test_ci_metadata.py -q
uv run --python 3.14 python -m ruff check .
uv run --python 3.14 python -m mypy
```

Expected: all pass and no stale `0.1.0` assertion remains in production/tests.

- [ ] **Step 5: Commit version metadata**

```powershell
git add custom_components/kepco_on/manifest.json `
  custom_components/kepco_on/const.py pyproject.toml `
  tests/test_scaffold.py tests/test_ci_metadata.py
git commit -m "Align KEPCO patch release metadata at 0.1.1" `
  -m "Keep manifest, runtime, project, and validation versions identical for HACS and release packaging." `
  -m "Constraint: Home Assistant minimum remains 2026.8.3 and runtime requirements remain empty." `
  -m "Confidence: high" `
  -m "Scope-risk: narrow" `
  -m "Tested: scaffold and CI metadata tests; Ruff; mypy." `
  -m "Not-tested: Git tag and release asset pending final verification."
```

### Task 4: Update user and protocol documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/PROTOCOL.md`
- Modify: `docs/TESTING.md`

- [ ] **Step 1: Update README sensor and troubleshooting tables**

Make these exact documentation changes:

- Set the documented release version to `0.1.1`.
- Add `neighbor_usage_comparison` to the default sensor table with state `월 사용량`, unit `kWh`, energy device class, and no state class.
- Change the CO₂ row unit from `kg` to `kg CO₂` and label it as a local estimate.
- State that all monetary sensors use `KRW`; Korean HA displays the won symbol.
- Record that detailed and CO₂ options produce 23 enabled entities after the new comparison entity is installed.
- Add this troubleshooting block:

```bash
# 설치된 버전 확인
cat /config/custom_components/kepco_on/manifest.json

# 구버전 오류 문구가 남아 있는지 확인
grep -R "login bootstrap content type changed" \
  /config/custom_components/kepco_on
```

Document: update through HACS, fully restart Home Assistant, confirm `0.1.1`, retry setup, and share only redacted logs/`login-schema.safe.json`—never raw passwords, cookies, tokens, customer numbers, HAR, or traces.

- [ ] **Step 2: Correct protocol notes with live evidence**

Update `docs/PROTOCOL.md` to state:

```text
GET /MYM001D00 -> fixed HTTPS bootstrap, redirects disabled, 200 required,
empty body/content-type allowed, JSESSIONID/WMONID names observed but not required.
POST /cyb/me/login/indi/api body -> {"dma_loginData": {...}}
login response -> dma_loginData2
explicit honest User-Agent -> HomeAssistant-KEPCO-ON/0.1.1
```

Record that live HAOS login, customer selection, current bill, response actions, options, detailed sensors, CO₂, and restart recovery passed on 2026-09-01. Keep invalid-password live testing and long-idle token lifetime explicitly untested.

- [ ] **Step 3: Update live testing evidence**

In `docs/TESTING.md`, replace the stale “not yet run” text with a dated result list:

```text
- HAOS 2026.8.3 config check and restart: passed
- Live individual login and one apartment customer selection: passed
- Current bill and seven original default sensors: passed
- Detailed option and CO₂ entity: passed
- get_monthly_bill and get_usage_history response actions: passed
- Full Core restart session recovery: passed
- New comparison sensor and kg CO₂ rendering: pending v0.1.1 deployment
- Controlled invalid-password attempt: not run to avoid account lock risk
```

- [ ] **Step 4: Run documentation safety scans**

Run:

```powershell
rg -n "userId|pwdVal|refreshToken|JSESSIONID|WMONID|CUST_NO|SI_CUST_NO|custNo|housCntrNo" README.md docs tools
rg -n "0\.1\.0|login bootstrap content type changed" README.md docs custom_components tests
git diff --check
```

Expected: matches are protocol field names, historical troubleshooting text, or intentionally retained `v0.1.0` history only; no raw values or stale current-version claims.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md docs/PROTOCOL.md docs/TESTING.md
git commit -m "Document verified KEPCO login and release recovery" `
  -m "Replace stale pre-live limitations with verified HAOS evidence, document the WebSquare envelope/bootstrap contract, and add safe HACS restart troubleshooting." `
  -m "Constraint: No account, customer, contract, token, cookie, or billing values are published." `
  -m "Confidence: high" `
  -m "Scope-risk: narrow" `
  -m "Tested: documentation field-name review and git diff check." `
  -m "Not-tested: Invalid-password live branch intentionally omitted to avoid lockout."
```

### Task 5: Run final repository and CI gates

**Files:**
- Verify all changed files; no new files expected.

- [ ] **Step 1: Run focused suites**

```powershell
uv run --python 3.14 python -m pytest tests/test_sensor.py -q
uv run --python 3.14 python -m pytest tests/test_api.py tests/test_auth.py tests/test_config_flow.py -q
uv run --python 3.14 python -m pytest tests/test_scaffold.py tests/test_ci_metadata.py -q
```

Expected: all pass.

- [ ] **Step 2: Run the complete local gate**

```powershell
npm ci
npm run test:login-schema
npm audit --audit-level=moderate
uv run --python 3.14 python -m ruff format .
uv run --python 3.14 python -m ruff format --check .
uv run --python 3.14 python -m ruff check .
uv run --python 3.14 python -m mypy
uv run --python 3.14 python -m pytest tests/test_ci_metadata.py
uv run --python 3.14 python -m pytest `
  --cov=custom_components.kepco_on `
  --cov-report=term-missing `
  --cov-fail-under=95
git diff --check
git status --short
```

Expected: Node 12/12, npm audit 0 vulnerabilities, Ruff/mypy clean, pytest all pass, coverage at least 95%, clean worktree.

- [ ] **Step 3: Push and verify GitHub Actions**

```powershell
git push origin main
gh run list --repo 1bobby-git/HA-Kepco-Meter --branch main --limit 6
```

Watch the new Tests and Validate runs:

```powershell
$headSha = git rev-parse HEAD
$runs = gh run list --repo 1bobby-git/HA-Kepco-Meter --branch main --limit 10 `
  --json databaseId,name,headSha,status | ConvertFrom-Json
$testsRun = ($runs | Where-Object { $_.headSha -eq $headSha -and $_.name -eq 'Tests' }).databaseId
$validateRun = ($runs | Where-Object { $_.headSha -eq $headSha -and $_.name -eq 'Validate' }).databaseId
if (-not $testsRun -or -not $validateRun) { throw 'Expected GitHub Actions runs were not found' }
gh run watch $testsRun --repo 1bobby-git/HA-Kepco-Meter --exit-status
gh run watch $validateRun --repo 1bobby-git/HA-Kepco-Meter --exit-status
```

Expected: Tests, HACS, and Hassfest complete successfully; do not continue on failure.

### Task 6: Package, release, deploy, and verify v0.1.1

**Files:**
- Create temporary release asset outside the repository.
- Deploy `custom_components/kepco_on` from tag `v0.1.1` to HAOS VM 100.

- [ ] **Step 1: Build and audit the release ZIP**

```powershell
$releaseVersion = '0.1.1'
$releaseDir = Join-Path ([System.IO.Path]::GetTempPath()) `
  ('kepco-release-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $releaseDir | Out-Null
$releaseZip = Join-Path $releaseDir "kepco_on-v$releaseVersion.zip"
git archive --format=zip `
  --prefix=custom_components/kepco_on/ `
  -o $releaseZip `
  HEAD:custom_components/kepco_on
tar -tf $releaseZip
Get-FileHash -Algorithm SHA256 -LiteralPath $releaseZip
```

Expected: ZIP contains only `custom_components/kepco_on/**`; no tests, captures, profiles, secrets, `.storage`, `__pycache__`, or `.pyc` files.

- [ ] **Step 2: Create the exact tag and GitHub Release**

```powershell
git status --short --branch
git tag -a v0.1.1 -m "KEPCO ON v0.1.1"
git push origin v0.1.1
gh release create v0.1.1 $releaseZip `
  --repo 1bobby-git/HA-Kepco-Meter `
  --title "KEPCO ON v0.1.1" `
  --notes "## 한전ON v0.1.1

- HAOS/WebSquare 로그인 bootstrap, envelope, and safe User-Agent fixes.
- 이웃 전기사용량 비교 센서와 kg CO₂ 표시.
- 상세 센서 옵션 expected str 오류 수정.
- 고정 HTTPS 호스트, 리다이렉트 차단, 상태 코드 및 크기 제한 유지.
- 업데이트 후 Home Assistant를 완전히 재시작해야 합니다."
```

Verify:

```powershell
git rev-parse v0.1.1^{}
git rev-parse HEAD
gh release view v0.1.1 --repo 1bobby-git/HA-Kepco-Meter --json tagName,name,assets,url
```

Expected: tag commit equals `HEAD`; asset is `kepco_on-v0.1.1.zip`.

- [ ] **Step 3: Deploy the exact tag to HAOS with backup**

```powershell
$haTar = Join-Path $releaseDir 'kepco_on-v0.1.1.tar'
git archive --format=tar --prefix=kepco_on/ `
  v0.1.1:custom_components/kepco_on -o $haTar
scp $haTar pve-new-ts:/tmp/kepco_on-v0.1.1.tar
ssh pve-new-ts 'qm guest exec 100 -- mkdir -p /mnt/data/supervisor/homeassistant/kepco_on_backups'
ssh pve-new-ts 'qm guest exec 100 -- cp -a /mnt/data/supervisor/homeassistant/custom_components/kepco_on /mnt/data/supervisor/homeassistant/kepco_on_backups/pre-v0.1.1-20260901'
ssh pve-new-ts 'cat /tmp/kepco_on-v0.1.1.tar | qm guest exec 100 --pass-stdin -- tar -xf - -C /mnt/data/supervisor/homeassistant/custom_components'
ssh pve-new-ts 'qm guest exec 100 -- ha core check'
ssh pve-new-ts 'qm guest exec 100 -- ha core restart'
```

Wait until both probes succeed:

```powershell
curl.exe -sS -o NUL -w "%{http_code}" https://homeassistant.toiss.kr/
curl.exe --http1.1 -sS -o NUL -w "%{http_code}" `
  -H "Connection: Upgrade" -H "Upgrade: websocket" `
  -H "Sec-WebSocket-Version: 13" `
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" `
  https://homeassistant.toiss.kr/api/websocket
```

Expected: HTTP `200`, WebSocket `101`.

- [ ] **Step 4: Verify live HAOS rendering and recovery**

Verify without printing raw identifiers or bill values:

```text
1 config entry
1 device
23 enabled entities, 0 disabled
neighbor sensor visible with kWh state
same_building_average_kwh and apartment_average_kwh attributes present
CO₂ sensor unit shown as kg CO₂
monetary sensors shown as KRW-localized won currency
no kepco_on setup/update errors in Core logs
```

Run both response actions again and assert response keys only:

```text
get_monthly_bill -> billing_month, usage_period_start/end, usage_kwh,
amount_due_krw, charge_breakdown
get_usage_history -> history entries with month and usage_kwh
```

Reload the config entry once, then fully restart Core once. Confirm the same entry/device/entity counts and available values after each recovery step.

- [ ] **Step 5: Final completion audit**

Record:

```text
commit SHA
tag and GitHub Release URL
asset filename, size, SHA256
manifest and pyproject version
GitHub Tests/HACS/Hassfest run URLs
HAOS version, config-check result, backup path
entry/device/enabled-entity counts
live login/current bill/history/action/reload/restart/diagnostics result
controlled invalid-password branch: not tested to avoid lockout
```

Only after every item above is evidenced, mark the active goal complete.
