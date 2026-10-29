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
