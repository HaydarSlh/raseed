# Raseed Operations Runbook

Operational procedures for the Raseed platform. See `docs/DESIGN.md` for
architecture and `SECURITY.md` for security procedures.

---

## Startup

### Fresh clone

```bash
git clone https://github.com/HaydarSlh/raseed.git
cd raseed
cp .env.example .env          # fill in production values
docker compose up -d          # starts all default services
```

Default services: `postgres`, `redis`, `minio`, `vault`, `backend`, `modelserver`,
`worker`, `frontend`.

### Health check

```bash
# All services should be healthy within ~3 minutes
docker compose ps

# Verify API is reachable
curl http://localhost:8000/health
```

### Seed demo data (optional)

```bash
DATABASE_URL=postgresql+asyncpg://raseed:<password>@localhost:5432/raseed \
  python scripts/seed_demo.py
```

---

## Secret rotation

All secrets resolve from **HashiCorp Vault** at startup. To rotate:

1. Update the secret in Vault at the configured path (`vault_secret_path` in `.env`):

   ```bash
   vault kv put secret/raseed jwt_secret="new-secret-value"
   ```

2. Restart the backend service to pick up the new value:

   ```bash
   docker compose restart backend
   ```

3. Existing JWT tokens signed with the old secret will be invalid after the restart.
   Users will need to log in again.

**JWT secret** — stored at `secret/raseed.jwt_secret`. Rotate if the secret is
compromised. All active sessions are invalidated immediately on restart.

**LLM API key** (Gemini/Grok) — stored at `secret/raseed.gemini_api_key` and
`secret/raseed.grok_api_key`. Rotate independently; the adapter will use the new
key on the next request after restart.

**Database password** — changing requires updating both Vault and the Postgres user:

```bash
# 1. Update Postgres
docker compose exec postgres psql -U postgres \
  -c "ALTER USER raseed PASSWORD 'new-password';"

# 2. Update Vault
vault kv patch secret/raseed database_password="new-password"

# 3. Restart services that hold connections
docker compose restart backend worker
```

---

## Retraining

### Trigger a retrain manually

```bash
# Start the trainer (heavy image; off the default profile)
docker compose --profile training up -d trainer

# Enqueue a retrain job
docker compose exec backend python -c "
from app.infra.queue import get_queue
q = get_queue('training')
q.enqueue('workers.retrain.run_retrain', job_timeout=3600)
print('Retrain job enqueued:', q.job_ids[-1])
"
```

### Monitor the retrain job

```bash
# Watch RQ job status
docker compose exec worker rq info --url redis://redis:6379

# Check trainer logs
docker compose logs -f trainer
```

### Champion/challenger gate

After the trainer completes, the gate is evaluated automatically by
`training/gate_holdout.py`. If the challenger beats the champion:

```bash
# A Slack alert will fire with the run_id.
# To promote manually:
curl -X POST http://localhost:8000/retrain/<run_id>/promote \
  -H "Authorization: Bearer <operator-jwt>"
```

If the challenger loses or ties the gate, promotion is blocked. The champion stays.

---

## Erasure (Right-to-Erasure)

A user can delete all their data via the account page in the UI or via the API:

```bash
# Via API (requires user's JWT)
curl -X DELETE http://localhost:8000/users/me/erasure \
  -H "Authorization: Bearer <user-jwt>"
```

This hard-deletes all rows in: `corrections`, `memory`, `user_settings`, `goals`,
`forecasts`, `anomalies`, `subscriptions`, `transactions`, and the `users` row.
Redis session keys are also purged.

An `erasure_audit` record is retained for operator compliance review:

```bash
# Check audit records (operator only)
docker compose exec postgres psql -U raseed -d raseed \
  -c "SELECT user_id, status, completed_at, per_store_counts FROM erasure_audit ORDER BY requested_at DESC LIMIT 10;"
```

**Note**: If the user's label corrections were used in a model retrain that has
already been promoted, the model weights may still reflect those corrections. Full
machine unlearning requires a retrain cycle excluding those examples; see
`SECURITY.md §Model Unlearning Limitation`.

---

## Alert response

### Drift alert received

When a drift alert fires in Slack:

1. **Identify the signal** — the webhook payload includes which of the four drift
   signals fired (mean confidence, correction rate, PSI, new-merchant rate).

2. **Inspect recent transactions** — look for distribution shifts:

   ```bash
   docker compose exec postgres psql -U raseed -d raseed \
     -c "SELECT category, COUNT(*), AVG(confidence) FROM transactions
         WHERE created_at > NOW() - INTERVAL '7 days'
         GROUP BY category ORDER BY COUNT(*) DESC;"
   ```

3. **Simulate the drift** (for rehearsal/testing):

   ```bash
   docker compose exec worker python /app/scripts/simulate_drift.py
   ```

4. **Decide**: retrain or tune thresholds in `eval_thresholds.yaml`.

5. **Retrain if needed** — follow the Retraining procedure above.

6. **Acknowledge in Slack** after the champion is promoted or the alert is resolved.

### Service down

```bash
# Restart a single service
docker compose restart backend

# Check logs
docker compose logs --tail=100 backend

# Full stack restart (preserves data)
docker compose down && docker compose up -d
```
