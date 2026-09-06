"""Apply a guarded, contract-scoped v0.3.8 patch to the inspected v0.3.7 tree."""
from pathlib import Path

ROOT = Path.cwd()


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    assert text.count(old) == count, (path, "source anchor changed")
    target.write_text(text.replace(old, new), encoding="utf-8")


parser_path = "custom_components/kepco_on/parser.py"
text = (ROOT / parser_path).read_text(encoding="utf-8")
start = text.index("def parse_power_planner(\n")
end = text.index("\ndef _parse_float(", start)
new_parser = '''def parse_power_planner_value(
    payload: dict[str, object], source_field: str, *, unit_wh: bool = False
) -> float | None:
    """Read one optional quantity without guessing units from numeric magnitude."""
    field_names = {"F_AP_QT": "current_period_usage", "PREDICT_TOT": "predicted_usage"}
    if source_field not in field_names:
        raise ValueError("Unsupported Power Planner field")
    code = parse_power_planner_return_code(payload)
    result = payload.get("dma_powerPlanner")
    if not isinstance(result, dict) or code not in (None, "00"):
        return None
    field_name = field_names[source_field]
    try:
        value = _parse_float(result.get(source_field), field_name)
    except OverflowError as err:
        raise KepcoOnProtocolError(f"{field_name} is outside the numeric range") from err
    if value is not None and (not math.isfinite(value) or value < 0):
        raise KepcoOnProtocolError(f"{field_name} must be finite and nonnegative")
    return value / 1000 if value is not None and unit_wh else value


def parse_power_planner(
    payload: dict[str, object], *, current_unit_wh: bool = False, predicted_unit_wh: bool = False
) -> tuple[float | None, float | None]:
    """Keep legacy defaults; explicitly enable the reported prediction Wh profile.

    The combined-contract compatibility profile follows the user's working
    request and conversion. It is not proof of a universal KEPCO unit contract.
    Other profiles continue to leave the ambiguous prediction field unmapped.
    """
    current = parse_power_planner_value(payload, "F_AP_QT", unit_wh=current_unit_wh)
    predicted = (
        parse_power_planner_value(payload, "PREDICT_TOT", unit_wh=True)
        if predicted_unit_wh
        else None
    )
    return current, predicted

'''
(ROOT / parser_path).write_text(text[:start] + new_parser + text[end:], encoding="utf-8")
replace(parser_path, '    "parse_power_planner_return_code",\n', '    "parse_power_planner_return_code",\n    "parse_power_planner_value",\n')

api_path = "custom_components/kepco_on/api.py"
replace(api_path, "    parse_power_planner,\n", "    parse_power_planner_value,\n")
replace(api_path, "            current, predicted = parse_power_planner(payload, current_unit_wh=combined)\n", "")
replace(api_path, '''        # Authentication and cancellation errors deliberately continue to propagate.
        return dataclasses.replace(
            bill,
            current_period_usage_kwh=current,
            predicted_period_usage_kwh=predicted,
            power_planner_status="ok" if current is not None else "no_data",
            power_planner_return_code=code,
        )''', '''        # A malformed optional field must not discard the other valid field.
        # Authentication and cancellation errors deliberately continue to propagate.
        values: dict[str, float | None] = {}
        statuses: dict[str, str] = {}
        fields = ("F_AP_QT", "PREDICT_TOT") if combined else ("F_AP_QT",)
        for source_field in fields:
            try:
                value = parse_power_planner_value(payload, source_field, unit_wh=combined)
            except KepcoOnProtocolError:
                values[source_field] = None
                statuses[source_field] = "invalid_response"
            else:
                values[source_field] = value
                statuses[source_field] = "ok" if value is not None else "no_data"
        status = "no_data"
        if "invalid_response" in statuses.values():
            status = "invalid_response"
        if any(value is not None for value in values.values()):
            status = "ok"
        return dataclasses.replace(
            bill,
            current_period_usage_kwh=values.get("F_AP_QT"),
            predicted_period_usage_kwh=values.get("PREDICT_TOT"),
            power_planner_status=status,
            power_planner_return_code=code,
            power_planner_current_status=statuses.get("F_AP_QT"),
            power_planner_prediction_status=statuses.get("PREDICT_TOT"),
        )''')
replace("custom_components/kepco_on/models.py", '    power_planner_return_code: str | None = None\n', '    power_planner_return_code: str | None = None\n    power_planner_current_status: str | None = None\n    power_planner_prediction_status: str | None = None\n')

sensor_path = "custom_components/kepco_on/sensor.py"
replace(sensor_path, '''            status = bill.power_planner_status
            if key == "predicted_period_usage" and (
                status == "ok" or (status == "no_data" and bill.power_planner_return_code == "00")
            ):
                status = "source_unit_unverified"
            combined = self.customer.contract_method == COMBINED_APARTMENT_PLANNER_CONTRACT''', '''            combined = self.customer.contract_method == COMBINED_APARTMENT_PLANNER_CONTRACT
            field_status = (
                bill.power_planner_current_status
                if key == "current_period_usage"
                else bill.power_planner_prediction_status
            )
            status = field_status or bill.power_planner_status
            if field_status is None and key == "predicted_period_usage" and (
                status == "ok" or (status == "no_data" and bill.power_planner_return_code == "00")
            ):
                status = "no_data" if combined else "source_unit_unverified"''')
replace(sensor_path, '''                "value_divisor": (
                    (1000 if combined else 1) if key == "current_period_usage" else None
                ),''', '''                "value_divisor": 1000 if combined else (1 if key == "current_period_usage" else None),
                "conversion_basis": (
                    "user_reported_combined_contract" if combined else "legacy_contract_profile"
                ),''')
for key in ("current_period_usage", "predicted_period_usage"):
    old = f'''        key="{key}",
        translation_key="{key}",'''
    replace(sensor_path, old, old + '\n        suggested_display_precision=2,')

# Preserve original regression scenarios, changing only superseded expectations.
path = "tests/test_apartment_planner.py"
replace(path, '''    assert result.current_period_usage_kwh == pytest.approx(expected_current)
    assert result.predicted_period_usage_kwh is None''', '''    assert result.current_period_usage_kwh == pytest.approx(expected_current)
    if contract == "아파트(종합계약)":
        assert result.predicted_period_usage_kwh == pytest.approx(99.999)
    else:
        assert result.predicted_period_usage_kwh is None''')
replace(path, '''    assert result.current_period_usage_kwh is None
    assert result.predicted_period_usage_kwh is None
    assert result.power_planner_status == "no_data"
    assert result.usage_kwh == synthetic_bill().usage_kwh''', '''    assert result.current_period_usage_kwh is None
    assert result.predicted_period_usage_kwh == pytest.approx(99.999)
    assert result.power_planner_current_status == "no_data"
    assert result.power_planner_prediction_status == "ok"
    assert result.power_planner_status == "ok"
    assert result.usage_kwh == synthetic_bill().usage_kwh''')
replace(path, 'async def test_current_sensor_available_and_prediction_explains_unverified_unit()', 'async def test_current_sensor_available_and_missing_prediction_explains_no_data()')
replace(path, '        == "source_unit_unverified"\n', '        == "no_data"\n')
path = "tests/test_combined_planner_regression.py"
replace(path, '''    assert predicted.native_value is None
    assert predicted.available is True
    assert predicted.extra_state_attributes["data_status"] == "source_unit_unverified"
    assert current.extra_state_attributes["value_divisor"] == divisor
    assert predicted.extra_state_attributes["value_divisor"] is None''', '''    combined = contract == "아파트(종합계약)"
    if combined:
        assert predicted.native_value == pytest.approx(987.65)
    else:
        assert predicted.native_value is None
    assert predicted.available is True
    assert predicted.extra_state_attributes["data_status"] == (
        "ok" if combined else "source_unit_unverified"
    )
    assert current.extra_state_attributes["value_divisor"] == divisor
    assert predicted.extra_state_attributes["value_divisor"] == (1000 if combined else None)''')
replace(path, '        assert sensors[key].extra_state_attributes["data_status"] == "invalid_response"', '        assert sensors[key].extra_state_attributes["data_status"] == (\n            "invalid_response" if key == "current_period_usage" else "no_data"\n        )')
replace("tests/test_planner_state_publication.py", '            "source_unit_unverified"\n', '            "no_data"\n')

for path in (ROOT / "tests").glob("*.py"):
    text = path.read_text(encoding="utf-8")
    if "0.3.7" in text:
        path.write_text(text.replace("0.3.7", "0.3.8"), encoding="utf-8")
for path in ("custom_components/kepco_on/const.py", "custom_components/kepco_on/manifest.json", "pyproject.toml"):
    replace(path, '"0.3.7"', '"0.3.8"')
replace("README.md", '- 버전: `v0.3.7`.', '- 버전: `v0.3.8`.')
replace("README.md", '| 현재 검침기간 누적 사용량 | 509.783 kWh |\n| 한전 예측 사용량 | 636.263 kWh |', '| 현재 검침기간 누적 사용량 | 246.80 kWh (종합계약 호환 예시) |\n| 한전 예측 사용량 | 987.65 kWh (종합계약 호환 예시) |')
replace("README.md", '`현재 검침기간 누적 사용량`과 `한전 예측 사용량`은 주택용 직접계약의 Power Planner 응답에서 제공합니다. 값이 없는 계정에서는 `unknown`으로 표시될 수 있습니다.', '아파트(종합계약)은 사용자 재현 보고에 따른 호환 프로필로 Power Planner의 `F_AP_QT`와 `PREDICT_TOT`를 각각 1000으로 나눠 기존 두 센서에 전달합니다. 이 단위 해석은 한전 공통 규격으로 검증되지 않았으며 `conversion_basis=user_reported_combined_contract`로 명시합니다. 다른 계약의 예측값 보류는 유지합니다. 값이 없는 필드만 `unknown`이고 실제 0은 유지됩니다.')
notes = '''## 한전ON v0.3.8

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

'''
for path, prefix in (("RELEASE_NOTES.md", notes + '### 이전 릴리스 기록\n\n'), ("CHANGELOG.md", '# Changelog\n\n' + notes.replace('## 한전ON v0.3.8', '## 0.3.8 — 2026-09-06'))):
    target = ROOT / path
    old = target.read_text(encoding="utf-8")
    if path == "CHANGELOG.md":
        old = old.removeprefix('# Changelog\n\n')
    target.write_text(prefix + old, encoding="utf-8")
for path in ("README.md", "docs/PROTOCOL.md"):
    with (ROOT / path).open("a", encoding="utf-8") as stream:
        stream.write('\n\n' + notes)
path = ROOT / "docs/POWER_PLANNER_DIAGNOSTICS.md"
old = path.read_text(encoding="utf-8")
path.write_text('# 파워플래너 — v0.3.8\n\n종합계약의 현재·예측 필드는 각각 사용자 보고 기반 /1000 호환 변환을 사용합니다. `conversion_basis`는 `user_reported_combined_contract`, `value_divisor`는 두 필드 모두 1000입니다. 한 필드의 누락/오류는 다른 값에 영향을 주지 않습니다. 종합계약 이외의 예측 단위 미확인 처리는 유지합니다. 진단 회신은 설치 전제 조건이 아닙니다.\n\n## 진단 표시의 이전 변경과 템플릿\n\n' + old, encoding="utf-8")
for path in ("README.md", "CHANGELOG.md", "RELEASE_NOTES.md", "docs/PROTOCOL.md", "docs/POWER_PLANNER_DIAGNOSTICS.md"):
    target = ROOT / path
    target.write_text(target.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
