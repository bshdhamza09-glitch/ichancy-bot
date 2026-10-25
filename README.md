# Sheikh Bot V5 — nested admin menus

- Main inline keyboard has no admin entry. `/admin` opens the admin panel for authorized Telegram numeric IDs only.
- Two admins: Railway `ADMIN_IDS=111111111,222222222` (replace with real IDs; comma-separated, no spaces necessary).
- Admin menus are grouped into Users, Offers, Loyalty, Settings, Reports, Codes, Referrals, Broadcast.
- Users submenu: search, history, add/deduct balance (placeholders, **not live financial transfers**), ban/unban, back.
- Submenu navigation edits the menu message in place; action prompts may send additional messages.
- Loyalty points are local, and approval does not transfer Ichancy funds.
- All live Ichancy operations are disabled pending validated integration and authorization.
- Database: SQLite; configure a Railway persistent volume or migrate to PostgreSQL before production.
- Never commit real tokens or agent credentials.
