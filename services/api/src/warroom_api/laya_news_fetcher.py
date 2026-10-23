"""Modul Pemindai & Pengumpul Berita Makro Ekonomi (RSS Feeds & Fed Announcements).

Mengumpulkan headline berita secara berkala untuk diumpankan ke model Laya-Finance
dan menentukan skor sentimen serta deteksi event berisiko tinggi.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("warroom_api.laya_news_fetcher")

# RSS Feeds Kredibel Berlisensi Terbuka
FEEDS = [
    "https://www.federalreserve.gov/feeds/press_all.xml",
]

KEYWORDS_GOLD_BULL = re.compile(
    r"\b(rate cut|dovish|inflation cool|slowing|safe haven|tension|geopolitical|crisis|recession)\b",
    re.I
)

KEYWORDS_GOLD_BEAR = re.compile(
    r"\b(rate hike|hawkish|strong jobs|hot inflation|dollar surge|yields surge|tightening)\b",
    re.I
)

def evaluate_headlines_sentiment(headlines: list[str]) -> tuple[str, float]:
    """Menghitung bias dan skor rata-rata berdasarkan daftar headline."""
    if not headlines:
        return "NEUTRAL", 0.0
    
    total_score = 0.0
    count = 0
    for h in headlines:
        score = 0.0
        if KEYWORDS_GOLD_BULL.search(h):
            score += 0.5
        if KEYWORDS_GOLD_BEAR.search(h):
            score -= 0.5
        total_score += score
        count += 1
        
    avg = total_score / count if count > 0 else 0.0
    bias = "BULL" if avg >= 0.25 else ("BEAR" if avg <= -0.25 else "NEUTRAL")
    return bias, round(avg, 2)
