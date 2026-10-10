#!/usr/bin/env bash
# Membangun database dari nol: ekstensi, wilayah, data UMKM, dan role read-only.
# Pemakaian: PGDATABASE=ta_umkm AI_EXECUTOR_PASSWORD=rahasia ./db/setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
: "${PGDATABASE:?set PGDATABASE}"
: "${AI_EXECUTOR_PASSWORD:?set AI_EXECUTOR_PASSWORD}"

psql -v ON_ERROR_STOP=1 -f db/01_init.sql
DATABASE_URL="postgresql://${PGUSER:-postgres}${PGPASSWORD:+:$PGPASSWORD}@${PGHOST:-localhost}:${PGPORT:-5432}/${PGDATABASE}" \
    python -m scripts.load_wilayah
psql -v ON_ERROR_STOP=1 -f backup_umkm.sql
psql -v ON_ERROR_STOP=1 -v ai_password="'${AI_EXECUTOR_PASSWORD}'" -f db/02_readonly_role.sql
