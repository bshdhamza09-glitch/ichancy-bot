# Sheikh Bot V7 — local-first

Telegram aiogram 3 bot, inline keyboard for both public and admin menus. All balances, gift codes, loyalty points and transfers are LOCAL only; **no Ichancy API connection**.

## Working features
- `/start` menu; `/admin` restricted to comma-separated `ADMIN_IDS`; `/balance`; `/cancel`.
- User listing, search by Telegram ID or username, user profile, ban/unban, local credit/debit, transaction history, points.
- Loyalty rewards and requests, admin review and refund on rejection.
- Gift codes and redemption, local balance gifting between registered users, referral link and count.
- Broadcast, support messages, editable bonus text and configurable informational sections and links, bot pause, simple reports, admin settings.

## Limits / pending integrations
- Ichancy login, agent wallet, game balance, deposit/withdraw and external services are **not connected**.
- Cash payment, cash-back settlement, weekly scheduled referral payout, automatic rewards, real payment codes, jackpot/spins and external transaction burning are **not implemented**. Some admin settings store descriptive/configuration values only.
- Telegram inline buttons cannot fill the entire width of the chat viewport.
- SQLite must be stored on a Railway persistent volume (`DATABASE_PATH=/data/sheikh.db`) or replaced with PostgreSQL before production. Two replicas must NOT share this SQLite DB.
- Admin actions involving money should be confirmed with the owner before use; this is a prototype, not production-grade financial accounting.

## Setup
1. Python 3.11+, `pip install -r requirements.txt`
2. Set `BOT_TOKEN`, `ADMIN_IDS=111,222`, `BOT_NAME=Sheikh`, `DATABASE_PATH`.
3. `python bot.py`
4. Railway start command: `python bot.py`; use one instance only.
5. For faster `/start`, welcome GIF is disabled by default. Set `SEND_WELCOME_GIF=1` to enable.

## Security
Do not put agent passwords or bot tokens in GitHub. Use Railway Variables. Avoid enabling any external money movements until official API documentation, permissions, idempotency and reconciliation are implemented.

## V8 — gift code wizard and account notifications
- Admin > Codes > Add code: enter English name, automatically append `SHEIKH`, then amount and number of users.
- Existing gift code redemption remains local to the bot.
- User receives a private Telegram message for admin balance credit/debit, loyalty points grants, and ban/unban changes.
- If the user has blocked the bot or never opened it, Telegram cannot deliver the notification; this is logged.
- No Ichancy API integration or real financial movement.
