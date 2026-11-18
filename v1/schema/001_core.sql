-- War Room v1 — skema inti (dari nol)
-- Prinsip: satu bentuk untuk semua market; perbedaan di tabel ekstensi.
-- Uang selalu numeric(20,8) + currency eksplisit. Kredensial tidak pernah di tabel domain.

CREATE SCHEMA IF NOT EXISTS v1;
SET search_path TO v1, public;

-- ============ ENUM ============
DO $$ BEGIN
  CREATE TYPE venue_kind    AS ENUM ('broker','exchange','prediction','equity','chain');
  CREATE TYPE market_kind   AS ENUM ('forex','crypto','equity','prediction','onchain');
  CREATE TYPE instr_kind    AS ENUM ('spot','perp','stock','binary','token');
  CREATE TYPE account_mode  AS ENUM ('live','demo','paper');
  CREATE TYPE account_kind  AS ENUM ('broker','exchange','wallet','prediction');
  CREATE TYPE side_t        AS ENUM ('buy','sell');
  CREATE TYPE decision_t    AS ENUM ('approved','rejected','expired');
  CREATE TYPE order_type_t  AS ENUM ('market','limit','stop','swap');
  CREATE TYPE order_status_t AS ENUM ('new','filled','partial','cancelled','rejected');
  CREATE TYPE ledger_kind_t AS ENUM ('trade','fee','swap','funding','settlement',
                                     'deposit','withdrawal','adjustment');
  CREATE TYPE strat_status_t AS ENUM ('draft','paper','live','retired');
  CREATE TYPE run_status_t  AS ENUM ('starting','running','stopped','error');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============ REFERENSI ============
CREATE TABLE IF NOT EXISTS venue (
  id          bigserial PRIMARY KEY,
  code        text NOT NULL UNIQUE,          -- 'exness','okx','polymarket','idx','gmgn'
  kind        venue_kind NOT NULL,
  name        text NOT NULL,
  timezone    text NOT NULL DEFAULT 'UTC',
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account (
  id                  bigserial PRIMARY KEY,
  venue_id            bigint NOT NULL REFERENCES venue(id),
  label               text NOT NULL,
  login_ext           text,                  -- nomor akun / address / email
  currency            text NOT NULL,
  mode                account_mode NOT NULL,
  kind                account_kind NOT NULL,
  leverage            int,
  status              text NOT NULL DEFAULT 'unknown',   -- ok|expired|error|unknown
  status_at           timestamptz,
  vault_credential_id bigint,                -- FK ditambah setelah vault_credential dibuat
  active              boolean NOT NULL DEFAULT true,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (venue_id, login_ext, mode)
);

CREATE TABLE IF NOT EXISTS instrument (
  id             bigserial PRIMARY KEY,
  venue_id       bigint NOT NULL REFERENCES venue(id),
  market         market_kind NOT NULL,
  symbol         text NOT NULL,
  kind           instr_kind NOT NULL,
  quote_ccy      text NOT NULL,
  tick_size      numeric(20,8),
  contract_size  numeric(20,8),
  digits         int,
  active         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (venue_id, symbol, kind)
);

-- ============ STRATEGI (logika di luar platform) ============
CREATE TABLE IF NOT EXISTS strategy (
  id           bigserial PRIMARY KEY,
  code         text NOT NULL UNIQUE,          -- 'mtrb_pro','gold_reaper_hexa','crypto_engine'
  name         text NOT NULL,
  market       market_kind NOT NULL,
  version      text NOT NULL,
  repo_ref     text,                          -- commit/URL tempat kode hidup (di luar sini)
  manifest_json jsonb NOT NULL DEFAULT '{}',  -- parameter, magic, simbol, cara publish sinyal
  status       strat_status_t NOT NULL DEFAULT 'draft',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strategy_run (
  id                bigserial PRIMARY KEY,
  strategy_id       bigint NOT NULL REFERENCES strategy(id),
  account_id        bigint REFERENCES account(id),
  instrument_id     bigint REFERENCES instrument(id),
  magic             bigint,
  params_json       jsonb NOT NULL DEFAULT '{}',
  host              text,                     -- mis. 'webdock','cyber1'
  unit              text,                     -- systemd unit / nama proses
  status            run_status_t NOT NULL DEFAULT 'starting',
  started_at        timestamptz NOT NULL DEFAULT now(),
  stopped_at        timestamptz,
  last_heartbeat_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_run_active
  ON strategy_run (account_id, magic) WHERE stopped_at IS NULL;

-- ============ SINYAL & ORDER ============
CREATE TABLE IF NOT EXISTS signal (
  id              bigserial PRIMARY KEY,
  strategy_run_id bigint NOT NULL REFERENCES strategy_run(id),
  instrument_id   bigint NOT NULL REFERENCES instrument(id),
  ts              timestamptz NOT NULL,
  side            side_t,
  decision        decision_t NOT NULL,
  reason_code     text,                       -- 'DI_LUAR_SESI','SPREAD_TINGGI','RR_KURANG'
  entry           numeric(20,8),
  sl              numeric(20,8),
  tp1             numeric(20,8),
  tp2             numeric(20,8),
  rr              numeric(10,4),
  confidence      numeric(10,4),
  gate_json       jsonb NOT NULL DEFAULT '{}',-- atr, rsi, spread, sesi, ema
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_signal_inst_ts ON signal (instrument_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_signal_dec_ts  ON signal (decision, ts DESC);

CREATE TABLE IF NOT EXISTS "order" (
  id              bigserial PRIMARY KEY,
  account_id      bigint NOT NULL REFERENCES account(id),
  instrument_id   bigint NOT NULL REFERENCES instrument(id),
  strategy_run_id bigint REFERENCES strategy_run(id),
  ext_id          text,
  type            order_type_t NOT NULL,
  side            side_t NOT NULL,
  qty             numeric(20,8) NOT NULL,
  price           numeric(20,8),
  sl              numeric(20,8),
  tp              numeric(20,8),
  status          order_status_t NOT NULL DEFAULT 'new',
  reason          text,
  placed_at       timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_order_ext ON "order" (account_id, ext_id) WHERE ext_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS position (
  id              bigserial PRIMARY KEY,
  account_id      bigint NOT NULL REFERENCES account(id),
  instrument_id   bigint NOT NULL REFERENCES instrument(id),
  strategy_run_id bigint REFERENCES strategy_run(id),
  ext_id          text,
  side            side_t NOT NULL,
  qty_open        numeric(20,8) NOT NULL,
  qty_closed      numeric(20,8) NOT NULL DEFAULT 0,
  entry_price     numeric(20,8) NOT NULL,
  exit_price      numeric(20,8),
  sl              numeric(20,8),
  tp1             numeric(20,8),
  tp2             numeric(20,8),
  be_active       boolean NOT NULL DEFAULT false,
  opened_at       timestamptz NOT NULL,
  closed_at       timestamptz,
  realized_pnl    numeric(20,8),
  fee_total       numeric(20,8) NOT NULL DEFAULT 0,
  swap_total      numeric(20,8) NOT NULL DEFAULT 0,
  r_multiple      numeric(10,4),
  close_reason    text,
  evidence_json   jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_pos_acc_close ON position (account_id, closed_at DESC);
CREATE INDEX IF NOT EXISTS ix_pos_run_open  ON position (strategy_run_id, opened_at DESC);

CREATE TABLE IF NOT EXISTS fill (
  id          bigserial PRIMARY KEY,
  order_id    bigint REFERENCES "order"(id),
  position_id bigint REFERENCES position(id),
  ext_id      text,
  ts          timestamptz NOT NULL,
  price       numeric(20,8) NOT NULL,
  qty         numeric(20,8) NOT NULL,
  fee         numeric(20,8) NOT NULL DEFAULT 0,
  swap        numeric(20,8) NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_fill_pos ON fill (position_id, ts);

-- ============ UANG ============
CREATE TABLE IF NOT EXISTS ledger_entry (
  id            bigserial PRIMARY KEY,
  account_id    bigint NOT NULL REFERENCES account(id),
  ts            timestamptz NOT NULL,
  kind          ledger_kind_t NOT NULL,
  amount        numeric(20,8) NOT NULL,
  currency      text NOT NULL,
  ref_table     text,
  ref_id        bigint,
  balance_after numeric(20,8),
  note          text
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ledger_idem
  ON ledger_entry (account_id, ref_table, ref_id, kind) WHERE ref_table IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_ledger_acc_ts ON ledger_entry (account_id, ts DESC);

CREATE TABLE IF NOT EXISTS account_snapshot (
  account_id   bigint NOT NULL REFERENCES account(id),
  ts           timestamptz NOT NULL,
  balance      numeric(20,8) NOT NULL,
  equity       numeric(20,8) NOT NULL,
  margin       numeric(20,8),
  free_margin  numeric(20,8),
  floating_pnl numeric(20,8),
  currency     text NOT NULL,
  PRIMARY KEY (account_id, ts)
);

-- ============ MARKET DATA ============
CREATE TABLE IF NOT EXISTS candle (
  instrument_id bigint NOT NULL REFERENCES instrument(id),
  tf            text NOT NULL,
  ts            timestamptz NOT NULL,
  o numeric(20,8), h numeric(20,8), l numeric(20,8), c numeric(20,8), v numeric(20,8),
  feed_id       bigint,
  PRIMARY KEY (instrument_id, tf, ts)
);

CREATE TABLE IF NOT EXISTS quote (
  instrument_id bigint NOT NULL REFERENCES instrument(id),
  ts            timestamptz NOT NULL,
  bid numeric(20,8), ask numeric(20,8), last numeric(20,8), spread numeric(20,8),
  feed_id       bigint,
  PRIMARY KEY (instrument_id, ts)
);

-- ============ FEED & OPERASI ============
CREATE TABLE IF NOT EXISTS feed (
  id           bigserial PRIMARY KEY,
  code         text NOT NULL UNIQUE,
  provider     text NOT NULL,
  market       market_kind,
  owner_host   text NOT NULL,
  sla_seconds  int NOT NULL,
  status       text NOT NULL DEFAULT 'unknown',   -- ok|stale|error|unknown
  last_ok_at   timestamptz,
  last_error   text,
  last_error_at timestamptz,
  active       boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS feed_check (
  id         bigserial PRIMARY KEY,
  feed_id    bigint NOT NULL REFERENCES feed(id),
  ts         timestamptz NOT NULL DEFAULT now(),
  latency_ms int,
  ok         boolean NOT NULL,
  detail     text
);
CREATE INDEX IF NOT EXISTS ix_feedcheck ON feed_check (feed_id, ts DESC);

-- ============ JEJAK ============
CREATE TABLE IF NOT EXISTS event (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  actor        text NOT NULL,
  action       text NOT NULL,
  target_table text,
  target_id    bigint,
  before_json  jsonb,
  after_json   jsonb
);
CREATE INDEX IF NOT EXISTS ix_event_ts ON event (ts DESC);
CREATE INDEX IF NOT EXISTS ix_event_target ON event (target_table, target_id);

-- ============ AKSES & VAULT ============
CREATE TABLE IF NOT EXISTS role (
  id              bigserial PRIMARY KEY,
  code            text NOT NULL UNIQUE,      -- owner|researcher|viewer
  permissions_json jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS app_user (
  id           bigserial PRIMARY KEY,
  email        text NOT NULL UNIQUE,
  name         text,
  role_id      bigint REFERENCES role(id),
  active       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz
);

CREATE TABLE IF NOT EXISTS vault_credential (
  id          bigserial PRIMARY KEY,
  label       text NOT NULL,
  provider    text NOT NULL,
  kind        text NOT NULL,                 -- 'login_password','api_key','wallet_pk','investor'
  cipher_blob bytea NOT NULL,
  key_id      text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  rotated_at  timestamptz
);

ALTER TABLE account
  DROP CONSTRAINT IF EXISTS account_vault_fk;
ALTER TABLE account
  ADD CONSTRAINT account_vault_fk
  FOREIGN KEY (vault_credential_id) REFERENCES vault_credential(id);

-- ============ EDITORIAL ============
CREATE TABLE IF NOT EXISTS journal (
  id            bigserial PRIMARY KEY,
  ts            timestamptz NOT NULL DEFAULT now(),
  market        market_kind,
  instrument_id bigint REFERENCES instrument(id),
  position_id   bigint REFERENCES position(id),
  tag           text,
  note          text NOT NULL,
  evidence_uri  text,
  created_by    bigint REFERENCES app_user(id)
);
CREATE INDEX IF NOT EXISTS ix_journal_ts ON journal (ts DESC);

-- ============ EKSTENSI PER MARKET ============
CREATE TABLE IF NOT EXISTS prediction_event (
  id         bigserial PRIMARY KEY,
  venue_id   bigint NOT NULL REFERENCES venue(id),
  slug       text NOT NULL,
  title      text NOT NULL,
  category   text,
  close_at   timestamptz,
  resolve_at timestamptz,
  resolution text,
  UNIQUE (venue_id, slug)
);

CREATE TABLE IF NOT EXISTS prediction_outcome (
  instrument_id bigint PRIMARY KEY REFERENCES instrument(id),
  event_id      bigint NOT NULL REFERENCES prediction_event(id),
  outcome       text NOT NULL,
  payout_ratio  numeric(12,6)
);

CREATE TABLE IF NOT EXISTS equity_profile (
  instrument_id bigint PRIMARY KEY REFERENCES instrument(id),
  sector        text,
  board         text,
  market_cap    numeric(24,2),
  eps           numeric(20,8),
  pe            numeric(12,4),
  div_yield     numeric(12,4)
);

CREATE TABLE IF NOT EXISTS token_profile (
  instrument_id bigint PRIMARY KEY REFERENCES instrument(id),
  chain         text NOT NULL,
  contract      text NOT NULL,
  liquidity_usd numeric(24,2),
  holders       int,
  lp_locked     boolean,
  lp_burned     boolean,
  rug_flags_json jsonb NOT NULL DEFAULT '{}'
);
