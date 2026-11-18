-- War Room v1 — risk rule + seed data nyata (bukan contoh)
SET search_path TO v1, public;

CREATE TABLE IF NOT EXISTS risk_rule (
  id         bigserial PRIMARY KEY,
  scope      text NOT NULL,          -- global|market|account|strategy
  ref_id     bigint,
  kind       text NOT NULL,          -- daily_loss_pct|per_trade_pct|max_open|max_exposure_pct
  value      numeric(20,8) NOT NULL,
  note       text,
  active     boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (scope, ref_id, kind)
);

-- ---------- VENUE ----------
INSERT INTO venue (code, kind, name, timezone) VALUES
  ('exness', 'broker', 'Exness Technologies Ltd', 'Etc/UTC')
ON CONFLICT (code) DO NOTHING;

-- ---------- AKUN ----------
INSERT INTO account (venue_id, label, login_ext, currency, mode, kind, leverage, status)
SELECT v.id, x.label, x.login_ext, x.currency, x.mode::account_mode, 'broker'::account_kind,
       x.lev, 'unknown'
FROM (VALUES
  ('LIVE Cent 452009427', '452009427', 'USC', 'live', 2000),
  ('Demo 464202979',      '464202979', 'USD', 'demo', 2000)
) AS x(label, login_ext, currency, mode, lev)
JOIN venue v ON v.code = 'exness'
ON CONFLICT (venue_id, login_ext, mode) DO NOTHING;

-- ---------- INSTRUMEN ----------
INSERT INTO instrument (venue_id, market, symbol, kind, quote_ccy, tick_size, contract_size, digits)
SELECT v.id, 'forex'::market_kind, x.symbol, 'spot'::instr_kind, 'USD', x.tick, x.cs, x.dig
FROM (VALUES
  ('XAUUSDc', 0.001::numeric, 1::numeric,  3),
  ('XAUUSDm', 0.001::numeric, 1::numeric,  3),
  ('EURUSDc', 0.00001::numeric, 100000::numeric, 5)
) AS x(symbol, tick, cs, dig)
JOIN venue v ON v.code = 'exness'
ON CONFLICT (venue_id, symbol, kind) DO NOTHING;

-- ---------- STRATEGI (kode hidup di luar platform) ----------
INSERT INTO strategy (code, name, market, version, repo_ref, manifest_json, status) VALUES
  ('gold_reaper_hexa', 'GOLD Reaper Hexa', 'forex', '3.00',
   'mtrb-pro? no — sumber: sesi Antigravity (GOLD_Reaper_Hexa.mq5)',
   '{"magic":20261104,"symbol":"XAUUSDc","tf":"M5","publish":"file-status-json"}', 'live'),
  ('mtrb_pro', 'MTRB Pro', 'forex', '3.08',
   'github.com/Darkwinter777/mtrb-pro',
   '{"magic":772001,"symbol":"XAUUSDm","tf":"M5","publish":"file-status-json"}', 'paper')
ON CONFLICT (code) DO NOTHING;

-- ---------- STRATEGY RUN (yang benar-benar jalan sekarang) ----------
INSERT INTO strategy_run (strategy_id, account_id, instrument_id, magic, params_json, host, unit, status, last_heartbeat_at)
SELECT s.id, a.id, i.id, 20261104,
       '{"risk_pct":0.5,"max_trades_day":6,"max_daily_loss_pct":2.0,"spread_max":0.35}'::jsonb,
       'webdock', 'mt5-ex-live', 'running', now()
FROM strategy s, account a, instrument i
WHERE s.code = 'gold_reaper_hexa' AND a.login_ext = '452009427' AND i.symbol = 'XAUUSDc'
ON CONFLICT DO NOTHING;

INSERT INTO strategy_run (strategy_id, account_id, instrument_id, magic, params_json, host, unit, status, last_heartbeat_at)
SELECT s.id, a.id, i.id, 772001,
       '{"lot":0.01,"max_open_risk":50,"daily_loss_pct":4.0}'::jsonb,
       'webdock', 'mt5-ex-demo', 'running', now()
FROM strategy s, account a, instrument i
WHERE s.code = 'mtrb_pro' AND a.login_ext = '464202979' AND i.symbol = 'XAUUSDm'
ON CONFLICT DO NOTHING;

-- ---------- FEED REGISTRY ----------
INSERT INTO feed (code, provider, market, owner_host, sla_seconds, status, last_ok_at) VALUES
  ('mt5_live',   'exness-status-json', 'forex',      'webdock', 15,  'ok', now()),
  ('mt5_demo',   'mtrb-status-json',   'forex',      'webdock', 10,  'ok', now()),
  ('okx',        'okx-rest',           'crypto',     'webdock', 30,  'unknown', NULL),
  ('gmgn',       'gmgn-rpc',           'onchain',    'webdock', 60,  'unknown', NULL),
  ('polymarket', 'gamma-rest',         'prediction', 'webdock', 300, 'unknown', NULL),
  ('idx',        'idx-yahoo',          'equity',     'webdock', 900, 'unknown', NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------- BATAS RISIKO (seed yang disetujui) ----------
INSERT INTO risk_rule (scope, ref_id, kind, value, note) VALUES
  ('global', NULL, 'daily_loss_pct', 3.0,  'batas rugi harian semua akun'),
  ('market', NULL, 'per_trade_pct',  0.5,  'forex: 0,5% per trade'),
  ('market', NULL, 'max_open',       3,    'maks 3 posisi terbuka per market'),
  ('global', NULL, 'max_exposure_pct', 10.0, 'total exposure maks 10% equity')
ON CONFLICT (scope, ref_id, kind) DO NOTHING;

-- ---------- VERIFIKASI ----------
SELECT 'venue' t, count(*) n FROM venue
UNION ALL SELECT 'account', count(*) FROM account
UNION ALL SELECT 'instrument', count(*) FROM instrument
UNION ALL SELECT 'strategy', count(*) FROM strategy
UNION ALL SELECT 'strategy_run', count(*) FROM strategy_run
UNION ALL SELECT 'feed', count(*) FROM feed
UNION ALL SELECT 'risk_rule', count(*) FROM risk_rule;
