#!/usr/bin/env bash
# Test: Start Django backend and Angular frontend dev servers

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER="$ROOT/modules/ommr4all-server"
CLIENT="$ROOT/modules/ommr4all-client"

cleanup() {
    echo ""
    echo "Stopping servers..."
    kill "$SERVER_PID" "$CLIENT_PID" 2>/dev/null
    wait "$SERVER_PID" "$CLIENT_PID" 2>/dev/null
}
trap cleanup INT TERM

# Path to the specific vllm312 virtual environment
VENV_PATH="$ROOT/.venv/bin/activate"

if [ -f "$VENV_PATH" ]; then
    echo "Activating virtual environment"
    source "$VENV_PATH"
else
    echo "Error: Could not find the virtual environment at $VENV_PATH"
    exit 1
fi

echo "Starting Django dev server..."
python "$SERVER/manage.py" runserver &
SERVER_PID=$!

echo "Starting Angular dev server..."
(cd "$CLIENT" && yarn start) &
CLIENT_PID=$!

echo "Backend PID: $SERVER_PID | Frontend PID: $CLIENT_PID"
echo "Press Ctrl+C to stop both."
wait
