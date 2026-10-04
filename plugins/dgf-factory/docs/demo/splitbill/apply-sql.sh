#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Apply the SQL that /dgf-scaffold generated to the showcase stack's live database.
#
#   apply-sql.sh <app-folder> <compose-folder>
#
#   <app-folder>      the generated application (it holds database/<App>.Database/)
#   <compose-folder>  DGF's src/samples/DGF.Compose (its .env holds the sa password)
#
# What it applies, in order:
#   1. ContinuousDeployment/*.sql - the aspnet_Applications row and the roles. Both are idempotent
#      as generated (IF NOT EXISTS), so they run as they are.
#   2. dbo/Tables/*.sql - each wrapped in IF OBJECT_ID(...) IS NULL, so a table that exists is left
#      alone, and applied in foreign-key order: a table runs once every generated table it references
#      exists.
#
# The generated database project would normally be published by its own db-app container. DGF pins no
# image for the framework baseline that container runs after, so on this machine the scripts run
# through sqlcmd inside dgf-sqlserver instead. Re-running this script changes nothing.
# ---------------------------------------------------------------------------
set -euo pipefail

APP=${1:?usage: apply-sql.sh <app-folder> <compose-folder>}
COMPOSE=${2:?usage: apply-sql.sh <app-folder> <compose-folder>}
CONTAINER=${SQL_CONTAINER:-dgf-sqlserver}
SQLCMD=/opt/mssql-tools18/bin/sqlcmd

fail() { printf 'apply-sql: %s\n' "$*" >&2; exit 1; }

db_dir=$(find "$APP/database" -mindepth 1 -maxdepth 1 -type d -name '*.Database' | head -1)
[ -n "$db_dir" ] || fail "no database/<App>.Database folder under $APP"
[ -f "$COMPOSE/.env" ] || fail "no .env in $COMPOSE - run up.sh there first"

PW=$(grep -E '^MSSQL_SA_PASSWORD=' "$COMPOSE/.env" | cut -d= -f2-)
DB=$(grep -E '^MSSQL_DB=' "$COMPOSE/.env" | cut -d= -f2-)
DB=${DB:-DGF}
[ -n "$PW" ] || fail "MSSQL_SA_PASSWORD is not set in $COMPOSE/.env"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

run_sql() {
  # $1 = local file, $2 = label
  docker cp "$1" "$CONTAINER:/tmp/apply.sql" >/dev/null
  printf -- '-- %s\n' "$2"
  docker exec "$CONTAINER" "$SQLCMD" -S localhost -U sa -P "$PW" -C -I -d "$DB" -b -i /tmp/apply.sql
}

echo "Applying $(basename "$db_dir") to database $DB in $CONTAINER"

for f in "$db_dir"/ContinuousDeployment/*.sql; do
  run_sql "$f" "$(basename "$f")"
done

# Tables in foreign-key order.
tables=()
for f in "$db_dir"/dbo/Tables/*.sql; do tables+=("$(basename "$f" .sql)"); done
done_list=" "
remaining=("${tables[@]}")
while [ "${#remaining[@]}" -gt 0 ]; do
  next=()
  progressed=0
  for t in "${remaining[@]}"; do
    f="$db_dir/dbo/Tables/$t.sql"
    ready=1
    for ref in $(grep -oE 'REFERENCES \[dbo\]\.\[[A-Za-z0-9_]+\]' "$f" | sed -E 's/.*\[([A-Za-z0-9_]+)\]$/\1/'); do
      [ "$ref" = "$t" ] && continue
      case " ${tables[*]} " in *" $ref "*) ;; *) continue ;; esac   # a framework table: already there
      case "$done_list" in *" $ref "*) ;; *) ready=0 ;; esac
    done
    if [ "$ready" -eq 0 ]; then next+=("$t"); continue; fi
    {
      printf "IF OBJECT_ID(N'dbo.%s', N'U') IS NULL\nBEGIN\n" "$t"
      grep -vE '^[[:space:]]*GO[[:space:]]*$' "$f"
      printf "PRINT 'Created table dbo.%s.';\nEND\nELSE\n    PRINT 'Table dbo.%s already exists - left unchanged.';\nGO\n" "$t" "$t"
    } > "$work/$t.sql"
    run_sql "$work/$t.sql" "dbo/Tables/$t.sql"
    done_list="$done_list$t "
    progressed=1
  done
  [ "$progressed" -eq 1 ] || fail "circular foreign keys among: ${next[*]}"
  remaining=("${next[@]+"${next[@]}"}")
done

echo "Done."
