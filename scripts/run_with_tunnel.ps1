# Run BusinessOS (web server + queue consumer) and expose it publicly via a free
# Cloudflare quick tunnel. Prints an https://<random>.trycloudflare.com URL to
# register in Meta as the webhook callback (append /webhook).
#
# Windows PowerShell port of run_with_tunnel.sh. Same behaviour, native Windows —
# no WSL needed.
#
# The quick-tunnel URL changes every run. For a STABLE url you need a domain on
# Cloudflare (named tunnel) — not needed until you're Live on Meta.
#
# Usage:   powershell -ExecutionPolicy Bypass -File scripts\run_with_tunnel.ps1
# Needs:   cloudflared installed (winget install Cloudflare.cloudflared),
#          plus .venv and a filled-in .env.
# Stop:    Ctrl-C (stops the server, consumer, and tunnel together).

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Activate the virtualenv for THIS script's env (so python/uvicorn resolve).
& (Join-Path (Get-Location) ".venv\Scripts\Activate.ps1")

Write-Host "starting web server + consumer..."
$server   = Start-Process -PassThru -NoNewWindow uvicorn `
    -ArgumentList "app.main:app","--host","0.0.0.0","--port","8000","--log-level","info"
$consumer = Start-Process -PassThru -NoNewWindow python `
    -ArgumentList "-m","app.queue.consumer"

# Kill both child processes on exit / Ctrl-C.
function Stop-Children {
    foreach ($p in @($server, $consumer)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
try {
    # Wait for the server to answer /health, then open the tunnel.
    do {
        Start-Sleep -Seconds 1
        try { $ok = (Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 3).StatusCode -eq 200 }
        catch { $ok = $false }
    } until ($ok)
    Write-Host "server healthy - opening Cloudflare tunnel (Ctrl-C to stop everything)"
    Write-Host ">>> Register the printed https://...trycloudflare.com URL + '/webhook' in Meta <<<"

    # --protocol http2 pins the edge transport to TCP/443. The default (quic/UDP)
    # is faster but drops on NAT'd / UDP-throttled networks — the edge tears the
    # tunnel down mid-session. http2 is the stable choice.
    cloudflared tunnel --url http://localhost:8000 --protocol http2
}
finally {
    Stop-Children
}
