# Security and Privacy

This integration handles KEPCO ON credentials, account identifiers, customer numbers, contract numbers, session tokens, and cookies. Treat Home Assistant configuration storage and backups as sensitive.

## Stored Data

| Location | Data | Notes |
| --- | --- | --- |
| Config entry | Username, `save_password` flag, optional password, display name, account hash, selected customer hashes, selected raw customer and house contract IDs | Raw IDs are stored only because KEPCO ON bill requests require them. They are not used as entity IDs. |
| Private Home Assistant Store | Refresh token, optional token, session identity fields, cookie snapshot | Home Assistant Store files are not a secret vault. Backups can contain this data. |
| One-time handoff | Initial login session payload under `CONF_SESSION_HANDOFF` | Setup consumes this into Store and removes it from entry data. Code anchor: `__init__.py:81`, `__init__.py:97`. |
| Diagnostics | Redacted summaries only | Secret canaries are covered by tests. |

## Threat Boundaries

- The integration never disables TLS verification.
- The integration never accepts a user-supplied KEPCO host.
- Browser automation is not part of the Home Assistant integration.
- The safe capture tool is a developer-only one-time schema tool and is not an integration requirement.
- CAPTCHA, MFA, OACX, certificate login, and other interactive challenges are not automated or bypassed.
- Logs, diagnostics, repairs, entity states, entity attributes, device identifiers, and fixtures must not expose passwords, tokens, cookies, raw customer numbers, contract numbers, names, addresses, phone numbers, or emails.

## Safe Capture Procedure

Use `npm run capture:login-schema` only for protocol maintenance. The tool:

- Prompts for username and masked password, or accepts one-time `KEPCO_LOGIN_SCHEMA_USERNAME` and `KEPCO_LOGIN_SCHEMA_PASSWORD` environment variables with a warning.
- Creates a temporary Chrome profile under the OS temp directory with the `kepco-login-schema-` prefix.
- Opens installed Chrome through Playwright and waits for the user to complete normal login.
- Observes only `/cyb/me/login/indi/api`, `/me/login/firstLogin/check`, `/sessionCheck`, and `/ssoCheck`.
- Writes only `login-schema.safe.json`, which is ignored by Git.
- Records endpoint, method, safe submission id, JSON key paths/types/string lengths/null flags/credential-pattern booleans, status, content type, sensitive-field names and lengths, and success/failure code field names.
- Refuses to write when the serialized output contains the exact username/password canaries or suspicious secret-shaped values.
- Deletes only the validated temp profile path in `finally`.

Do not attach raw HAR, trace, screenshot, cookie export, request body, response body, or browser profile to an issue.

## Issue Reporting

When reporting protocol changes, include:

- Integration version and commit SHA.
- Home Assistant version.
- Safe error category or repair issue title.
- `login-schema.safe.json` only after reviewing that it contains no raw values.
- Relevant timestamps and which endpoint category changed.

Do not include raw identifiers or account details. If a maintainer needs live reproduction, perform it in a protected local environment and share only the safe capture output.

## Host and Backup Protection

Protect the Home Assistant host, `.storage`, backups, terminal scrollback, shell history, and any external secret manager. If password storage is enabled, rotate the KEPCO ON password after suspected backup or host exposure. Remove stale `login-schema.safe.json` files after protocol review.
