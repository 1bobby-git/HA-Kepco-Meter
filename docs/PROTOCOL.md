# KEPCO ON Protocol Notes

This document records the protocol evidence used by the integration without committing raw KEPCO ON captures.

Document review date: 2026-09-01
Integration version: `0.1.0`

## Evidence Baseline

| Evidence | Status | Details |
| --- | --- | --- |
| Endpoint inventory | Confirmed safe artifact, not committed raw | SHA-256 `9ab036e15bd80e018a923cf9ca9250067cf3b2a911248d88ad2a8fdff940558b`; 4,052 bytes; 50 nonblank lines. |
| Safe wire capture | Confirmed safe artifact, not committed raw | SHA-256 `cdd9f5f7443781e2986484cd030e5b95d9d89ae764a5ee2e759d144c2459620a`; 20,826,701 bytes; 611 records. |
| Public WebSquare XML/JS | Confirmed HTTP 200 on 2026-08-31 | `https://online.kepco.co.kr/MEM001D01.xml` Last-Modified 2026-07-28; `https://online.kepco.co.kr/MYM001D00.xml` Last-Modified 2026-07-29; commonAPI, commonGlobal, commonScope, commonUtil fetched 200. |

Raw endpoint and wire artifacts are intentionally untracked. Recompute their hashes from a local capture path when auditing:

```powershell
Get-FileHash -Algorithm SHA256 <path-to-kepco-on-endpoints.txt>
Get-FileHash -Algorithm SHA256 <path-to-kepco-on-wire.safe.jsonl>
(Get-Content <path-to-kepco-on-endpoints.txt> | Where-Object { $_.Trim() }).Count
(Get-Item <path-to-kepco-on-wire.safe.jsonl>).Length
```

```bash
sha256sum <path-to-kepco-on-endpoints.txt> <path-to-kepco-on-wire.safe.jsonl>
grep -cve '^[[:space:]]*$' <path-to-kepco-on-endpoints.txt>
wc -c <path-to-kepco-on-wire.safe.jsonl>
```

## Confirmed vs Unconfirmed

| Area | Confirmed | Not Yet Proven Live |
| --- | --- | --- |
| Login request | `/cyb/me/login/indi/api` receives `userId`, `pwdVal`, `autoFlag: "N"` and submission id `mf_login_popup_wframe_sbm_submission4`. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth._async_login_unlocked`; endpoint constant in `custom_components/kepco_on/const.py`. | Exact bad-password response body and all conditional challenge variants. |
| First-login check | `/me/login/firstLogin/check` exists in capture and tool scope. Code anchor: endpoint constant in `custom_components/kepco_on/const.py`. | Whether billing requires this endpoint in every fresh account/session case. |
| Session validation | `/sessionCheck` sends `refreshToken`, `userId`, `mbrsNm` and rotates token fields when `result` is true. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth.async_validate_session`. | Token lifetime and restart behavior after long idle periods. |
| SSO check | `/ssoCheck` sends `userId`, `userMngSeqno`, `name`, `autoLogin: "Y"` and expects `loginChk: "Y"`. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth.async_sso_check`. | Whether every deployment needs SSO check before protected requests. |
| Cookies | Candidate names are `JSESSIONID` and `kepcoSSO`; persisted allowlist is empty. Code anchor: `custom_components/kepco_on/const.py` `CANDIDATE_COOKIE_NAMES` and `PERSISTED_COOKIE_ALLOWLIST`. | Minimum cookie allowlist for durable restart recovery. |
| Account type | `/isCorp` returns `userClNm`; only `INDI` is accepted. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnClient.async_get_account_type`. | Behavior of non-INDI accounts beyond safe rejection. |
| Customer list | `/my/indi/info/myPageCustNoList` uses the 12-key `dma_search` body below. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnClient.async_get_customers` with submission id `mf_wfm_layout_sbm_myPageCustList`. | Empty `myPage` result behavior from a real account. |
| Bill detail | `/my/charge/pay/aptBillDetail` uses latest empty month or explicit `YYYYMM`. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnClient.async_get_bill` with submission id `mf_wfm_layout_sbm_search`. | Month availability outside tested recent cases. |
| Historical mismatch | Requested `202607` can succeed with `DO_ERR_CODE == "HXI001"` while the response repeats another `DO_BILL_YM`; requested month remains effective. | Additional mismatch patterns. |
| Real-time and CO2 | Real-time Power Planner data and server CO2 values are not implemented. CO2 is a local estimate only. Code anchor: `custom_components/kepco_on/sensor.py` `CO2_SENSOR_DESCRIPTION`. | None for first release. |

## Public Resource Sources

| Resource | URL | Fetch Date | HTTP Result | Last-Modified |
| --- | --- | --- | --- | --- |
| Login page definition | `https://online.kepco.co.kr/MEM001D01.xml` | 2026-08-31 | 200 | 2026-07-28 |
| My page definition | `https://online.kepco.co.kr/MYM001D00.xml` | 2026-08-31 | 200 | 2026-07-29 |
| Common API script | `https://online.kepco.co.kr/commonAPI.js` | 2026-08-31 | 200 | Not recorded in committed files |
| Common global script | `https://online.kepco.co.kr/commonGlobal.js` | 2026-08-31 | 200 | Not recorded in committed files |
| Common scope script | `https://online.kepco.co.kr/commonScope.js` | 2026-08-31 | 200 | Not recorded in committed files |
| Common utility script | `https://online.kepco.co.kr/commonUtil.js` | 2026-08-31 | 200 | Not recorded in committed files |

## Request Contracts

| Endpoint | Method | Submission ID | Body |
| --- | --- | --- | --- |
| `/cyb/me/login/indi/api` | POST | `mf_login_popup_wframe_sbm_submission4` | `userId`, `pwdVal`, `autoFlag: "N"` |
| `/sessionCheck` | POST | None | `refreshToken`, `userId`, `mbrsNm` |
| `/ssoCheck` | POST | None | `userId`, `userMngSeqno`, `name`, `autoLogin: "Y"` |
| `/isCorp` | POST | None | No JSON body |
| `/my/indi/info/myPageCustNoList` | POST | `mf_wfm_layout_sbm_myPageCustList` | `dma_search` object with `schYm`, `custNo`, `gubun`, `schChart`, `CUST_NO`, `housCntrNo`, `yyyymm`, `searchType`, `dong`, `ho`, `months`, `chgYmd` |
| `/my/charge/pay/aptBillDetail` | POST | `mf_wfm_layout_sbm_search` | `dma_search.custNo`, `housCntrNo`, `yymm`, `yyyymm`, `searchType: "DETAIL"` |

`CUST_NO` maps to bill request `custNo`; `SI_CUST_NO` maps to `housCntrNo`. The integration stores selected raw IDs only in config-entry data because they are required for future bill requests; entity/device identifiers use derived stable keys.

## Response Contracts

| Response | Used Keys |
| --- | --- |
| Login | `result`, `errorCode`, `errorMessage`, `token`, `refreshToken`, `userId`, `mbrsNm`, `movePage`, `serviceMode`, `pwdUpdFlag`, `frstLoginTF`, `pwdUp`, optional `userMngSeqno` |
| Session check | `result`, `token`, `refreshToken`, `userId`, `mbrsNm`, optional `userMngSeqno` |
| SSO check | `loginChk`, optional `refreshToken` |
| Account type | `userClNm` |
| Customer list | Apartment/officetel rows parsed into apartment name, dong, ho, contract method, customer number, house contract number, support flag |
| Bill detail | Effective month, server bill month, usage period, current/previous meter readings, usage comparisons, amount due, charge breakdown, ordered monthly history |

No raw response body, request body, header set, cookie value, HAR, trace, or screenshot is committed.

## Runtime Limitations

The integration has not yet completed final live Home Assistant OS installation, Hassfest, HACS install, restart recovery, or release packaging verification. Public docs and code must not state those gates as complete until new evidence exists.
