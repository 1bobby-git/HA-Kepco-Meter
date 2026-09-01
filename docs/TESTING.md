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

Record the exact tool version and output when these release gates are run for `v0.1.1`.

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
| New `neighbor_usage_comparison` sensor on exact `v0.1.1` release deployment | Pending |
| `kg CO₂` display on exact `v0.1.1` release deployment | Pending |
| Controlled invalid-password live test | Not run to avoid account-lock risk |

The live result record must not include usernames, raw customer or contract numbers, derived stable keys, addresses, bill values, tokens, cookies, or passwords.

## Home Assistant Live Smoke Checklist

Run on the target HAOS instance only after confirming its current version, config directory, and backup state:

- Install or copy `custom_components/kepco_on`.
- Run Home Assistant config check.
- Restart Home Assistant.
- Add KEPCO ON through the UI.
- Confirm login succeeds without unsupported conditional challenges.
- Select one or more supported apartment customers.
- Confirm default sensors load and contain no raw customer IDs in entity IDs or attributes.
- Confirm detailed sensors respect the option registry behavior.
- Confirm CO2 appears only when enabled and is labeled as an estimate.
- Run `kepco_on.get_monthly_bill` with response data.
- Run `kepco_on.get_usage_history` with response data.
- Unload/reload the entry.
- Restart Home Assistant and verify session recovery or reauth behavior.
- Download diagnostics and scan for credential/customer canaries.

For `v0.1.1`, repeat the checklist against the exact released package before marking HACS update and release deployment complete. The 2026-09-01 live run proves the existing HAOS path through restart recovery, but the new comparison sensor and `kg CO₂` rendering remain pending until the exact `v0.1.1` release is deployed.

## Privacy Scan

Before publishing a release or issue artifact:

```powershell
rg -n "userId|pwdVal|refreshToken|JSESSIONID|WMONID|kepcoSSO|CUST_NO|SI_CUST_NO|custNo|housCntrNo" README.md docs tools -g "!docs/superpowers/**"
git diff --check
git status --short
```

The protocol-field scan intentionally finds schema field names; review matches to ensure no raw values are present.
