"""Registrasi handler job ke schedule."""

from __future__ import annotations

from typing import Any

from warroom_worker import schedule

from .domain import (
    handler_gmgn_sync,
    handler_lpagent_sync,
    handler_parity_drift,
    handler_poly_sync,
    handler_polybtc_sync,
    handler_reconcile,
    handler_rekonsiliasi_crypto,
    handler_signal_sync,
    handler_verdict_sync,
)
from .formula import (
    handler_konfluensi_feed,
    handler_learner,
    handler_paper_eval,
    handler_paper_scan,
)
from .housekeeping import handler_retensi
from .infra import (
    handler_backup,
    handler_collect,
    handler_denyut,
    handler_forwardtest_watchdog,
    handler_freshness,
    handler_job_health,
    handler_lp_mark,
    handler_notify,
    handler_publish_facts,
    handler_radar_update,
    handler_refresh_snapshot,
    handler_slo_check,
    handler_source_health,
)
from .jurnal import handler_jurnal_sinyal
from .okx import handler_okx_sync
from .strategi import handler_break_retest_scanner, handler_strategi_alert
from .trades_sync import handler_trades_crypto_sync, handler_trades_forex_sync, handler_trades_idx_sync


def register_handlers() -> dict[str, Any]:
    """Daftarkan handler ke `schedule.HANDLERS` (dipanggil sekali saat worker start)."""
    schedule.HANDLERS.update(
        {
            "publish-facts": handler_publish_facts,
            "freshness": handler_freshness,
            "forwardtest-watchdog": handler_forwardtest_watchdog,
            "jurnal-sinyal": handler_jurnal_sinyal,
            "job-health": handler_job_health,
            "notify": handler_notify,
            "collect": handler_collect,
            "refresh-snapshot": handler_refresh_snapshot,
            "radar-update": handler_radar_update,
            "lp-mark": handler_lp_mark,
            "backup": handler_backup,
            "denyut": handler_denyut,
            "poly-sync": handler_poly_sync,
            "verdict-sync": handler_verdict_sync,
            "parity-drift": handler_parity_drift,
            "reconcile": handler_reconcile,
            "gmgn-sync": handler_gmgn_sync,
            "lpagent-sync": handler_lpagent_sync,
            "reconcile-crypto": handler_rekonsiliasi_crypto,
            "signal-sync": handler_signal_sync,
            "polybtc-sync": handler_polybtc_sync,
            "learner": handler_learner,
            "konfluensi-feed": handler_konfluensi_feed,
            "paper-eval": handler_paper_eval,
            "paper-scan": handler_paper_scan,
            "break-retest-scan": handler_break_retest_scanner,
            "strategi-alert": handler_strategi_alert,
            "retention": handler_retensi,
            "source-health": handler_source_health,
            "okx-sync": handler_okx_sync,
            "slo-check": handler_slo_check,
            "trades-crypto-sync": handler_trades_crypto_sync,
            "trades-forex-sync": handler_trades_forex_sync,
            "trades-idx-sync": handler_trades_idx_sync,
        }
    )
    return schedule.HANDLERS

