#!/usr/bin/env bash
# Run BusinessOS (web server + queue consumer) and expose it publicly via a free
# Cloudflare quick tunnel. Prints an https://<random>.trycloudflare.com URL to
# register in Meta as the webhook callback (append /webhook).
#
# The quick-tunnel URL changes every run. For a STABLE url you need a domain on
# Cloudflare (named tunnel) — not needed until you're Live on Meta.
#
# Usage:   ./scripts/run_with_tunnel.sh
# Needs:   cloudflared installed, plus .venv and a filled-in .env.
# Stop:    Ctrl-C (stops the server, consumer, and tunnel together).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "starting web server + consumer…"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info &
SERVER_PID=$!
python -m app.queue.consumer &
CONSUMER_PID=$!

cleanup() { kill "$SERVER_PID" "$CONSUMER_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# wait for the server to answer /health, then open the tunnel
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do sleep 1; done
echo "server healthy ✓  — opening Cloudflare tunnel (Ctrl-C to stop everything)"
echo ">>> Register the printed https://…trycloudflare.com URL + '/webhook' in Meta <<<"
# --protocol http2 pins the edge transport to TCP/443. The default (quic/UDP) is
# faster but drops on NAT'd / UDP-throttled networks — the edge tears the tunnel
# down mid-session ("Application error 0x0 (remote)"). http2 is the stable choice.
cloudflared tunnel --url http://localhost:8000 --protocol http2
