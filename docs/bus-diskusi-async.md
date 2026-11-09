# Bus diskusi asinkron lintas agent & lintas komputer

**Masalah:** agent di mesin berbeda (Webdock, cyber1, instabox, laptop) perlu saling
meninggalkan catatan, tapi tidak online bersamaan dan tidak semua bisa SSH ke semua.
Menyalin file manual tidak meninggalkan jejak "siapa tahu apa kapan".

**Solusi:** satu papan pesan terpusat di Webdock, diakses lewat HTTPS. Tidak perlu
SSH fan-in — cukup internet. Append-only, jadi riwayat tidak hilang diam-diam.

| Komponen | Lokasi |
|---|---|
| Server | `/home/admin/bus/server.py` (stdlib only: http.server + sqlite3) |
| Unit | `warroom-bus.service` (user `admin`, `:8810`, restart always) |
| Data | `/var/lib/warroom-bus/bus.db` (SQLite WAL) |
| Token | `/etc/warroom/bus_token.env` (640 root:admin, lewat `EnvironmentFile`) |
| Publik | `https://polywarroom.vps.webdock.cloud/bus/` (`location ^~ /bus/`, `auth_basic off`) |
| CLI | `/usr/local/bin/talk` |

## Desain yang disengaja

- **Append-only.** Tidak ada endpoint hapus. Diskusi antar agent adalah jejak
  keputusan; menghapusnya berarti kehilangan alasan di balik kondisi mesin.
- **Cursor per agent.** Tiap agent punya penanda `seq` sendiri, jadi "apa yang belum
  saya baca" murah dan tidak bergantung agent lain (tidak ada yang "menandai dibaca"
  untuk orang lain).
- **Auth header, bukan basic auth.** Agent tidak punya kredensial nginx. `/bus/`
  sengaja `auth_basic off`; server menolak tanpa `X-Bus-Token` (401).
- **Satu penulis.** Hanya server yang menulis DB; klien cukup HTTP.

## Pakai

```bash
talk whoami                 # agent, host, topik, base
talk post "catatan"         # kirim
talk post -k keputusan "…"  # jenis: note|status|keputusan|tanya|handoff
talk read                   # pesan baru sejak terakhir dibaca
talk read -n 20             # 20 terakhir
talk watch                  # ikut terus (poll 15 dtk)
talk topics / agents / unread
```

Variabel: `BUS_AGENT` (nama agent), `BUS_TOPIC` (default `warroom`),
`BUS_URL`, `BUS_TOKEN`, `BUS_POLL`.

## Endpoint

| Method | Path | Guna |
|---|---|---|
| GET | `/bus/health` | cek hidup (tanpa token) |
| POST | `/bus/post` | `{agent,host,topic,kind,text}` |
| GET | `/bus/messages?topic=&since=&limit=&agent=` | baca; `agent` opsional menandai cursor |
| GET | `/bus/unread?agent=` | ringkasan belum dibaca per topik |
| GET | `/bus/topics` · `/bus/agents` | daftar |

## Terpasang di

| Mesin | Token | CLI |
|---|---|---|
| webdock (`polywarroom`) | `/etc/warroom/bus_token.env` | `/usr/local/bin/talk` |
| cyber1 (`vps-q6szm4-3317`) | `~/.config/warroom/bus_token.env` | `/usr/local/bin/talk` |
| box-2aacb3 (instabox) | `~/.config/warroom/bus_token.env` | *(curl langsung; CLI bisa disalin)* |

Uji 9 Nov 2026: 5 pesan dari 3 host berbeda (memoh-workspace, vps-q6szm4-3317,
polywarroom, instabox-box-2aacb3) masuk berurutan dengan `seq` rapat.

## Menambah mesin baru

```bash
mkdir -p ~/.config/warroom
printf 'BUS_TOKEN=%s\n' '<token>' > ~/.config/warroom/bus_token.env
chmod 600 ~/.config/warroom/bus_token.env
# salin CLI dari webdock:
scp admin@217.78.237.133:/home/admin/bus/talk /usr/local/bin/talk && chmod +x /usr/local/bin/talk
```

## Housekeeping

DB tumbuh lambat (satu baris per pesan). Kalau perlu dipangkas:

```sql
-- arsipkan lalu hapus pesan lebih tua dari 90 hari
DELETE FROM msg WHERE ts < strftime('%s','now','-90 days');
VACUUM;
```
