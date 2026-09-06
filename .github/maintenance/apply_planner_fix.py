"""Apply a narrow, checked v0.3.5 patch to the v0.3.4 source snapshot."""
from pathlib import Path

ROOT = Path.cwd()


def replace(path, old, new, count=1):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise RuntimeError(f"Unexpected source anchor: {path}")
    target.write_text(text.replace(old, new), encoding="utf-8")


parser = "custom_components/kepco_on/parser.py"
replace(parser, "import re\n", "import math\nimport re\n")
replace(parser, 'SUPPORTED_APARTMENT_CONTRACT = "아파트(단일계약)"', '''SUPPORTED_APARTMENT_CONTRACT = "아파트(단일계약)"
SUPPORTED_APARTMENT_CONTRACTS = frozenset(
    {SUPPORTED_APARTMENT_CONTRACT, "아파트(종합계약)", "아파트(종합계약/나)"}
)''')
replace(parser, 'is_supported=contract_method == SUPPORTED_APARTMENT_CONTRACT,', 'is_supported=contract_method in SUPPORTED_APARTMENT_CONTRACTS,')
replace(parser, '''                _house_contract_number=house_contract_number,
''', '''                _house_contract_number=house_contract_number,
                _change_ymd=_optional_str(row, "DC_USER_CHG_NM_YMD") or "",
''')
replace(parser, 'Only apartment single-contract customers are supported', 'Only supported apartment contracts are accepted')
replace(parser, '''def parse_power_planner(payload: dict[str, object]) -> tuple[float | None, float | None]:
    """Parse 파워플래너 현재 검침기간 누적/예측 사용량 (kWh)."""
    result = payload.get("dma_powerPlanner")
    if not isinstance(result, dict):
        return (None, None)
    return (
        _parse_float(result.get("F_AP_QT"), "current_period_usage"),
        _parse_float(result.get("PREDICT_TOT"), "predicted_usage"),
    )
''', '''def parse_power_planner_return_code(payload: dict[str, object]) -> str | None:
    """Return only a bounded numeric status, never arbitrary server text."""
    result = payload.get("dma_powerPlanner")
    if result is None:
        return None
    if not isinstance(result, dict):
        raise KepcoOnProtocolError("Power Planner result must be an object")
    code = result.get("RETURN_CD")
    if code is None or code == "":
        return None
    if not isinstance(code, str) or re.fullmatch(r"[0-9]{2}", code) is None:
        raise KepcoOnProtocolError("Power Planner RETURN_CD is invalid")
    return code


def parse_power_planner(payload: dict[str, object]) -> tuple[float | None, float | None]:
    """Parse verified energy data, retaining the legacy two-value interface.

    The public page labels PREDICT_TOT as an expected charge, not a verified
    energy quantity. Do not publish that ambiguous field as kWh.
    """
    result = payload.get("dma_powerPlanner")
    if not isinstance(result, dict):
        return (None, None)
    if parse_power_planner_return_code(payload) not in (None, "00"):
        return (None, None)
    current = _parse_float(result.get("F_AP_QT"), "current_period_usage")
    if current is not None and (not math.isfinite(current) or current < 0):
        raise KepcoOnProtocolError("current_period_usage must be finite and nonnegative")
    return (current, None)
''')
replace(parser, '    "parse_power_planner",\n', '    "parse_power_planner",\n    "parse_power_planner_return_code",\n')

models = "custom_components/kepco_on/models.py"
replace(models, '''    predicted_period_usage_kwh: float | None = None
''', '''    predicted_period_usage_kwh: float | None = None
    power_planner_status: str = "not_requested"
    power_planner_return_code: str | None = None
''')

api = "custom_components/kepco_on/api.py"
replace(api, '    parse_power_planner,\n', '    parse_power_planner,\n    parse_power_planner_return_code,\n')
replace(api, '''        return parse_bill(payload, requested_month)
''', '''        bill = parse_bill(payload, requested_month)
        # Current-period data must never be attached to an explicit historical bill.
        if requested_month is not None:
            return bill
        return await self._async_with_power_planner(bill, customer)
''')
start = (ROOT / api).read_text().index('        # 파워플래너는 부가 정보라 실패해도 청구 이력은 유지한다.')
end = (ROOT / api).read_text().index('    async def async_get_all_current_bills(', start)
old = (ROOT / api).read_text()[start:end]
replace(api, old, '''        return await self._async_with_power_planner(bill, customer)

    async def _async_with_power_planner(
        self, bill: KepcoBill, customer: KepcoCustomer
    ) -> KepcoBill:
        """Enrich a current bill without losing billing data on optional failures."""
        # MYM001D00.xml dataInit executes the planner with SI_CUST_NO before
        # replacing custNo with the apartment's CUST_NO for billing requests.
        search: dict[str, object] = {
            "schYm": "",
            "custNo": customer.house_contract_number,
            "gubun": "",
            "schChart": "12",
            "CUST_NO": "",
            "housCntrNo": "",
            "yyyymm": "",
            "searchType": "",
            "dong": "",
            "ho": "",
            "months": "",
            "chgYmd": customer.change_ymd,
        }
        try:
            payload = await self._auth.async_protected_request(
                ENDPOINT_POWER_PLANNER,
                {"dma_search": search},
                submission_id="mf_wfm_layout_sbm_powerPlanner",
            )
            code = parse_power_planner_return_code(payload)
            current, predicted = parse_power_planner(payload)
        except KepcoOnRateLimitError:
            return dataclasses.replace(bill, power_planner_status="rate_limited")
        except KepcoOnConnectionError:
            return dataclasses.replace(bill, power_planner_status="connection_error")
        except (KepcoOnProtocolError, OverflowError):
            return dataclasses.replace(bill, power_planner_status="invalid_response")
        # Authentication and cancellation errors deliberately continue to propagate.
        return dataclasses.replace(
            bill,
            current_period_usage_kwh=current,
            predicted_period_usage_kwh=predicted,
            power_planner_status="ok" if current is not None else "no_data",
            power_planner_return_code=code,
        )

''')

sensor = "custom_components/kepco_on/sensor.py"
replace(sensor, 'KepcoValueFunction = Callable[[KepcoBill, dict[str, Any]], KepcoSensorValue]\n', '''KepcoValueFunction = Callable[[KepcoBill, dict[str, Any]], KepcoSensorValue]

POWER_PLANNER_FIELDS = {
    "current_period_usage": "F_AP_QT",
    "predicted_period_usage": "PREDICT_TOT",
}
POWER_PLANNER_MESSAGES = {
    "ok": "한전 파워플래너에서 사용량을 수신했습니다.",
    "no_data": "한전 파워플래너가 해당 계약의 사용량을 제공하지 않았습니다.",
    "not_requested": "현재 검침기간 사용량을 아직 조회하지 않았습니다.",
    "rate_limited": "한전 요청 제한으로 부가 사용량 조회를 완료하지 못했습니다.",
    "connection_error": "한전 파워플래너 연결에 실패했습니다.",
    "invalid_response": "한전 파워플래너 응답을 해석하지 못했습니다.",
    "source_unit_unverified": "예측 필드의 kWh 단위가 확인되지 않아 사용량으로 표시하지 않습니다.",
}
''')
replace(sensor, '''        data = self.coordinator.data
        return (
''', '''        if self.entity_description.key in POWER_PLANNER_FIELDS and self.native_value is None:
            return False
        data = self.coordinator.data
        return (
''')
replace(sensor, '''        if bill is None:
            return {}
        offset = self.entity_description.history_month_offset
''', '''        if bill is None:
            return {}
        key = self.entity_description.key
        if key in POWER_PLANNER_FIELDS:
            status = bill.power_planner_status
            if key == "predicted_period_usage" and (
                status == "ok" or bill.power_planner_return_code == "00"
            ):
                status = "source_unit_unverified"
            # Billing dates describe a past bill, not the current planner period.
            return {
                "data_source": "kepco_power_planner",
                "source_field": POWER_PLANNER_FIELDS[key],
                "data_status": status,
                "data_status_message": POWER_PLANNER_MESSAGES.get(status, status),
                "return_code": bill.power_planner_return_code,
            }
        offset = self.entity_description.history_month_offset
''')

replace("tests/test_api_house.py", '    assert bill.predicted_period_usage_kwh == pytest.approx(636.263)', '    assert bill.predicted_period_usage_kwh is None')
p = ROOT / "tests/test_api_house.py"
t = p.read_text(); pos = t.index('            ENDPOINT_POWER_PLANNER,'); a,b=t[:pos], t[pos:]
assert b.count('"chgYmd": "202604"') == 1
p.write_text(a+b.replace('"chgYmd": "202604"','"chgYmd": "20260409"'))
replace("tests/test_parser_house.py", '    assert predicted == pytest.approx(636.263)', '    assert predicted is None')
replace("tests/test_api.py", '''        assert path == "/my/charge/pay/aptBillDetail"
''', '''        if path == "/my/memo/powerPlanner":
            assert payload is not None
            search = payload["dma_search"]
            assert isinstance(search, dict)
            assert search["custNo"] == "HOUSE"
            return {"dma_powerPlanner": {"RETURN_CD": "90"}}
        assert path == "/my/charge/pay/aptBillDetail"
''')
replace("tests/test_sensor.py", '    assert {entity.available for entity in successful} == {True}', '''    for entity in successful:
        is_planner = entity.entity_description.key in {
            "current_period_usage",
            "predicted_period_usage",
        }
        assert entity.available is not is_planner''')

for path in ["custom_components/kepco_on/const.py", "custom_components/kepco_on/manifest.json", "pyproject.toml"]:
    replace(path, '"0.3.4"', '"0.3.5"')
for path in (ROOT / "tests").glob("test_*.py"):
    text = path.read_text()
    text = text.replace('"HomeAssistant-KEPCO-ON/0.3.4"', '"HomeAssistant-KEPCO-ON/0.3.5"')
    text = text.replace('"version": "0.3.4"', '"version": "0.3.5"')
    text = text.replace('const.VERSION == "0.3.4"', 'const.VERSION == "0.3.5"')
    path.write_text(text)
replace("README.md", '- 버전: `v0.3.4`.', '- 버전: `v0.3.5`.')
p=ROOT / "README.md"; text=p.read_text()
text=text.replace('아파트/오피스텔 단일계약 및 주택용 직접계약', '아파트 단일·종합계약 및 주택용 직접계약')
text=text.replace('아파트/오피스텔 세대 단일계약 및 주택용 직접계약', '아파트 세대 단일·종합계약 및 주택용 직접계약')
text += '''

## v0.3.5: 종합계약과 파워플래너 진단

- 아파트(종합계약), 아파트(종합계약/나)를 단일계약과 같은 청구 조회 경로로 허용합니다. 종합계약 청구 동작은 사용자 보고에 근거하며 이번 작업에서 실계정으로 재검증하지 않았습니다.
- 아파트 최신 청구 조회에도 파워플래너를 연결합니다. 2026-09-06 확인한 공식 MYM001D00.xml의 dataInit처럼 custNo에는 세대계약번호 SI_CUST_NO를 사용하고 chgYmd에는 전체 계약변경일을 전달합니다. 아파트 전체 CUST_NO를 대신 보내지 않습니다.
- 현재 검침기간 누적 사용량은 F_AP_QT의 유효한 숫자만 사용합니다. RETURN_CD가 제공되면서 00 이외이면 값을 채우지 않습니다. 코드 없는 기존 응답은 숫자 유효성을 검사합니다. 90 등의 정확한 서버 원인(AMI 미지원, 데이터 지연 등)은 코드만으로 단정하지 않습니다.
- PREDICT_TOT는 공식 XML에서 예상 전기요금으로 설명되며 실제 kWh 단위가 검증되지 않았습니다. 기존의 무조건적인 kWh 매핑을 중단하고 한전 예측 사용량 엔티티의 ID는 유지합니다. 이 센서가 사용 불가로 표시되는 것은 수치 조작이나 임의 단위 변경을 막기 위한 조치입니다.
- 두 엔티티의 속성 data_status, data_status_message, return_code에서 미제공/연결 실패/요청 제한/형식 오류/단위 미확인을 구분합니다. 현재 사용량에 과거 청구월·기간을 붙이지 않습니다.
- 부가 조회가 실패해도 월별 청구 사용량·요금은 유지합니다. 인증 실패는 기존 재인증 흐름에 전달합니다. 명시적인 과거월 조회에는 현재 사용량을 섞지 않습니다.
- 서버 null을 0으로, 청구 사용량을 현재 사용량으로, 예측 요금을 예측 kWh로 대체하지 않습니다. 실제 계약에 값이 제공되는지는 업데이트 후 확인이 필요합니다.

업데이트: HACS에서 0.3.5를 내려받고 Home Assistant를 재시작합니다. 기존 통합을 삭제하거나 sed 수정을 다시 적용할 필요가 없습니다. 이 GitHub 배포는 운영 HA에 직접 설치하거나 재시작하지 않습니다.
'''
p.write_text(text)
p=ROOT / "RELEASE_NOTES.md"; old=p.read_text()
p.write_text('''## 한전ON v0.3.5

### 아파트 종합계약 및 파워플래너 개선

- 종합계약과 종합계약/나를 허용하고 기존 고객·엔티티 식별자를 유지합니다.
- 아파트 최신 청구 조회에도 파워플래너를 추가합니다. 공식 페이지의 SI_CUST_NO와 전체 계약변경일 매핑을 사용합니다.
- 현재 사용량은 유효한 F_AP_QT만 수용하며 오류 코드, null, 비정상 숫자를 구분합니다.
- PREDICT_TOT의 kWh 단위는 검증되지 않았고 공식 XML은 예상 요금으로 설명합니다. 기존 예측 사용량 ID는 보존하지만 근거 없는 에너지 수치 표시는 중단합니다.
- 부가 조회의 실패 원인을 두 센서의 속성으로 표시하고 월별 요금 조회는 유지합니다.
- 실계정의 현재 사용량 제공 여부와 예측 사용량은 이번 테스트로 보장하지 않습니다.

기존 주택용 직접계약 호환성 개선과 주택용 파서 안정성 보강을 유지합니다.
최소 Home Assistant 버전은 2026.8.3입니다.

### 이전 릴리스 기록

''' + old)
p=ROOT / "docs/PROTOCOL.md"
text=p.read_text().replace('Document review date: 2026-09-02', 'Document review date: 2026-09-06').replace('Integration version: `0.2.1`', 'Integration version: `0.3.5`')
text += '''

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
'''
p.write_text(text)
print("Applied apartment/planner patch")
