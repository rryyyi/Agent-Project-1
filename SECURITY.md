# Security policy

## Supported version

The current `main` / 0.1.x line receives fixes. This is a local single-process portfolio demonstration, without authentication, tenant authorization or public-deployment hardening.

## Reporting

Use GitHub's **Security → Report a vulnerability** when private vulnerability reporting is enabled. If that option is unavailable, open an Issue containing only a request for a private reporting channel; do not post exploit details, keys, personal data or customer conversations. The maintainer will arrange a private channel. No response-time SLA is promised.

## Data and model boundaries

- API keys stay in server environment/configuration and are masked in settings representations.
- Error events store bounded categories rather than upstream response bodies.
- The browser renders conversation and evidence with `textContent`.
- A restrictive workbench CSP blocks inline scripts and dynamic evaluation.
- Runtime databases contain private conversation/checkpoint data; keep them out of Git and public backups.
- Session deletion is logical SQLite deletion, not guaranteed forensic erasure.
- Prompt instructions reduce authority confusion but do not establish complete injection resistance.
- Provider URLs are administrator-controlled. Do not expose provider configuration to end users.

Do not expose the demo publicly with real customer data. Add authentication, authorization, rate/body limits, privacy controls and distributed coordination before production use. See docs/operations.md.
