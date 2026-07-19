#!/usr/bin/env bash
# Build the OMMR4all Docker image and start the container.
# Run from the repo root:  ./start.sh
#
# Options:
#   --gpu         Pass the NVIDIA GPU into the container (needs nvidia-container-toolkit).
#                 Can be combined with --no-cache:  ./start.sh --gpu --no-cache
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
for arg in "$@"; do
    case "$arg" in
        --stop)
            echo "==> Stopping OMMR4all..."
            $COMPOSE down
            exit 0
            ;;
        --no-cache)
            NO_CACHE=1
            ;;
        --gpu)
            GPU=1
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 1
            ;;
    esac
done

if [[ "$GPU" == 1 ]]; then
    # docker-compose.gpu.yml adds the NVIDIA device reservation to the web service
    COMPOSE="$COMPOSE -f docker-compose.yml -f docker-compose.gpu.yml"
fi

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
# Read PORT from .env (default 8001)
PORT=$(grep -E '^PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
PORT=${PORT:-8001}
echo "OMMR4all is starting at http://localhost:${PORT}"
if [[ "$GPU" == 1 ]]; then
    echo "GPU passthrough enabled. Verify with:"
    echo "  docker compose exec web /opt/ommr4all/ommr4all-deploy-venv/bin/python -c 'import torch; print(torch.cuda.is_available())'"
fi
echo "Logs: docker compose logs -f"
echo "Stop: ./start.sh --stop"
