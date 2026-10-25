# Railway setup
Deploy from GitHub. Configure `BOT_TOKEN`, `BOT_NAME`, `ADMIN_IDS`. Add a persistent volume mounted at `/data` and `DATABASE_PATH=/data/sheikh.db`. Use one bot worker/replica with long polling. Restart deployment after updating variables.
