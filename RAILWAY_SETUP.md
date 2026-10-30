Railway: BOT_TOKEN, ADMIN_IDS, DATABASE_PATH=/data/sheikh.db, MINIAPP_URL=https://YOUR-APP.up.railway.app, DEPOSIT_CHAT_ID=-1004294689688, WITHDRAWAL_CHAT_ID=-1004439550155, SUPPORT_CHAT_ID=-1004401691217. Mount a persistent volume at /data. Enable public domain/HTTPS for the same Railway service on port from PORT. Deploy python bot.py. Bot must be admin in Telegram review groups/channels. Never paste BOT_TOKEN in chat.

V50 automatic deposits (API Syria):
- API_SYRIA_KEY = your API Syria key (secret; only Railway variables)
- API_SYRIA_SYRIATEL_GSM = linked receiving Syriatel Cash number/cash code (must match the bot's receiving number)
- API_SYRIA_SHAM_ADDRESS = linked receiving ShamCash address (must match the bot's receiving address)
- SHAM_ACCOUNT and SYRIATEL_ACCOUNT must match the real accounts shown to users.
- Deposit is credited only after find_tx returns found=true, matching transaction ID, amount and currency, and Syriatel destination. A found ShamCash transaction is scoped by API Syria to the linked receiving account.
- IMPORTANT: Check that API Syria transaction amounts use the same SYP denomination as the bot (new Syrian pounds). No automatic old/new currency scaling is assumed.
- Old pending manual deposit requests are preserved in DB but cannot be manually approved from old Telegram buttons; reconcile them separately before migration if needed.
- Do not deploy without a persistent database volume, valid API key, and linked accounts.
