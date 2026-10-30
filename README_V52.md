EL SHEIKH V52
- Admin maintenance menu with explicit ON/OFF actions; non-admin Telegram messages and callback buttons blocked while off.
- Admin deposit promotion percentage 1-100; removal sets 0; deposit menu banner only when active.
- Promotional credit applied in same database transaction as deposit credit (auto and legacy admin approval paths), preserving wheel bonus separately.
- Withdrawal refund logic untouched.

Deployment: replace the existing bot files and restart Railway. Keep the same persistent DATABASE_PATH and secrets.
Caution: Telegram Mini App /wheel API is not covered by Telegram update middleware; verify its access policy separately before relying on maintenance mode to disable the wheel. Test with a non-admin account and a small deposit before production use.
