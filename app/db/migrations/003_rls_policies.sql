-- LAK-36: enable Row-Level Security on every tenant table.
--
-- The app connects with the service/secret key, which BYPASSES RLS — so enabling
-- RLS does NOT affect server-side access. What it DOES do is deny all anon /
-- authenticated (client-side) access by default (RLS on + no policy = deny-all),
-- which is exactly the posture we want before any browser/dashboard touches the data.
--
-- When a client/dashboard with per-business auth is added, replace the deny-all with
-- per-business policies, e.g.:
--   CREATE POLICY tenant_isolation ON orders FOR ALL TO authenticated
--     USING (business_id = (auth.jwt() ->> 'business_id')::uuid);

ALTER TABLE businesses            ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages              ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders                ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments              ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE pending_confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_summaries       ENABLE ROW LEVEL SECURITY;
