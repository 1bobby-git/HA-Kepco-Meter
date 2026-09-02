# Testing and Release Verification

This file separates checks already runnable in the repository from dated live evidence and future release gates.

## Local Windows Commands

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements_test.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m pytest --cov=custom_components.kepco_on --cov-report=term-missing
.\.venv\Scripts\python -m ruff check custom_components tests
.\.venv\Scripts\python -m ruff format --check custom_components tests
.\.venv\Scripts\python -m mypy custom_components tests
```

`pytest-homeassistant-custom-component` is excluded on Windows by `requirements_test.txt`, so Home Assistant plugin-specific coverage belongs on Linux.

## Linux Plugin Marker

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_test.txt
pytest -q
pytest -q -m "not no_ha_plugin"
```

Use the Linux run to cover tests that require `pytest-homeassistant-custom-component`.

## Fixture Extractor

PowerShell with the known Desktop capture path:

```powershell
.\.venv\Scripts\python tools\extract-safe-fixtures.py --input "$env:USERPROFILE\Desktop\kepco-on-wire.safe.jsonl" --check
```

Portable form:

```powershell
.\.venv\Scripts\python tools\extract-safe-fixtures.py --input <path-to-kepco-on-wire.safe.jsonl> --check
```

The extractor must operate on safe, minimized fixtures only. Raw KEPCO ON captures stay outside Git.

## JSON, Node, and Package Checks

```powershell
npm run test:login-schema
npm audit
node -e "JSON.parse(require('fs').readFileSync('package-lock.json', 'utf8'))"
.\.venv\Scripts\python -m json.tool custom_components\kepco_on\strings.json > $null
.\.venv\Scripts\python -m json.tool custom_components\kepco_on\translations\ko.json > $null
.\.venv\Scripts\python -m json.tool custom_components\kepco_on\translations\en.json > $null
```

`npm run test:login-schema` does not launch a browser. Browser launch is limited to `npm run capture:login-schema`.

## HACS and Hassfest

Future release gates:

```bash
hacs validate
hassfest
```

For `v0.2.1`, the GitHub `Release` workflow waits for both the Tests workflow and the same-commit HACS/Hassfest validation before creating the tag, release, and HACS ZIP asset.

## Dated Live Results

Validated on HAOS 2026.8.3 on 2026-09-01:

| Check | Result |
| --- | --- |
| Home Assistant config check | Passed |
| Full Home Assistant Core restart | Passed |
| Personal KEPCO ON login | Passed |
| Supported apartment customer selection | Passed |
| Current bill retrieval | Passed |
| Original default sensors | Passed |
| Detailed sensor option | Passed |
| CO2 estimate option | Passed |
| `kepco_on.get_monthly_bill` response action | Passed |
| `kepco_on.get_usage_history` response action | Passed |
| Full Core restart session recovery | Passed |
| Exact `v0.1.1` tag, GitHub Release, and release ZIP | Passed |
| Tests, HACS, and Hassfest for the exact release commit | Passed |
| Exact `v0.1.1` deployment and Core restart | Passed |
| New `neighbor_usage_comparison` sensor on exact `v0.1.1` release deployment | Passed |
| `kg CO₂` display on exact `v0.1.1` release deployment | Passed |
| 23 enabled / 0 disabled KEPCO ON entities after restart | Passed |
| Live HACS upgrade from `v0.1.0` to `v0.1.1` | Not run; exact release archive was deployed directly |
| Controlled invalid-password live test | Not run to avoid account-lock risk |

The live result record must not include usernames, raw customer or contract numbers, derived stable keys, addresses, bill values, tokens, cookies, or passwords.

The `v0.2.1` naming, config-entry title migration, and sensor-information grouping update is validated by repository unit, type, formatting, HACS, and Hassfest gates before publication. This file does not claim a target-HAOS live upgrade result until that separate deployment is run.


## Home Assistant Live Smoke Checklist

Run on the target HAOS instance only after confirming its current version, config directory, and backup state:

- Install or copy `custom_components/kepco_on`.
- Run Home Assistant config check.
- Restart Home Assistant.
- Add KEPCO ON through the UI.
- Confirm login succeeds without unsupported conditional challenges.
- Select one or more supported apartment customers.
- Confirm five logical devices and 32 sensor entities load for each selected customer.
- Confirm six monthly-history entities show the expected current and prior-year month labels.
- Confirm integration-disabled legacy detailed entities are re-enabled while user-disabled entities stay disabled.
- Confirm all three CO2 entities are labeled as estimates and use the configured factor.
- Run `kepco_on.get_monthly_bill` with response data.
- Run `kepco_on.get_usage_history` with response data.
- Unload/reload the entry.
- Restart Home Assistant and verify session recovery or reauth behavior.
- Download diagnostics and scan for credential/customer canaries.

The 2026-09-01 exact-release run deployed `v0.1.1`, passed the Core config check and restart, restored 23 enabled KEPCO ON entities with none disabled, and verified the comparison sensor, its two average attributes, kWh usage units, `kg CO₂` display, and currency rendering in the Home Assistant UI. The direct release-archive path is proven; a live HACS upgrade from `v0.1.0` remains a separate untested path.

## Privacy Scan

Before publishing a release or issue artifact:

```powershell
rg -n "userId|pwdVal|refreshToken|JSESSIONID|WMONID|kepcoSSO|CUST_NO|SI_CUST_NO|custNo|housCntrNo" README.md docs tools -g "!docs/superpowers/**"
git diff --check
git status --short
```

The protocol-field scan intentionally finds schema field names; review matches to ensure no raw values are present.
