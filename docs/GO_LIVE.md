# Going Live — BusinessOS

How to take the app from "works on my machine" to "a real trader's WhatsApp
messages flow through it." Everything code-side is done; what remains is a public
URL + Meta account setup.

---

## The one-line picture

```
trader's WhatsApp  →  Meta Cloud API  →  (public URL)  →  your app  →  Supabase/Redis/OpenAI
                                              ↑
                                   Cloudflare Tunnel gives you this, free
```

The **only** thing standing between you and a live demo is Meta **Business
Verification** — in dev mode Meta delivers *zero* real inbound messages (no
customer orders, no owner button taps). Verification requires a registered legal
entity and takes a few days to review.

---

## Step 1 — Run the app + tunnel on the always-on PC

Do this on the **home PC** (Windows), not the laptop — the tunnel dies when the
laptop sleeps.

**One-time setup** (PowerShell, in the project folder):

```powershell
winget install Cloudflare.cloudflared
```

Make sure the repo is present with a `.venv` and a filled-in `.env` (copy the
`.env` from the Mac).

**Every run:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_with_tunnel.ps1
```

This starts the web server, the queue consumer, and the tunnel together, waits
until the app is healthy, and prints a URL like
`https://<random>.trycloudflare.com`. Ctrl-C stops all three.

> ⚠️ The quick-tunnel URL is **random and changes every run**. Each restart means
> re-pasting the new URL into Meta (Step 3). A *stable* URL needs a domain on
> Cloudflare (named tunnel) — do that once you're Live, not before.

(Mac/Linux equivalent: `./scripts/run_with_tunnel.sh`.)

---

## Step 2 — Get a permanent WhatsApp token  *(LAK-30)*

The token from Meta's API Setup tab **expires every 24 hours**. For anything real,
create a **System User** token:

1. Meta Business Settings → **Users → System Users** → Add → make it an Admin.
2. **Add Assets** → your WhatsApp app → full control.
3. **Generate New Token** → select the app → scopes `whatsapp_business_messaging`
   + `whatsapp_business_management` → **no expiry**.
4. Put it in `.env` as `WHATSAPP_ACCESS_TOKEN` and restart.

---

## Step 3 — Point Meta's webhook at the tunnel  *(LAK-31)*

Meta App Dashboard → **WhatsApp → Configuration → Webhook**:

- **Callback URL:** the tunnel URL **+ `/webhook`**
  (e.g. `https://<random>.trycloudflare.com/webhook`)
- **Verify token:** the value of `WHATSAPP_VERIFY_TOKEN` in your `.env`
- Click **Verify and Save** (the app must be running — Meta does a GET handshake).
- **Subscribe** to the `messages` field.

Re-do the Callback URL whenever the tunnel URL changes (Step 1 caveat).

---

## Step 4 — Business Verification → flip to Live  *(LAK-32, the real blocker)*

Until this clears, real inbound stays blocked no matter what else is set up.

1. Add a **Privacy Policy URL** to the app (Meta requires one to go Live).
2. Meta Business Settings → **Business Info → Security Center → Start
   Verification**. Needs a **registered legal entity** (business name, address,
   proof docs). Review takes days.
3. Once verified, App Dashboard → toggle **App Mode: Dev → Live**.
4. Restart server + consumer + tunnel, re-confirm the webhook URL.

After this, a real trader messaging your WhatsApp number reaches the app, and the
owner's Confirm/Edit/Skip taps come back through.

---

## Before real businesses depend on it

- **Move off free Supabase/Upstash tiers.** Both auto-pause after ~1 week idle —
  a paused DB/Redis silently drops an incoming order. Use paid tiers or a
  keep-warm ping.
- **Stable URL.** Register a domain on Cloudflare and switch to a *named* tunnel
  so the webhook URL stops changing.
- Run migrations on the target DB: `python scripts/setup_db.py` (idempotent).
- Onboard the business row: `python scripts/onboard_business.py`.

---

## Status cheat-sheet

| Item | State |
|---|---|
| Core pipeline (understand → confirm → execute) | ✅ built + tested (31 passing) |
| Public URL (Cloudflare Tunnel, http2) | ✅ proven this run |
| Supabase / Redis / OpenAI reachable | ✅ verified |
| LAK-30 permanent token | ⏳ you, ~10 min |
| LAK-31 webhook repoint | ⏳ you, ~2 min |
| LAK-32 Business Verification | ⏳ you, days, needs legal entity |
| Paid data tiers + stable URL | ⏳ before real businesses |
