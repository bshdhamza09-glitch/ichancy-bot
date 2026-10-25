# Sheikh Telegram Bot — Railway

This version uses **ReplyKeyboardMarkup** to fill the chat keyboard area (Telegram decides actual button sizes). The admin panel is accessed by `/admin` and only IDs listed in `ADMIN_IDS` can open it.

## Railway
1. Upload the contents of this folder to a GitHub repository.
2. Create a Railway service from the repository; `railway.json` starts `python bot.py`.
3. Set Railway Variables: `BOT_TOKEN`, `BOT_NAME=Sheikh`, `ADMIN_IDS` (comma-separated Telegram numeric IDs).
4. For persistent storage, attach a Railway Volume and set `DATABASE_PATH=/data/sheikh.db` (adjust `/data` to your volume mount). Without a volume, SQLite data may be lost on redeploy.
5. Deploy and send `/start` to the bot. Admin sends `/admin`.

## Features
- Main reply keyboard arranged like reference, plus Loyalty Points.
- Admin keyboard arranged like screenshots.
- Working local loyalty points grants, reward creation, claim requests, manual approval/rejection with refund on rejection, and audit log.
- Working user lookup, user counts, banning, broadcast, bonuses text and bot enable/disable.
- Other admin buttons are intentionally **placeholders** until requirements are clarified. In particular, no fake Ichancy API, cash deposits, withdrawals, cashback, gift code or automatic prize transfer is implemented.
- Claim approval records an admin decision only. It does **not** issue a financial transfer. Do not approve until prize fulfillment is verified separately.

## Security
Never put the agent password, Bot Token, or API tokens in source code or GitHub. Use Railway secret variables. Only operations explicitly documented by Ichancy Agent API should ever be automated. Use PostgreSQL or a persistent volume before production.
