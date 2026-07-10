#!/usr/bin/env bash
# Container entrypoint.
# 1. Ensures the storage directory exists.
# 2. Runs Django database migrations.
# 3. Creates a superuser if DJANGO_SUPERUSER_* vars are set and no superuser exists yet.
# 4. Execs the CMD (apachectl -D FOREGROUND).

set -euo pipefail

PYTHON=/opt/ommr4all/ommr4all-deploy/.venv/bin/python
MANAGE=/opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/manage.py
STORAGE=/opt/ommr4all/storage

mkdir -p "$STORAGE"

echo "==> Running database migrations..."
"$PYTHON" "$MANAGE" migrate --noinput

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

echo "==> Starting Apache..."
exec "$@"
