-- BusinessOS initial schema (Phase 1)
-- Run against Supabase (PostgreSQL + pgvector).

CREATE EXTENSION IF NOT EXISTS vector;

-- TODO(security): enable Row-Level Security + per-business_id policies on all
-- tenant tables before any anon/client key or dashboard reads them. Phase 1 is
-- server-only via the service key, so RLS is deferred but MUST land before Phase 2.

-- Every business using our platform
CREATE TABLE IF NOT EXISTS businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_name TEXT NOT NULL,
  phone_number TEXT UNIQUE NOT NULL,
  whatsapp_phone_number_id TEXT,
  business_name TEXT,
  vertical TEXT,
  city TEXT,
  language_preference TEXT DEFAULT 'hi',
  onboarded_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE,
  autopilot_level INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Everyone a business communicates with
CREATE TABLE IF NOT EXISTS contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  phone_number TEXT NOT NULL,
  name TEXT,
  role TEXT,
  language TEXT DEFAULT 'hi',
  reliability_score FLOAT DEFAULT 0.5,
  typical_order_size INTEGER,
  payment_terms_days INTEGER,
  last_contacted TIMESTAMPTZ,
  total_orders INTEGER DEFAULT 0,
  total_amount_transacted DECIMAL DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(business_id, phone_number)
);

-- Every message that comes through our system
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  whatsapp_message_id TEXT UNIQUE,
  direction TEXT NOT NULL,
  message_type TEXT NOT NULL,
  raw_content TEXT,
  voice_transcript TEXT,
  processed_content TEXT,
  intent TEXT,
  entities JSONB,
  confidence_score FLOAT,
  embedding vector(1536),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Confirmed orders extracted from messages
CREATE TABLE IF NOT EXISTS orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  source_message_id UUID REFERENCES messages(id),
  order_number TEXT,
  direction TEXT NOT NULL,
  items JSONB,
  total_amount DECIMAL,
  currency TEXT DEFAULT 'INR',
  delivery_date DATE,
  delivery_address TEXT,
  payment_terms TEXT,
  status TEXT DEFAULT 'confirmed',
  payment_status TEXT DEFAULT 'pending',
  notes TEXT,
  confirmed_by_owner BOOLEAN DEFAULT FALSE,
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Payment tracking
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  order_id UUID REFERENCES orders(id),
  amount DECIMAL NOT NULL,
  currency TEXT DEFAULT 'INR',
  direction TEXT NOT NULL,
  due_date DATE,
  paid_date DATE,
  status TEXT DEFAULT 'pending',
  payment_method TEXT,
  upi_id TEXT,
  reminder_count INTEGER DEFAULT 0,
  last_reminder_sent TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks and commitments extracted from conversations
CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  contact_id UUID REFERENCES contacts(id),
  source_message_id UUID REFERENCES messages(id),
  task_type TEXT,
  description TEXT NOT NULL,
  due_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',
  auto_send BOOLEAN DEFAULT FALSE,
  auto_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pending confirmations waiting for owner input
CREATE TABLE IF NOT EXISTS pending_confirmations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  message_id UUID REFERENCES messages(id),
  confirmation_type TEXT,
  proposed_action JSONB,
  whatsapp_confirm_sent BOOLEAN DEFAULT FALSE,
  owner_response TEXT,
  status TEXT DEFAULT 'pending',
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily summaries sent to business owners
CREATE TABLE IF NOT EXISTS daily_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  summary_date DATE NOT NULL,
  orders_received INTEGER DEFAULT 0,
  orders_dispatched INTEGER DEFAULT 0,
  payments_received DECIMAL DEFAULT 0,
  payments_due DECIMAL DEFAULT 0,
  pending_follow_ups INTEGER DEFAULT 0,
  summary_text TEXT,
  sent_at TIMESTAMPTZ,
  UNIQUE(business_id, summary_date)
);

-- Helpful indexes for hot lookups
CREATE INDEX IF NOT EXISTS idx_messages_business ON messages(business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_business ON contacts(business_id);
CREATE INDEX IF NOT EXISTS idx_orders_business ON orders(business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_due ON payments(business_id, due_date) WHERE status != 'paid';
