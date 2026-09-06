"""Prepare the scoped v0.3.6 patch against the inspected v0.3.5 commit."""
from pathlib import Path

ROOT = Path('.')

def replace_once(filename, old, new):
    path = ROOT / filename
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'Expected exactly one patch anchor in {filename}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

component = 'custom_components/kepco_on/'
replace_once(component + 'const.py', 'VERSION = "0.3.5"', 'VERSION = "0.3.6"')
replace_once(component + 'const.py', 'CONFIG_ENTRY_VERSION = 3\n', '''CONFIG_ENTRY_VERSION = 3
# Scope the user-reported request and Wh conversion to the exact tested contract.
COMBINED_APARTMENT_PLANNER_CONTRACT = "아파트(종합계약)"
''')
replace_once(component + 'const.py', '    "CONFIG_ENTRY_VERSION",', '    "COMBINED_APARTMENT_PLANNER_CONTRACT",\n    "CONFIG_ENTRY_VERSION",')
replace_once(component + 'manifest.json', '"version": "0.3.5"', '"version": "0.3.6"')
replace_once('pyproject.toml', 'version = "0.3.5"', 'version = "0.3.6"')
replace_once(component + 'api.py', '    BASE_URL,', '    BASE_URL,\n    COMBINED_APARTMENT_PLANNER_CONTRACT,')
replace_once(component + 'api.py', '''        # MYM001D00.xml dataInit executes the planner with SI_CUST_NO before
        # replacing custNo with the apartment's CUST_NO for billing requests.
        search: dict[str, object] = {''', '''        # The combined-contract account was reported to work with both IDs.
        # Keep the v0.3.5 request for other contracts pending separate evidence.
        combined = customer.contract_method == COMBINED_APARTMENT_PLANNER_CONTRACT
        search: dict[str, object] = {''')
replace_once(component + 'api.py', '            "custNo": customer.house_contract_number,', '''            "custNo": customer.customer_number if combined else customer.house_contract_number,''')
replace_once(component + 'api.py', '''            "chgYmd": customer.change_ymd,
        }
        try:''', '''            "chgYmd": "" if combined else customer.change_ymd,
        }
        if combined:
            search["housCntrNo"] = customer.house_contract_number
        code: str | None = None
        try:''')
replace_once(component + 'api.py', '            current, predicted = parse_power_planner(payload)', '            current, predicted = parse_power_planner(payload, current_unit_wh=combined)')
replace_once(component + 'api.py', '''        except KepcoOnProtocolError, OverflowError:
            return dataclasses.replace(bill, power_planner_status="invalid_response")''', '''        except KepcoOnProtocolError, OverflowError:
            return dataclasses.replace(
                bill, power_planner_status="invalid_response", power_planner_return_code=code
            )''')
replace_once(component + 'parser.py', '''def parse_power_planner(payload: dict[str, object]) -> tuple[float | None, float | None]:''', '''def parse_power_planner(
    payload: dict[str, object], *, current_unit_wh: bool = False
) -> tuple[float | None, float | None]:''')
replace_once(component + 'parser.py', '''    energy quantity. Do not publish that ambiguous field as kWh.
''', '''    energy quantity. Do not publish that ambiguous field as kWh.
    current_unit_wh is explicitly selected only for the reported combined-contract
    profile; never infer units from a value's magnitude or integer/float type.
''')
replace_once(component + 'parser.py', '    return (current, None)', '''    if current is not None and current_unit_wh:
        current /= 1000
    return (current, None)''')
replace_once(component + 'sensor.py', 'from .const import DEFAULT_CO2_FACTOR_KG_PER_KWH, DOMAIN, OPT_CO2_FACTOR_KG_PER_KWH, PAGE_URL', '''from .const import (
    COMBINED_APARTMENT_PLANNER_CONTRACT,
    DEFAULT_CO2_FACTOR_KG_PER_KWH,
    DOMAIN,
    OPT_CO2_FACTOR_KG_PER_KWH,
    PAGE_URL,
    VERSION,
)''')
replace_once(component + 'sensor.py', '''                status == "ok" or bill.power_planner_return_code == "00"
''', '''                status == "ok" or (status == "no_data" and bill.power_planner_return_code == "00")
''')
replace_once(component + 'sensor.py', '''            # Billing dates describe a past bill, not the current planner period.
            return {''', '''            combined = self.customer.contract_method == COMBINED_APARTMENT_PLANNER_CONTRACT
            # Billing dates describe a past bill, not the current planner period.
            return {''')
replace_once(component + 'sensor.py', '''                "return_code": bill.power_planner_return_code,
''', '''                "return_code": bill.power_planner_return_code,
                "provider_return_code": bill.power_planner_return_code,
                "integration_version": VERSION,
                "request_variant": (
                    "apartment_customer_and_contract" if combined else "household_and_change_date"
                ),
                "value_divisor": (
                    (1000 if combined else 1) if key == "current_period_usage" else None
                ),
''')
replace_once('tests/test_apartment_planner.py', 'test_latest_apartment_planner_uses_household_id_and_full_change_date', 'test_latest_apartment_planner_uses_contract_specific_request')
replace_once('tests/test_apartment_planner.py', '''                    "custNo": "TEST_HOUSEHOLD",
''', '''                    "custNo": "TEST_BUILDING" if contract == "아파트(종합계약)" else "TEST_HOUSEHOLD",
''')
replace_once('tests/test_apartment_planner.py', '''                    "housCntrNo": "",
''', '''                    "housCntrNo": "TEST_HOUSEHOLD" if contract == "아파트(종합계약)" else "",
''')
replace_once('tests/test_apartment_planner.py', '''                    "chgYmd": "20260409",
''', '''                    "chgYmd": "" if contract == "아파트(종합계약)" else "20260409",
''')
replace_once('tests/test_apartment_planner.py', '''    assert result.current_period_usage_kwh == pytest.approx(123.45)
''', '''    expected_current = 0.12345 if contract == "아파트(종합계약)" else 123.45
    assert result.current_period_usage_kwh == pytest.approx(expected_current)
''')
replace_once('tests/test_apartment_planner.py', '''    assert result.current_period_usage_kwh == pytest.approx(float(str(value).replace(",", "")))
''', '''    assert result.current_period_usage_kwh == pytest.approx(float(str(value).replace(",", "")) / 1000)
''')
# Only version expectations change in these existing tests; none are removed.
for name in ('test_api.py', 'test_auth.py', 'test_diagnostics.py', 'test_scaffold.py'):
    path = ROOT / 'tests' / name
    text = path.read_text(encoding='utf-8')
    if '0.3.5' not in text:
        raise RuntimeError(f'Missing version assertion in {name}')
    path.write_text(text.replace('0.3.5', '0.3.6'), encoding='utf-8')
replace_once('README.md', '- 버전: `v0.3.5`.', '- 버전: `v0.3.6`.')
notes = '''## 한전ON v0.3.6 — 종합계약 요청 복원 및 1차 진단 개선

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
'''
path = ROOT / 'RELEASE_NOTES.md'
path.write_text(notes + '\n### 이전 릴리스 기록\n\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
path = ROOT / 'README.md'
with path.open('a', encoding='utf-8') as handle:
    handle.write('\n\n' + notes)
path = ROOT / 'CHANGELOG.md'
text = path.read_text(encoding='utf-8')
if not text.startswith('# Changelog\n'):
    raise RuntimeError('Unexpected changelog header')
path.write_text(text.replace('# Changelog\n', '# Changelog\n\n' + notes + '\n', 1), encoding='utf-8')
path = ROOT / 'docs/PROTOCOL.md'
with path.open('a', encoding='utf-8') as handle:
    handle.write('\n\n' + notes)
