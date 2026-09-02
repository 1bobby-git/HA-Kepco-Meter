# KEPCO ON Protocol Notes

This document records the protocol evidence used by the integration without committing raw KEPCO ON captures.

Document review date: 2026-09-02
Integration version: `0.2.0`

## Evidence Baseline

| Evidence | Status | Details |
| --- | --- | --- |
| Endpoint inventory | Confirmed safe artifact, not committed raw | Safe endpoint inventory was reviewed without committing raw captures or stable digest values. |
| Safe wire capture | Confirmed safe artifact, not committed raw | Safe wire metadata was reviewed without committing raw payloads, headers, cookie values, customer identifiers, bill values, or stable digest values. |
| Public WebSquare XML/JS | Confirmed HTTP 200 on 2026-08-31 | Static XML paths include `/ui/me/login/indi/MEM001D01.xml` and `/ui/my/indi/MYM001D00.xml`; commonAPI, commonGlobal, commonScope, and commonUtil fetched 200. |
| Live HAOS smoke | Passed on 2026-09-01 | HAOS 2026.8.3 config check, full Core restart, personal login, customer selection, current bill retrieval, both response actions, detailed option, CO2 option, and restart recovery passed. |

Raw endpoint and wire artifacts are intentionally untracked. Do not publish raw captures, cookies, tokens, customer identifiers, account identifiers, bill values, or digest values derived from private captures.

## Confirmed vs Unconfirmed

| Area | Confirmed | Not Yet Proven Live |
| --- | --- | --- |
| Login bootstrap | Fixed HTTPS GET `https://online.kepco.co.kr/MYM001D00` with redirects disabled. HTTP 200 is required. Empty body and empty or missing content type are allowed. Response size is bounded. Observed cookie names include `JSESSIONID` and `WMONID`, but no cookie name is required for success and bootstrap cookies are not persisted. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnTransport.async_prepare_login_session`. | Long-idle token lifetime remains untested. |
| Login request | `/cyb/me/login/indi/api` receives a credential-bearing JSON object wrapped under `dma_loginData`, with `userId`, `pwdVal`, `autoFlag: "N"` and submission id `mf_login_popup_wframe_sbm_submission4`. The response is read from `dma_loginData2` when present, and one bounded same-session retry is allowed only for an empty object response. The User-Agent is `HomeAssistant-KEPCO-ON/0.2.0`. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth._async_login_unlocked`; endpoint constant in `custom_components/kepco_on/const.py`. | Controlled invalid-password live test was not run to avoid account-lock risk. Conditional challenge variants remain untested. |
| First-login check | `/me/login/firstLogin/check` exists in capture and tool scope. Code anchor: endpoint constant in `custom_components/kepco_on/const.py`. | Whether billing requires this endpoint in every fresh account/session case. |
| Session validation | `/sessionCheck` sends `refreshToken`, `userId`, `mbrsNm` and rotates token fields when `result` is true. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth.async_validate_session`. | Token lifetime and restart behavior after long idle periods. |
| SSO check | `/ssoCheck` sends `userId`, `userMngSeqno`, `name`, `autoLogin: "Y"` and expects `loginChk: "Y"`. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth.async_sso_check`. | Whether every deployment needs SSO check before protected requests. |
| Cookies | Live bootstrap observed `JSESSIONID` and `WMONID`. The current persisted cookie allowlist is empty, so restart recovery does not depend on committed cookie values. Code anchor: `custom_components/kepco_on/const.py` `PERSISTED_COOKIE_ALLOWLIST`. | Whether future KEPCO changes require a persisted cookie allowlist. |
| Account type | `/isCorp` returns `userClNm`; only `INDI` is accepted. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnClient.async_get_account_type`. | Behavior of non-INDI accounts beyond safe rejection. |
| Customer list | `/my/indi/info/myPageCustNoList` uses the 12-key `dma_search` body below. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnClient.async_get_customers` with submission id `mf_wfm_layout_sbm_myPageCustList`. | Empty `myPage` result behavior from a real account. |
| Bill detail | `/my/charge/pay/aptBillDetail` uses latest empty month or explicit `YYYYMM`. Code anchor: `custom_components/kepco_on/api.py` `KepcoOnClient.async_get_bill` with submission id `mf_wfm_layout_sbm_search`. | Month availability outside tested recent cases. |
| Historical mismatch | Requested `202607` can succeed with `DO_ERR_CODE == "HXI001"` while the response repeats another `DO_BILL_YM`; requested month remains effective. | Additional mismatch patterns. |
| Real-time and CO2 | Real-time Power Planner data and server CO2 values are not implemented. Three CO2 values are local estimates derived from current, previous-month, and previous-year usage. Code anchor: `custom_components/kepco_on/sensor.py` `GREENHOUSE_GAS_SENSOR_DESCRIPTIONS`. | Server-provided CO2 values remain unimplemented. |

## Public Resource Sources

| Resource | URL | Fetch Date | HTTP Result | Last-Modified |
| --- | --- | --- | --- | --- |
| Login page definition | `https://online.kepco.co.kr/ui/me/login/indi/MEM001D01.xml` | 2026-08-31 | 200 | 2026-07-28 |
| My page definition | `https://online.kepco.co.kr/ui/my/indi/MYM001D00.xml` | 2026-08-31 | 200 | 2026-07-29 |
| Apartment bill page definition | `https://online.kepco.co.kr/ui/my/charge/MYM053D50.xml` | 2026-09-01 | 200 | Not recorded in committed files |
| Common API script | `https://online.kepco.co.kr/commonAPI.js` | 2026-08-31 | 200 | Not recorded in committed files |
| Common global script | `https://online.kepco.co.kr/commonGlobal.js` | 2026-08-31 | 200 | Not recorded in committed files |
| Common scope script | `https://online.kepco.co.kr/commonScope.js` | 2026-08-31 | 200 | Not recorded in committed files |
| Common utility script | `https://online.kepco.co.kr/commonUtil.js` | 2026-08-31 | 200 | Not recorded in committed files |

## Request Contracts

| Endpoint | Method | Submission ID | Body |
| --- | --- | --- | --- |
| `https://online.kepco.co.kr/MYM001D00` | GET | None | Credential-free bootstrap; redirects disabled; HTTP 200 required; empty body/content type allowed; response size bounded |
| `/cyb/me/login/indi/api` | POST | `mf_login_popup_wframe_sbm_submission4` | `dma_loginData` object containing `userId`, `pwdVal`, `autoFlag: "N"` |
| `/sessionCheck` | POST | None | `refreshToken`, `userId`, `mbrsNm` |
| `/ssoCheck` | POST | None | `userId`, `userMngSeqno`, `name`, `autoLogin: "Y"` |
| `/isCorp` | POST | None | No JSON body |
| `/my/indi/info/myPageCustNoList` | POST | `mf_wfm_layout_sbm_myPageCustList` | `dma_search` object with `schYm`, `custNo`, `gubun`, `schChart`, `CUST_NO`, `housCntrNo`, `yyyymm`, `searchType`, `dong`, `ho`, `months`, `chgYmd` |
| `/my/charge/pay/aptBillDetail` | POST | `mf_wfm_layout_sbm_search` | `dma_search.custNo`, `housCntrNo`, `yymm`, `yyyymm`, `searchType: "DETAIL"` |

`CUST_NO` maps to bill request `custNo`; `SI_CUST_NO` maps to `housCntrNo`. The integration stores selected raw IDs only in config-entry data because they are required for future bill requests; entity/device identifiers use derived stable keys.

## Response Contracts

| Response | Used Keys |
| --- | --- |
| Login | `dma_loginData2` wrapper when present; used keys are `result`, `errorCode`, `errorMessage`, `token`, `refreshToken`, `userId`, `mbrsNm`, `movePage`, `serviceMode`, `pwdUpdFlag`, `frstLoginTF`, `pwdUp`, optional `userMngSeqno` |
| Session check | `result`, `token`, `refreshToken`, `userId`, `mbrsNm`, optional `userMngSeqno` |
| SSO check | `loginChk`, optional `refreshToken` |
| Account type | `userClNm` |
| Customer list | Apartment/officetel rows parsed into apartment name, dong, ho, contract method, customer number, house contract number, support flag |
| Bill detail | Effective month, server bill month, usage period, current/previous meter readings, total/household/common usage, usage comparisons, neighbor comparison fields from `/ui/my/charge/MYM053D50.xml`, amount due, charge breakdown, ordered monthly history |

The official `/ui/my/charge/MYM053D50.xml` neighbor chart maps `DO_KWH` to the customer's monthly usage, `DO_APT_HOUS_USKI_AVG` to the same-building household average, and `DO_APT_TOT_USKI_AVG` to the whole-apartment average. All three values are kWh.

No raw response body, request body, header set, cookie value, HAR, trace, or screenshot is committed.

## Runtime Limitations

Live HAOS validation on 2026-09-01 remains the proven baseline for `v0.1.1`: login, customer selection, current bill retrieval, response actions, restart recovery, 23 enabled entities, the neighbor comparison sensor, and `kg CO₂` rendering passed. Version `v0.2.0` changes only the parsed bill model and Home Assistant sensor/device presentation to five logical devices and 32 entities; a live HAOS/HACS upgrade of this new structure is not claimed by this document. The controlled invalid-password branch and long-idle token lifetime also remain untested.
