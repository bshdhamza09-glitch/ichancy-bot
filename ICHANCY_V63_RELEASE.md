# EL SHEIKH V63 — Agent API alignment

## What changed
- Removed the invented default `ICHANCY_API_BASE_URL`. The official document lists paths only
  (`/global/api/UserApi/...`), no host. Set the host Ichancy gave you for the Agent API.
- `ICHANCY_AGENT_ID` defaults to `2836401`.
- signIn uses the **agent email** (`ICHANCY_AGENT_EMAIL` / `ICHANCY_AGENT_PASSWORD`);
  old `ICHANCY_CASHIER_*` names still work as fallback.
- Token header format is NOT in the document; `Bearer` is assumed and configurable via `ICHANCY_AUTH_SCHEME`.
- Everything else (token rotation, 201+"ex" handling, no replay of money operations, NSP only,
  no admin requests, all inline buttons) is unchanged.

## Known unresolved blocker
HTTP 403 on `UserApi/signin` is a server-side refusal. Cashier login at `/global/api/User/signIn`
is a different API and does not prove the Agent API is reachable from Railway. Fix requires the
correct official host and/or IP allowance from Ichancy. No Cloudflare bypass is implemented.

## Verification
`python -m unittest discover -s tests -v` (offline, mocked). No live server test was possible.
