#!/usr/bin/env bash
# Build the OMMR4all Docker image and start the container.
# Run from the repo root:  ./start.sh
#
# On first run this creates .env from .env.example (edit it to change the port,
# the storage directory or the database location, then re-run ./start.sh).
#
# Options:
#   --gpu         Pass the NVIDIA GPU into the container (needs nvidia-container-toolkit).
#                 Can be combined with --no-cache:  ./start.sh --gpu --no-cache
#   --gpu-legacy  Like --gpu, but builds the image with a Pascal-compatible torch
#                 (sm_61, e.g. GTX 10xx). Recent torch dropped Pascal support; this
#                 bakes torch 2.7.1+cu126 into the image. Pair with --no-cache to rebuild.
#   --no-cache    Force a full rebuild (no Docker layer cache)
#   --stop        Stop and remove the running container

set -euo pipefail
cd "$(dirname "$0")"

# Enable BuildKit (required for --network=host on RUN steps)
export DOCKER_BUILDKIT=1

COMPOSE="docker compose"
# Fall back to the older standalone binary if the plugin isn't available
if ! docker compose version &>/dev/null 2>&1; then
    COMPOSE="docker-compose"
fi

NO_CACHE=0
GPU=0
STOP=0
GPU_MODE=""
export GPU_MODE
for arg in "$@"; do
    case "$arg" in
        --stop)
            STOP=1
            ;;
        --no-cache)
            NO_CACHE=1
            ;;
        --gpu)
            GPU=1
            ;;
        --gpu-legacy)
            GPU=1
            # Bake a Pascal-compatible torch into the image (see Dockerfile ARG GPU_MODE)
            GPU_MODE=legacy
            export GPU_MODE
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 1
            ;;
    esac
done

# ── Configuration ───────────────────────────────────────────────────────────
# Create .env on first run so a fresh clone starts with a single command.
if [[ ! -f .env ]]; then
    echo "==> No .env found, creating one from .env.example"
    cp .env.example .env
    echo "    Edit .env to change PORT / STORAGE / DB_DIR, then re-run ./start.sh"
fi

# Read the path/port settings from .env so the defaults below (and the summary
# at the end) match what compose will use. Compose reads .env itself; this only
# fills in the gaps. Deliberately parsed rather than sourced — .env is Docker's
# format, not shell, so sourcing it would execute unquoted values.
env_get() {
    local value
    value=$(grep -E "^[[:space:]]*$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-)
    # strip surrounding quotes and whitespace
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    echo "$value" | sed -e 's/[[:space:]]*$//' -e 's/^[[:space:]]*//'
}

PORT=$(env_get PORT);         PORT=${PORT:-8001}
STORAGE=$(env_get STORAGE);   STORAGE=${STORAGE:-./storage}
DB_NAME=$(env_get DB_NAME);   DB_NAME=${DB_NAME:-db.sqlite3}
# Database directory defaults to the storage directory, i.e. <STORAGE>/db.sqlite3
DB_DIR=$(env_get DB_DIR);     DB_DIR=${DB_DIR:-$STORAGE}
export PORT STORAGE DB_DIR DB_NAME

if [[ "$STOP" == 1 ]]; then
    echo "==> Stopping OMMR4all..."
    $COMPOSE down
    exit 0
fi

# Create the host directories up front. Without this Docker would create them as
# root-owned, and a typo'd path would silently become a new empty data directory.
mkdir -p "$STORAGE" "$DB_DIR"

if [[ "$GPU" == 1 ]]; then
    # docker-compose.gpu.yml adds the NVIDIA device reservation to the web service
    COMPOSE="$COMPOSE -f docker-compose.yml -f docker-compose.gpu.yml"
fi

echo "==> Configuration (from .env)"
echo "    Port:     ${PORT}"
echo "    Storage:  $(cd "$STORAGE" && pwd)"
echo "    Database: $(cd "$DB_DIR" && pwd)/${DB_NAME}"

if [[ "$NO_CACHE" == 1 ]]; then
    echo "==> Building (no cache)..."
    $COMPOSE build --no-cache
else
    echo "==> Building..."
    $COMPOSE build
fi

echo "==> Starting..."
$COMPOSE up -d

echo ""
echo "OMMR4all is starting at http://localhost:${PORT}"
if [[ "$GPU" == 1 ]]; then
    if [[ "$GPU_MODE" == legacy ]]; then
        echo "GPU passthrough enabled (Pascal-compatible torch 2.7.1+cu126 baked in). Verify with:"
    else
        echo "GPU passthrough enabled. Verify with:"
    fi
    echo "  docker compose exec web /opt/ommr4all/ommr4all-deploy-venv/bin/python -c 'import torch; print(torch.cuda.is_available())'"
fi
echo "Logs: docker compose logs -f"
echo "Stop: ./start.sh --stop"
