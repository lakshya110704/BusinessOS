# BusinessOS — Architecture & Code Walkthrough

A file-by-file map of the codebase, written for debugging: what each file does, the
non-obvious lines, and **where to look when something breaks**. Pairs with `CLAUDE.md`
(project rules) and `CLAUDE_CODE_CONTEXT.md` (the full spec).

## The system in one picture

```
WhatsApp ──POST──► webhook.py ──push──► Redis queue ──blpop──► consumer.py
  (Meta)          (verify sig,          (producer /           (worker process)
                   dedup, 200)           redis_client)              │
                                                                    ▼
                                              classify → extract → generate
                                            (intent)   (entities)  (ProposedAction)
                                                                    │
                                                              [next: confirm engine
                                                               → "Reply 1/2/3" → executor → DB]
```

The web server and the consumer are **separate processes** that only talk through Redis,
so either can restart without losing messages.

---

## Group 1 — Foundation

### `app/config.py`
Single source of settings. `Settings(BaseSettings)` auto-loads fields from environment
variables and `.env` (`env_file=".env"`, `extra="ignore"`). Every field has a default
(`: str = ""`), so a missing secret becomes `""` rather than crashing. `settings = Settings()`
runs **once at import** — that's when `.env` is read; everyone shares that one object.
- 🐛 Env var not picked up → the name must match a field here **exactly** (this was the
  `UPSTASH_REDIS_URL` vs `UPSTASH_REDIS_REST_URL` bug). A real shell env var overrides `.env`.

### `app/utils/logger.py`
Structured JSON logs. `JsonFormatter.format()` builds a JSON line; anything passed via
`logger.info("msg", extra={...})` that isn't a reserved LogRecord attribute gets merged in
(that's how `wa_message_id` shows up). `ensure_ascii=False` keeps Hindi/emoji readable.
`get_logger()` guards with `if not logger.handlers` (no duplicate lines) and
`propagate=False` (no double-printing).
- ⚠️ Never pass message body text to a log call — ids/types/counts only (Critical Rule #1).
- 🐛 Custom field missing → it must go through `extra=`, not string-formatting.

### `app/main.py`
App entry point. `lifespan()` runs setup before `yield`, teardown after (future DB/Redis
pools go here). `FastAPI(..., lifespan=lifespan)` builds the app; `include_router()` bolts on
the endpoints defined in `app/api/`.
- 🐛 New endpoint 404s → forgot to `include_router` it. Won't boot → traceback starts in an import here.

### `app/api/health.py`
`GET /health` → `{"status":"ok"}`. Railway pings it (`healthcheckPath`). Intentionally dumb;
LAK-28 will make it check Supabase/Redis/OpenAI.

---

## Group 2 — Ingress (security-critical)

### `app/api/webhook.py`
- **GET `/webhook`** (verify handshake): Meta sends `hub.mode/hub.verify_token/hub.challenge`
  (aliased because Python can't name a var `hub.mode`). All three must hold: mode `subscribe`,
  **non-empty** configured token, and a `compare_digest` match → echo the challenge; else 403.
- **`_verify_signature()`**: fail-closed if no header or no secret. Recomputes
  `hmac-sha256(raw_body, WHATSAPP_APP_SECRET)`, prefix `sha256=`, and compares with
  **`hmac.compare_digest`** (constant-time — never `==`, which leaks timing).
- **POST `/webhook`** (hot path, <1s): (1) read raw bytes; (2) **signature check first**;
  (3) parse to `WebhookPayload`, wrapped in try/except so an authentic-but-unparsable payload
  logs + still 200s (no Meta retry storm); (4) per message: `SET dedup:<id> NX EX 24h` — first
  writer wins, duplicates skipped; on enqueue failure, **delete the dedup key** so Meta's retry
  reprocesses, then re-raise; (5) ack `{"status":"ok"}`.
- 🐛 Signature always fails → must hash the **raw bytes** as received (re-serializing changes them).
  Everything 403s → `WHATSAPP_APP_SECRET` mismatch. Message received but not processed → check the
  `enqueued` log + that the consumer is running.

### `app/whatsapp/message_types.py`
Pydantic models mirroring Meta's nesting (`WebhookPayload → entry[] → changes[] → value → messages[]`).
`extra="allow"` keeps unknown fields (a Meta update won't 500 you). `from_: str = Field(alias="from")`
because `from` is a keyword. `iter_messages()` flattens the nesting into one loop; `(… or [])`
guards status-only webhooks with no messages.
- 🐛 Field "missing" → it's in the model's extra fields. Parse blew up → a required field
  (`id`/`from`/`type`) was absent.

### `app/utils/phone.py`
`normalize_phone()` → `+91XXXXXXXXXX`. `re.sub(r"\D","",raw)` strips non-digits; trims `91`/`0`
prefixes; requires exactly 10 digits starting 6–9; else **raises ValueError** (so a bad number
can never be silently stored).
- 🐛 Valid number rejected → count digits after stripping; landlines/short-codes fail by design.

---

## Group 3 — Queue

### `app/queue/redis_client.py`
Lazy singleton `get_redis()` builds the async client once from `UPSTASH_REDIS_URL` via
`from_url(...)`. `rediss://` scheme = TLS (this broke when `.env` had the REST `https://` URL).
`decode_responses=True` → `str` not bytes. `set_context`/`get_context` = the 24h conversation
cache (`SET key val EX 86400`, JSON-encoded).
- ⚠️ The `_redis` singleton binds to one asyncio loop — reusing it across separate `asyncio.run()`
  calls fails (the harmless test-cleanup error).
- 🐛 Connection errors → URL scheme must be `rediss://` with native (not REST) creds.

### `app/queue/producer.py`
`push(queue, payload)` = `rpush` (append to tail) of a JSON string. Redis list = queue.
- 🐛 Consumer never gets it → producer and consumer must use the same `queue_name`.

### `app/queue/consumer.py`
Separate process (`python -m app.queue.consumer`). `run()` loops forever; `blpop(queue, timeout=5)`
**blocks** until a message arrives (efficient, not polling — the reason we need native Redis).
Returns `(queue, value)`; JSON-decode with a try/except so one bad item can't kill the worker;
`handle()` is currently a stub (prints) — the `# TODO` is to wire `classify→extract→generate`.
- 🐛 Messages pile up, nothing happens → the consumer process isn't running (starting uvicorn does
  NOT start it).

---

## Group 4 — The AI brain

### `app/ai/openai_client.py`
`get_openai()` = `@lru_cache` singleton; `AsyncOpenAI(..., max_retries=3)` (SDK retries 429/5xx).
`complete_json()` calls chat completions with `temperature=0.0` (deterministic) and
`response_format={"type":"json_object"}` (guaranteed valid JSON), then `json.loads` the reply.
- 🐛 `AuthenticationError` → bad `OPENAI_API_KEY`. Weird result → print raw
  `resp.choices[0].message.content` before `json.loads`.

### `app/core/intent_classifier.py`
Loads the prompt as a `string.Template` **once at import** (uses `$placeholders` so the JSON
example's `{ }` don't clash with `str.format`). `classify()` fills the template, calls the LLM,
then the **trust gate**: intent not in `VALID_INTENTS` or `confidence < 0.70` → force `unknown` +
`escalate=True` (Critical Rule #8). Returns typed `IntentResult`.
- 🐛 Everything escalating → low confidences or intent strings not matching `VALID_INTENTS`.
  Prompt edit not taking effect → restart (cached at import).

### `app/core/entity_extractor.py`
Injects **today's date (IST)** so the model resolves "kal" → real ISO date. `_refinement_for()`
appends `order_parser.txt`/`payment_parser.txt` based on intent. `flat = data.get("entities", data)`
accepts flat or nested output. `_as_int`/`_as_float` coerce the LLM's `"50"`/`50`/`null` into
clean types. Returns `EntityResult` (all fields Optional — "return null, never guess").
- 🐛 Wrong dates → check `_today_ist()`. String where int expected → that's what `_as_*` handle.

### `app/core/action_generator.py`
**Pure logic, no LLM.** `_INTENT_ACTION` dict maps intent → action; `.get(intent, ESCALATE_TO_OWNER)`
means any unmapped intent safely escalates. A leading gate re-checks confidence/escalate.
`_entity_fields()` drops `None`s so the `ProposedAction` carries only what was found — ready for the
confirm engine.
- 🐛 Unexpected escalation → check incoming `confidence`/`escalate` and whether the intent is in
  `_INTENT_ACTION`. Missing confirmation fields → they were `None` and got filtered out.

---

## Group 5 — Data + scripts

### `app/db/supabase_client.py`
Async lazy singleton using `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (the REST client) — **different**
from `SUPABASE_DB_URL` (raw Postgres, used only by migrations). Service key = admin, server-side only
(see the RLS TODO). Not used by a feature yet (repositories come later).

### `app/db/migrations/001_initial.sql`
`CREATE EXTENSION vector` (for embeddings). `CREATE TABLE IF NOT EXISTS` = idempotent (safe re-run).
`REFERENCES businesses(id)` = foreign keys (can't orphan a row). `UNIQUE(whatsapp_message_id)` =
DB-level dedup backstop. Bottom indexes speed up hot lookups.
- 🐛 "foreign key violation" → inserting a child before its parent. "duplicate key" → the UNIQUE doing its job.

### `scripts/setup_db.py`
Standalone (calls `load_dotenv()` itself). Connects via `psycopg` over `SUPABASE_DB_URL` with
`autocommit=True` (needed for DDL), runs `*.sql` in sorted order. Exit code 0 = ok, non-zero = fail.
- 🐛 "could not translate host name" → placeholder still in the URL. "password authentication failed"
  → wrong password or unencoded special char (`@` → `%40`).

### `scripts/test_webhook_local.py`
Fabricates + signs a WhatsApp payload and POSTs it, so you can test the webhook without Meta. Uses
`content=body` (exact signed bytes). Signed → 200, `--unsigned` → 403.

### `tests/test_phone_normalizer.py`
`@pytest.mark.parametrize` runs one function across many inputs; `pytest.raises(ValueError)` asserts
bad input is rejected. Run: `python -m pytest tests/ -v`.

---

## Debugging by symptom

| Symptom | Look here |
|---|---|
| Nothing happens on a message | Is the **consumer process** running? (separate from uvicorn) |
| Everything 403s | `WHATSAPP_APP_SECRET` (webhook) / `WHATSAPP_VERIFY_TOKEN` (verify) |
| "X must be set in .env" | Env var **name** mismatch — `config.py` is the source of truth |
| Wrong AI output | Print raw `complete_json` response; confirm `temperature=0`; restart if a prompt changed |
| DB errors | Foreign-key insert order, or connection-string format |
| Redis connection errors | `rediss://` scheme + native (not REST) creds |

---
---

# Part 2 — The "Act & Remember" half

Part 1 covered *understanding* a message. This part covers everything after: talking back
on WhatsApp, asking permission, writing to the DB, voice notes, and the memory layer.

## The full loop

```
WhatsApp msg (text OR voice)
   → webhook: verify sig, dedup, enqueue {message, phone_number_id}
   → consumer → route():
        ├─ voice? → whisper transcribe                 (ears)
        ├─ resolve business + contact
        ├─ enrich: recall history + relationship        (memory)
        ├─ persist message                              (memory)
        ├─ classify → extract → generate (with context) (brain)
        └─ send_confirmation → 📱 "📦 … [Confirm][Edit][Skip]"   (manners → mouth)
   → you tap "1" → webhook → route → handle_reply
        └─ claim_pending (once!) → execute:             (hands)
             contact upsert → order (ORD-…) → stats → reminder
        └─ "✅ Order logged (ORD-2026-001). Reminder set for …"
```
The web server and consumer are separate processes; they only talk through Redis.

## Group 1 — The mouth (`app/whatsapp/`)

### `client.py` — low-level HTTP to Meta
- `_RateLimiter` enforces ≤80 msg/s (Rule #9): a lock + last-send timestamp spaces sends to
  1/80s apart. Uses `time.monotonic()` (forward-only clock).
- `send_message()` — the single outbound choke point. Retry loop: 429/5xx → wait + exponential
  backoff; 4xx → raise immediately (no point retrying a bad request). Logs `wa_message_id` only.
- `get_media_url()` / `download_media()` — the two-hop voice download (id → temp URL → bytes);
  both require the access token.
- 🐛 4xx `wa_send_failed` body = the real reason (bad number / expired token / outside 24h).

### `sender.py` — the three send helpers
- `send_text` (session), `send_interactive` (the 1/2/3 buttons), `send_template` (works anytime).
- Each normalizes the number first (`_wa_number` strips `+` → Meta's format).
- 🐛 `send_text`/`send_interactive` are **session** messages — only within 24h of the user
  messaging you. `send_template` is the only cold-open path (why first contact used `hello_world`).

### `templates.py` — registry mapping internal names → approved template + params.

## Group 2 — The manners (`app/core/confirm_engine.py`)

- `send_confirmation(business, action, source_message_id)` — LLM writes a short Hindi summary
  (`summary_generator.txt`), `send_interactive` the buttons, THEN write the `pending_confirmations`
  row (so `whatsapp_confirm_sent=True` is honest). `proposed_action.model_dump()` freezes the whole
  action as JSON — the reply button only says "1", so the details must be stored to replay.
- `handle_reply(business_id, owner_phone, reply)`:
  - `get_latest_pending()` — the tap doesn't say which confirmation; grab newest `pending`.
  - **`claim_pending()`** = conditional update `SET status=... WHERE id=X AND status='pending'`.
    Only the first caller flips it and gets rows; a concurrent/duplicate tap gets 0 rows →
    `already_handled`, does NOT execute. This is the duplicate-order guard.
  - `1` → claim + `execute()`; `2` → edited; `3` → ignored; else → re-send buttons.
- 🐛 tapped 1 but no order → `reply_already_handled` (race) vs `no_pending` (status not pending).

## Group 3 — The hands (`app/core/action_executor.py` + repos)

- Repository pattern: one file per table under `app/db/repositories/`. No raw queries elsewhere.
- `execute(action, business_id, source_message_id)` routes by `action_type`.
- `_create_order`: (1) `contact_repo.get_or_create` → (2) `order_repo.next_order_number` + insert
  (with `source_message_id`, `confirmed_by_owner=True`) → (3) `contact_repo.increment_stats` →
  (4) `task_repo.create` a reminder if `_reminder_date` resolves (`net-7 → today+7` in IST).
- `order_repo.next_order_number` = **MAX(suffix)+1** (survives deletions; count would collide).
- `contact_repo.get_or_create` catches the UNIQUE race and re-fetches.
- `contact_repo.increment_stats` = read-modify-write (documented Phase-1 race).
- 🐛 order missing → check `executed` log then Supabase; FK violation → child before parent.

## Group 4 — The ears (`app/ai/whisper.py`, `app/parsers/voice_parser.py`)

- `whisper.transcribe(bytes, filename, language="hi")` — `file=(name, bytes)` tuple (SDK detects
  format from the name extension); `language="hi"` boosts Hindi accuracy; inherits SDK retries.
- `voice_parser.parse(media_id)` = `get_media_url` → `download_media` → `transcribe`. Logs id +
  length only, never the transcript (Rule #1).
- Voice adds NO second pipeline — it produces text that flows into the same classify→extract→confirm.
- 🐛 `voice_parse_failed` → 401 (expired token) or 404 (media URL expired — download promptly).

## Group 5 — The memory + the conductor

### `app/db/repositories/message_repo.py`
- `create` (idempotent on `whatsapp_message_id`) stores the raw message immediately;
  `update_analysis` attaches intent/entities *after* the AI runs (two-phase, so a failed AI step
  never loses the raw message). `get_recent` powers history recall.

### `app/core/context_enricher.py`
- `enrich(business_id, contact_id)` → `EnrichedContext(contact, history, recent_orders, is_known)`.
- `_history` = cache-aside: Redis (`contact:{id}`) → miss → DB `get_recent` → repopulate (300s TTL).
- Unknown/new contact → empty defaults (pipeline behaves as pre-enrichment for strangers).

### `app/core/message_router.py` — the conductor
- Holds no business logic; pure orchestration calling every group.
- Order matters: **enrich BEFORE persisting the current message** so history = earlier messages.
- Fed by the webhook (`{message, phone_number_id}`) via the consumer. `phone_number_id` is how it
  knows which business received the message.
- 🐛 Follow the breadcrumbs: `enqueued → enriched → routed → confirmation_sent/escalated →
  reply_handled → executed`. Where the chain stops is where to look.

## Debugging by symptom (Part 2)

| Symptom | Look here |
|---|---|
| Confirmation sent but no DB row | `send_interactive` ok, `repo.create` threw (Supabase creds/schema) |
| No confirmation arrives | 24h session window closed, or wrong owner phone |
| Tapped 1, no order | `reply_already_handled` (race) vs `no_pending` (status/expired) |
| Voice fails | `voice_parse_failed` → 401 (token) / 404 (media URL expired) |
| Stale contact history | 5-min Redis cache — clear `contact:{id}:context` |
| Duplicate order numbers | Concurrent orders — needs Postgres sequence + `UNIQUE(order_number)` |

---
---

# Part 3 — Testing

Layout under `tests/`:
- `conftest.py` — loads the fixture corpus; the `patch_json` fixture stubs `complete_json` with a
  canned async response (mocks the LLM without hitting OpenAI).
- `fixtures/sample_messages.json` — 50 labeled Hindi/Hinglish messages (all 8 intents, 11 flagged
  ambiguous). `fixtures/sample_voice_notes/` — 3 `.ogg`/opus notes + `labels.json`.
- `test_intent_classifier.py` / `test_entity_extractor.py` — **mocked** logic tests (confidence
  gate → unknown+escalate, type coercion, null handling, nested-shape) that always run, PLUS
  **live** eval tests gated behind `RUN_LIVE_EVAL=1` (real classifier vs corpus → ≥90% intent
  accuracy, `kal → tomorrow` date resolution, entity-ambiguity flagging).
- `test_webhook.py` — signature valid/invalid/missing/tampered → 200/403, duplicate id → idempotent.
  Redis + `push` are mocked so it stays pure/fast.
- `test_phone_normalizer.py` — every format + 9-digit / non-numeric edge cases.

Run: `pytest tests/` (mocked, ~0.5s) or `RUN_LIVE_EVAL=1 pytest tests/` (adds ~50 OpenAI calls).

**Design note — two kinds of ambiguity.** *Intent*-ambiguity (gibberish → `unknown`) is caught by
the classifier; *entity*-ambiguity ("kuch piece bhej do" — clear intent, missing quantity) is caught
by the extractor (null qty + `ambiguities`). Tests assert each at the correct layer.

**`app/parsers/text_parser.py`** (LAK-12): extracts the text body and NFC-normalizes it (so Hindi
combining characters store/compare consistently). `route()` uses it for `type == "text"`.
