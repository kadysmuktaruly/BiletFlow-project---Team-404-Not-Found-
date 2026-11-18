#!/usr/bin/env bash
# Restore a backup made by scripts/backup-db.sh into the Compose `db` service.
#
#   scripts/restore-db.sh backups/x.dump biletflow_restore_check   # into a separate database
#   scripts/restore-db.sh backups/x.dump --yes                       # REPLACES the main database
#
# Restoring into a separate database is the safe way to test a backup. Restoring over the
# main database drops and recreates every object in it, so it needs --yes; stop the api
# service first (`docker compose stop api`) and start it again afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."

DUMP="${1:?usage: scripts/restore-db.sh <file.dump> [target-db | --yes]}"
DB_USER="${POSTGRES_USER:-biletflow}"
MAIN_DB="${POSTGRES_DB:-biletflow}"
TARGET="${2:-}"
if [[ -z "$TARGET" ]]; then
  echo "Name a target database (safe), or pass --yes to replace $MAIN_DB." >&2
  exit 2
fi
if [[ "$TARGET" == "--yes" ]]; then
  TARGET="$MAIN_DB"
elif [[ "$TARGET" == "$MAIN_DB" ]]; then
  echo "Refusing to overwrite $MAIN_DB without --yes." >&2
  exit 2
fi
[[ -f "$DUMP" ]] || { echo "No such file: $DUMP" >&2; exit 2; }

if ! docker compose exec -T db psql -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$TARGET'" | grep -q 1; then
  docker compose exec -T db createdb -U "$DB_USER" "$TARGET"
fi
docker compose exec -T db pg_restore -U "$DB_USER" -d "$TARGET" --clean --if-exists --no-owner --exit-on-error < "$DUMP"
echo "Restored $DUMP into $TARGET"
