"""Tes verdict kanonik (audit QA 7 Okt) — satu sumber keputusan, tidak boleh kontradiktif.

Yang dijaga di sini BUKAN tampilan, melainkan ATURAN:
1. Tanpa split beku, Polymarket TIDAK BOLEH "promotable" walau statistiknya bagus (ADR-003).
2. Bukti di bawah PRELIMINARY tidak boleh promotable, apa pun angkanya.
3. Pelanggaran risiko (breach) selalu memblokir.
4. Mesin beku selalu memblokir (IDX).
5. Expectancy/PnL negatif memblokir — pakem mengukur KEMATANGAN SAMPEL, bukan arah hasil.
   (Bug nyata yang ditemukan saat menguji: GMGN berlabel PRELIMINARY dengan WR 0% dan
   PnL negatif sempat berstatus "LOLOS SEMUA GATE".)
6. Verdict berasal dari backend; headline & alasan blokir selalu terisi bila blocked.
"""

from __future__ import annotations

from warroom_core.db import session_scope
from warroom_core.verdict import verdict_pasar, verdict_semua_pasar


def _fakta(s, kind, key, value, ttl=3600):
    from datetime import UTC, datetime

    from warroom_core.db import Fact

    # observed_at WAJIB (kolom NOT NULL) — diisi eksplisit supaya tes tidak bergantung
    # pada default sisi model yang bisa berubah.
    s.add(
        Fact(
            kind=kind, key=key, value_json=value, source="uji", ttl_s=ttl,
            observed_at=datetime.now(UTC), hash=f"h-{kind}-{key}",
        )
    )


def _sinyal(pasar="polymarket", ada=True, terverifikasi=False, status_data="ada"):
    from warroom_core.sinyal import SinyalPasar

    label = {"polymarket": "Polymarket (favorit 5m)", "crypto": "Crypto (SMC)"}.get(pasar, pasar)
    return SinyalPasar(
        pasar=pasar, label=label, ada=ada, subjek="favorit", arah="BELI",
        skor=78, tier="EDGE", terverifikasi=terverifikasi, status_data=status_data,
    )


def test_polymarket_tanpa_split_tidak_boleh_promotable(db) -> None:
    """ADR-003: split beku wajib. Statistik bagus TIDAK cukup."""
    with session_scope() as s:
        _fakta(s, "snapshot", "pasar_akurasi", {
            "pasar": {"polymarket": {"tersedia": True, "per_setup": {
                "B kandidat": {"n": 179, "n_hari": 40, "winrate_pct": 81.56,
                               "mean_r": 0.02, "total_r": 3.0, "tingkat": "TUNING"}}}}})
    with session_scope() as s:
        v = verdict_pasar(s, _sinyal(terverifikasi=False))
    assert v.promotion_state == "blocked"
    assert v.promotable_edge is False
    assert v.blocked_reason and "split" in v.blocked_reason.lower()
    assert v.observed_edge is True, "edge teramati tetap dicatat terpisah"
    assert v.validated_edge is False


def test_polymarket_dengan_split_boleh_promotable(db) -> None:
    with session_scope() as s:
        _fakta(s, "snapshot", "pasar_akurasi", {
            "pasar": {"polymarket": {"tersedia": True, "per_setup": {
                "B kandidat": {"n": 179, "n_hari": 40, "winrate_pct": 81.56,
                               "mean_r": 0.02, "total_r": 3.0, "tingkat": "TUNING"}}}}})
    with session_scope() as s:
        v = verdict_pasar(s, _sinyal(terverifikasi=True))
    assert v.promotion_state == "promotable", v.blocked_reason
    assert v.promotable_edge is True and v.validated_edge is True


def test_bukti_insufficient_memblokir(db) -> None:
    """Sampel kecil tidak boleh dipromosikan walau tidak ada pelanggaran lain."""
    with session_scope() as s:
        _fakta(s, "snapshot", "pasar_akurasi", {
            "pasar": {"crypto": {"tersedia": True, "per_setup": {
                "SMC": {"n": 5, "n_hari": 3, "winrate_pct": 60.0, "mean_r": 0.4,
                        "total_r": 2.0, "tingkat": "INSUFFICIENT"}}}}})
    with session_scope() as s:
        v = verdict_pasar(s, _sinyal(pasar="crypto", terverifikasi=True))
    assert v.promotion_state == "blocked"
    assert v.blocked_reason and "insufficient" in v.blocked_reason.lower()


def test_expectancy_negatif_memblokir_walau_pakem_matang(db) -> None:
    """Pakem mengukur kematangan sampel, BUKAN arah hasil — dua-duanya harus diperiksa.

    Ini menutup bug yang ditemukan saat menguji: GMGN PRELIMINARY dengan PnL negatif
    sempat berstatus "LOLOS SEMUA GATE".
    """
    with session_scope() as s:
        _fakta(s, "snapshot", "pasar_akurasi", {
            "pasar": {"gmgn": {"tersedia": True, "per_setup": {
                "LP Terukur (mark lokal)": {"n": 31, "winrate_pct": 0.0, "mean_r": -0.5,
                                            "total_r": -15.0, "tingkat": "PRELIMINARY",
                                            "total_pnl_usd": -28.46}}}}})
    with session_scope() as s:
        v = verdict_pasar(s, _sinyal(pasar="gmgn", terverifikasi=True))
    assert v.promotion_state == "blocked"
    assert v.blocked_reason and "PnL" in v.blocked_reason


def test_idx_beku_selalu_blocked(db) -> None:
    """Mesin beku = data historis; tidak boleh dipromosikan apa pun angkanya."""
    with session_scope() as s:
        _fakta(s, "snapshot", "idx_akurasi", {
            "tersedia": True, "per_setup": {
                "ARA_HUNTER": {"n": 198, "n_hari": 40, "winrate_pct": 38.0,
                               "mean_r": -0.7, "total_r": -139.0, "tingkat": "TUNING"}}})
        _fakta(s, "snapshot", "dompet", {"pasar": {"idx": {"invariant": {
            "pelanggaran_1r": 97, "model_breach": True, "terburuk": {"r": -13.84}}}}})
    with session_scope() as s:
        v = verdict_pasar(s, _sinyal(pasar="idx", terverifikasi=True))
    assert v.execution_state == "frozen"
    assert v.risk_state == "breach"
    assert v.promotion_state == "blocked"
    assert "beku" in v.headline.lower() or "historis" in v.headline.lower()


def test_verdict_selalu_punya_headline_dan_alasan(db) -> None:
    """Kontrak UI: headline selalu ada; bila blocked, alasannya wajib terisi."""
    with session_scope() as s:
        rows = verdict_semua_pasar(s)
    assert rows, "harus mengembalikan semua pasar"
    for v in rows:
        assert v.headline, f"{v.pasar}: headline kosong"
        assert v.decision, f"{v.pasar}: decision kosong"
        if v.promotion_state == "blocked":
            assert v.blocked_reason, f"{v.pasar}: blocked tanpa alasan"
