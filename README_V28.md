# Sheikh V28 — Telegram Mini App wheel

- Same dark navy/cyan wheel aesthetic, EL SHEIKH center.
- Plays bundled hardluck.mp4 (including original audio) when HARDLUCK is shown. Telegram autoplay sound may require tapping video controls.
- Every admin-approved deposit gives one spin (once per deposit, using UNIQUE deposit_id). Historical approved deposits do not grant spins automatically.
- Server determines outcomes: first 10 spins HARDLUCK, spin 11 gives 5% bonus expiring after 24 hours, repeat.
- Prize amount wedges are explicitly marked as decorative and not winnable, to avoid misleading players.
- **Important:** bonus is stored in `wheel_bonuses` and shown on the wheel. It is NOT YET applied to a subsequent deposit or shown on the deposit form; that requires a separate audited redemption integration. Do not claim bonus payout is active.
- Telegram initData HMAC verified server-side; spin balances and outcomes cannot be set by browser requests.

## Railway
Keep existing `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_PATH=/data/sheikh.db`, `WITHDRAWAL_CHAT_ID`, etc. Add:

`MINIAPP_URL=https://YOUR-PUBLIC-RAILWAY-DOMAIN/`

Set up a public Railway domain under Networking and ensure PORT is exposed. `bot.py` starts HTTP server and bot polling in one process. Deploy updated requirements and bot.py and new wheel_server.py + miniapp folder. Ensure the Railway Volume is retained. For BotFather configure the mini app domain if prompted.

## Tests required before production
- Validate channel membership, approved deposits, duplicate approvals, spin issuance, 11th spin, 24h expiry, and admin withdrawal permissions with test accounts.
- Run a separate audited integration before enabling 5% bonus redemption or real financial use.
