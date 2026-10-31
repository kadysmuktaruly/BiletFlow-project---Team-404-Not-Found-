#!/usr/bin/env bash
# Regenerate packages/api-types from the FastAPI OpenAPI schema. Never edit the output by hand.
#   npm run gen:api-types      (from the repo root)
# CI runs this and fails if the committed files differ.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/packages/api-types"

# Importing the app builds the engine object but opens no connection, so no database is needed.
(cd "$ROOT/apps/api" && uv run --quiet python -c '
import json, sys
from app.main import app
json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
sys.stdout.write("\n")
') > "$OUT/openapi.json"

"$ROOT/node_modules/.bin/openapi-typescript" "$OUT/openapi.json" \
  --output "$OUT/src/schema.d.ts" --alphabetize --root-types

echo "api-types regenerated: $OUT/src/schema.d.ts"
