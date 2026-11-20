-- W1-08: audit hook di level database (tidak bisa dilewati aplikasi)
-- Prinsip: yang menyentuh uang / identitas / konfigurasi wajib punya jejak.
SET search_path TO v1, public;

CREATE OR REPLACE FUNCTION v1.audit_row() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = v1, public AS $$
DECLARE
  b jsonb;
  a jsonb;
  rec_id bigint;
BEGIN
  b := CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN to_jsonb(OLD) END;
  a := CASE WHEN TG_OP IN ('INSERT','UPDATE') THEN to_jsonb(NEW) END;
  rec_id := COALESCE(
    CASE WHEN TG_OP = 'DELETE' THEN (to_jsonb(OLD)->>'id')::bigint
         ELSE (to_jsonb(NEW)->>'id')::bigint END, 0);

  INSERT INTO v1.event (actor, action, target_table, target_id, before_json, after_json)
  VALUES (session_user, TG_OP || ':' || TG_TABLE_NAME, TG_TABLE_NAME, rec_id, b, a);

  RETURN COALESCE(NEW, OLD);
END $$;

-- akun & identitas
DROP TRIGGER IF EXISTS trg_audit_account ON v1.account;
CREATE TRIGGER trg_audit_account AFTER INSERT OR UPDATE OR DELETE ON v1.account
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

-- uang: ledger append-only
DROP TRIGGER IF EXISTS trg_audit_ledger ON v1.ledger_entry;
CREATE TRIGGER trg_audit_ledger AFTER INSERT OR UPDATE OR DELETE ON v1.ledger_entry
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

-- posisi: buka/tutup saja (bukan tiap tick update)
DROP TRIGGER IF EXISTS trg_audit_position ON v1.position;
CREATE TRIGGER trg_audit_position AFTER INSERT OR DELETE ON v1.position
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

DROP TRIGGER IF EXISTS trg_audit_position_close ON v1.position;
CREATE TRIGGER trg_audit_position_close AFTER UPDATE ON v1.position
  FOR EACH ROW WHEN (OLD.closed_at IS DISTINCT FROM NEW.closed_at)
  EXECUTE FUNCTION v1.audit_row();

-- strategi berjalan
DROP TRIGGER IF EXISTS trg_audit_run ON v1.strategy_run;
CREATE TRIGGER trg_audit_run AFTER INSERT OR DELETE ON v1.strategy_run
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

DROP TRIGGER IF EXISTS trg_audit_run_upd ON v1.strategy_run;
CREATE TRIGGER trg_audit_run_upd AFTER UPDATE ON v1.strategy_run
  FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status
                     OR OLD.stopped_at IS DISTINCT FROM NEW.stopped_at
                     OR OLD.params_json IS DISTINCT FROM NEW.params_json)
  EXECUTE FUNCTION v1.audit_row();

-- feed: hanya saat status berubah (bukan tiap heartbeat)
DROP TRIGGER IF EXISTS trg_audit_feed ON v1.feed;
CREATE TRIGGER trg_audit_feed AFTER INSERT OR DELETE ON v1.feed
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

DROP TRIGGER IF EXISTS trg_audit_feed_status ON v1.feed;
CREATE TRIGGER trg_audit_feed_status AFTER UPDATE ON v1.feed
  FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
  EXECUTE FUNCTION v1.audit_row();

-- batas risiko: paling sensitif
DROP TRIGGER IF EXISTS trg_audit_risk ON v1.risk_rule;
CREATE TRIGGER trg_audit_risk AFTER INSERT OR UPDATE OR DELETE ON v1.risk_rule
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

-- baseline uang
DROP TRIGGER IF EXISTS trg_audit_baseline ON v1.account_baseline;
CREATE TRIGGER trg_audit_baseline AFTER INSERT OR UPDATE OR DELETE ON v1.account_baseline
  FOR EACH ROW EXECUTE FUNCTION v1.audit_row();

-- helper baca jejak
CREATE OR REPLACE VIEW v1.jejak_terbaru AS
SELECT id, ts, actor, action, target_table, target_id, before_json, after_json
FROM v1.event
ORDER BY ts DESC
LIMIT 200;

GRANT SELECT ON v1.jejak_terbaru TO v1api;
