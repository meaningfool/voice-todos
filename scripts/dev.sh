#!/usr/bin/env bash
# Start backend and frontend dev servers on fixed ports.
# Usage: ./scripts/dev.sh        (start both)
#        ./scripts/dev.sh stop   (kill both)

set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_PORT=8000
FRONTEND_PORT=5173
PIDFILE_BACKEND=".pid.backend"
PIDFILE_FRONTEND=".pid.frontend"

stop_servers() {
    for pidfile in "$PIDFILE_BACKEND" "$PIDFILE_FRONTEND"; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                echo "Stopped PID $pid"
            fi
            rm -f "$pidfile"
        fi
    done
    # Belt-and-suspenders: kill anything still on those ports
    kill $(lsof -ti :$BACKEND_PORT) 2>/dev/null || true
    kill $(lsof -ti :$FRONTEND_PORT) 2>/dev/null || true
}

if [ "${1:-}" = "stop" ]; then
    stop_servers
    echo "Dev servers stopped."
    exit 0
fi

# Stop any existing servers first
stop_servers
sleep 1

# Start backend
echo "Starting backend on :$BACKEND_PORT..."
cd backend
set -a && source .env 2>/dev/null && set +a
uv run uvicorn app.main:app --reload --port $BACKEND_PORT --log-level info &
echo $! > "../$PIDFILE_BACKEND"
cd ..

# Wait for backend to be ready
for i in $(seq 1 10); do
    if curl -s -o /dev/null http://localhost:$BACKEND_PORT/health 2>/dev/null; then
        echo "Backend ready."
        break
    fi
    sleep 1
done

# Start frontend
echo "Starting frontend on :$FRONTEND_PORT..."
cd frontend
pnpm dev &
echo $! > "../$PIDFILE_FRONTEND"
cd ..

# Wait for frontend
for i in $(seq 1 10); do
    if curl -s -o /dev/null http://localhost:$FRONTEND_PORT 2>/dev/null; then
        echo "Frontend ready."
        break
    fi
    sleep 1
done

echo ""
echo "App running at http://localhost:$FRONTEND_PORT"
echo "Backend API at http://localhost:$BACKEND_PORT"
echo "Stop with: ./scripts/dev.sh stop"
