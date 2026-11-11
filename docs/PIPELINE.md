# BusinessOS - Product & Pipelines

> Snapshot of the complete product as of **2026-11-04**, the internal data-flow, and
> the step-by-step plan to the next thing that matters: **calls**.
> Strategy/north-star lives in [VISION.md](VISION.md); code walkthrough in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. What the product is today

**A business partner that captures a shop's orders with zero typing, keeps the books
itself, and answers the owner's questions from real data.** Today that runs on WhatsApp.

| | State |
|---|---|
| WhatsApp capture loop (text + Hindi voice → confirm → logged + khata) | ✅ live on real infra |
| Multi-item orders (`items` JSONB) | ✅ built |
| Direction = **sale** on inbound (receivable); purchases are outbound, uncaptured | ✅ built (BOS-56) |
| Ask-your-business assistant (owner asks → read-only tool-calling → Hindi answer) | ✅ built, merged (PR #1), proven via `scripts/ask.py` |
| Proactive: 8 PM daily summary, 9 AM payment reminders | ✅ built |
| Concierge call tester (recordings → orders + khata + accuracy report) | 🟡 built, **never run on real call audio** |
| Calls as an ingested channel | ❌ the core bet (below) |
| Item catalog → derived stock · purchase capture · semantic memory · dashboard | ❌ later |

**Honest one-liner:** real but **WhatsApp-only**. Orders mostly happen on *calls*, so calls
is make-or-break - and it sits at a validation gate, not a build gate.

**Blocker for a live phone demo:** Meta **Live mode** (privacy URL + business verification).
Dev mode only delivers dashboard "Test" webhooks. See [GO_LIVE.md](GO_LIVE.md).

---

## 2. Data-flow pipeline - how one message/call becomes a khata entry

### 2a. WhatsApp (live today)

```
inbound WhatsApp (text / voice)
  └─ api/webhook.py        verify X-Hub-Signature-256 · dedup in Redis (nx) · enqueue · ack <1s
       └─ queue/consumer   (separate worker process)
            └─ core/message_router.route()
                 ├─ sender == business phone?  → core/assistant.answer()  → reply   (owner query)
                 └─ otherwise (a customer):
                      ├─ parsers/            text  |  voice → ai/whisper (Hindi)
                      ├─ core/intent_classifier   order_placed / payment / … (+ confidence)
                      ├─ core/entity_extractor    line items, qty, amount, dates, terms
                      ├─ core/context_enricher    contact history (is_known, recent orders)
                      ├─ core/action_generator    → ProposedAction
                      └─ core/confirm_engine      Hindi card + [Confirm][Edit][Skip] to owner
                           └─ owner taps 1 → core/action_executor.execute()
                                └─ order_repo.create(direction="sale", items=[…])
                                   contact stats bumped · payment reminder scheduled
```

Idempotency: primary dedup at the webhook (Redis `dedup:<msg_id>`, nx); `message_repo.create`
is also idempotent on `whatsapp_message_id`; `confirm_engine.claim_pending` guarantees
execute() runs at most once per confirmation.

### 2b. Calls (today = the concierge batch tester; tomorrow = a channel)

```
call recordings folder (.m4a/.amr/… the OEM dialer already saves)
  └─ scripts/concierge_call_orders.py
       ├─ ai/whisper.transcribe(language="hi")
       └─ ai/openai_client.complete_json(EXTRACT_PROMPT)
            → { is_order, items[], customer_name, delivery_location,
                amount, payment_status, confidence, notes }
       └─ printed ORDER LIST + accuracy report (confidence <0.70 → ⚠ CHECK)
```

The extraction shape here **already matches** the production line-item model - turning it
into a channel is wiring, not new intelligence. The unknown is accuracy on *real* calls.

---

## 3. Execution pipeline - from here to a testable calls product

Each step gates the next. **Do not start a step before the one above passes.**

1. **Smoke-test the engine** (today, 1 command)
   `python scripts/concierge_call_orders.py tests/fixtures`
   Confirms transcribe → extract → list runs end to end. *Proves plumbing, not accuracy.*

2. **Get real call audio** (this week, no code)
   Record ~10 realistic Hinglish order calls on a dialer that saves audio (MIUI/One UI/
   ColorOS). Role-play them - no shop needed yet. Cover the messy cases on purpose:
   multi-item · udhaar / "monthly mein likh dena" · background noise / second speaker ·
   a non-order (should return `is_order:false`) · flat/landmark delivery address.

3. **Validate capture = BOS-55** (the real gate)
   Run step 1's command on that folder. Read the accuracy report.
   - **Pass** (orders trustworthy, ⚠ rate low) → step 4.
   - **Fail** → fix the extraction prompt / transcription language handling and re-run.
     This is prompt work, **not** a product build. Don't build the wrapper on weak capture.

4. **Wrap into a testable product = BOS-52** (only if step 3 passes)
   The smallest thing a shopkeeper can use:
   - **Input path** - recordings in regularly (OEM call-recording folder → bulk share / sync).
     No telephony, no IVR, no bot answering the line - that breaks the human-relationship wedge.
   - **Correctable order list** - owner sees today's parsed orders and taps to fix wrong ones.
     The corrections *are* the ongoing accuracy signal.

5. **Pilot with one real shop** (validates willingness to pay, not tech)
   Only now does a real shopkeeper enter. Needs the Meta Live-mode unblock + a fresh
   `businesses` row (DB was wiped).

**What NOT to build:** a telephony/IVR channel, a separate inventory system (stock is
derived), purchase capture, or the dashboard - none of it matters until capture on real
calls is proven (step 3).
