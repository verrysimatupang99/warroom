#!/usr/bin/env python3
"""bus — papan diskusi asinkron lintas agent & lintas komputer.

Kenapa ada: agent di mesin berbeda (Webdock, cyber1, instabox, laptop) perlu
saling meninggalkan catatan tanpa harus online bersamaan dan tanpa SSH fan-in.
Server ini satu-satunya tempat menulis; semua klien cukup HTTPS.

Desain:
- SQLite append-only (atomic, berurutan, aman untuk penulis bersamaan).
- Tiap agent punya cursor sendiri -> "apa yang belum saya baca" itu murah.
- Tidak ada penghapusan lewat API. Jejak diskusi tidak boleh hilang diam-diam.

Auth: header `X-Bus-Token` (dibaca dari file, mode 600).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB = "/var/lib/warroom-bus/bus.db"
PORT = 8810
MAX_TEXT = 20000


def token() -> str:
    # Dibaca dari environment systemd (EnvironmentFile, mode 640 root:admin),
    # bukan dari disk: service jalan sebagai `admin` dan tidak perlu hak baca
    # ke /etc/warroom.
    return os.environ.get("BUS_TOKEN", "").strip()


def db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS msg (
            seq      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       REAL NOT NULL,
            topic    TEXT NOT NULL,
            agent    TEXT NOT NULL,
            host     TEXT DEFAULT '',
            kind     TEXT DEFAULT 'note',
            text     TEXT NOT NULL,
            refs     TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_topic_seq ON msg(topic, seq);
        CREATE TABLE IF NOT EXISTS cursor (
            agent TEXT NOT NULL,
            topic TEXT NOT NULL,
            seq   INTEGER NOT NULL,
            PRIMARY KEY (agent, topic)
        );
    """)
    return con


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # senyap; journal sudah cukup
        pass

    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        want = token()
        if not want:
            self._send(500, {"error": "server token belum diset"})
            return False
        if self.headers.get("X-Bus-Token", "") != want:
            self._send(401, {"error": "token salah"})
            return False
        return True

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}

        if u.path == "/bus/health":
            return self._send(200, {"ok": True, "ts": time.time()})
        if not self._auth():
            return

        con = db()
        if u.path == "/bus/messages":
            topic = q.get("topic", "warroom")
            limit = min(int(q.get("limit", 50)), 500)
            since = q.get("since")
            agent = q.get("agent")
            cur = con.execute(
                "SELECT seq,ts,topic,agent,host,kind,text,refs FROM msg "
                "WHERE topic=? AND seq>? ORDER BY seq LIMIT ?",
                (topic, int(since or 0), limit),
            )
            rows = [dict(zip(("seq", "ts", "topic", "agent", "host", "kind", "text", "refs"), r))
                    for r in cur.fetchall()]
            out = {"topic": topic, "count": len(rows), "messages": rows}
            if agent:
                # tandai sudah dibaca sampai pesan terakhir
                if rows:
                    last = rows[-1]["seq"]
                    con.execute(
                        "INSERT INTO cursor(agent,topic,seq) VALUES(?,?,?) "
                        "ON CONFLICT(agent,topic) DO UPDATE SET seq=excluded.seq",
                        (agent, topic, last),
                    )
                    con.commit()
                out["read_until"] = rows[-1]["seq"] if rows else int(since or 0)
            return self._send(200, out)

        if u.path == "/bus/unread":
            agent = q.get("agent", "")
            con2 = db()
            rows = con2.execute("""
                SELECT m.topic, COUNT(*) FROM msg m
                LEFT JOIN cursor c ON c.agent=? AND c.topic=m.topic
                WHERE m.seq > COALESCE(c.seq,0) AND m.agent != ?
                GROUP BY m.topic
            """, (agent, agent)).fetchall()
            return self._send(200, {"agent": agent,
                                    "unread": [{"topic": t, "n": n} for t, n in rows]})

        if u.path == "/bus/topics":
            rows = con.execute(
                "SELECT topic, COUNT(*), MAX(ts) FROM msg GROUP BY topic ORDER BY MAX(ts) DESC"
            ).fetchall()
            return self._send(200, {"topics": [{"topic": t, "n": n, "last_ts": ts}
                                               for t, n, ts in rows]})

        if u.path == "/bus/agents":
            rows = con.execute(
                "SELECT agent, host, COUNT(*), MAX(ts) FROM msg GROUP BY agent, host"
            ).fetchall()
            return self._send(200, {"agents": [{"agent": a, "host": h, "n": n, "last_ts": ts}
                                               for a, h, n, ts in rows]})
        return self._send(404, {"error": "tidak ada"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/bus/post":
            return self._send(404, {"error": "tidak ada"})
        if not self._auth():
            return
        b = self._body()
        text = (b.get("text") or "").strip()
        if not text:
            return self._send(400, {"error": "text wajib"})
        if len(text) > MAX_TEXT:
            return self._send(400, {"error": f"text > {MAX_TEXT} karakter"})
        agent = (b.get("agent") or "anonymous").strip()[:64]
        topic = (b.get("topic") or "warroom").strip()[:64]
        con = db()
        cur = con.execute(
            "INSERT INTO msg(ts,topic,agent,host,kind,text,refs) VALUES(?,?,?,?,?,?,?)",
            (time.time(), topic, agent, (b.get("host") or "")[:64],
             (b.get("kind") or "note")[:24], text, json.dumps(b.get("refs") or [])),
        )
        con.commit()
        return self._send(200, {"ok": True, "seq": cur.lastrowid, "topic": topic})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()