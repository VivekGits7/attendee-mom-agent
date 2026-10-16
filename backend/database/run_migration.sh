#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_CONTAINER="${DB_CONTAINER:-doe-postgres}"
DB_NAME="${DB_NAME:-attendee-mom}"
DB_USER="${DB_USER:-postgres}"

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <file.sql> [more.sql ...]"
  echo "Example: $0 auth.sql"
  echo "Bare names are looked up in $SCRIPT_DIR"
  echo "Target is $DB_CONTAINER / $DB_NAME as $DB_USER, override with DB_CONTAINER, DB_NAME, DB_USER"
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "Container $DB_CONTAINER is not running on this machine" >&2
  exit 1
fi

files=()
for file in "$@"; do
  if [ -f "$file" ]; then
    files+=("$file")
  elif [ -f "$SCRIPT_DIR/$file" ]; then
    files+=("$SCRIPT_DIR/$file")
  else
    echo "SQL file not found: $file" >&2
    exit 1
  fi
done

for file in "${files[@]}"; do
  echo "Running $(basename "$file") on $DB_NAME in $DB_CONTAINER"
  docker exec -i "$DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 --single-transaction -U "$DB_USER" -d "$DB_NAME" < "$file"
done

echo "Tables in $DB_NAME"
docker exec "$DB_CONTAINER" psql -X -U "$DB_USER" -d "$DB_NAME" -c '\dt'
