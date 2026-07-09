# BusinessOS — Claude Code Project Guide

> WhatsApp-native AI Operating System for Indian SMBs.
> The full technical bible is `CLAUDE_CODE_CONTEXT.md`. This file is the always-loaded summary — read it first, every session.

**Note on naming:** Internal docs may say "Dhaaga." The project's real name is **BusinessOS**. Use BusinessOS in code, commits, and user-facing text.

---

## Current status (updated 2026-07-09)

**Phase 1 core is built, tested, and pushed** — 19 tickets done (LAK-5→20, 23, 24, 25). The full
loop works end to end against real infra (Meta, Supabase, OpenAI, Upstash): **message (text or
voice) → understand → confirm on WhatsApp → owner taps 1/2/3 → order logged + remembered.**

**Done:** FastAPI skeleton · Supabase schema · Redis queue · signed webhook (verify + receive +
dedup) · Meta sender · phone normalizer · intent classifier · entity extractor · action
generator + executor · confirm engine + reply handling · voice notes (Whisper) · context
enricher · message persistence · message router · unit tests + opt-in live accuracy eval + Hindi fixtures.

**Not done (4 tickets):** LAK-21 daily-summary job · LAK-22 payment-reminder scheduler (both need
scheduler wiring — `app/scheduler/jobs.py` currently has only `expire_confirmations`) · LAK-26/27
integration tests · LAK-28 health-check upgrade.

**Known blocker — live phone demo:** everything is wired, but Meta only delivers real webhooks in
**Live mode** (needs Privacy Policy URL + Business Verification review). Dev mode delivers only
dashboard "Test" webhooks. To resume: add privacy URL → verify business → flip App Mode to Live →
restart server/consumer/ngrok → update the Meta callback URL (ngrok's free URL changes each restart).
See memory note `businessos-meta-live-blocker`. Also onboard a fresh `businesses` row (DB was wiped).

---

## How to work in this repo

- **Plan first, point to learning (don't lecture).** At the start of a task, state the plan — what we're about to do — before acting. The user learns by watching videos on their own, so do NOT teach inline. When new concepts come up, surface a concise list of topic names to go study (grouped, prioritized) rather than explaining them, and tag them inline with **📺 worth a video**. Routine/familiar work can move fast.
- **Proactively suggest relevant skills.** When a request maps to an available skill, name it and offer to run it instead of doing it ad hoc. Map: code changes / "is this safe to merge" → `/code-review`; pre-onboarding or webhook/auth work → `/security-review`; a bug or stack trace → `/engineering:debug`; before a Railway deploy → `/engineering:deploy-checklist`; standup / progress summary → `/engineering:standup`; production incident → `/engineering:incident-response`. Type `/` to see the full menu.
- **Run `/code-review` on any non-trivial diff before committing** (per Critical Rules — webhook security, SQL injection, idempotency).
- Don't commit or push unless asked.

---

## What this is

An AI layer over the Meta WhatsApp Cloud API that converts unstructured SMB communication (voice notes, Hindi/Hinglish text, PDFs, invoice images) into structured operations: orders, payments, tasks, reminders.

Pipeline: `incoming message → type detector → parser (text/voice/pdf/image) → intent classifier → entity extractor → context enricher → action generator → confirm-before-act → executor → response sender`.

---

## Stack

- **Backend:** Python + FastAPI (async — required for webhook handling)
- **DB:** Supabase (Postgres + pgvector for conversation embeddings)
- **Messaging:** Meta WhatsApp Cloud API, direct (no BSP)
- **Voice:** OpenAI Whisper API (Hindi/Hinglish)
- **NLP:** GPT-4o mini (intent + entity extraction)
- **PDF:** pdfplumber (digital) + GPT-4 Vision (scanned) — *Phase 2*
- **Queue + cache:** Upstash Redis
- **Hosting:** Railway (auto-deploys from GitHub `main`)

---

## Critical rules (do not violate)

1. **Never log raw WhatsApp message content** — privacy risk.
2. **Always validate webhook signatures** (`X-Hub-Signature-256`) — the endpoint is public.
3. **Respond to webhooks in <1s** — ack immediately, push to Redis, process async. Meta retries aggressively.
4. **Deduplicate by `whatsapp_message_id`** — Meta resends.
5. **Never auto-execute actions** — Phase 1 is always confirm-before-act, no exceptions.
6. **Normalize all Indian phone formats** (+91…, 91…, 0…, bare 10-digit) → `+91XXXXXXXXXX`.
7. **Default language is Hindi/Hinglish** — all prompts must handle code-switching.
8. **Confidence threshold 0.70** — below it, escalate to the owner instead of guessing.
9. **Rate limit** WhatsApp sends to 80 msg/s with backoff.
10. **All DB writes idempotent** — safe to retry.

---

## Project layout

```
app/
  main.py            FastAPI app (lifespan) + router mounts
  config.py          pydantic-settings (all env vars; source of truth for names)
  api/               webhook.py (GET verify + signed POST), health.py
  core/              message_router · intent_classifier · entity_extractor · context_enricher
                     action_generator · action_executor · confirm_engine
  parsers/           text_parser · voice_parser (Whisper)     (pdf/image = Phase 2)
  whatsapp/          client (send + media download) · sender · templates · message_types
  ai/                openai_client · whisper · prompts/*.txt   (embeddings = later)
  db/                supabase_client · migrations/001_initial.sql
     repositories/   business · contact · message · order · payment · task · pending_confirmation
  queue/             redis_client · producer · consumer (SEPARATE worker process)
  scheduler/         jobs.py (expire_confirmations; daily-summary + reminders TBD = LAK-21/22)
  utils/             phone · logger
tests/               unit tests + conftest + fixtures/ (50-msg corpus + 3 .ogg voice notes)
scripts/             setup_db · test_webhook_local
docs/ARCHITECTURE.md   full file-by-file code walkthrough (read this to understand the code)
```

---

## Schema (core tables)

`businesses`, `contacts`, `messages`, `orders`, `payments`, `tasks`, `pending_confirmations`, `daily_summaries`. Full DDL in `CLAUDE_CODE_CONTEXT.md` §3. Key points: every table keys off `business_id`; `messages.entities` is JSONB; `messages.embedding` is `vector(1536)`; dedup on `messages.whatsapp_message_id`.

---

## Workflow conventions

- **Branches:** `main` (prod, deployable) ← `dev` (integration) ← `feature/xxx` / `fix/xxx`.
- **Commits:** `feat:` / `fix:` / `test:` prefix, imperative.
- **Local dev — TWO processes** (the consumer is separate; uvicorn does NOT start it):
  - server: `uvicorn app.main:app --reload --port 8000`
  - consumer: `python -m app.queue.consumer`
  - tunnel: `ngrok http 8000` · simulate inbound: `python scripts/test_webhook_local.py`
- **Tests:** `pytest tests/` (fast, mocked — no API). Live model eval: `RUN_LIVE_EVAL=1 pytest tests/` (uses OpenAI).
- **DB migrations:** `python scripts/setup_db.py` (needs `SUPABASE_DB_URL`).
- **Deploy:** `railway up` (or push to `main`).

## Before merging / shipping
- Run `/code-review` on the diff (webhook security, SQL injection, idempotency).
- Run `/security-review` before onboarding any real business.
- Run `/engineering:deploy-checklist` before a Railway deploy.

---

## Phase 1 MVP scope (weeks 1–6)

**In:** webhook receive/send · text intent (orders + payments) · voice → transcript → intent · order extraction → confirm → record · payment reminder scheduling · daily summary (8 PM) · auto-create contacts · health check + logging.

**Out (Phase 2+):** PDF parsing · multi-language beyond Hindi · autopilot/full-auto · dashboard UI · UPI links · credit scoring · mobile app · multi-business mgmt.

**Default when unsure:** ship the simpler version, validate with real users, then improve.
