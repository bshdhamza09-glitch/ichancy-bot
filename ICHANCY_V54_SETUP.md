# Ichancy API integration V54

This release preserves existing bot modules and adds a separate official API integration.

Railway variables:
- `ICHANCY_API_BASE_URL=https://agents.ichancy.com` (candidate; **verify with vendor**)
- `ICHANCY_CASHIER_USERNAME` and `ICHANCY_CASHIER_PASSWORD` (secrets; never commit)
- `ICHANCY_AGENT_ID` (required for registerPlayer)
- `ICHANCY_TOKEN_PATH=/data/ichancy_agent_tokens.json` if a persistent Railway volume is mounted at /data

**Implemented:** Ichancy menu, official account registration (only confirms when result=1), player balance lookup `/ichancy_balance username`, site links, token refresh with rotation and persistence. API client includes documented NSP deposit/withdraw methods for controlled integration.

**Not enabled:** automated deposits, withdrawals, full-balance actions. These buttons clearly explain they are disabled. This is intentional: the existing bot's local balance is separate from NSP, and no safe accounting/idempotency reconciliation was specified. Never automatically retry ambiguous financial API responses.

**Agent ID:** required by official registerPlayer endpoint as `parentId`. It may be discoverable from an existing player `affiliateId`, but is not guaranteed by docs.

**Important:** `agents.ichancy.com` is the provided cashier panel domain, not a confirmed API host. Verify with vendor before live operation. The generated `@saw.com` address is synthetic and might not be accepted; the vendor's policy must be checked.

No production financial transfers or live API tests were executed. Run `python -m compileall -q .` before deployment and test using a non-production account.
