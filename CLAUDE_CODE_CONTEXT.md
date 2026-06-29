# Project Dhaaga — Complete Technical Bible & Claude Code Onboarding Document
> WhatsApp-native AI Operating System for Indian SMBs
> Version 1.0 | For internal use + Claude Code context

---

## 0. How to use this document

Paste this entire file into Claude Code at the start of every session.
It is the single source of truth for what we're building, why, and how.
Claude Code should read every section before writing a single line of code.

---

## 1. What We Are Building — In Extreme Depth

### 1.1 The One-Line Truth

We are building an AI layer that sits on top of WhatsApp Business API and turns
unstructured Indian SMB communication — voice notes, informal texts, PDFs, images —
into structured business operations automatically.

### 1.2 The Problem We're Solving (Technical Framing)

Indian SMBs (textile traders, manufacturers, distributors) run 100% of their
business through WhatsApp. A typical trader receives:

- 200–400 WhatsApp messages per day
- 30–80 voice notes per day (in Hindi/Hinglish)
- 10–20 PDFs (invoices, delivery challans) per day
- Multiple group chats with suppliers and customers

None of this is structured. Orders get lost. Payments get forgotten. Follow-ups
don't happen. There is no ERP, no CRM, no ops tool. WhatsApp IS the operating system.

### 1.3 What Our Product Actually Does

Our system connects to a business owner's WhatsApp Business number via Meta's
Cloud API. Every message that arrives goes through our pipeline:

```
Incoming Message (text/voice/image/PDF)
        ↓
Message Type Detector
        ↓
┌───────────────┬──────────────┬──────────────┬──────────────┐
│  Text Parser  │ Voice Parser │  PDF Parser  │ Image Parser │
│  (GPT-4o mini)│  (Whisper)   │(pdfplumber + │ (GPT-4 vision│
│               │              │  GPT-4o mini)│   )          │
└───────────────┴──────────────┴──────────────┴──────────────┘
        ↓
Intent Classifier
(order / payment / inquiry / delivery / complaint / unknown)
        ↓
Entity Extractor
(who, what quantity, which SKU, what amount, what date, which vendor)
        ↓
Context Enricher
(pulls conversation history + relationship graph from DB)
        ↓
Action Generator
(what should happen: create order, send reminder, update record, flag for review)
        ↓
Confirm-Before-Act Engine
(sends owner a WhatsApp confirmation: "Reply 1 to confirm, 2 to edit")
        ↓
[Owner confirms]
        ↓
Action Executor
(updates DB, sends message to vendor/customer, creates task)
        ↓
Response Sender
(sends confirmation back to owner via WhatsApp)
```

### 1.4 The Confirm-Before-Act Mechanism (Core Trust Bridge)

This is the most important UX decision in the product. The AI NEVER acts
autonomously without owner confirmation in Phase 1.

Flow:
1. Vendor sends: "Bhai 50 piece bhejo kal tak, payment haftey mein"
2. Our system processes: INTENT=order_received, QTY=50, DELIVERY=tomorrow, PAYMENT=net-7
3. System sends owner on WhatsApp:
   ```
   📦 Naya order detect hua:
   ─────────────────────
   Vendor: Ramesh Textiles
   Quantity: 50 pieces
   Delivery: Kal (tomorrow)
   Payment: 7 din mein

   Reply karo:
   1️⃣ Confirm karo
   2️⃣ Edit karo
   3️⃣ Ignore karo
   ```
4. Owner replies "1"
5. System creates order record, schedules payment reminder, logs delivery date
6. System confirms back: "✅ Order logged. Payment reminder set for [date]."

### 1.5 The Memory Graph (Our Deepest Moat)

Every business has a unique relational memory that grows over time:

- **Contact Graph**: Every person the business communicates with, their role
  (customer/vendor/transporter), communication frequency, reliability score
- **Order History**: Every order ever extracted, with SKU patterns per contact
- **Payment Behavior**: Days-to-pay per customer, default payment terms per vendor
- **Language Fingerprints**: How each contact phrases orders, their typical quantities,
  their common abbreviations
- **Commitment Tracker**: Every promise made ("kal bhejta hoon"), automatically
  tracked with follow-up triggers

After 3 months of usage, switching to any competitor means losing this entire
institutional memory. This is our retention moat.

---

## 2. Tech Stack — Every Decision Explained

### 2.1 Backend: Python + FastAPI

**Why Python**: Our core value is AI. Python has the best AI/ML ecosystem.
WhisperAI, LangChain, OpenAI SDK, pdfplumber — all Python-native.

**Why FastAPI**: Async support (critical for webhook handling), automatic API docs,
Pydantic validation, fast enough for our scale.

### 2.2 Database: Supabase (PostgreSQL + pgvector)

**Why Supabase**: Free tier is generous. Built-in auth. PostgreSQL (mature, reliable).
pgvector extension for storing conversation embeddings (needed for semantic search
in memory graph). Real-time subscriptions for dashboard later.

### 2.3 WhatsApp: Meta Cloud API (Direct, No BSP)

**Why direct**: BSPs (Twilio, Wati) charge markup. Meta Cloud API is free for
first 1000 conversations/month. We handle webhooks ourselves.

**Key API concepts**:
- **Webhook**: Meta sends POST request to our server for every incoming message
- **Phone Number ID**: Unique ID for each business WhatsApp number
- **Template Messages**: Pre-approved message formats for outbound (required after
  24h window expires)
- **Session Messages**: Free-form messages within 24h of user-initiated conversation

### 2.4 Voice Transcription: OpenAI Whisper API

**Why Whisper**: Best-in-class Hindi/Hinglish transcription. Handles background noise
better than alternatives. $0.006/minute — extremely cheap.

**Flow**: WhatsApp sends voice note as .ogg file URL → we download → send to
Whisper API → get transcript → feed to intent classifier

### 2.5 AI/NLP: GPT-4o mini

**Why GPT-4o mini**: 98% cheaper than GPT-4. Good enough for intent classification
and entity extraction. We structure our prompts carefully to compensate for smaller
model size.

**Later consideration**: Fine-tune on Indian SMB language patterns. Our data
accumulates with every real business interaction.

### 2.6 PDF Processing: pdfplumber + GPT-4 Vision

**Why two tools**: pdfplumber handles digital PDFs (text extractable). GPT-4 Vision
handles scanned/photographed invoices (images). We detect which type and route
accordingly.

### 2.7 Queue: Redis (via Upstash free tier)

**Why a queue**: WhatsApp webhooks must respond in <1 second or Meta retries.
Heavy AI processing takes 2-5 seconds. We acknowledge webhook immediately, push
to queue, process async.

### 2.8 Hosting: Railway

**Why Railway**: Free tier. Easy Python deployment. Automatic HTTPS (needed for
Meta webhooks). Environment variable management. One-command deploy from GitHub.

### 2.9 Caching: Redis (same Upstash instance)

Cache conversation context per phone number (TTL: 24 hours). Avoids DB hit on
every message.

---

## 3. Complete Database Schema

```sql
-- Every business using our platform
CREATE TABLE businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_name TEXT NOT NULL,
  phone_number TEXT UNIQUE NOT NULL,  -- Their WhatsApp Business number
  whatsapp_phone_number_id TEXT,       -- Meta API Phone Number ID
  business_name TEXT,
  vertical TEXT,                        -- 'textile', 'pharma', 'fmcg', etc.
  city TEXT,
  language_preference TEXT DEFAULT 'hi', -- 'hi', 'gu', 'mr', 'ta'
  onboarded_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE,
  autopilot_level INTEGER DEFAULT 0,   -- 0=all confirm, 1=trust known contacts, 2=full auto
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Everyone a business communicates with
CREATE TABLE contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  phone_number TEXT NOT NULL,
  name TEXT,
  role TEXT,                            -- 'customer', 'vendor', 'transporter', 'unknown'
  language TEXT DEFAULT 'hi',
  reliability_score FLOAT DEFAULT 0.5, -- 0-1, based on payment history
  typical_order_size INTEGER,
  payment_terms_days INTEGER,           -- How many days they typically take to pay
  last_contacted TIMESTAMPTZ,
  total_orders INTEGER DEFAULT 0,
  total_amount_transacted DECIMAL DEFAULT 0,
  notes TEXT,                           -- AI-generated profile of this contact
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(business_id, phone_number)
);

-- Every message that comes through our system
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  whatsapp_message_id TEXT UNIQUE,      -- Meta's message ID (for deduplication)
  direction TEXT NOT NULL,              -- 'inbound', 'outbound'
  message_type TEXT NOT NULL,          -- 'text', 'voice', 'pdf', 'image', 'template'
  raw_content TEXT,                    -- Original message text
  voice_transcript TEXT,               -- If voice note, Whisper transcript
  processed_content TEXT,              -- Cleaned/normalized version
  intent TEXT,                         -- 'order', 'payment', 'inquiry', 'delivery', 'complaint', 'unknown'
  entities JSONB,                      -- Extracted: {qty, sku, amount, date, vendor}
  confidence_score FLOAT,              -- How confident AI is in extraction (0-1)
  embedding vector(1536),             -- pgvector embedding for semantic search
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Confirmed orders extracted from messages
CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  source_message_id UUID REFERENCES messages(id),
  order_number TEXT,                   -- Auto-generated: ORD-2025-001
  direction TEXT NOT NULL,             -- 'incoming' (from customer) or 'outgoing' (to vendor)
  items JSONB,                         -- [{sku, description, qty, unit, rate}]
  total_amount DECIMAL,
  currency TEXT DEFAULT 'INR',
  delivery_date DATE,
  delivery_address TEXT,
  payment_terms TEXT,
  status TEXT DEFAULT 'confirmed',     -- 'pending_confirm', 'confirmed', 'dispatched', 'delivered', 'cancelled'
  payment_status TEXT DEFAULT 'pending', -- 'pending', 'partial', 'paid'
  notes TEXT,
  confirmed_by_owner BOOLEAN DEFAULT FALSE,
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Payment tracking
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  order_id UUID REFERENCES orders(id),
  amount DECIMAL NOT NULL,
  currency TEXT DEFAULT 'INR',
  direction TEXT NOT NULL,             -- 'receivable' or 'payable'
  due_date DATE,
  paid_date DATE,
  status TEXT DEFAULT 'pending',       -- 'pending', 'partial', 'paid', 'overdue'
  payment_method TEXT,                 -- 'upi', 'cash', 'cheque', 'neft'
  upi_id TEXT,
  reminder_count INTEGER DEFAULT 0,
  last_reminder_sent TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks and commitments extracted from conversations
CREATE TABLE tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  source_message_id UUID REFERENCES messages(id),
  task_type TEXT,                      -- 'follow_up', 'delivery', 'payment', 'callback', 'custom'
  description TEXT NOT NULL,
  due_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',       -- 'pending', 'done', 'snoozed', 'cancelled'
  auto_send BOOLEAN DEFAULT FALSE,     -- Whether to auto-send WhatsApp when due
  auto_message TEXT,                   -- Message to send if auto_send is true
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pending confirmations waiting for owner input
CREATE TABLE pending_confirmations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  message_id UUID REFERENCES messages(id),
  confirmation_type TEXT,              -- 'order', 'payment', 'task', 'message_send'
  proposed_action JSONB,               -- What we're asking permission to do
  whatsapp_confirm_sent BOOLEAN DEFAULT FALSE,
  owner_response TEXT,                 -- '1', '2', '3' etc
  status TEXT DEFAULT 'pending',       -- 'pending', 'confirmed', 'edited', 'ignored'
  expires_at TIMESTAMPTZ,             -- Auto-expire after 24h
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily summaries sent to business owners
CREATE TABLE daily_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  summary_date DATE NOT NULL,
  orders_received INTEGER DEFAULT 0,
  orders_dispatched INTEGER DEFAULT 0,
  payments_received DECIMAL DEFAULT 0,
  payments_due DECIMAL DEFAULT 0,
  pending_follow_ups INTEGER DEFAULT 0,
  summary_text TEXT,                   -- Full WhatsApp message sent
  sent_at TIMESTAMPTZ,
  UNIQUE(business_id, summary_date)
);
```

---

## 4. Project File Structure

```
dhaaga/
├── README.md
├── CLAUDE_CODE_CONTEXT.md          ← This file
├── .env.example
├── .gitignore
├── requirements.txt
├── railway.toml                     ← Railway deployment config
│
├── app/
│   ├── main.py                      ← FastAPI app entry point
│   ├── config.py                    ← All env vars and config
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhook.py               ← Meta WhatsApp webhook endpoint
│   │   ├── health.py                ← Health check endpoint
│   │   └── dashboard.py             ← Internal admin endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── message_router.py        ← Routes messages to correct parser
│   │   ├── intent_classifier.py     ← GPT-4o mini intent extraction
│   │   ├── entity_extractor.py      ← Entity extraction (qty, amount, date)
│   │   ├── context_enricher.py      ← Pulls history + relationship graph
│   │   ├── action_generator.py      ← Decides what action to take
│   │   ├── confirm_engine.py        ← Handles confirm-before-act flow
│   │   └── action_executor.py       ← Executes confirmed actions
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── text_parser.py           ← Handles plain text messages
│   │   ├── voice_parser.py          ← Whisper transcription + parse
│   │   ├── pdf_parser.py            ← pdfplumber + GPT-4 Vision
│   │   └── image_parser.py          ← GPT-4 Vision for invoice images
│   │
│   ├── whatsapp/
│   │   ├── __init__.py
│   │   ├── client.py                ← Meta Cloud API client
│   │   ├── message_types.py         ← Pydantic models for WA messages
│   │   ├── templates.py             ← Pre-approved template messages
│   │   └── sender.py                ← Send messages/templates
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── openai_client.py         ← OpenAI API wrapper
│   │   ├── whisper.py               ← Voice transcription
│   │   ├── embeddings.py            ← Generate + store embeddings
│   │   └── prompts/
│   │       ├── intent_classifier.txt
│   │       ├── entity_extractor.txt
│   │       ├── order_parser.txt
│   │       ├── payment_parser.txt
│   │       └── summary_generator.txt
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase_client.py       ← Supabase connection
│   │   ├── migrations/              ← SQL migration files
│   │   │   └── 001_initial.sql      ← Schema from section 3
│   │   ├── repositories/
│   │   │   ├── business_repo.py
│   │   │   ├── contact_repo.py
│   │   │   ├── message_repo.py
│   │   │   ├── order_repo.py
│   │   │   ├── payment_repo.py
│   │   │   └── task_repo.py
│   │
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── redis_client.py          ← Upstash Redis connection
│   │   ├── producer.py              ← Push to queue
│   │   └── consumer.py              ← Process queue (runs as separate worker)
│   │
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── jobs.py                  ← Payment reminders, daily summaries
│   │
│   └── utils/
│       ├── __init__.py
│       ├── language.py              ← Language detection utilities
│       ├── phone.py                 ← Phone number normalization
│       └── logger.py                ← Structured logging
│
├── tests/
│   ├── conftest.py
│   ├── test_intent_classifier.py
│   ├── test_entity_extractor.py
│   ├── test_webhook.py
│   └── fixtures/
│       ├── sample_messages.json     ← Real-world test messages
│       └── sample_voice_notes/      ← Test audio files
│
└── scripts/
    ├── setup_db.py                  ← Run migrations on Supabase
    ├── test_webhook_local.py        ← Simulate WhatsApp message locally
    └── onboard_business.py          ← CLI to register a new business
```

---

## 5. Environment Variables

```bash
# .env.example

# Meta WhatsApp Cloud API
WHATSAPP_ACCESS_TOKEN=          # Meta permanent access token
WHATSAPP_PHONE_NUMBER_ID=       # Your test business phone number ID
WHATSAPP_VERIFY_TOKEN=          # Random string you choose for webhook verification
WHATSAPP_APP_SECRET=            # Meta app secret (for webhook signature verification)

# OpenAI
OPENAI_API_KEY=                 # For GPT-4o mini + Whisper

# Supabase
SUPABASE_URL=                   # https://xxx.supabase.co
SUPABASE_SERVICE_KEY=           # Service role key (full access)

# Upstash Redis
UPSTASH_REDIS_URL=              # rediss://xxx.upstash.io:6379
UPSTASH_REDIS_TOKEN=            # Upstash REST token

# App Config
ENVIRONMENT=development         # 'development' or 'production'
LOG_LEVEL=INFO
PORT=8000

# Feature Flags
CONFIRM_ALL_ACTIONS=true        # Phase 1: always confirm before acting
DAILY_SUMMARY_ENABLED=true
PAYMENT_REMINDERS_ENABLED=true
```

---

## 6. Core AI Prompts

### 6.1 Intent Classifier Prompt

```
You are an AI assistant for an Indian SMB (small business) operations platform.
A business owner's WhatsApp messages are passed to you. Your job is to classify
the INTENT of each message.

CONTEXT:
- Business type: {business_vertical}
- Sender: {contact_name} ({contact_role})
- Conversation history (last 5 messages): {history}

MESSAGE TO CLASSIFY:
"{message}"

AVAILABLE INTENTS:
- order_placed: Customer/vendor placing a new order
- order_inquiry: Asking about an existing order status
- payment_sent: Someone saying they've paid
- payment_request: Asking for payment or sending payment details
- delivery_update: Update about delivery/dispatch
- complaint: Complaint about product, service, or delay
- greeting: Simple hello/acknowledgment
- unknown: Cannot classify with confidence

Respond ONLY with valid JSON:
{
  "intent": "order_placed",
  "confidence": 0.92,
  "reasoning": "Message contains quantity (50 pieces) and delivery timeline (kal tak)"
}
```

### 6.2 Entity Extractor Prompt

```
You are an entity extraction AI for Indian business WhatsApp messages.
Extract ALL business entities from this message.

MESSAGE: "{message}"
INTENT: {intent}
CONTACT HISTORY: {contact_history}

Extract these entities (use null if not present):
- quantity: Number of items (INTEGER)
- unit: Unit of measure (piece/kg/meter/box/etc)
- sku: Product code or description (STRING)
- amount: Money amount in INR (DECIMAL)
- delivery_date: Delivery date mentioned (ISO DATE or relative like "tomorrow")
- payment_date: When payment will be made (ISO DATE or relative)
- payment_terms: Net-7, advance, on-delivery, etc (STRING)
- vendor_name: Person/company name if mentioned (STRING)

IMPORTANT RULES:
- "kal" = tomorrow
- "parso" = day after tomorrow
- "is hafte" = this week
- "agle hafte" = next week
- If quantity is ambiguous, set confidence to LOW
- Do NOT guess. Return null if not clearly stated.

Respond ONLY with valid JSON:
{
  "entities": {
    "quantity": 50,
    "unit": "piece",
    "sku": null,
    "amount": null,
    "delivery_date": "2025-06-15",
    "payment_date": null,
    "payment_terms": "net-7",
    "vendor_name": "Ramesh"
  },
  "confidence": "HIGH",
  "ambiguities": ["SKU not specified - need to check with contact history"]
}
```

### 6.3 Confirm Message Generator Prompt

```
Generate a WhatsApp confirmation message in Hindi for an Indian business owner.
The message should be SHORT, CLEAR, and feel natural — like a trusted assistant.

ACTION TO CONFIRM: {action_type}
EXTRACTED DATA: {entities}
CONTACT: {contact_name}

Rules:
- Keep under 80 words
- Use simple Hindi mixed with English numbers
- Always end with numbered reply options
- Use emojis sparingly (1-2 max)
- Tone: respectful, professional, but friendly

Example output for an order:
"📦 Ramesh bhai ka order aaya:
50 pieces, kal delivery
Payment: 7 din mein

Reply karein:
1 - Confirm
2 - Edit karein
3 - Skip"
```

---

## 7. WhatsApp Webhook Flow (Technical)

### 7.1 Webhook Verification (One-time setup)

```python
# Meta calls GET /webhook with these params to verify our server
# hub.mode = "subscribe"
# hub.verify_token = our WHATSAPP_VERIFY_TOKEN
# hub.challenge = random number we must return

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403)
```

### 7.2 Incoming Message Webhook

```python
# Meta calls POST /webhook for every incoming message
# We MUST respond with 200 OK within 1 second
# We push to Redis queue and process async

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    # 1. Verify webhook signature
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    verify_signature(body, signature)  # Raises if invalid

    # 2. Parse payload
    data = await request.json()

    # 3. Push to Redis queue immediately
    await queue.push("incoming_messages", data)

    # 4. Return 200 immediately (Meta requires this)
    return {"status": "ok"}
```

### 7.3 Message Types We Handle

```python
# WhatsApp sends different structures for different message types
# We normalize ALL of them into our standard format

MESSAGE_TYPE_HANDLERS = {
    "text": handle_text_message,
    "audio": handle_voice_note,      # .ogg voice notes
    "document": handle_document,     # PDFs, docs
    "image": handle_image,           # Invoice photos
    "interactive": handle_interactive, # Button replies (1/2/3)
    "button": handle_button_reply,   # Template button responses
}
```

---

## 8. Phase 1 MVP — Exact Scope

### What we build in weeks 1-6:

**INCLUDE:**
- WhatsApp webhook receive + send
- Text message intent classification (orders + payments only)
- Voice note transcription → intent classification
- Order extraction → confirmation flow → order record creation
- Payment reminder scheduling (manual trigger)
- Daily summary message (hardcoded, sent at 8 PM)
- Basic contact management (auto-create contacts from phone numbers)
- Health check + basic logging

**DO NOT BUILD YET (Phase 2+):**
- PDF parsing
- Multi-language (beyond Hindi/Hinglish)
- Autopilot mode (full auto-execute)
- Dashboard UI
- Embedded payments / UPI links
- Credit scoring
- Mobile app
- Multi-business management

### MVP Success Criteria:
- Business receives order via WhatsApp → owner confirms → order is logged ✅
- Owner sees daily summary every evening ✅
- Payment reminders sent for overdue orders ✅
- 5 real businesses using it daily ✅
- Zero critical bugs for 7 consecutive days ✅

---

## 9. Development Workflow

### Daily Development Cycle:

```bash
# Start local development
cd dhaaga
python -m uvicorn app.main:app --reload --port 8000

# Tunnel local server for Meta webhook testing (use ngrok)
ngrok http 8000
# Copy ngrok HTTPS URL → paste in Meta Developer Console as webhook URL

# Simulate incoming WhatsApp message locally
python scripts/test_webhook_local.py --type text --message "bhai 50 piece bhejo kal tak"
python scripts/test_webhook_local.py --type voice --file tests/fixtures/sample_voice_notes/order1.ogg

# Run tests
pytest tests/ -v

# Deploy to Railway
railway up
```

### Git Branching:
```
main          → always deployable, production
dev           → integration branch
feature/xxx   → individual features
fix/xxx       → bug fixes
```

### Commit Message Format:
```
feat: add voice note transcription via Whisper
fix: handle missing delivery date in entity extractor
test: add sample Hindi order messages to fixtures
```

---

## 10. Critical Rules Claude Code Must Follow

1. **Never store raw WhatsApp message content in logs** — privacy violation risk

2. **Always validate webhook signatures** — anyone can POST to our webhook URL

3. **Respond to webhooks in <1 second** — Meta retries aggressively, causes duplicate processing

4. **Always deduplicate by whatsapp_message_id** — Meta sometimes sends same message twice

5. **Never auto-execute actions** — Phase 1 is ALWAYS confirm-before-act, no exceptions

6. **Handle Indian number formats** — +91XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX — normalize ALL to +91XXXXXXXXXX

7. **Default language is Hindi** — all AI prompts must account for Hindi/Hinglish code-switching

8. **Confidence threshold** — if confidence < 0.70, escalate to owner instead of guessing

9. **Rate limiting** — Max 80 messages/second to WhatsApp API, implement backoff

10. **Idempotent actions** — all database writes must be safe to retry

---

## 11. Testing Strategy

### Unit Tests:
- Intent classifier: test 50 real Hindi SMB messages with known intents
- Entity extractor: test edge cases (partial dates, missing quantities, ambiguous SKUs)
- Phone normalizer: test all Indian number formats
- Webhook signature verifier: test valid + invalid signatures

### Integration Tests:
- Full message flow: text → intent → confirm → create order
- Voice note flow: .ogg → whisper → intent → confirm
- Daily summary generation

### Real-world Test Fixtures (build these first):
```
tests/fixtures/sample_messages.json
Include:
- 10 clear order messages in Hindi
- 5 ambiguous messages (missing quantity/date)
- 5 payment messages
- 5 greetings/unknowns
- 3 complaint messages
- 3 delivery update messages
```

---

## 12. First Week Technical Milestones

| Day | Milestone | Done When |
|-----|-----------|-----------|
| Day 1 | WhatsApp API connected | Can send/receive test message |
| Day 1 | Supabase schema deployed | Tables visible in Supabase dashboard |
| Day 2 | Webhook receiving messages | ngrok logs show incoming messages |
| Day 2 | Text message parsed by GPT-4o mini | Intent returned in console |
| Day 3 | Voice note → Whisper → transcript | Voice note text visible in logs |
| Day 4 | Confirm flow working end-to-end | Owner gets "Reply 1/2/3" message |
| Day 5 | Order saved to database | Order record in Supabase after confirm |
| Day 6 | Daily summary sends at 8 PM | WhatsApp message received at 8 PM |
| Day 7 | First real business tests it | Real human uses it, no crashes |

---

## 13. Startup Context for Claude Code

This is not a side project. This is a funded-startup-track product targeting:
- 500 businesses in 3 months
- YC application in ~3 months
- Series A in 18 months

Every technical decision must balance:
- **Speed**: Ship fast, get real feedback, iterate
- **Reliability**: Cannot lose a business owner's order — that's their livelihood
- **Cost**: Zero money right now — use free tiers everywhere possible
- **Scalability**: Architecture must not require full rewrite at 10,000 users

When in doubt: **ship the simpler version, validate with real users, then improve.**

---

## 14. Key People

- **Founder 1 (Lakshya)**: Full-stack, CS grad, Delhi/NCR. Product, sales, frontend.
- **Founder 2**: Backend + AI, CS grad, Delhi/NCR, fully available. Core pipeline, AI, infra.
- **Target User**: Textile trader, Gandhi Nagar Delhi. Hindi-speaking. 30-60 years old.
  Uses WhatsApp all day. Never used business software in their life.

---

## 15. Session Start Checklist for Claude Code

At the start of every Claude Code session, confirm:

1. Which phase are we in? (Week X of Phase Y)
2. What was the last thing shipped?
3. What broke in the last session?
4. What is today's single most important milestone?
5. Are we building for real users or still in dev mode?

Then build. One feature at a time. Test before moving on.

---

*Document version: 1.0*
*Last updated: Day 0 of build*
*Next update: After first real business onboards*
