## KEPCO ON v0.2.1

### Home Assistant 로컬 브랜드 이미지

- `custom_components/kepco_on/brand/`에 한전ON 기본 아이콘과 전체 로고를 포함했습니다.
- `icon.png`는 한전ON의 빨간색 O 심볼을 사용하며 256×256 투명 PNG입니다.
- `icon@2x.png`는 512×512 고해상도 투명 PNG입니다.
- `logo.png`와 `logo@2x.png`는 전체 한전ON 로고이며 배경과 불필요한 여백을 제거했습니다.
- Home Assistant 2026.3 이상에서는 로컬 Brands Proxy API가 이 이미지를 기존 Brands CDN보다 우선 사용합니다.

센서, 로그인, 요금 계산 및 데이터 파싱 동작 변경은 없습니다.
