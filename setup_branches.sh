#!/usr/bin/env bash
# setup_branches.sh — checkout the branches configured in .env for all submodules.
#
# Usage:
#   ./setup_branches.sh            # reads .env from current directory
#   ./setup_branches.sh --check    # print current branch of each submodule (no checkout)
#
# Windows users: run this from Git Bash or WSL.
# After running, rebuild the image:  docker-compose up --build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if it exists
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
else
    echo "Warning: .env not found — using default branch 'master' for all modules."
fi

SERVER_BRANCH="${SERVER_BRANCH:-master}"
CLIENT_BRANCH="${CLIENT_BRANCH:-master}"
LINE_DETECTION_BRANCH="${LINE_DETECTION_BRANCH:-master}"
LAYOUT_ANALYSIS_BRANCH="${LAYOUT_ANALYSIS_BRANCH:-master}"

declare -A BRANCHES=(
    ["modules/ommr4all-server"]="$SERVER_BRANCH"
    ["modules/ommr4all-client"]="$CLIENT_BRANCH"
    ["modules/ommr4all-line-detection"]="$LINE_DETECTION_BRANCH"
    ["modules/ommr4all-layout-analysis"]="$LAYOUT_ANALYSIS_BRANCH"
)

if [[ "${1:-}" == "--check" ]]; then
    echo "Current submodule branches:"
    for path in "${!BRANCHES[@]}"; do
        branch=$(git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "(not initialised)")
        printf "  %-40s %s\n" "$path" "$branch"
    done
    exit 0
fi

echo "Checking out submodule branches..."
for path in "${!BRANCHES[@]}"; do
    target="${BRANCHES[$path]}"
    current=$(git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [[ "$current" == "$target" ]]; then
        printf "  %-40s already on '%s'\n" "$path" "$target"
    else
        printf "  %-40s %s → %s\n" "$path" "$current" "$target"
        git -C "$path" fetch origin
        git -C "$path" checkout "$target"
    fi
done

echo ""
echo "Done. Rebuild the image with:  docker-compose up --build"
