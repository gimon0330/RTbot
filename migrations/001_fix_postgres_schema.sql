CREATE TABLE IF NOT EXISTS userdata (
  id BIGINT PRIMARY KEY,
  money NUMERIC(40, 0) NOT NULL DEFAULT 5000,
  bank NUMERIC(40, 0) NOT NULL DEFAULT 0,
  adminuser INTEGER NOT NULL DEFAULT 0,
  blacklist INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reinforce (
  uuid TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  id BIGINT NOT NULL,
  level INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE userdata
  ALTER COLUMN money TYPE NUMERIC(40, 0) USING money::numeric,
  ALTER COLUMN money SET DEFAULT 5000,
  ALTER COLUMN bank TYPE NUMERIC(40, 0) USING bank::numeric,
  ALTER COLUMN bank SET DEFAULT 0;

ALTER TABLE reinforce ADD COLUMN IF NOT EXISTS uuid TEXT;
UPDATE reinforce
SET uuid = md5(random()::text || clock_timestamp()::text)
WHERE uuid IS NULL;
ALTER TABLE reinforce ALTER COLUMN uuid SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reinforce_user_id ON reinforce(id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reinforce_user_item ON reinforce(id, name);
