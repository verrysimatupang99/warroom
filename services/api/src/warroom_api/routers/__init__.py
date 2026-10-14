"""Router API terpisah (P1-2: memecah app.py yang sebelumnya ~1.450 baris).

Setiap modul di sini adalah `APIRouter` yang didaftarkan di `create_app()`.
Pemecahan murni: path, perilaku, dan status kode tidak berubah.
"""

from __future__ import annotations

__all__: list[str] = []
