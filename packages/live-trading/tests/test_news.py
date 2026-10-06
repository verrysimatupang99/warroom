"""Regresi: kolektor berita RSS (6 Okt 2026).

Yang dikunci:
1. Item tanpa judul / tanpa tautan / tanpa tanggal sah DIBUANG — bukan ditebak.
2. Judul dibersihkan dari tag HTML (feed kadang mengirim entity/tag).
3. Feed mati tidak menjatuhkan semuanya; bila semua mati → cache, dan bila cache
   tak ada → kosong + alasan (bukan daftar palsu).
"""

from __future__ import annotations

from live_trading.collectors import news

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Bitcoin &lt;b&gt;Rally&lt;/b&gt; Tests $90K</title><link>https://x.test/a</link>
  <pubDate>Mon, 06 Oct 2026 10:00:00 +0000</pubDate></item>
<item><title>Tanpa tanggal</title><link>https://x.test/b</link></item>
<item><title></title><link>https://x.test/c</link><pubDate>Tue, 07 Oct 2026 10:00:00 +0000</pubDate></item>
<item><title>Solana upgrade</title><link>https://x.test/d</link>
  <pubDate>Tue, 07 Oct 2026 11:00:00 +0000</pubDate></item>
</channel></rss>"""


def test_item_cacat_dibuang_dan_tag_dibersihkan() -> None:
    items = news.parse_feed(RSS, "Uji")
    assert len(items) == 2, "item tanpa tanggal & tanpa judul harus dibuang"
    judul = {b.judul for b in items}
    assert "Bitcoin Rally Tests $90K" in judul, "tag HTML harus dibersihkan dari judul"
    assert all(b.tautan.startswith("https://") for b in items)


def test_xml_rusak_mengembalikan_kosong() -> None:
    assert news.parse_feed("<rss><channel><item>", "Uji") == []
    assert news.parse_feed("bukan xml", "Uji") == []


def test_feed_mati_pakai_cache_lalu_jujur_kosong(tmp_path, monkeypatch) -> None:
    from live_trading.config import get_settings

    s = get_settings()
    monkeypatch.setattr(type(s), "state_dir", property(lambda self: tmp_path), raising=False)
    col = news.NewsCollector(s, feeds=(("Mati", "https://x.invalid/feed"),))

    # Tanpa cache: kosong + alasan yang menyebut kegagalan, bukan daftar palsu.
    items, sumber = col.ambil()
    assert items == []
    assert "gagal" in sumber

    # Dengan cache: dipakai, dan keterangannya menyebut cache.
    col._ke_cache([news.Berita(judul="Lama", tautan="https://x.test/z", sumber="Uji", ts=1.0)])
    items2, sumber2 = col.ambil()
    assert len(items2) == 1 and items2[0].judul == "Lama"
    assert "cache" in sumber2
