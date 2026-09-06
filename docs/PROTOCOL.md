# KEPCO ON Protocol Notes

This document records the protocol evidence used by the integration without committing raw KEPCO ON captures.

Document review date: 2026-09-06
Integration version: `0.3.5`

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
| Login request | `/cyb/me/login/indi/api` receives a credential-bearing JSON object wrapped under `dma_loginData`, with `userId`, `pwdVal`, `autoFlag: "N"` and submission id `mf_login_popup_wframe_sbm_submission4`. The response is read from `dma_loginData2` when present, and one bounded same-session retry is allowed only for an empty object response. The User-Agent is `HomeAssistant-KEPCO-ON/0.2.1`. Code anchor: `custom_components/kepco_on/auth.py` `KepcoOnAuth._async_login_unlocked`; endpoint constant in `custom_components/kepco_on/const.py`. | Controlled invalid-password live test was not run to avoid account-lock risk. Conditional challenge variants remain untested. |
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

Live HAOS validation on 2026-09-01 remains the proven baseline for `v0.1.1`: login, customer selection, current bill retrieval, response actions, restart recovery, 23 enabled entities, the neighbor comparison sensor, and `kg CO₂` rendering passed. Version `v0.2.0` introduced the five logical devices and 32 entities. Version `v0.2.1` normalizes the config-entry/device names and moves three date/day entities into the diagnostic sensor-information category; a live HAOS/HACS upgrade of these presentation changes is not claimed by this document. The controlled invalid-password branch and long-idle token lifetime also remain untested.


## v0.3.5 public Power Planner binding verification (2026-09-06)

Source: https://online.kepco.co.kr/ui/my/indi/MYM001D00.xml
Read-only, credential-free fetch: https://github.com/1bobby-git/HA-Kepco-Meter/actions/runs/34022622853

The public `dataInit` function reads `sel_custNo` from `SI_CUST_NO`, sets
`dma_search.custNo` and the complete `DC_USER_CHG_NM_YMD`, then submits
`/my/memo/powerPlanner`. Only afterwards does the apartment billing branch
replace `custNo` with `CUST_NO` and set `housCntrNo`. The planner must not be
queried using an apartment building's billing customer number.

The same page recognizes apartment single, comprehensive, and comprehensive/na
contracts. Current energy rendering is conditional on `RETURN_CD == "00"` and
uses `F_AP_QT` with kWh. The XML labels `PREDICT_TOT` as expected electricity
charges; its sample magnitude is not evidence of an energy unit. Version 0.3.5
therefore keeps the legacy prediction entity ID but does not map that ambiguous
field into kWh. No derived prediction or monetary sensor is introduced.

A `90` response with null values was recorded in the earlier capture summary;
this is not a fresh per-account measurement or proof of a specific AMI limitation.
No private account was accessed in this change. Two planner sensors expose only
safe status metadata, not raw responses, identifiers, amounts, or tokens. The
older evidence-baseline rows above describe historical versions, not current
support. Current-period data is never attached to an explicit historical bill.

## 한전ON v0.3.6

### 종합계약 사용자 확인 Wh 응답 옵션

- `종합계약: 사용자 확인 Wh 응답 사용` 옵션을 추가했습니다. 기본값은 꺼짐입니다. 해당 계정에서 두 필드가 Wh 에너지라는 점을 확인한 경우에만 켭니다.
- 옵션을 켠 종합계약에서만 사용자 보고의 성공 요청처럼 `custNo=CUST_NO`, `housCntrNo=SI_CUST_NO`, `chgYmd=""`를 전달합니다. 단일계약과 주택용의 요청은 변경하지 않습니다.
- 이 프로필에서 유효한 `F_AP_QT`, `PREDICT_TOT`를 각각 1000으로 나눠 기존 두 kWh 엔티티에 반영합니다. 이는 명시적인 사용자 선택 해석이며 한전의 모든 응답 단위가 검증됐다는 뜻이 아닙니다. 특히 요금 값을 에너지로 해석하면 안 됩니다. 단위를 숫자 크기로 추측하지 않습니다.
- 실제 0, null, 실패 코드, 비정상 숫자를 구분합니다. 내부 정밀도는 유지하고 표시 정밀도만 두 자리로 제안합니다. 부가 조회 실패가 청구 데이터를 지우지 않습니다.
- 기존 `return_code`를 유지하면서 같은 값의 `provider_return_code` 별칭을 추가했습니다. `response_profile`, `unit_basis`, `unit_conversion_divisor` 속성으로 적용 설정을 확인할 수 있습니다.
- 기존 주택용 직접계약 호환성 개선과 주택용 파서 안정성 보강, 계약 허용, 청구 경로, 엔티티 ID, 인증 및 취소 처리를 유지합니다. 명시적 과거월 조회에는 현재 사용량을 섞지 않습니다.

### 적용과 검증 범위

HACS에서 0.3.6 업데이트 후 Home Assistant를 재시작하고 한전ON 통합의 옵션에서 `종합계약: 사용자 확인 Wh 응답 사용`을 켜고 저장합니다. 업데이트만으로 이 옵션이 자동 활성화되지는 않습니다. 끄면 v0.3.5 기본 요청·단위 처리로 돌아갑니다. 통합 삭제나 sed 수정은 필요 없습니다.

실제 계정·운영 HA에는 접근하지 않았습니다. 숫자를 에너지로 해석할 근거는 해당 계정 사용자의 확인이며 모든 종합계약에 대한 공식 단위 검증은 아닙니다. 테스트에는 가상 식별자와 가상 수치만 사용합니다.
최소 Home Assistant 버전은 2026.8.3입니다.
