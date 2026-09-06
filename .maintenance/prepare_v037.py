"""Prepare a narrowly scoped diagnostic visibility fix on inspected v0.3.6."""
from pathlib import Path


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise SystemExit(f"Unexpected source in {path}: expected {count} matches")
    file.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    "custom_components/kepco_on/sensor.py",
    '        if self.entity_description.key in POWER_PLANNER_FIELDS and self.native_value is None:\n            return False\n',
    '        # A valid bill snapshot can have missing optional planner values.\n'
    '        # Keep those states unknown so Home Assistant publishes their diagnostics;\n'
    '        # unavailable entities lose extra_state_attributes in Entity state writing.\n',
)
for name in ("tests/test_apartment_planner.py", "tests/test_combined_planner_regression.py"):
    file = Path(name)
    text = file.read_text(encoding="utf-8")
    # Only the two planner-specific test modules change this assertion. General
    # coordinator, missing-bill and per-customer failure tests remain unchanged.
    if text.count(".available is False") != 2:
        raise SystemExit(f"Unexpected planner availability assertions: {name}")
    file.write_text(text.replace(".available is False", ".available is True"), encoding="utf-8")
replace_exact(
    "tests/test_apartment_planner.py",
    "test_planner_unavailable_reason_does_not_disable_monthly_sensors",
    "test_missing_planner_reason_does_not_disable_monthly_sensors",
)
version_paths = [
    "custom_components/kepco_on/const.py",
    "custom_components/kepco_on/manifest.json",
    "pyproject.toml",
    "tests/test_api.py",
    "tests/test_auth.py",
    "tests/test_diagnostics.py",
    "tests/test_scaffold.py",
    "tests/test_combined_planner_regression.py",
]
for name in version_paths:
    file = Path(name)
    text = file.read_text(encoding="utf-8")
    if "0.3.6" not in text:
        raise SystemExit(f"Missing version marker: {name}")
    file.write_text(text.replace("0.3.6", "0.3.7"), encoding="utf-8")
replace_exact("README.md", "- 버전: `v0.3.6`.", "- 버전: `v0.3.7`.")
notes = """## 한전ON v0.3.7

### 파워플래너 진단 속성이 사라지는 문제 수정

- 0.3.5와 0.3.6은 파워플래너 값이 None이면 available=False를 반환했습니다. Home Assistant Core 2026.8.3의 Entity 상태 기록은 unavailable일 때 extra_state_attributes를 생략하므로 source_field, data_status, 반환 코드가 실제 상태/템플릿에서 사라졌습니다.
- 청구 데이터 조회가 성공한 고객은 부가 파워플래너 값이 없더라도 상태를 unknown으로 유지하여 진단 속성을 함께 표시합니다. 값이나 응답 코드를 만들어 채우지 않습니다. 숫자가 0이면 정상적인 0으로 유지합니다.
- 코디네이터 전체 조회 실패, 고객별 청구 실패, 청구 스냅샷 없음은 기존처럼 unavailable입니다. 이 경우의 속성 생략은 HA 기본 동작입니다.
- 0.3.6의 종합계약 요청 매핑과 F_AP_QT /1000 변환은 유지합니다. 주택용/다른 계약, 인증 및 재시도, 엔티티 ID/수/설정은 변경하지 않습니다.
- PREDICT_TOT를 예측 kWh로 강제 매핑하지 않습니다. 단위 미확인 표시는 유지하며 이번 수정은 예측 사용량 숫자를 확보했다는 뜻이 아닙니다.
- 직접 Python 속성만 검사하던 기존 테스트에 더해 실제 HA EntityComponent, hass.states, Jinja 템플릿으로 상태/속성 발행과 실패/복구를 검증합니다.

### 적용

HACS에서 0.3.7로 업데이트하고 Home Assistant를 재시작합니다. 통합 삭제나 sed 재수정은 필요 없습니다. 두 파워플래너 센서의 integration_version이 0.3.7인지 확인합니다. source_field가 없을 때도 이름으로 찾을 수 있는 템플릿은 docs/POWER_PLANNER_DIAGNOSTICS.md에 있습니다.
숫자가 계속 없으면 state, data_status, return_code/provider_return_code, data_status_message를 회신합니다. 비밀번호, 토큰, 쿠키, 고객번호를 공개하지 마세요.

운영 HA와 실제 사용자 계정에는 접속하지 않았으며 실제 서버 응답이나 예측 단위는 이번 변경에서 검증하지 않았습니다. 최소 Home Assistant 버전은 2026.8.3입니다. 문제가 생기면 HACS 재다운로드에서 0.3.6으로 되돌릴 수 있습니다.

"""
file = Path("RELEASE_NOTES.md")
file.write_text(notes + "### 이전 릴리스 기록\n\n" + file.read_text(encoding="utf-8"), encoding="utf-8")
replace_exact(
    "CHANGELOG.md", "# Changelog\n", "# Changelog\n\n## 0.3.7 — 2026-09-06\n\n"
    "- 파워플래너의 누락값을 unavailable로 처리하여 HA가 진단 속성을 숨기던 문제 수정.\n"
    "- 청구 스냅샷이 정상인 경우 unknown 상태에서도 source_field와 상태/반환 코드를 발행.\n"
    "- 실제 HA 상태 머신과 템플릿을 검사하는 회귀 테스트 추가.\n"
    "- 0.3.6 요청/단위 변환 및 예측값 단위 미확인 정책 유지.\n",
)
with Path("README.md").open("a", encoding="utf-8") as file:
    file.write("\n\n## v0.3.7: 진단 속성 표시 복구\n\n"
               "0.3.5/0.3.6에서는 값이 없는 파워플래너 센서를 unavailable로 표시해 HA가 사용자 정의 속성을 숨겼습니다. "
               "청구 조회가 정상인 경우 이제 누락값은 unknown으로 표시하고 진단 속성은 유지합니다. "
               "전체/고객별 청구 조회 실패는 기존처럼 unavailable입니다. 숫자 생성이나 예측 단위 확정은 하지 않았습니다.\n\n"
               "[상태 확인 템플릿과 해석](docs/POWER_PLANNER_DIAGNOSTICS.md). "
               "0.3.7 업데이트 후 Home Assistant를 재시작하며 통합 재등록은 필요 없습니다.\n")
with Path("docs/PROTOCOL.md").open("a", encoding="utf-8") as file:
    file.write("\n\n## v0.3.7: Home Assistant state-attribute publication\n\n"
               "Inspected Core 2026.8.3 `homeassistant/helpers/entity.py`: "
               "`Entity.__async_calculate_state` merges `extra_state_attributes` only when available. "
               "The integration previously returned unavailable for every absent planner value, so its diagnosis disappeared "
               "from `hass.states` even though direct property tests passed. Optional missing fields now remain unknown "
               "while the billing snapshot is healthy. Coordinator failure, missing bills, and customer billing errors "
               "still make the entities unavailable. Requests, raw-data units, authentication and IDs are unchanged. "
               "Real EntityComponent/state-machine/template regression tests cover publication, loss and recovery.\n\n"
               "Sources: https://github.com/home-assistant/core/blob/2026.8.3/homeassistant/helpers/entity.py "
               "and https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable/\n")
