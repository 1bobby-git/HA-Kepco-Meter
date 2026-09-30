## 한전ON v0.4.0

- 주택용 직접계약의 월별 청구액을 새로 노출합니다. `월별 사용량`(이력) 센서에 해당 월 청구액이 있으면 `amount_krw` 속성이 추가됩니다.
- `kepco_on.get_usage_history` 서비스 응답의 각 이력 항목에도 청구액이 있으면 `amount_krw` 필드가 함께 반환됩니다. 청구액이 없는 월은 기존 `month`·`usage_kwh` 형태를 그대로 유지합니다.
- 청구액은 한전ON `mainChart` 응답의 `afterMny`에서 가져오며, 기존 엔티티 ID·고유 ID·서비스 이름과 응답 구조는 모두 호환됩니다.
- 기여자 [@seojingyo](https://github.com/seojingyo)의 PR #10을 병합했습니다.
- HACS에서 `v0.4.0`으로 업데이트한 뒤 Home Assistant를 완전히 재시작하세요.
