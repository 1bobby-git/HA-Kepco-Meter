# 파워플래너 — v0.3.8

종합계약의 현재·예측 필드는 각각 사용자 보고 기반 /1000 호환 변환을 사용합니다. `conversion_basis`는 `user_reported_combined_contract`, `value_divisor`는 두 필드 모두 1000입니다. 한 필드의 누락/오류는 다른 값에 영향을 주지 않습니다. 종합계약 이외의 예측 단위 미확인 처리는 유지합니다. 진단 회신은 설치 전제 조건이 아닙니다.

## 진단 표시의 이전 변경과 템플릿

# 파워플래너 진단 — v0.3.7

## source_field가 없었던 이유

0.3.5/0.3.6은 값이 없으면 두 파워플래너 엔티티를 unavailable로 만들었습니다. Home Assistant Core는 unavailable일 때 extra_state_attributes를 상태에 기록하지 않습니다. 따라서 unit_of_measurement, device_class, friendly_name만 보일 수 있으며, 이는 업데이트 미적용이나 센서 삭제의 증거가 아닙니다.

0.3.7은 청구 조회가 성공한 상태에서 부가 사용량만 없는 경우 unknown과 진단 속성을 함께 발행합니다. 전체 또는 고객별 청구 조회 자체가 실패하면 unavailable 처리는 유지됩니다. 값 0, 미제공 null, 오류를 서로 바꾸지 않습니다. 실제 계정의 수치나 에너지 단위를 새로 검증한 버전이 아닙니다.

## 적용

HACS에서 0.3.7을 내려받고 Home Assistant를 재시작합니다. 통합 삭제·재등록이나 sed 재수정은 필요 없습니다. 파일의 manifest.json 버전과 센서 속성 integration_version을 비교하면 설치 파일과 실행 중인 코드의 버전 차이를 구분하는 데 도움이 됩니다.

## 확인 템플릿

HA 개발자 도구의 템플릿에서 실행합니다. source_field가 없는 이전 상태도 사용자에게 안내된 한글 센서명으로 찾습니다. 이름을 직접 바꾼 경우에는 기기 화면에서 해당 엔티티 ID를 찾아 상태를 확인합니다. 아래 예시는 실제 반환 코드를 임의로 채우지 않습니다.

```jinja
{% for s in states.sensor
   if s.attributes.get('source_field') in ['F_AP_QT', 'PREDICT_TOT']
   or '한전 예측 사용량' in s.name
   or '현재 검침기간 누적 사용량' in s.name %}
{{ s.name }}
entity_id = {{ s.entity_id }}
state = {{ s.state }}
integration_version = {{ s.attributes.get('integration_version', '속성 없음') }}
data_status = {{ s.attributes.get('data_status', '속성 없음') }}
return_code = {{ s.attributes.get('return_code', '속성 없음') }}
provider_return_code = {{ s.attributes.get('provider_return_code', '속성 없음') }}
data_status_message = {{ s.attributes.get('data_status_message', '속성 없음') }}
request_variant = {{ s.attributes.get('request_variant', '속성 없음') }}
value_divisor = {{ s.attributes.get('value_divisor', '속성 없음') }}

{% else %}
대상 센서를 찾지 못했습니다. 기기 화면에서 해당 센서의 실제 엔티티 ID를 확인하세요.
{% endfor %}
```

## 해석

- unknown + data_status: 해당 값은 없지만 청구 스냅샷과 진단은 확보했습니다.
- no_data: 유효한 사용량이 제공되지 않았습니다. 반환 코드의 상세 원인은 별도 근거 없이 추정하지 않습니다.
- source_unit_unverified: 예측 필드의 kWh 단위를 확정하지 못해 표시를 보류했습니다. 수신값을 임의로 채우지 않습니다.
- connection_error / rate_limited / invalid_response: 부가 요청의 실패 종류입니다. 청구 조회가 정상이라면 진단은 보이고 월별 센서는 유지됩니다.
- unavailable: 코디네이터 또는 해당 고객의 청구 조회 실패, 청구 스냅샷 누락을 먼저 확인합니다. 이때 HA가 진단 속성을 생략할 수 있습니다.

공개 회신에는 위 상태·진단 항목만 포함합니다. 토큰, 쿠키, 비밀번호, 고객번호, 원본 요청/응답은 공유하지 않습니다.

## 변경하지 않은 동작

0.3.6의 정확한 아파트(종합계약) 요청 매핑과 F_AP_QT /1000 변환을 유지합니다. 단일계약, 종합계약/나, 주택용과 PREDICT_TOT의 단위 미확인 정책은 유지합니다. 엔티티 ID와 34개 센서 구성은 바뀌지 않습니다.
