V40
- Main menu: "البونصات والعروض الحالية" removed, replaced by "استرداد آخر طلب سحب" (requests go to REFUND_CHAT_ID, default -1004294689688; admins approve/reject with inline buttons; approval returns the reserved amount and cancels the withdrawal).
- Wheel: HARDLUCK, BONUS 5% (deposit, 24h), CASHBACK 5% (next deposit amount, single use). 200/500/1000/2000 SYP slices are decoration only (never selected, disclosed on the page).
- Reward is given on the 11th spin (after 10 HARDLUCK), server picks bonus or cashback 50/50.
- HARDLUCK dims the whole screen, then the video plays inside the wheel circle.
- DB: new table refund_requests, new column wheel_bonuses.kind (auto-migrated).
- Env: REFUND_CHAT_ID (optional). The bot must be a member/admin of that channel.
V40.1: removed the disclosure note under the wheel; wheel now has a single HARDLUCK slice (7 slices: HARDLUCK, 200, BONUS 5%, 500, CASHBACK 5%, 1000, 2000). Server logic unchanged.

V41
- Referral screen replaced with the new text (+ referral count, link, next distribution date in Damascus time UTC+3, live countdown). Removed buttons: حالة إحالاتي / تفاصيل إحالاتي / إحصائيات متقدمة.
- Admin: new button "📤 توزيع الإحالات" (first row of the admin panel and inside the referral admin menu). Shows a preview, then pays 5% (setting referral_percent) of approved deposits made by referred users during the period to referrers with >= 3 active referrals (setting referral_min_active). Each deposit is paid once (table referral_paid_deposits). Next distribution moves forward by 10 days.
- Settings keys: referral_next_distribution, referral_last_distribution (epoch seconds). Defaults: next = 2026-10-28 19:00 Damascus.
- Existing button ids are unchanged, new buttons use their own ids.

V42
- Wheel button message: "يجب ان تشحن للحصول على لفة مجانية".
- Loyalty points exchange rebuilt: free wheel spin (60), gift code 20,000 (75), bot balance 35,000 (150), withdrawal without fee (300). Locked prizes show a lock; affordable ones are green. Costs/values editable from admin "🎁 تعديل جوائز نقاط الولاء" (settings loyalty_*).
- Fee-free withdrawal = one-time token (users.free_withdrawals); returned if the withdrawal is rejected or refunded.
- Main menu: Ichancy button uses Telegram button style "primary" (blue).

V43
- Sham Cash withdrawals (SYP and USD, measured in new SYP): max 50,000; larger amounts -> contact @Al_Basha_Ropert (shown in the prompt and in the error).
- Withdrawal requests: detailed HTML message sent ONLY to WITHDRAWAL_CHAT_ID (admins' private chats only as a last-resort fallback if the channel send fails). User confirmation message is detailed too.
- "إهداء رصيد": rewritten (Arabic digits, clear errors, balance shown, recipient notified); typed menu labels (gift transfer / gift code / message to admin) now work too.
- "تواصل معنا": support menu (bot issue / site issue / main menu) with the requested texts.
- Wheel renamed Al_Basha-ichancy (page title, header, hub, bot message).

V44
- Removed from gift-transfer text the line "التحويل نهائي ولا يمس رصيد Ichancy".
- Redeeming "سحب بدون عمولة" notifies the admin channel (ADMIN_CHAT_ID env, defaults to WITHDRAWAL_CHAT_ID).
- Fee-free withdrawal only for amounts <= free_withdraw_max (default 10,000 new SYP); larger amounts pay the admin-defined fee (withdraw_fee_percent, default 10). Token is kept if the amount is above the cap; returned on reject/refund only if it was really used (withdrawals.used_free).
- Admin panel redesigned: live summary, pending requests view, full report, "عمولة وحدود السحب" editor (fee %, free cap, Sham max), explanatory section texts, search button in users list, clearer bot on/off. Dead "العروض والبونصات" removed from the panel. Button ids are frozen (LEGACY_BUTTON_ORDER) so old menus stay valid.

V45
- NEW CURRENCY: every amount is now in the new Syrian pound (old / 100). Defaults: Syriatel 4-500, Sham max 500, free-withdraw cap 100, gift code prize 200, bot-balance prize 350, dollar rate 142.5, loyalty 1 point per 2 SYP, referral caps 5,000 / 50,000, wheel decoration slices 2/5/10/20.
- One-time automatic DB conversion at first start (users.bot_balance, ledger, deposits, withdrawals, gift codes, referral tables, amount settings). A full copy is saved next to the DB as <db>.pre_currency_<timestamp>.bak and admins get a Telegram report. Flag: settings.currency_scale='new' (never runs twice). Set SKIP_CURRENCY_MIGRATION=1 to skip.
- Cashback = compensation: 5% of the deposit, claimable only if the user loses it; user presses "طلب تعويض الكاش باك", request goes to ADMIN_CHAT_ID (default: withdrawal channel) and is paid only after admin confirms. Table cashback_claims.
- Bonus = +5% on the next deposit approved within 24h of winning.
- Winning bonus/cashback sends a message inside the bot chat (from the wheel server via Bot API).
- Fix: sham_usd withdrawals crashed when storing the Decimal exchange rate.

V46
- Reverted V45's "remove two zeros": all amounts are back to the OLD scale (Syriatel 400-50000, Sham max 50000, free-withdraw cap 10000, prizes 20000/35000, dollar 14250, 1 loyalty point per 200, caps 500000/5000000, wheel slices 200/500/1000/2000).
- The automatic conversion was removed. If a DB had already been converted by V45 (settings.currency_scale='new'), the first V46 start multiplies everything by 100 again (backup saved as <db>.pre_revert_<ts>.bak, report sent to admins, flag set to 'old', never repeats).
- Kept from V45: cashback-as-compensation flow, prize message inside the bot, sham_usd Decimal fix.

V47 (full project = everything from V43 to now)
- Prizes: gift code 200, bot balance 350 (everything else stays on the old scale). Referral caps 5,000 monthly / 500,000 total. Old defaults stored in an existing DB are updated once; admin-edited values are never touched.

Changes since V43 (all included in this zip):
 V44: detailed admin panel, pending requests, report, fee/limits editor, fee-free withdrawal only up to the cap (10,000), admin-channel notice when "سحب بدون عمولة" is redeemed.
 V45: cashback = compensation claims (admin confirms loss), bonus +5% for 24h, prize message inside the bot chat, sham_usd withdrawal fix.
 V46: removed the "remove two zeros" conversion (old scale) + automatic restore for DBs converted by V45.
 V47: prizes 200/350 and referral caps.

V48
- Admin panel is now a normal keyboard under the message box (placeholder "👮 لوحة تحكم الإدارة"), same buttons/order as the reference screenshots. Opened with /admin or the admin button.
- "➕ إضافة رصيد / ➖ خصم رصيد" now work directly (send: ID amount). "💰 توزيع أرباح الإحالات" opens the referral distribution preview.
- Extra tools (pending requests, fees & limits, loyalty, referral settings/log, content) are under the inline buttons of the "تقرير" message.
