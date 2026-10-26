# Sheikh Bot V9 — manual deposits and channel membership

## New
- Gift code redemption accepts `CODESHEIKH` or short `CODE` (appends SHEIKH), validates single redemption per user and code use limit.
- Required channel membership before accessing bot features. Bot must be an **administrator** in @IchancyElSheikh so `getChatMember` can reliably check other users.
- ShamCash and Syriatel Cash manual deposit flows: show payment details, collect amount and transaction reference, collect ShamCash sender wallet identifier and displayed holder name, send pending request to review chat/admins, approve/reject with protected buttons, notify user.
- ShamCash QR image included. First sender wallet is recorded as verified **only after admin approval**. The bot **cannot independently read the sender wallet from the QR, screenshot or ShamCash API**. Admin must verify sender identity, currency, amount and receipt against actual incoming funds BEFORE approving.
- Balances are INTERNAL BOT BALANCES, not Ichancy. Ichancy buttons remain disabled.

## Railway
1. Upload all contents of this folder to GitHub.
2. Set BOT_TOKEN, ADMIN_IDS (comma-separated Telegram numeric IDs), DATABASE_PATH=/data/sheikh.db.
3. Mount a persistent Railway Volume at `/data`; deploy only one polling worker.
4. Set REQUIRED_CHANNEL=@IchancyElSheikh; add bot as admin of that channel.
5. Set DEPOSIT_CHAT_ID=-1004294689688 (the provided numeric Telegram chat ID) of the deposit review channel and add the bot as an admin with posting rights. The provided name `AdminIchancyEl-Sheikh` contains a hyphen, which is not a valid public Telegram username; do not assume `@AdminIchancyEl-Sheikh` works. Use numeric ID.
6. Optional SHAM_ACCOUNT and SYRIATEL_ACCOUNT.
7. Verify a gift code and both deposit methods using small, non-production test values. Do not approve a deposit without checking the payment provider separately.

## Important limits
- User-supplied transfer reference and sender wallet details are unverified claims; Telegram Bot API cannot confirm ShamCash/Syriatel transfers.
- The screenshot QR is for the merchant's destination wallet, **not** proof of the customer's sender wallet. The sender wallet/holder are collected from the user and verified by a human.
- The `getChatMember` call may fail if the bot is not channel admin. Access is denied in that case.
- Other pre-existing V8 buttons remain at their previous implementation level. Some are informational/placeholders; they have not all been verified end-to-end.
- This is a test build; protect credentials and back up the database.
