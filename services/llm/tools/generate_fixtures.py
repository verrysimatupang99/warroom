# ruff: noqa: E501
"""Generator fixture repo: berkas prompt (``prompts/``) dan golden eval (``golden/``).

Dijalankan sekali untuk melahirkan berkas statis; skema diambil langsung dari model
pydantic supaya tidak pernah menyimpang. Bukan bagian runtime gateway.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "llm" / "src"))

from warroom_llm.schemas import ROLE_MODELS  # noqa: E402

BODIES = {
    "narrator": (
        "Kamu adalah narator War Room. Tulis narasi ringkas HANYA dari BLOK FAKTA yang diberikan. "
        "Setiap kalimat yang menyebut angka WAJIB menyertakan fact_ids dari blok FAKTA tersebut. "
        "Dilarang mengarang atau menghitung angka baru. Bila fakta tidak cukup, katakan belum bisa disimpulkan. "
        "Keluarkan JSON valid sesuai skema."
    ),
    "verifier": (
        "Kamu adalah verifier War Room. Periksa klaim terhadap BLOK FAKTA. "
        "setuju=true hanya bila SETIAP angka pada klaim didukung fact_id yang ada di blok FAKTA. "
        "Set angka pada fact_ids dan tulis alasan tanpa menambah angka baru. "
        "tingkat=kurang bila fakta tidak mencukupi. Keluarkan JSON valid sesuai skema."
    ),
    "anomaly": (
        "Kamu adalah detektor anomali War Room. Bandingkan deret metrik dengan baseline di BLOK FAKTA. "
        "Laporkan HANYA anomali yang didukung fact_id; magnitudo harus berasal dari fakta, bukan karangan. "
        "Keluarkan JSON valid sesuai skema."
    ),
}
CATATAN = {
    "narrator": "Peran baca: narasi ber-grounding, satu kalimat berangka satu kutipan.",
    "verifier": "Peran baca: pemeriksa klaim sebelum keluaran tampil ke pengguna di area uang/verdict.",
    "anomaly": "Peran baca: deteksi drift winrate, feed mati, dan lonjakan tingkat fallback.",
}
CONTOH = {
    "narrator": [{"kalimat": [{"teks": "win rate 79.0% pada n=1175.", "fact_ids": [101]}], "nada": "netral"}],
    "verifier": [{"setuju": True, "alasan": "angka didukung fakta", "fact_ids": [101], "tingkat": "yakin"}],
    "anomaly": [
        {
            "anomali": [{"metrik": "win_rate", "arah": "naik", "magnitudo": 2.0, "fact_ids": [101]}],
            "catatan": "dipantau",
        }
    ],
}


def tulis_prompts() -> list[str]:
    out = ROOT / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    dibuat = []
    for role, model in ROLE_MODELS.items():
        spec = {
            "role": role,
            "version": f"{role}/1.0.0",
            "body": BODIES[role],
            "schema_json": model.model_json_schema(),
            "contoh": CONTOH[role],
            "catatan": CATATAN[role],
        }
        path = out / f"{role}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        dibuat.append(str(path))
    return dibuat


# --- golden eval ----------------------------------------------------------------------

F1 = {"fact_id": 101, "label": "F1", "text": "n=1175, win=79.0%, be=77.0%, ci=[76.6,81.2]"}
F2 = {"fact_id": 102, "label": "F2", "text": "trades=1200, pnl_usd=42.5"}
DEFAULT_FACTS = [F1, F2]


def kasus(
    cid: str,
    role: str,
    candidate: object,
    verdict: str,
    code: str | None = None,
    *,
    facts: list[dict] | None = None,
    existing: list[int] | None = None,
) -> dict:
    f = facts if facts is not None else DEFAULT_FACTS
    ex = existing if existing is not None else [x["fact_id"] for x in f]
    return {
        "id": cid,
        "role": role,
        "provided_facts": f,
        "existing_fact_ids": ex,
        "candidate": candidate,
        "expect": {"verdict": verdict, "code": code},
    }


def golden_narrator() -> list[dict]:
    ks: list[dict] = []
    oks = [
        ("n tercatat 1175 dengan win rate 79.0%.", [101]),
        ("win rate 79.0% berada di atas be 77.0%.", [101]),
        ("n=1175 dan trades=1200 tercatat pada snapshot.", [101, 102]),
        ("Tidak ada angka baru pada kalimat ini.", []),
        ("Setup lolos ambang berdasarkan interval kepercayaan.", [101]),
        ("Batas bawah interval berada di atas ambang be.", [101]),
        ("n=1175 menunjukkan sampel cukup.", [101]),
        ("win rate 79.0% konsisten dengan be 77.0%.", [101]),
        ("Dua fakta dirujuk: jumlah sampel dan jumlah trade.", [101, 102]),
        ("Catatan naratif tanpa angka apa pun.", []),
        ("Selisih 2.0 persen poin dari ambang.", [101]),
        ("Data terbaru: n=1175.", [101]),
    ]
    for i, (teks, ids) in enumerate(oks, 1):
        ks.append(
            kasus(
                f"narrator-ok-{i:02d}",
                "narrator",
                {"kalimat": [{"teks": teks, "fact_ids": ids}], "nada": "netral"},
                "ok",
            )
        )
    # campuran: kalimat berangka + kalimat bebas
    ks.append(
        kasus(
            "narrator-ok-13",
            "narrator",
            {
                "kalimat": [
                    {"teks": "n=1175.", "fact_ids": [101]},
                    {"teks": "Ringkasan tanpa angka.", "fact_ids": []},
                ],
                "nada": "ringkas",
            },
            "ok",
        )
    )
    ks.append(
        kasus(
            "narrator-ok-14",
            "narrator",
            {
                "kalimat": [
                    {"teks": "win 79.0%", "fact_ids": [101]},
                    {"teks": "pnl 42.5", "fact_ids": [102]},
                ],
                "nada": "tegas",
            },
            "ok",
        )
    )
    ks.append(
        kasus(
            "narrator-ok-15",
            "narrator",
            {"kalimat": [{"teks": "trades 1200", "fact_ids": [102]}], "nada": "netral"},
            "ok",
        )
    )

    g = lambda teks, ids: {"kalimat": [{"teks": teks, "fact_ids": ids}], "nada": "x"}  # noqa: E731
    ks.append(
        kasus("narrator-rej-angka-01", "narrator", g("win rate 80.0%", []), "rejected", "angka_tanpa_fact_id")
    )
    ks.append(
        kasus(
            "narrator-rej-angka-02", "narrator", g("naik 5% hari ini", []), "rejected", "angka_tanpa_fact_id"
        )
    )
    ks.append(
        kasus(
            "narrator-rej-angka-03",
            "narrator",
            {
                "kalimat": [{"teks": "n=1175.", "fact_ids": [101]}, {"teks": "turun 3%.", "fact_ids": []}],
                "nada": "x",
            },
            "rejected",
            "angka_tanpa_fact_id",
        )
    )
    ks.append(
        kasus("narrator-rej-kpn-01", "narrator", g("n=1175.", [999]), "rejected", "fact_id_tidak_diberikan")
    )
    ks.append(
        kasus(
            "narrator-rej-kpn-02",
            "narrator",
            g("win 79.0%", [101, 777]),
            "rejected",
            "fact_id_tidak_diberikan",
        )
    )
    ks.append(
        kasus(
            "narrator-rej-ada-01",
            "narrator",
            g("n=1175.", [101]),
            "rejected",
            "fact_id_tidak_ada",
            facts=[F1],
            existing=[102],
        )
    )
    ks.append(
        kasus(
            "narrator-rej-schema-01",
            "narrator",
            {"kalimat": [{"teks": "n=1175.", "fact_ids": [101]}]},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "narrator-rej-schema-02",
            "narrator",
            {"kalimat": [{"teks": "n=1175.", "fact_ids": [101]}], "nada": "x", "extra": 1},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "narrator-rej-schema-03",
            "narrator",
            {"kalimat": [{"teks": "n=1175."}], "nada": "x"},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "narrator-rej-kredi-01",
            "narrator",
            g("kunci sk-ABCDEF123456", [101]),
            "rejected",
            "kredensial_terdeteksi",
        )
    )
    ks.append(
        kasus(
            "narrator-rej-kredi-02",
            "narrator",
            g("api_key=rahasia123456", [101]),
            "rejected",
            "kredensial_terdeteksi",
        )
    )
    return ks


def golden_verifier() -> list[dict]:
    ks: list[dict] = []
    oks = [
        (True, "angka didukung fakta", [101], "yakin"),
        (True, "win 79.0% cocok dengan F1", [101], "yakin"),
        (False, "fakta tidak mencukupi", [], "kurang"),
        (True, "dua fakta konsisten", [101, 102], "yakin"),
        (False, "klaim memakai angka di luar fakta", [101], "ragu"),
        (True, "tidak ada angka tanpa kutipan", [], "yakin"),
        (True, "n=1175 sesuai", [101], "yakin"),
        (False, "perlu data tambahan", [], "kurang"),
        (True, "pnl 42.5 sesuai F2", [102], "yakin"),
        (True, "setuju berdasarkan interval", [101], "yakin"),
    ]
    for i, (setuju, alasan, ids, tingkat) in enumerate(oks, 1):
        ks.append(
            kasus(
                f"verifier-ok-{i:02d}",
                "verifier",
                {"setuju": setuju, "alasan": alasan, "fact_ids": ids, "tingkat": tingkat},
                "ok",
            )
        )
    ks.append(
        kasus(
            "verifier-ok-11",
            "verifier",
            {"setuju": True, "alasan": "cocok", "fact_ids": [101], "tingkat": "ragu"},
            "ok",
        )
    )
    ks.append(
        kasus(
            "verifier-ok-12",
            "verifier",
            {"setuju": False, "alasan": "kurang bukti", "fact_ids": [], "tingkat": "kurang"},
            "ok",
        )
    )

    def v(setuju, alasan, ids, tingkat):
        return {"setuju": setuju, "alasan": alasan, "fact_ids": ids, "tingkat": tingkat}

    ks.append(
        kasus(
            "verifier-rej-angka-01",
            "verifier",
            v(True, "win 80.0%", [], "yakin"),
            "rejected",
            "angka_tanpa_fact_id",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-angka-02",
            "verifier",
            v(True, "naik 12%", [], "yakin"),
            "rejected",
            "angka_tanpa_fact_id",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-kpn-01",
            "verifier",
            v(True, "ok", [999], "yakin"),
            "rejected",
            "fact_id_tidak_diberikan",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-kpn-02",
            "verifier",
            v(True, "ok", [101, 888], "yakin"),
            "rejected",
            "fact_id_tidak_diberikan",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-ada-01",
            "verifier",
            v(True, "ok", [101], "yakin"),
            "rejected",
            "fact_id_tidak_ada",
            facts=[F1],
            existing=[102],
        )
    )
    ks.append(
        kasus(
            "verifier-rej-schema-01",
            "verifier",
            v(True, "ok", [101], "mungkin"),
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-schema-02",
            "verifier",
            {"setuju": "true", "alasan": "ok", "fact_ids": [101], "tingkat": "yakin"},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-schema-03",
            "verifier",
            {"setuju": True, "fact_ids": [101], "tingkat": "yakin"},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-schema-04",
            "verifier",
            {"setuju": True, "alasan": "ok", "fact_ids": "101", "tingkat": "yakin"},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-schema-05",
            "verifier",
            {"setuju": True, "alasan": "ok", "fact_ids": [101], "tingkat": "yakin", "extra": True},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-kredi-01",
            "verifier",
            v(True, "token sk-ZZZZZZ999999", [101], "yakin"),
            "rejected",
            "kredensial_terdeteksi",
        )
    )
    ks.append(
        kasus(
            "verifier-rej-kredi-02",
            "verifier",
            v(True, "secret=abcdef123456", [101], "yakin"),
            "rejected",
            "kredensial_terdeteksi",
        )
    )
    return ks


def golden_anomaly() -> list[dict]:
    ks: list[dict] = []
    oks = [
        ("win_rate", "naik", 2.0, [101]),
        ("win_rate", "turun", 1.5, [101]),
        ("pnl", "naik", 42.5, [102]),
        ("n", "naik", 1175.0, [101]),
        ("trades", "turun", 1200.0, [102]),
        ("win_rate", "naik", 0.0, [101]),
        ("win_rate", "datar", 0.5, [101, 102]),
        ("pnl", "turun", 3.25, [102]),
        ("n", "datar", 0.0, [101]),
        ("win_rate", "naik", 5.0, [101]),
    ]
    for i, (metrik, arah, mag, ids) in enumerate(oks, 1):
        ks.append(
            kasus(
                f"anomaly-ok-{i:02d}",
                "anomaly",
                {
                    "anomali": [{"metrik": metrik, "arah": arah, "magnitudo": mag, "fact_ids": ids}],
                    "catatan": "dipantau",
                },
                "ok",
            )
        )
    ks.append(
        kasus(
            "anomaly-ok-11",
            "anomaly",
            {
                "anomali": [
                    {"metrik": "a", "arah": "naik", "magnitudo": 1.0, "fact_ids": [101]},
                    {"metrik": "b", "arah": "turun", "magnitudo": 2.0, "fact_ids": [102]},
                ],
                "catatan": "dua sinyal",
            },
            "ok",
        )
    )
    ks.append(
        kasus(
            "anomaly-ok-12",
            "anomaly",
            {
                "anomali": [{"metrik": "a", "arah": "naik", "magnitudo": 1.0, "fact_ids": [101]}],
                "catatan": "lonjakan 12%",
            },
            "ok",
        )
    )

    def a(metrik, arah, mag, ids, catatan="dipantau"):
        return {
            "anomali": [{"metrik": metrik, "arah": arah, "magnitudo": mag, "fact_ids": ids}],
            "catatan": catatan,
        }

    ks.append(
        kasus(
            "anomaly-rej-angka-01",
            "anomaly",
            a("win_rate", "naik", 2.0, []),
            "rejected",
            "angka_tanpa_fact_id",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-angka-02", "anomaly", a("pnl", "turun", 3.0, []), "rejected", "angka_tanpa_fact_id"
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-angka-03",
            "anomaly",
            {"anomali": [], "catatan": "naik 9%"},
            "rejected",
            "angka_tanpa_fact_id",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-kpn-01",
            "anomaly",
            a("win_rate", "naik", 2.0, [999]),
            "rejected",
            "fact_id_tidak_diberikan",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-kpn-02",
            "anomaly",
            a("win_rate", "naik", 2.0, [101, 888]),
            "rejected",
            "fact_id_tidak_diberikan",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-ada-01",
            "anomaly",
            a("win_rate", "naik", 2.0, [101]),
            "rejected",
            "fact_id_tidak_ada",
            facts=[F1],
            existing=[102],
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-schema-01",
            "anomaly",
            {"anomali": [{"metrik": "m", "arah": "naik", "magnitudo": 1.0, "fact_ids": [101]}]},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-schema-02", "anomaly", a("m", "naik", "besar", [101]), "rejected", "schema_invalid"
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-schema-03",
            "anomaly",
            {"anomali": [{"arah": "naik", "magnitudo": 1.0, "fact_ids": [101]}], "catatan": "x"},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-schema-04",
            "anomaly",
            {"anomali": [], "catatan": "x", "extra": 1},
            "rejected",
            "schema_invalid",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-kredi-01",
            "anomaly",
            a("sk-LLLLLL123456", "naik", 1.0, [101]),
            "rejected",
            "kredensial_terdeteksi",
        )
    )
    ks.append(
        kasus(
            "anomaly-rej-kredi-02",
            "anomaly",
            a("m", "naik", 1.0, [101], catatan="token=abcdef123456"),
            "rejected",
            "kredensial_terdeteksi",
        )
    )
    return ks


def tulis_golden() -> list[str]:
    out = ROOT / "services" / "llm" / "golden"
    out.mkdir(parents=True, exist_ok=True)
    dibuat = []
    for role, kasus_list in (
        ("narrator", golden_narrator()),
        ("verifier", golden_verifier()),
        ("anomaly", golden_anomaly()),
    ):
        path = out / f"{role}.jsonl"
        teks = "\n".join(json.dumps(k, ensure_ascii=False) for k in kasus_list)
        path.write_text(teks + "\n", encoding="utf-8")
        dibuat.append(f"{path} ({len(kasus_list)} kasus)")
    return dibuat


if __name__ == "__main__":
    for p in tulis_prompts():
        print("prompt:", p)
    for p in tulis_golden():
        print("golden:", p)
