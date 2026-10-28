V40
- Main menu: "البونصات والعروض الحالية" removed, replaced by "استرداد آخر طلب سحب" (requests go to REFUND_CHAT_ID, default -1004294689688; admins approve/reject with inline buttons; approval returns the reserved amount and cancels the withdrawal).
- Wheel: HARDLUCK, BONUS 5% (deposit, 24h), CASHBACK 5% (next deposit amount, single use). 200/500/1000/2000 SYP slices are decoration only (never selected, disclosed on the page).
- Reward is given on the 11th spin (after 10 HARDLUCK), server picks bonus or cashback 50/50.
- HARDLUCK dims the whole screen, then the video plays inside the wheel circle.
- DB: new table refund_requests, new column wheel_bonuses.kind (auto-migrated).
- Env: REFUND_CHAT_ID (optional). The bot must be a member/admin of that channel.
