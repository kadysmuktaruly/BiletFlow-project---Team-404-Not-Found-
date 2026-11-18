#!/usr/bin/env bash
# Back up the BiletFlow database from the Compose `db` service (Report 6, SRS 7 "regular
# backups and recovery procedures").
#
#   scripts/backup-db.sh                 # writes backups/biletflow-<UTC timestamp>.dump
#   scripts/backup-db.sh path/to/file.dump
#
# Custom-format pg_dump (compressed, restorable with scripts/restore-db.sh). backups/ is
# git-ignored: dumps contain personal data and must never be committed.
set -euo pipefail
cd "$(dirname "$0")/.."

DB_USER="${POSTGRES_USER:-biletflow}"
DB_NAME="${POSTGRES_DB:-biletflow}"
OUT="${1:-backups/biletflow-$(date -u +%Y%m%dT%H%M%SZ).dump}"
mkdir -p "$(dirname "$OUT")"

docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner > "$OUT.partial"
mv "$OUT.partial" "$OUT"
echo "Backed up $DB_NAME to $OUT ($(du -h "$OUT" | cut -f1))"
