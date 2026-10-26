# Sheikh V17

- Admin loyalty menu: grant points + edit loyalty redemption prizes. Add/edit by `points credit`, hide by `حذف points`.
- User loyalty buttons and prices are read from persistent SQLite. Redemptions are atomic and recheck prize values.
- Support: an authorized admin can **reply to the original bot message** in the configured support group; the bot forwards the reply to the requesting user. In a Telegram channel, channel post replies require channel posting permissions and may be impractical: a supergroup is recommended.
- Add bot to support group and ensure SUPPORT_CHAT_ID matches it. Replies are linked only for newly submitted support messages after this update.
- No Ichancy API integration. Other bot features have not been end-to-end tested.
