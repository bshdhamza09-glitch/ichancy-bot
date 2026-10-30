# V50 — API Syria automatic deposits

- ShamCash SYP/USD and Syriatel Cash: selecting a method asks directly for transaction ID (3–30 digits).
- Removed deposit copy and “completed transfer” buttons; removed financial transfers from withdrawal menu.
- Automatic API Syria `find_tx` verification; real credited amount comes from verified transaction, not user input.
- For ShamCash USD, bot uses configured `dollar_rate` to convert verified USD to local SYP balance.
- No manual deposit approval; legacy review buttons are disabled. Existing pending deposit records remain untouched.
- Transaction IDs are unique per payment method; credit, bonus, loyalty points and spin award happen in a single SQLite transaction.
- Network/API errors do not masquerade as "not found"; key is read from Railway env.
- Not live-tested: requires the owner's valid API key, linked receiving accounts, and a test payment.
- Please ensure old pending deposits are reconciled before switching off manual review.

See `RAILWAY_SETUP.md` for variables.
