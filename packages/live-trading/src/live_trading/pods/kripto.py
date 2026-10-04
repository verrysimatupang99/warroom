"""Pod Kripto: analis sinyal + bukti + pasar, lead merangkum."""

from __future__ import annotations

from typing import Any

from . import HasilAnalis, LaporanPod, _rangkum


def analis_sinyal(snap: dict[str, Any]) -> HasilAnalis:
    kand = snap.get("kandidat") or []
    boleh = [k for k in kand if k.get("allowed")]
    unik = list({(k.get("pair"), k.get("direction")): k for k in boleh}.values())
    if unik:
        top = ", ".join(f"{k.get('pair')} {k.get('direction')}" for k in unik[:3])
        extra = f" (+{len(boleh) - len(unik)} duplikat)" if len(boleh) > len(unik) else ""
        return HasilAnalis("sinyal", "hijau", [f"{len(unik)} unik lolos: {top}{extra}"])
    if not kand:
        return HasilAnalis("sinyal", "abu", ["belum ada kandidat"])
    alasan = (kand[0].get("rules") or [{}])[0] if isinstance(kand[0].get("rules"), list) else {}
    return HasilAnalis(
        "sinyal", "kuning", [f"{len(kand)} kandidat semua SKIP (mis. {alasan})"]
    )


def analis_bukti(snap: dict[str, Any]) -> HasilAnalis:
    led = snap.get("ledger") or {}
    ukur = snap.get("pengukuran") or {}
    fakta = [f"ledger {led.get('total_r', 0):+.2f}R/{led.get('trade', 0)} trade"]
    status = "hijau"
    lolos = (ukur.get("lolos") or {}) if isinstance(ukur, dict) else {}
    if lolos:
        exp = lolos.get("expectancy_r", 0) or 0
        fakta.append(f"forward lolos exp {exp:+.3f}R n={lolos.get('n', 0)}")
        if exp <= 0:
            status = "merah"
            fakta.append("sistem -EV: jangan live")
    return HasilAnalis("bukti", status, fakta)


def analis_pasar(snap: dict[str, Any]) -> HasilAnalis:
    r = snap.get("risiko") or {}
    if r.get("mode") != "paper":
        return HasilAnalis("pasar", "merah", ["mode bukan paper — eskalasi"])
    return HasilAnalis(
        "pasar",
        "hijau",
        [f"ruang rugi {r.get('sisa_ruang_r', '?')}R, terbuka {r.get('posisi_terbuka', 0)}"],
    )


def lead(snap: dict[str, Any]) -> LaporanPod:
    analis = [analis_sinyal(snap), analis_bukti(snap), analis_pasar(snap)]
    st = _rangkum(analis)
    ringkas = [a.baris() for a in analis]
    return LaporanPod(pod="kripto", status=st, ringkas=ringkas, analis=analis)
