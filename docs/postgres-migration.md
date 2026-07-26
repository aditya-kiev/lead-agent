# Postgres Migration: Render Free → Neon

## Why Neon

- **Permanent free tier** (0.5 GB storage, 100 compute-hours/month) — not a trial
- Compute auto-suspends after 5 min idle; resumes in ~300ms on first query — invisible for request-driven apps
- No credit card required for free tier
- Upgrade later to paid Launch tier (usage-based, no minimum) when there's revenue

## Prerequisites

- [Neon account](https://console.neon.tech) — create one, no credit card needed
- `pg_dump` / `pg_restore` installed locally (part of PostgreSQL client tools)
- `psql` installed locally
- Access to Render dashboard for the old DB connection string

## Migration Steps

### 1. Create a Neon project

1. Go to https://console.neon.tech → "Create a project"
2. Choose a region close to your Render deployment (e.g. `US East (N. Virginia)`)
3. Copy the **pooled connection string** from the dashboard (it looks like `postgres://user:pass@ep-xxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require`)

### 2. Run existing Alembic migrations against Neon

```bash
# Point DATABASE_URL at the new Neon DB (use the non-pooled connection string for migrations)
export DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb"

# Run migrations
alembic upgrade head
```

### 3. Dump data from the old Render Postgres

```bash
# Get the Render Postgres connection string from Render dashboard
pg_dump --data-only --column-inserts "$RENDER_DATABASE_URL" > render-dump.sql
```

> Using `--column-inserts` produces portable INSERT statements that work across Postgres versions and avoids issues with custom-format dumps and different `pg_dump`/`pg_restore` versions on Neon.

### 4. Restore into Neon

```bash
psql "$NEON_DATABASE_URL" < render-dump.sql
```

### 5. Verify row counts

```bash
# Run against Neon
psql "$NEON_DATABASE_URL" -c "SELECT count(*) FROM lead_conversations;"

# Compare with old Render count
psql "$RENDER_DATABASE_URL" -c "SELECT count(*) FROM lead_conversations;"
```

### 6. Update DATABASE_URL in Render env vars

1. Go to Render dashboard → your service → Environment
2. Set `DATABASE_URL` to the **pooled** Neon connection string
3. Deploy / restart

### 7. Keep old Render Postgres as fallback

Do not delete the Render Postgres for a few days. If issues arise, revert `DATABASE_URL` to the old value and redeploy.

## Restore from Backup

```bash
# Download the backup artifact from GitHub Actions (see backup-db.yml)
# or run the backup script directly:
scripts/backup_db.sh

# Restore
psql "$DATABASE_URL" < backup_file.sql
```

## Moving to Paid Tier Later

When there's a paying client, consider:
- **Neon Launch plan** (usage-based, no monthly minimum, no cold-start)
- **Render paid Postgres** (~$7-9/mo starter) — simpler if you're already on Render
