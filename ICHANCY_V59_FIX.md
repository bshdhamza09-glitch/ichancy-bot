# V59 — Diagnosis + safe preflight

The Agent API documentation specifies `/global/api/UserApi/signin`, `getAgentAllWallets` and `registerPlayer`, but does not provide a separate working base domain.

The user's Railway returned HTTP 403 text/html on `signin`. That indicates a network/server or Cloudflare rejection **before a documented JSON response**; it is NOT a failed account name or Agent ID. The existing configured domain matches the browser's `getData` domain, but this does not prove the UserApi endpoint is whitelisted for Railway.

Updates:
- `403` HTML includes sanitized Cloudflare Ray ID when supplied by the server; no tokens or HTML are logged.
- Normal, transparent User-Agent identifying the integration (not browser impersonation).
- Registration button performs read-only `getAgentAllWallets` preflight; does not ask for username when API is inaccessible.
- Admin command `/ichancy_check`: non-mutating API connectivity test; no secrets displayed.
- Fixed legacy reply-keyboard transfer handler signature; inline buttons still work.

Railway variables:
- `ICHANCY_API_BASE_URL`: official host that actually serves `/global/api/UserApi/` (currently `https://agents.ichancy.com`, but may be blocked; verify with provider)
- `ICHANCY_CASHIER_USERNAME`, `ICHANCY_CASHIER_PASSWORD`, `ICHANCY_AGENT_ID`
- `ADMIN_IDS`: comma-separated Telegram admin IDs

Once 403 is fixed by site operator/official API access, run `/ichancy_check`, then test a single registration with a new name. Never repeat a deposit, withdrawal, or ambiguous registration blindly.

NOT a fix for a provider-side 403; only the owner/operator can authorize server-to-server API requests. Previous exposed browser session cookies must be invalidated.
