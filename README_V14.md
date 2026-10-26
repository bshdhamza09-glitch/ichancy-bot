# Sheikh V14 — Referral notifications fix

- On first /start with `?start=ref_<id>`, the new user is bound to a valid existing referrer.
- After channel membership is verified, the referrer gets a Telegram message naming the new referral and showing the count.
- On first verification via channel button, the notification also fires.
- `referral_notifications` SQLite table prevents repeat notices; failed deliveries are retried when the new user starts again.
- Keep DATABASE_PATH=/data/sheikh.db and persistent Railway Volume to retain data.
- If the user already opened the bot before using a referral link, Telegram will not reassign them.
- This is not an Ichancy API integration. Site-level financial stats still require verified site data.
- Other sections were not end-to-end tested; do not assume every existing button works.
