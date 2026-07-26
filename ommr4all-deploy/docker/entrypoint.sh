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

# Both paths are container-side and configurable from the .env file (see
# docker-compose.yml). settings.py reads the same two variables, so whatever is
# set here is exactly what Django uses. The DB defaults into the storage mount
# so a plain `docker run` with only the storage volume still persists it.
STORAGE="${OMMR4ALL_STORAGE_ROOT:-/opt/ommr4all/storage}"
DB="${OMMR4ALL_DB_PATH:-$STORAGE/db.sqlite3}"
export OMMR4ALL_STORAGE_ROOT="$STORAGE"
export OMMR4ALL_DB_PATH="$DB"

echo "==> Storage:  $STORAGE"
echo "==> Database: $DB"

mkdir -p "$STORAGE" "$(dirname "$DB")"

if [[ -f "$DB" ]]; then
    echo "==> Backing up database to $DB.backup..."
    cp "$DB" "$DB.backup"
fi

echo "==> Running database migrations..."
if ! "$PYTHON" "$MANAGE" migrate --noinput; then
    echo "!! Database migration failed." >&2
    if [[ -f "$DB.backup" ]]; then
        echo "!! Restoring database from $DB.backup (pre-migration state)." >&2
        cp "$DB.backup" "$DB"
    fi
    echo "!! Aborting startup so the database is not left half-migrated." >&2
    echo "!! The pre-migration backup is preserved at $DB.backup." >&2
    echo "!! Fix the migration issue and restart the container." >&2
    exit 1
fi

chmod 666 "$DB"
# SQLite needs write access to the *directory* too (-journal / -wal side files)
chmod o+w "$STORAGE" "$(dirname "$DB")"

# Apache runs as www-data, but the storage tree is usually owned by whoever
# created the books on the host (often root). Grant "other" read+write across the
# tree so the workers can read book_meta.json and write page data back. 'X' adds
# +x to directories only, never to regular files. Cheap (metadata only) and
# self-healing after books are added from outside the container.
# Set FIX_STORAGE_PERMISSIONS=0 in .env to skip, e.g. for slow network storage.
if [[ "${FIX_STORAGE_PERMISSIONS:-1}" != "0" ]]; then
    echo "==> Making storage accessible to the Apache workers (www-data)..."
    chmod -R o+rwX "$STORAGE" \
        || echo "!! Could not fix all storage permissions; some books may be unreadable" >&2
fi

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
