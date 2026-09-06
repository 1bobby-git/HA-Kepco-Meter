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


## 한전ON v0.3.6 — 종합계약 요청 복원 및 1차 진단 개선

- 사용자 성공 재현에 따라 정확히 `아파트(종합계약)`인 고객은 파워플래너에 `custNo=customer_number`, `housCntrNo=house_contract_number`, `chgYmd=""`를 전달합니다. 임의 고객번호나 추가 엔드포인트를 사용하지 않습니다.
- 이 계약의 현재 사용량 `F_AP_QT`는 사용자 보고에 근거한 Wh 프로필로 처리해 한 번만 1000으로 나눕니다. 단일계약·종합계약/나·주택용은 기존 요청 및 단위 처리를 유지합니다. 값 크기로 단위를 추측하지 않으며 서버 전체의 공통 규격으로 확정한 것은 아닙니다.
- 예측 사용량의 `PREDICT_TOT` 에너지 단위는 아직 검증되지 않았습니다. v0.3.5의 표시 보류를 유지하며, 이 릴리스가 두 센서 모두 숫자를 보장하지는 않습니다.
- 기존 `return_code`에 같은 값의 `provider_return_code` 별칭을 추가하고 `integration_version`, `request_variant`, `value_divisor`를 표시합니다. 필드 오류가 발생해도 안전하게 검증된 반환 코드를 보존합니다.
- 부가 조회 실패는 월별 청구 데이터를 중단하지 않습니다. 과거월 조회에는 현재 사용량을 섞지 않고, 인증 만료와 취소는 기존 흐름에 전달합니다. 도메인·설정·고객 및 엔티티 ID는 유지합니다.

### 적용 및 다음 확인

HACS에서 0.3.6으로 업데이트 후 Home Assistant를 재시작합니다. 통합을 삭제하거나 종합계약 허용 sed 명령을 다시 실행할 필요가 없습니다.
두 센서의 `data_status`, `return_code` 또는 `provider_return_code`, `data_status_message`, `integration_version`을 확인해 회신합니다. 속성 회신을 받은 뒤 요청 결과와 예측 단위에 관한 후속 수정을 별도 진행합니다. 비밀번호·토큰·쿠키·고객번호·원본 응답은 공개하지 마세요.

이번 변경의 근거는 사용자 재현 코드와 계정 동작 보고입니다. 실제 사용자 HA/계정에 직접 접속하거나 예측 단위를 검증하지 않았습니다. 실제 서버 미제공 값을 0이나 과거 청구량으로 대체하지 않습니다.
최소 Home Assistant 버전은 2026.8.3입니다. 문제가 생기면 HACS 재다운로드에서 0.3.5로 되돌릴 수 있습니다.


## v0.3.7: Home Assistant state-attribute publication

Inspected Core 2026.8.3 `homeassistant/helpers/entity.py`: `Entity.__async_calculate_state` merges `extra_state_attributes` only when available. The integration previously returned unavailable for every absent planner value, so its diagnosis disappeared from `hass.states` even though direct property tests passed. Optional missing fields now remain unknown while the billing snapshot is healthy. Coordinator failure, missing bills, and customer billing errors still make the entities unavailable. Requests, raw-data units, authentication and IDs are unchanged. Real EntityComponent/state-machine/template regression tests cover publication, loss and recovery.

Sources: https://github.com/home-assistant/core/blob/2026.8.3/homeassistant/helpers/entity.py and https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable/


## 한전ON v0.3.8

### 종합계약의 두 파워플래너 센서 복원

- 정확히 아파트(종합계약)에 대해 사용자가 정상 동작을 확인한 요청 조합을 유지합니다: custNo=customer_number, housCntrNo=house_contract_number, chgYmd="".
- 같은 호환 프로필에서 F_AP_QT와 PREDICT_TOT를 각각 1000으로 나누어 기존 현재/예측 사용량 센서에 전달합니다. 종합계약 예측값을 항상 None으로 버리던 처리를 제거합니다. 추가 옵션이나 템플릿 입력은 필요 없습니다.
- 변환은 사용자 재현 보고에 기반합니다. PREDICT_TOT의 물리적 의미와 단위가 한전의 모든 계약에서 같다고 확인한 것은 아니며, 공개 화면의 요금 설명과의 차이는 남아 있습니다. conversion_basis 속성에 user_reported_combined_contract를 표시합니다. 숫자가 그럴듯하다는 이유로 단위를 자동 추정하지 않습니다.
- 두 필드의 파싱과 진단을 분리합니다. 한쪽 null 또는 비정상 숫자는 다른 정상값이나 청구 데이터를 지우지 않습니다. 실제 0은 보존하고 음수, bool, NaN/Infinity는 거부합니다. 서버 실패 코드를 무시하거나 값을 조작하지 않습니다.
- HA 내부에는 나눗셈 결과 정밀도를 유지하고 표시 권장 소수점만 2자리로 지정합니다. 정상 청구 상태의 누락값은 unknown과 진단 속성을 함께 게시합니다.
- 단일계약·종합계약/나·주택용의 요청/변환/예측 정책은 유지합니다. 기존 도메인, 설정, 34개 센서 및 unique_id를 유지하고 과거월에는 현재 사용량을 섞지 않습니다. 인증 만료와 취소는 정상 전파됩니다.

### 적용과 검증 범위

HACS에서 0.3.8로 업데이트한 후 Home Assistant 전체 재시작을 수행합니다. 통합 삭제, sed 재수정, 진단값 선제 회신은 필요 없습니다. 현재 값이 없는 경우에만 개별 data_status를 확인합니다.

테스트는 합성 응답을 사용하는 파서·API·실제 HA 상태 머신·Jinja 템플릿 회귀입니다. 운영 HA와 실제 계정에는 접근하지 않았으므로 실계정에서의 완전 동작이나 한전 서버 데이터 제공을 보장하지 않습니다. 사용자 원본 응답/계정 정보/실제 사용량은 커밋하지 않습니다. 기존 기록이나 통계는 변경하지 않습니다.

문제가 생기면 HACS 재다운로드에서 0.3.7을 선택할 수 있습니다. 최소 Home Assistant 버전은 2026.8.3입니다.
