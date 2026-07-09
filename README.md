# BusinessOS

> A WhatsApp-native AI operating system for Indian SMBs. It turns unstructured WhatsApp
> communication — Hindi/Hinglish text and voice notes — into structured business operations
> (orders, payments, reminders), with the owner confirming every action before it's taken.

**Status:** Phase 1 core is built, tested, and running against real infrastructure (Meta
WhatsApp Cloud API, Supabase, OpenAI, Upstash Redis). The full loop works:

```
message (text or voice) → understand → confirm on WhatsApp → owner taps 1/2/3 → order logged + remembered
```

## How it works (30 seconds)

1. A vendor/customer WhatsApps the business (text or a Hindi voice note).
2. The webhook verifies it (HMAC), dedups it, and drops it on a Redis queue.
3. A worker transcribes voice → classifies intent → extracts entities (qty, date, amount)
   → enriches with contact history → proposes an action.
4. The owner gets a Hindi confirmation with **[Confirm] [Edit] [Skip]** buttons.
5. On **Confirm**, the order is written to the DB (with a number, contact stats, and a payment
   reminder) and the message is remembered for future context.

Deep dive: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (full file-by-file walkthrough).
Project rules + current status: **[CLAUDE.md](CLAUDE.md)**. Full spec: `CLAUDE_CODE_CONTEXT.md`.

## Quick start

```bash
# 1. Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your credentials (see below)

# 2. Deploy the database schema (needs SUPABASE_DB_URL in .env)
python scripts/setup_db.py

# 3. Run — TWO processes
uvicorn app.main:app --reload --port 8000     # terminal 1: the web server
python -m app.queue.consumer                  # terminal 2: the queue worker

# 4. (optional) Expose for Meta webhooks + simulate an inbound message
ngrok http 8000
python scripts/test_webhook_local.py --type text --message "50 piece bhejo kal tak"
```

## Configuration

All settings live in `.env` (see `.env.example`). Key groups:

| Var(s) | Where to get it |
|---|---|
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | Meta → WhatsApp → API Setup / App Settings |
| `OPENAI_API_KEY` | OpenAI dashboard (GPT-4o mini + Whisper) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Supabase → Settings → API (REST client) |
| `SUPABASE_DB_URL` | Supabase → Settings → Database → direct URI (migrations) |
| `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN` | Upstash → your Redis DB (use the `rediss://` native URL) |

## Testing

```bash
pytest tests/                    # fast, mocked — no API calls (CI default)
RUN_LIVE_EVAL=1 pytest tests/    # also runs the live model accuracy eval (uses OpenAI)
```

Test corpus: 50 labeled Hindi/Hinglish messages + 3 `.ogg` voice notes in `tests/fixtures/`.

## Deploy

Railway, auto-deploying from `main`. Config in `railway.toml` (`/health` is the health check).

## Stack

FastAPI · Supabase (Postgres + pgvector) · Meta WhatsApp Cloud API (direct) · OpenAI GPT-4o mini
+ Whisper · Upstash Redis (queue + cache) · Railway.
