"""Alert siklus hidup strategi (benched/kill/entry/exit).

Yang diuji:
- subjek per kondisi tetap (dedup) vs subjek per trade (kejadian);
- severity benched/critical tidak pernah info untuk kondisi keselamatan uang;
- angka hanya muncul bila pemanggil benar-benar menyuplainya;
- payload transport tanpa kredensial.
"""

from __future__ import annotations

from warroom_notifier.strategy_alert import (
    alert_benched,
    alert_entry,
    alert_exit,
    alert_kill_switch,
    to_payload,
)


def test_benched_subjek_tetap_dan_severity_warning():
    a = alert_benched("smc-tf15", alasan="lewat batas harian")
    assert a.subjek == "strategi/benched:smc-tf15"
    assert a.severity == "warning"
    assert a.kondisi == "benched"


def test_benched_tanpa_angka_tak_menyebut_nol():
    pesan = alert_benched("x", alasan="blokir").pesan
    assert "0" not in pesan


def test_benched_dengan_trade_fee_muncul_di_pesan():
    pesan = alert_benched("x", alasan="lewat batas", trade=4, fee_usd=12.5).pesan
    assert "4 trade" in pesan
    assert "$12.50" in pesan


def test_kill_switch_subjek_dan_severity():
    a = alert_kill_switch("smc-tf15", alasan="3 hari rugi beruntun", posisi_ditutup=2)
    assert a.subjek == "strategi/kill-switch:smc-tf15"
    assert a.severity == "critical"
    assert "2 posisi ditutup" in a.pesan


def test_entry_exit_subjek_per_signal_id():
    masuk = alert_entry(
        "smc",
        signal_id="sig-9",
        pair="BTCUSDT",
        direction="long",
        entry=100,
        stop=98,
    )
    keluar = alert_exit("smc", signal_id="sig-9", pair="BTCUSDT", status="tp1", r=1.2)
    assert masuk.subjek == "trade/sig-9"
    assert keluar.subjek == "trade/sig-9"
    assert masuk.severity == "info" and keluar.severity == "info"
    assert "LONG" in masuk.pesan and "entry 100" in masuk.pesan
    assert "stop 98" in masuk.pesan
    assert "+1.200R" in keluar.pesan


def test_exit_tanpa_r_tak_menyebut_angka():
    pesan = alert_exit("smc", signal_id="s", pair="ETHUSDT", status="sl").pesan
    assert "sl" in pesan and "(" not in pesan


def test_to_payload_tanpa_kredensial():
    k = alert_kill_switch("smc", alasan="halt owner")
    payload = to_payload(k)
    assert set(payload) == {"strategi", "kondisi", "suggested_action"}
    teks = str(payload).lower()
    assert "token" not in teks and "webhook" not in teks and "password" not in teks


def test_subjek_kondisi_berbeda_tidak_saling_menahan():
    """Subjek benched/kill berbeda → alert lama benched tak menahan alert kill."""
    benched = alert_benched("smc", alasan="batas")
    kill = alert_kill_switch("smc", alasan="halt")
    assert benched.subjek != kill.subjek
