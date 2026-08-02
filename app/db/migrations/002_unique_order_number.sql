-- LAK-35: guarantee order numbers are unique per business at the DB level.
-- The app computes ORD-YYYY-NNN via MAX(suffix)+1; this constraint makes a
-- duplicate impossible even under a concurrent race (the loser's insert fails,
-- and the caller can retry with the next number).
--
-- Wrapped so re-running setup_db.py (which replays all migrations) is a no-op.

DO $$ BEGIN
  ALTER TABLE orders
    ADD CONSTRAINT orders_business_order_number_key UNIQUE (business_id, order_number);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
