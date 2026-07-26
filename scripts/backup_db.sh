#!/usr/bin/env bash
# Database backup script for lead-agent
# Requires: pg_dump, DATABASE_URL environment variable
#
# Usage: DATABASE_URL="postgresql+asyncpg://..." ./scripts/backup_db.sh
# Or:  ./scripts/backup_db.sh
#       (reads DATABASE_URL from .env or environment)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [ -f "$PROJECT_DIR/.env" ]; then
  set -o allexport
  source "$PROJECT_DIR/.env"
  set +o allexport
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set."
  echo "Usage: DATABASE_URL='postgresql+asyncpg://...' $0"
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/lead-agent-$TIMESTAMP.sql"

# Convert asyncpg URL to psql URL (replace +asyncpg suffix)
PSQL_URL="${DATABASE_URL/+asyncpg/}"

echo "Backing up to $BACKUP_FILE ..."
pg_dump --data-only --column-inserts "$PSQL_URL" > "$BACKUP_FILE"

# Gzip for smaller artifact size
gzip "$BACKUP_FILE"
echo "Done: ${BACKUP_FILE}.gz ($(du -h "${BACKUP_FILE}.gz" | cut -f1))"
