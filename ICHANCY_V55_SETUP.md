# V55 – Ichancy official API integration

Variables in Railway:

- `ICHANCY_API_BASE_URL=https://agents.ichancy.com` (candidate host; confirm with provider)
- `ICHANCY_CASHIER_USERNAME` (cashier email)
- `ICHANCY_CASHIER_PASSWORD` (cashier password)
- `ICHANCY_AGENT_ID` (official agent ID, required for registerPlayer)
- `DATABASE_PATH` (persistent Railway volume path; essential for balance, operations, and ownership)
- `ICHANCY_TOKEN_PATH` (persistent volume path for refresh token; keep private)

Financial transfers use only documented `depositToPlayer` and `withdrawFromPlayer`, NSP, moneyStatus 5. They require explicit user confirmation. Deposits debit the bot's NSP ledger before sending; withdrawals credit the bot ledger only after success. Accounts eligible for withdrawal must have been created through this bot. Existing external accounts require a separate ownership-verification process.

No automatic retry on ambiguous results. On timeout or ambiguous response the operation stays `needs_review`; admins must verify on Ichancy and use `/ichancy_review`, then `/ichancy_resolve ID completed` or `/ichancy_resolve ID not_executed`. **Do not guess.** If Railway loses the DB, financial reconciliation cannot be trusted. Use one bot instance and one persistent DB, and do not run multiple replicas of the same cashier session.

The API document does NOT provide an endpoint to discover a new cashier's own Agent ID. `registerPlayer` requires `parentId`; registration stays blocked until a verified ID is configured. API host is not proven by the document. No live payment or sign-in test has been performed.

Security: keep all secrets in Railway; never commit them to GitHub. Treat account creation email `@saw.com` as a placeholder, not a deliverable mailbox. Before going live, use a verified permitted domain and test with a dedicated cashier account.
