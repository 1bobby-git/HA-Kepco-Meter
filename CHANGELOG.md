# Changelog

## Unreleased

- 주택용 직접계약의 월별 청구액(`mainChart` `afterMny`)을 `월별 사용량` 센서의 `amount_krw` 속성과 `get_usage_history` 응답의 `amount_krw` 필드로 노출했습니다. 청구액이 없는 월은 기존과 같은 형태를 유지합니다.

## 0.3.2

- 주택용 직접계약 고객 행에 `CUST_NO`와 `SI_CUST_NO`가 함께 포함되어도 계약 유형(`주택용*`)을 우선해 주택용으로 인식하도록 호환성을 개선했습니다.
- 주택용 고객 식별은 계속 `SI_CUST_NO`를 기준으로 하므로 기존 주택용 고객의 안정 식별 규칙은 유지됩니다.
- PR #7의 경계 케이스 테스트를 포함해 주택용 파서 회귀 검증을 강화했습니다.
- 기여자 [@seojingyo](https://github.com/seojingyo)의 PR #7 테스트 기여를 기록했습니다.

## 0.3.1

- 주택용 직접계약과 Power Planner 사용량 센서를 지원했습니다.
