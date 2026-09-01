# 한전ON Home Assistant 커스텀 통합

한전ON 개인(`INDI`) 계정의 아파트 세대 전기요금 조회를 Home Assistant 센서와 응답 액션으로 가져오는 비공식 커스텀 통합입니다. 실시간 스마트미터가 아니라 한전ON 청구/검침 페이지에서 확인되는 월별 요금 데이터 기반입니다.

Repository: https://github.com/1bobby-git/HA-Kepco-Meter

## 현재 범위

- 지원: 한전ON 개인 계정(`INDI`), 아파트/오피스텔 세대 단일 계약 요금.
- 미지원: 법인 계정, 전기공사업체 계정, 인증서 로그인, OACX 간편인증 자동화, CAPTCHA/MFA 우회, Power Planner 실시간 사용량, CO2 실측값.
- 통신: `https://online.kepco.co.kr`의 고정된 한전ON 경로만 사용하며 TLS 검증을 끄지 않습니다.
- 버전: 통합 매니페스트 버전은 `0.1.0`입니다. 정식 릴리스 전에는 태그와 HACS 릴리스 패키지를 별도로 검증해야 합니다.

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
3. 조회할 아파트 세대를 선택합니다. 선택 화면에는 개인정보 보호를 위해 아파트명, 동, 호만 표시됩니다.

`비밀번호 저장`을 끄면 Config Entry에는 비밀번호만 저장하지 않습니다. 다만 재시작/세션 복구를 위해 refresh token, 세션 식별 정보, 그리고 라이브 검증으로 필요성이 입증된 쿠키 스냅샷은 private Home Assistant Store에 저장될 수 있습니다. 만료되면 재인증이 필요할 수 있습니다.

이 통합은 Config Entry, Store, 백업을 자체 암호화하지 않습니다. 비밀번호 저장 여부와 관계없이 Home Assistant 호스트, `.storage`, 백업 파일을 비밀 저장소처럼 보호하세요.

## 생성되는 센서

기본 활성 센서:

| 키 | 한전ON/파서 출처 | 단위 | 기기/상태 클래스 | 기본값 |
| --- | --- | --- | --- | --- |
| `monthly_usage` | 월 사용량 | `kWh` | energy / 없음 | 활성 |
| `meter_reading` | 현재 누적 검침값 | `kWh` | energy / `total_increasing` | 활성 |
| `amount_due` | 청구 금액 | `KRW` | monetary / 없음 | 활성 |
| `previous_month_usage` | 전월 사용량 | `kWh` | energy / 없음 | 활성 |
| `last_year_same_month_usage` | 전년 동월 사용량 | `kWh` | energy / 없음 | 활성 |
| `building_average_usage` | 동 평균 사용량 | `kWh` | energy / 없음 | 활성 |
| `apartment_average_usage` | 단지 평균 사용량 | `kWh` | energy / 없음 | 활성 |

상세 센서는 기본 비활성입니다. 옵션에서 상세 센서를 켜면 새 엔티티는 활성 기본값으로 생성되고, 기존에 통합 기본값 때문에 비활성화된 상세 엔티티는 활성화됩니다.

| 키 | 한전ON/파서 출처 | 단위 | 기기/상태 클래스 | 기본값 |
| --- | --- | --- | --- | --- |
| `previous_meter_reading` | 이전 누적 검침값 | `kWh` | energy / 없음 | 비활성 |
| `billing_month` | 청구월 | 없음 | 없음 / 없음 | 비활성 |
| `usage_period_start` | 사용기간 시작일 | 없음 | date / 없음 | 비활성 |
| `usage_period_end` | 사용기간 종료일 | 없음 | date / 없음 | 비활성 |
| `meter_reading_day` | 검침일 | 없음 | 없음 / 없음 | 비활성 |
| `electricity_subtotal` | 전기요금 소계 | `KRW` | monetary / 없음 | 비활성 |
| `base_charge` | 기본요금 | `KRW` | monetary / 없음 | 비활성 |
| `energy_charge` | 전력량요금 | `KRW` | monetary / 없음 | 비활성 |
| `climate_environment_charge` | 기후환경요금 | `KRW` | monetary / 없음 | 비활성 |
| `fuel_adjustment_charge` | 연료비조정요금 | `KRW` | monetary / 없음 | 비활성 |
| `child_discount` | 할인 금액 | `KRW` | monetary / 없음 | 비활성 |
| `vat` | 부가세 | `KRW` | monetary / 없음 | 비활성 |
| `power_industry_fund` | 전력산업기반기금 | `KRW` | monetary / 없음 | 비활성 |
| `rounding_amount` | 절사/반올림 금액 | `KRW` | monetary / 없음 | 비활성 |

선택 옵션 센서:

| 키 | 출처 | 단위 | 기기/상태 클래스 | 기본값 |
| --- | --- | --- | --- | --- |
| `co2_estimate` | 월 사용량 x 사용자 지정 `kg/kWh` 계수 | `kg` | 없음 / 없음 | 생성 안 함 |

CO2 값은 한전ON에서 내려주는 실측 배출량이 아니라 로컬 추정치입니다.

엔티티 ID는 Home Assistant가 설치 환경의 이름 충돌 상태에 따라 정합니다. 고객별 고유 ID도 원본 고객번호가 아니라 계정/고객 정보를 해시한 안정 키이므로 환경마다 다를 수 있습니다.

## Energy Dashboard

Energy Dashboard에는 기본 활성 `검침값` 센서를 전력 사용량 소스로 추가합니다. 이 센서는 누적 검침값이며 `total_increasing` 상태 클래스를 사용합니다. 월 사용량과 비교 사용량 센서는 월별 값이므로 Energy Dashboard 누적 소스로 쓰지 않습니다.

## 옵션, 재인증, 재구성

옵션에서 조정할 수 있는 값:

- 조회 주기: 1, 3, 6, 12, 24시간 중 선택. 기본값은 6시간입니다.
- 상세 센서 생성/활성화.
- CO2 추정 센서와 계수. 기본 계수는 `0.459 kg/kWh`, 허용 범위는 `0.001` 초과부터 `10` 이하입니다.
- 사용량 이력 응답 길이: 1~24개월. 기본값은 12개월입니다.

재인증은 기존 계정의 비밀번호만 다시 받습니다. 다른 한전ON 계정으로 로그인되면 항목 업데이트가 거절됩니다.

재구성은 선택 고객을 갱신합니다. 통합이 로드된 상태면 한전ON에서 고객 목록을 새로 받아오고, 실패하면 저장된 고객 목록을 기준으로 선택 화면을 엽니다. 선택에서 빠진 고객의 이 통합 소유 엔티티와 단독 기기는 정리됩니다.

## 응답 액션

`kepco_on.get_monthly_bill`은 지정 월의 한 고객 청구 상세를 반환합니다.

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
- 세션 만료: 비밀번호 저장을 껐거나 저장된 refresh token/session/cookie가 만료되면 재인증이 필요합니다.
- 고객 없음: 이 통합은 개인 아파트 세대 계약만 지원합니다.
- 일부 세대만 unavailable: 한 세대의 청구 조회 실패는 다른 세대 센서와 분리됩니다.
- 월 조회 실패: 응답 액션의 `month`는 `YYYYMM`이고 현재월보다 미래이거나 최근 24개월 범위 밖이면 거절됩니다.
- 프로토콜 변경 수리 이슈: 한전ON 응답 구조가 바뀌면 원본 응답 없이 안전한 오류 분류만 수리 이슈로 표시됩니다.

## 안전한 로그인 스키마 캡처

개발자가 한전ON 로그인 스키마 변경을 확인해야 할 때만 사용합니다. 이 도구는 원본 요청/응답 본문, 헤더, 쿠키, HAR, trace, screenshot을 저장하지 않고 안전 메타데이터만 `login-schema.safe.json`에 씁니다. 해당 파일은 Git에서 무시됩니다.

```powershell
npm run capture:login-schema
```

도구는 임시 Chrome 프로필을 만들고 사용자가 직접 정상 로그인하도록 기다립니다. CAPTCHA, MFA, OACX를 자동화하거나 우회하지 않습니다. 종료 시 OS 임시 폴더 아래의 도구 전용 프로필만 삭제합니다.

## 삭제

Home Assistant에서 통합 항목을 삭제하면 이 통합이 소유한 항목이 제거됩니다. Home Assistant 백업, `.storage`, 로그, 외부 비밀 파일에 남은 비밀번호나 세션 정보는 별도 보관 정책에 따라 직접 관리해야 합니다.

## 릴리스 체크

릴리스 태그는 매니페스트 `version`, Git 태그, GitHub 릴리스 제목을 일치시킨 뒤 생성합니다. HACS 커스텀 저장소 설치, Hassfest, Home Assistant 실제 로드, HAOS 재시작 복구, 라이브 한전ON 로그인/요금 조회는 아직 최종 릴리스 증거로 수행되지 않았습니다.

## 라이선스

[MIT License](LICENSE)를 따릅니다.

## English Summary

This is an unofficial Home Assistant custom integration for KEPCO ON individual apartment billing. It exposes monthly billing sensors and response actions, not real-time meter telemetry. Store credentials only if you accept Home Assistant storage and backup risk.
