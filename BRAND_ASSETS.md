# Local brand assets

This integration ships its Home Assistant brand images in:

```text
custom_components/kepco_on/brand/
```

Included files:

- `icon.png` — 256×256 transparent PNG using the KEPCO ON O symbol
- `icon@2x.png` — 512×512 transparent PNG
- `logo.png` — transparent KEPCO ON horizontal logo
- `logo@2x.png` — high-density transparent horizontal logo

Home Assistant 2026.3 and later serves these files through the local Brands Proxy API. The integration-local assets take precedence over legacy CDN assets.
