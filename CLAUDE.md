# BusinessOS — Claude Code Project Guide

> WhatsApp-native AI Operating System for Indian SMBs.
> The full technical bible is `CLAUDE_CODE_CONTEXT.md`. This file is the always-loaded summary — read it first, every session.

**Note on naming:** Internal docs may say "Dhaaga." The project's real name is **BusinessOS**. Use BusinessOS in code, commits, and user-facing text.

## How to work in this repo

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
  main.py            FastAPI entry
  api/               webhook, health, dashboard
  core/              message_router, intent_classifier, entity_extractor,
                     context_enricher, action_generator, confirm_engine, action_executor
  parsers/           text, voice (Whisper), pdf, image
  whatsapp/          Meta Cloud API client, message_types, templates, sender
  ai/                openai_client, whisper, embeddings, prompts/
  db/                supabase_client, migrations/, repositories/
  queue/             redis_client, producer, consumer (separate worker)
  scheduler/         jobs.py (payment reminders, daily summaries)
  utils/             language, phone, logger
tests/               unit + integration + fixtures (real Hindi messages)
scripts/             setup_db, test_webhook_local, onboard_business
```

---

## Schema (core tables)

`businesses`, `contacts`, `messages`, `orders`, `payments`, `tasks`, `pending_confirmations`, `daily_summaries`. Full DDL in `CLAUDE_CODE_CONTEXT.md` §3. Key points: every table keys off `business_id`; `messages.entities` is JSONB; `messages.embedding` is `vector(1536)`; dedup on `messages.whatsapp_message_id`.

---

## Workflow conventions

- **Branches:** `main` (prod, deployable) ← `dev` (integration) ← `feature/xxx` / `fix/xxx`.
- **Commits:** `feat:` / `fix:` / `test:` prefix, imperative.
- **Local dev:** `uvicorn app.main:app --reload --port 8000`, tunnel via `ngrok http 8000`, simulate with `scripts/test_webhook_local.py`.
- **Tests:** `pytest tests/ -v` — must pass before merge to `main`.
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
