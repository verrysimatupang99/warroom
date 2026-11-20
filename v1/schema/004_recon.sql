-- W1-05: baseline + jejak rekonsiliasi (QA gate)
SET search_path TO v1, public;

CREATE TABLE IF NOT EXISTS account_baseline (
  account_id bigint PRIMARY KEY REFERENCES account(id),
  amount     numeric(20,8) NOT NULL,
  currency   text NOT NULL,
  note       text,
  set_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recon_check (
  id             bigserial PRIMARY KEY,
  account_id     bigint NOT NULL REFERENCES account(id),
  ts             timestamptz NOT NULL DEFAULT now(),
  broker_balance numeric(20,8) NOT NULL,
  ledger_sum     numeric(20,8) NOT NULL,
  baseline       numeric(20,8) NOT NULL,
  expected       numeric(20,8) NOT NULL,
  drift          numeric(20,8) NOT NULL,
  ok             boolean NOT NULL,
  source         text
);
CREATE INDEX IF NOT EXISTS ix_recon_acc_ts ON recon_check (account_id, ts DESC);

GRANT SELECT ON account_baseline, recon_check TO v1api;
GRANT SELECT, INSERT ON recon_check TO v1ingest;
GRANT SELECT, INSERT ON account_baseline TO v1ingest;
GRANT USAGE, SELECT ON SEQUENCE recon_check_id_seq TO v1ingest;
