# EL SHEIKH V61 — Ichancy API only, no admin requests

- Removed all Ichancy manual account creation and admin queue actions from V60.
- No Ichancy user requests are forwarded to any admin/chat. No `/ichancy_requests` or `/ichancy_done` handlers.
- Old `ichmanual:*` callback buttons are rejected gracefully and cannot queue requests.
- Automatic creation only via documented `registerPlayer` after a read-only API preflight.
- If the API refuses a request (including Cloudflare 403), bot states that no registration was attempted and offers a retry check. There is **no bypass** for upstream 403.
- Previous database tables and account history are left intact. Existing rows in old manual table (if any) are untouched but no longer processed.
- Financial operations remain official-API-only. Unconfirmed financial transfers are marked for reconciliation to avoid duplicate charges; the bot does not auto-send Ichancy notifications to admins. Pre-existing other-bot services were not changed.

## Railway
Keep existing credentials, storage and DB; do not reset them. Required Ichancy variables:
`ICHANCY_API_BASE_URL=https://agents.ichancy.com`, `ICHANCY_CASHIER_USERNAME`, `ICHANCY_CASHIER_PASSWORD`, `ICHANCY_AGENT_ID=2836401`.
`ICHANCY_TOKEN_PATH` should be on a persistent Railway volume. Preserve existing `DATABASE_PATH` and data when deploying.

## Verification
`PYTHONPATH=. python -m unittest discover -s tests -v` and compile all `.py` files. All tests are offline/mocked. They do not prove the official API accepts connections from Railway.
