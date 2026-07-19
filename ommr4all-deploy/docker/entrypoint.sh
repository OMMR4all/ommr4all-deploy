#!/usr/bin/env bash
# Container entrypoint.
# 1. Ensures the storage directory exists.
# 2. Backs up the SQLite database, then runs Django migrations.
# 3. Makes the database/storage writable for the Apache (www-data) workers.
# 4. Creates a superuser if DJANGO_SUPERUSER_* vars are set and none exists yet.
# 5. Execs the CMD (apachectl -D FOREGROUND).

set -euo pipefail

PYTHON=/opt/ommr4all/ommr4all-deploy-venv/bin/python
MANAGE=/opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/manage.py
STORAGE=/opt/ommr4all/storage
DB="$STORAGE/db.sqlite3"

mkdir -p "$STORAGE"

if [[ -f "$DB" ]]; then
    echo "==> Backing up database to db.sqlite3.backup..."
    cp "$DB" "$DB.backup"
fi

echo "==> Running database migrations..."
"$PYTHON" "$MANAGE" migrate --noinput

chmod 666 "$DB"
chmod o+w "$STORAGE"

# Auto-create superuser when DJANGO_SUPERUSER_USERNAME is set and no superuser exists yet.
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]]; then
    SUPERUSER_EXISTS=$("$PYTHON" "$MANAGE" shell -c \
        "from django.contrib.auth import get_user_model; \
         U = get_user_model(); \
         print(U.objects.filter(is_superuser=True).exists())" 2>/dev/null | tail -1)
    if [[ "$SUPERUSER_EXISTS" == "False" ]]; then
        echo "==> Creating superuser '${DJANGO_SUPERUSER_USERNAME}'..."
        "$PYTHON" "$MANAGE" createsuperuser --noinput
    else
        echo "==> Superuser already exists, skipping."
    fi
fi

exec "$@"
