-- Run once against the approved demo PostgreSQL database. Never reset this
-- lifetime row on deployment. This does not store chat text or API credentials.
BEGIN;
CREATE TABLE IF NOT EXISTS demo_ai_budget (
  id text PRIMARY KEY CHECK (id = 'elsewhere-demo'),
  cap_micro_usd bigint NOT NULL CHECK (cap_micro_usd = 10000000),
  reserved_micro_usd bigint NOT NULL DEFAULT 0 CHECK (reserved_micro_usd >= 0 AND reserved_micro_usd <= cap_micro_usd)
);
INSERT INTO demo_ai_budget (id, cap_micro_usd) VALUES ('elsewhere-demo', 10000000) ON CONFLICT (id) DO NOTHING;
CREATE TABLE IF NOT EXISTS demo_ai_attempts (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS demo_ai_attempts_created ON demo_ai_attempts (created_at);
COMMIT;
