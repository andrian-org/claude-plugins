#!/usr/bin/env bash
# Publishes this application's tables into the stack's database, once the framework's baseline is there.
set -euo pipefail

: "${MSSQL_HOST:?MSSQL_HOST is not set}"
: "${MSSQL_SA_PASSWORD:?MSSQL_SA_PASSWORD is not set}"
: "${MSSQL_DB:?MSSQL_DB is not set}"
PORT="${MSSQL_PORT:-1433}"
ATTEMPTS="${PUBLISH_ATTEMPTS:-30}"

CONNECTION="Server=${MSSQL_HOST},${PORT};User Id=sa;Password=${MSSQL_SA_PASSWORD};Database=${MSSQL_DB};TrustServerCertificate=True"

for attempt in $(seq 1 "${ATTEMPTS}"); do
  if sqlpackage /Action:Publish \
      /SourceFile:/db/Inspections.Database.dacpac \
      /Profile:/db/Inspections.Database.publish.xml \
      /TargetConnectionString:"${CONNECTION}" \
      /p:CreateNewDatabase=False; then
    echo "published Inspections.Database"
    exit 0
  fi
  echo "publish failed (attempt ${attempt}/${ATTEMPTS}); retrying in 5 seconds" >&2
  sleep 5
done

echo "could not publish Inspections.Database after ${ATTEMPTS} attempts" >&2
exit 1
