"""Kolektor IDX lewat Arjum (``stock.arjum.com``).

Diwarisi dari ``arjum_pool.py`` (Tencent), tapi dibersihkan:

* tidak ada path hardcode ``~/.hermes`` — semua dari :class:`Settings`;
* cache per-endpoint dengan TTL eksplisit;
* *quota guard*: berhenti sebelum kuota harian habis, bukan setelah gagal;
* audit JSONL harian — tiap panggilan tercatat, jadi kuota bisa dilacak.

Kuota Arjum 6.000/hari. Tanpa guard ini, satu cron yang salah bisa menghabiskan
jatah dan mematikan semua job lain di hari yang sama.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
from . import make_client

# TTL per jenis endpoint (detik) — mengikuti perilaku asal.
TTL: dict[str, int] = {
    "screener": 30 * 60,
    "broker_summary": 60 * 60,
    "broker_accumulation": 60 * 60,
    "history": 4 * 60 * 60,
    "analysis": 24 * 60 * 60,
    "seasonal": 7 * 24 * 60 * 60,
    "search": 24 * 60 * 60,
    "financial_statements": 7 * 24 * 60 * 60,
    "insiders": 6 * 60 * 60,
    "market_cap": 6 * 60 * 60,
}


class QuotaExhausted(RuntimeError):
    """Kuota harian Arjum di bawah ambang aman — jangan panggil API."""


@dataclass
class ArjumCollector:
    settings: Settings
    client: httpx.Client | None = None
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = self.client or make_client()

    # ------------------------------------------------------------ lokasi berkas
    @property
    def cache_dir(self) -> Path:
        return self.settings.state_dir / "cache" / "arjum"

    @property
    def quota_path(self) -> Path:
        return self.settings.state_dir / "arjum_quota.json"

    @property
    def audit_path(self) -> Path:
        today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).strftime("%Y-%m-%d")
        return self.settings.logs_dir / f"arjum_audit_{today}.jsonl"

    # ------------------------------------------------------------------- cache
    def _cache_file(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)[:120]
        return self.cache_dir / f"{safe}.json"

    def _cache_get(self, key: str, ttl_s: int) -> dict[str, Any] | None:
        p = self._cache_file(key)
        if not p.is_file():
            return None
        if time.time() - p.stat().st_mtime > ttl_s:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_put(self, key: str, payload: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._cache_file(key).write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass  # cache gagal bukan alasan menggagalkan pengambilan data

    # ------------------------------------------------------------------- kuota
    def quota(self) -> dict[str, Any]:
        if not self.quota_path.is_file():
            return {"remaining": None, "limit": self.settings.arjum_daily_quota}
        try:
            return json.loads(self.quota_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"remaining": None, "limit": self.settings.arjum_daily_quota}

    def _save_quota(self, remaining: int | None, limit: int | None) -> None:
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).strftime("%Y-%m-%d")
        prev = self.quota()
        rec = {
            "date": today,
            "remaining": remaining if remaining is not None else prev.get("remaining"),
            "limit": limit or prev.get("limit") or self.settings.arjum_daily_quota,
        }
        if prev.get("date") != today and remaining is None:
            rec["remaining"] = None
        self.quota_path.write_text(json.dumps(rec), encoding="utf-8")

    def _guard_quota(self) -> None:
        remaining = self.quota().get("remaining")
        if remaining is not None and int(remaining) < self.settings.arjum_min_remaining:
            raise QuotaExhausted(
                f"sisa kuota {remaining} < ambang {self.settings.arjum_min_remaining}"
            )

    # ------------------------------------------------------------------- audit
    def _audit(self, record: dict[str, Any]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ---------------------------------------------------------------- pengambilan
    def key_file(self) -> str | None:
        try:
            key = self.settings.arjum_key_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return key or None

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        ttl_key: str | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any]:
        """Ambil ``path`` dari Arjum — cache dulu, lalu kuota, baru jaringan."""
        ck = cache_key or path
        if ttl_key and (hit := self._cache_get(ck, TTL[ttl_key])) is not None:
            self._audit({"endpoint": path, "status": "cache_hit", "source": ttl_key})
            return hit

        self._guard_quota()

        key = self.key_file()
        if not key:
            raise RuntimeError(f"API key Arjum tidak ada di {self.settings.arjum_key_path}")

        r = self._client.get(
            f"{self.settings.arjum_base}{path}",
            params=params,
            headers={"X-API-Key": key, "User-Agent": "warroom-live-trading/0.1"},
        )
        remaining = r.headers.get("x-ratelimit-remaining")
        limit = r.headers.get("x-ratelimit-limit")
        self._save_quota(int(remaining) if remaining else None, int(limit) if limit else None)
        self._audit(
            {
                "endpoint": path,
                "status": r.status_code,
                "remaining": remaining,
                "source": ttl_key or "live",
            }
        )
        r.raise_for_status()
        payload = r.json()
        if ttl_key:
            self._cache_put(ck, payload)
        return payload

    # ------------------------------------------------------- endpoint berguna
    def health(self) -> dict[str, Any]:
        return self.get("/api/health", ttl_key=None)

    def screener(self, limit: int | None = None, bucket: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if limit:
            params["limit"] = limit
        if bucket:
            params["bucket"] = bucket
        return self.get(
            "/api/screener/latest", params or None, ttl_key="screener", cache_key="screener_latest"
        )

    def broker_summary(self, code: str) -> dict[str, Any]:
        code = code.upper()
        return self.get(
            f"/api/broker-summary/{code}", ttl_key="broker_summary", cache_key=f"broker_summary_{code}"
        )

    def history(self, code: str, frame: str = "daily") -> dict[str, Any]:
        code = code.upper()
        return self.get(
            f"/api/history/{code}",
            {"frame": frame},
            ttl_key="history",
            cache_key=f"history_{code}_{frame}",
        )

    def analysis(self, code: str) -> dict[str, Any]:
        code = code.upper()
        return self.get(f"/api/analysis/{code}", ttl_key="analysis", cache_key=f"analysis_{code}")
