<!-- project-branding:start -->
<p align="center">
  <img src="https://raw.githubusercontent.com/1bobby-git/brands/master/custom_integrations/kepco_on/logo%402x.png" alt="한전ON 로고" width="420">
</p>
<p align="center">
  <a href="https://github.com/1bobby-git/HA-Kepco-Meter/stargazers"><img src="https://img.shields.io/github/stars/1bobby-git/HA-Kepco-Meter?style=flat-square&logo=github&label=Stars" alt="GitHub Stars"></a>
  <a href="https://github.com/1bobby-git/HA-Kepco-Meter/releases"><img src="https://img.shields.io/github/v/release/1bobby-git/HA-Kepco-Meter?style=flat-square&label=Release" alt="Latest Release"></a>
  <a href="https://github.com/1bobby-git/HA-Kepco-Meter/blob/main/custom_components/kepco_on/manifest.json"><img src="https://img.shields.io/badge/Architecture-independent-0ea5e9?style=flat-square" alt="Architecture independent"></a>
  <a href="https://github.com/1bobby-git/HA-Kepco-Meter/blob/main/LICENSE"><img src="https://img.shields.io/github/license/1bobby-git/HA-Kepco-Meter?style=flat-square&label=License" alt="License"></a>
  <a href="https://github.com/1bobby-git/HA-Kepco-Meter/commits/main"><img src="https://img.shields.io/github/last-commit/1bobby-git/HA-Kepco-Meter?style=flat-square&label=Updated" alt="Last Commit"></a>
</p>
<!-- project-branding:end -->

# 한전ON Home Assistant 커스텀 통합

한전ON 개인(`INDI`) 계정의 아파트/오피스텔 단일계약 및 주택용 직접계약 전기요금 조회를 Home Assistant 센서와 응답 액션으로 가져오는 비공식 커스텀 통합입니다. 실시간 스마트미터가 아니라 한전ON 청구/검침 페이지에서 확인되는 월별 요금 데이터 기반입니다.

Repository: https://github.com/1bobby-git/HA-Kepco-Meter

## 현재 범위

- 지원: 한전ON 개인 계정(`INDI`), 아파트/오피스텔 세대 단일계약 및 주택용 직접계약 요금.
- 미지원: 법인 계정, 전기공사업체 계정, 인증서 로그인, OACX 간편인증 자동화, CAPTCHA/MFA 우회, CO2 실측값. Power Planner 값은 실시간 스마트미터 값이 아닙니다.
- 통신: `https://online.kepco.co.kr`의 고정된 한전ON 경로만 사용하며 TLS 검증을 끄지 않습니다.
- 버전: `v0.3.1`. 선택 고객마다 5개 논리 기기와 34개 센서 엔티티를 생성합니다.

## 설치

### HACS 커스텀 저장소

1. HACS > Integrations > 우측 메뉴 > Custom repositories.
2. 저장소 URL에 `https://github.com/1bobby-git/HA-Kepco-Meter` 입력.
3. Category는 Integration 선택.
4. `한전ON (KEPCO ON)` 설치 후 Home Assistant를 재시작.

### 수동 설치

`custom_components/kepco_on` 폴더를 Home Assistant 설정 디렉터리의 `/config/custom_components/kepco_on`에 복사한 뒤 Home Assistant를 재시작합니다. `/config`는 File editor 애드온, Samba share, SSH 애드온, 또는 호스트에 마운트된 설정 디렉터리로 접근할 수 있습니다. 재시작 후 통합 목록이 오래된 상태로 보이면 브라우저 캐시를 지우고 다시 열어 보세요.

## 설정

설정 > 기기 및 서비스 > 통합 추가 > KEPCO ON을 선택합니다.

1. 한전ON 아이디와 비밀번호를 입력합니다.
2. 자동 재인증이 필요하면 `비밀번호 저장`을 켭니다.
3. 조회할 고객을 선택합니다. 아파트/오피스텔은 아파트명·동·호를, 주택용 직접계약은 계약 유형과 마스킹된 고객번호를 표시합니다.

`비밀번호 저장`을 끄면 비밀번호는 저장하지 않습니다. 재시작/세션 복구를 위해 refresh token과 최소 세션 식별 정보는 private Home Assistant Store에 저장됩니다. `0.2.2`의 `PERSISTED_COOKIE_ALLOWLIST`는 비어 있으므로 `JSESSIONID`와 `WMONID` 값은 저장하지 않습니다. 저장된 세션이 만료되면 재인증이 필요할 수 있습니다.

이 통합은 Config Entry, Store, 백업을 자체 암호화하지 않습니다. 비밀번호 저장 여부와 관계없이 Home Assistant 호스트, `.storage`, 백업 파일을 비밀 저장소처럼 보호하세요.

## 생성되는 기기와 센서

선택한 고객마다 다음 5개 논리 기기와 총 34개 센서 엔티티를 생성합니다. 모든 센서는 기본 활성 상태입니다. 한전ON에서 값이 제공되지 않으면 해당 엔티티는 `unknown`으로 표시될 수 있습니다.

통합 허브 제목은 `1001동 101호`(가상 예시)처럼 선택 세대 위치로 표시하고, 하위 기기 이름은 `월별 사용량`, `검침/전기사용량`, `전기요금`, `이웃 전기사용량 비교`, `온실가스 배출량`으로만 표시합니다. 동·호의 앞자리 0은 표시 단계에서 제거합니다. 사용자가 설정 과정에서 별도 표시 이름을 입력한 경우에는 해당 이름을 유지합니다.

### 월별 사용량 · 6개

현재 청구월을 기준으로 최근 3개월과 전년 같은 기간 3개월을 함께 제공합니다. 엔티티의 고유 ID는 상대 월 위치를 사용하므로 청구월이 바뀌어도 엔티티가 새로 누적되지 않고 표시 이름만 갱신됩니다.

| 표시 예시 | 값 예시 |
| --- | ---: |
| 2025년 6월 | 399 kWh |
| 2026년 6월 | 371 kWh |
| 2025년 7월 | 459 kWh |
| 2026년 7월 | 406 kWh |
| 2025년 8월 | 612 kWh |
| 2026년 8월 | 573 kWh |

### 검침/전기사용량 · 12개

| 센서 | 값 예시 |
| --- | ---: |
| 전기 사용 기간 시작일 | 2026-07-01 |
| 전기 사용 기간 종료일 | 2026-07-31 |
| 검침일 | 01 |
| 당월지침 | 23,139 kWh |
| 전월지침 | 22,566 kWh |
| 당월 사용량 | 573 kWh |
| 당월 세대 사용량 | 573 kWh |
| 당월 공용 사용량 | 0 kWh |
| 전월 사용량 | 406 kWh |
| 전년동월 사용량 | 612 kWh |
| 현재 검침기간 누적 사용량 | 509.783 kWh |
| 한전 예측 사용량 | 636.263 kWh |

`검침일`, `전기 사용 기간 시작일`, `전기 사용 기간 종료일`은 Home Assistant 기기 페이지의 `센서 정보` 영역에 표시하고, 나머지 9개 엔티티는 `센서` 영역에 표시합니다.

한전ON이 `당월 세대 사용량`과 `당월 공용 사용량`을 모두 비워서 반환하면 전체 사용량을 세대 사용량으로, 공용 사용량을 `0 kWh`로 보정합니다. 한쪽 또는 양쪽의 실제 값이 있으면 한전ON 원본 값을 우선 사용하고 필요한 한쪽만 전체 사용량과의 차이로 계산합니다.

`현재 검침기간 누적 사용량`과 `한전 예측 사용량`은 주택용 직접계약의 Power Planner 응답에서 제공합니다. 값이 없는 계정에서는 `unknown`으로 표시될 수 있습니다.

### 전기요금 · 10개

| 센서 | 값 예시 |
| --- | ---: |
| 전기요금 계 | 85,484 KRW |
| 전기요금 상세 기본요금 | 6,060 KRW |
| 전기요금 상세 전력량요금 | 87,402 KRW |
| 전기요금 상세 기후환경요금 | 5,157 KRW |
| 전기요금 상세 연료비조정요금 | 2,865 KRW |
| 전기요금 상세 출산가구할인요금 | -16,000 KRW |
| 부가가치세 | 8,548 KRW |
| 전력기금 | 2,300 KRW |
| 원단위절사금액 | 2 KRW |
| 청구금액 | 96,330 KRW |

Home Assistant 기기 화면은 기기 이름과 같은 일반 공백 접두어를 엔티티 이름에서 자동 생략할 수 있습니다. `v0.2.2`부터 전기요금 엔티티는 위 표의 전체 이름이 그대로 표시되도록 처리합니다.

금액 센서는 Home Assistant의 monetary device class 규칙에 맞춰 ISO 4217 통화 코드 `KRW`를 사용합니다. 위 기후환경요금 예시는 저장소의 한전ON 응답 샘플에 포함된 실제 값 `5,157원`을 기준으로 합니다.

### 이웃 전기사용량 비교 · 3개

| 센서 | 값 예시 |
| --- | ---: |
| 고객님 | 573 kWh |
| 해당동 | 363 kWh |
| 아파트 전체 | 284 kWh |

### 온실가스 배출량 · 3개

| 센서 | 값 예시 |
| --- | ---: |
| 당월 배출량 | 263 kg CO₂ |
| 전월 배출량 | 186 kg CO₂ |
| 전년동월 배출량 | 281 kg CO₂ |

온실가스 값은 한전ON 실측값이 아니라 각 전기사용량에 설정된 환산계수를 곱한 로컬 추정값입니다. 기본 환산계수는 `0.459 kg CO₂/kWh`입니다.

엔티티 ID는 Home Assistant가 설치 환경의 이름 충돌 상태에 따라 정합니다. 고객별 고유 ID에는 원본 고객번호나 계약번호 대신 계정·고객 정보로 만든 안정 해시를 사용합니다.

## Energy Dashboard

Energy Dashboard에는 `당월지침` 센서를 전력 사용량 소스로 추가합니다. 이 센서는 누적 검침값이며 `total_increasing` 상태 클래스를 사용합니다. 월별 사용량과 비교 사용량 센서는 한 달 단위 값이므로 누적 소스로 사용하지 않습니다.

## 옵션, 업그레이드, 재인증, 재구성

옵션에서 조정할 수 있는 값은 조회 주기, 온실가스 환산계수, 사용량 이력 응답 길이입니다. 조회 주기는 1·3·6·12·24시간 중 선택하며 기본값은 6시간입니다. 환산계수는 0보다 크고 10 이하이며 기본값은 `0.459`입니다. 이력 응답 길이는 1~24개월이며 기본값은 12개월입니다.

`v0.1.x`에서 업그레이드하면 기존 주요 엔티티의 고유 ID를 유지하면서 5개 기기로 재배치합니다. `v0.2.0`에서 `v0.2.1`로 업그레이드하면 기존 엔티티 ID와 unique ID를 유지하면서 허브와 하위 기기 이름만 정리하고, 검침일·시작일·종료일을 `센서 정보` 영역으로 이동합니다. 과거 통합 기본값 때문에 비활성화된 상세 엔티티는 자동으로 활성화하고, 사용자가 직접 비활성화한 엔티티는 그대로 둡니다. 더 이상 사용하지 않는 `청구월` 단독 엔티티와 상세/CO₂ 생성 토글 옵션은 마이그레이션 과정에서 정리됩니다. `v0.2.1`에서 `v0.2.2`로 업그레이드하면 전기요금 기기의 10개 엔티티가 표의 전체 이름으로 표시됩니다. 기존 엔티티 ID와 unique ID는 유지됩니다. `v0.3.1`부터 주택용 직접계약과 Power Planner 센서 2개를 지원하며 기존 아파트/오피스텔 엔티티 고유 ID는 유지됩니다. 업데이트 후 Home Assistant Core를 완전히 재시작하세요.

재인증은 기존 계정의 비밀번호만 다시 받습니다. 다른 한전ON 계정으로 로그인되면 항목 업데이트가 거절됩니다.

재구성은 선택 고객을 갱신합니다. 통합이 로드된 상태면 한전ON에서 고객 목록을 새로 받아오고, 실패하면 저장된 고객 목록을 기준으로 선택 화면을 엽니다. 선택에서 빠진 고객의 엔티티와 이 통합만 소유한 5개 논리 기기는 정리됩니다.

## 응답 액션

`kepco_on.get_monthly_bill`은 한 고객의 청구 상세를 반환합니다. 아파트/오피스텔은 지정 월을 조회하고, 주택용 직접계약은 한전ON `mainChart`의 최신 청구 이력을 사용합니다.

```yaml
action: kepco_on.get_monthly_bill
data:
  config_entry_id: !secret kepco_on_config_entry_id
  customer_id: !secret kepco_on_customer_id
  month: "202608"
response_variable: kepco_bill
```

`kepco_on.get_usage_history`는 선택 고객의 월별 사용량 이력을 반환합니다. `month`를 비우면 현재 코디네이터가 가진 최신 청구 데이터를 우선 사용합니다.

```yaml
action: kepco_on.get_usage_history
data:
  config_entry_id: !secret kepco_on_config_entry_id
  customer_id: !secret kepco_on_customer_id
response_variable: kepco_history
```

`config_entry_id`는 개발자 도구 > 액션 또는 자동화 시각 편집기에서 `config_entry_id` 선택기를 열고 KEPCO ON 항목을 선택하면 Home Assistant가 채웁니다. 수동 YAML에 넣어야 할 때는 선택기로 항목을 고른 뒤 YAML 보기로 전환해 생성된 ID를 복사하세요.

`customer_id`는 원본 한전 고객번호가 아니라 통합이 생성한 64자 안정 해시 키입니다. 가장 신뢰할 수 있는 확인 경로는 Settings > Devices & Services > KEPCO ON 항목 > 점 세 개 메뉴 > Download diagnostics에서 진단 파일을 내려받은 뒤 `selected_customer_ids` 값을 복사하는 것입니다. 이 값은 응답 액션에 필요한 안전 식별자이며 원본 한전 고객번호나 계약번호가 아닙니다. 그래도 공개 이슈나 자동화 예제에 올릴 필요는 없습니다. 진단 다운로드가 어려운 환경에서는 Settings > Devices & Services > Entities에서 KEPCO ON 센서 엔티티 설정을 열고 entity registry의 unique ID 앞 64자를 확인하는 방법을 fallback으로 사용할 수 있습니다.

## 자동화 예시

```yaml
alias: 한전ON 월 사용량 알림
triggers:
  - trigger: time
    at: "09:00:00"
conditions:
  - condition: template
    value_template: "{{ now().day == 1 }}"
actions:
  - action: kepco_on.get_usage_history
    data:
      config_entry_id: !secret kepco_on_config_entry_id
      customer_id: !secret kepco_on_customer_id
    response_variable: usage_history
  - action: notify.mobile_app_phone
    data:
      message: "한전ON 최근 이력: {{ usage_history.history | count }}개월"
```

## 문제 해결

- 로그인 실패: 한전ON 웹에서 같은 계정으로 직접 로그인되는지 확인합니다. CAPTCHA, MFA, OACX 등 조건부 챌린지가 나오면 이 통합은 우회하지 않습니다.
- 세션 만료: 비밀번호 저장을 껐거나 저장된 refresh token/session이 만료되면 재인증이 필요합니다. `0.2.2`에서도 `JSESSIONID`/`WMONID` 값을 저장하지 않습니다.
- 고객 없음: 이 통합은 개인 아파트 세대 계약만 지원합니다.
- 일부 세대만 unavailable: 한 세대의 청구 조회 실패는 다른 세대 센서와 분리됩니다.
- 월 조회 실패: 응답 액션의 `month`는 `YYYYMM`이고 현재월보다 미래이거나 최근 24개월 범위 밖이면 거절됩니다.
- 프로토콜 변경 수리 이슈: 한전ON 응답 구조가 바뀌면 원본 응답 없이 안전한 오류 분류만 수리 이슈로 표시됩니다.
- `login bootstrap content type changed`가 보이는 경우: 기존 `v0.1.0` 또는 오래된 설치본에서 로그인 bootstrap 응답을 지나치게 엄격하게 검사했을 수 있습니다. HACS에서 `v0.1.1` 이상으로 업데이트한 뒤 Home Assistant를 완전히 재시작하고, 설치된 통합 버전이 `0.1.1` 이상인지 확인한 다음 다시 설정하세요.

설치된 매니페스트 버전 확인:

```bash
cat /config/custom_components/kepco_on/manifest.json
```

과거 로그인 bootstrap 오류 검색:

```bash
grep -F "login bootstrap content type changed" /config/home-assistant.log* 2>/dev/null
```

문제가 계속되면 공개 이슈에는 비밀번호, 쿠키, 토큰, 원본 고객번호, 계약번호, HAR, raw capture를 올리지 마세요. 공유 가능한 자료는 검토 후 민감값을 지운 로그와 `login-schema.safe.json`뿐입니다.

## 안전한 로그인 스키마 캡처

개발자가 한전ON 로그인 스키마 변경을 확인해야 할 때만 사용합니다. 이 도구는 원본 요청/응답 본문, 헤더, 쿠키, HAR, trace, screenshot을 저장하지 않고 안전 메타데이터만 `login-schema.safe.json`에 씁니다. 해당 파일은 Git에서 무시됩니다.

```powershell
npm run capture:login-schema
```

도구는 임시 Chrome 프로필을 만들고 사용자가 직접 정상 로그인하도록 기다립니다. CAPTCHA, MFA, OACX를 자동화하거나 우회하지 않습니다. 종료 시 OS 임시 폴더 아래의 도구 전용 프로필만 삭제합니다.

## 삭제

Home Assistant에서 통합 항목을 삭제하면 이 통합이 소유한 항목이 제거됩니다. Home Assistant 백업, `.storage`, 로그, 외부 비밀 파일에 남은 비밀번호나 세션 정보는 별도 보관 정책에 따라 직접 관리해야 합니다.

## 릴리스 체크

릴리스는 `main`의 Tests가 성공하고 같은 커밋의 HACS/Hassfest 검증까지 성공한 경우에만 자동 생성됩니다. 매니페스트 버전 `0.2.2`, Git 태그 `v0.2.2`, GitHub 릴리스 제목과 `kepco_on-v0.2.2.zip` 자산을 일치시킵니다.

## 라이선스

[MIT License](LICENSE)를 따릅니다.

## English Summary

This is an unofficial Home Assistant custom integration for KEPCO ON individual apartment billing. It exposes monthly billing sensors and response actions, not real-time meter telemetry. Store credentials only if you accept Home Assistant storage and backup risk.
