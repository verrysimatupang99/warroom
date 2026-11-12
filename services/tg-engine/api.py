import re
import gate_audit
import risk_gate
import uvicorn
from db import get_signals, get_stats, init_db
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from parser import parse_forex_signal

app = FastAPI(title="Telegram Trading Signals API & Dashboard", version="1.0.0")

@app.middleware("http")
async def clean_path_middleware(request: Request, call_next):
    path = request.scope.get("path", "")
    if "//" in path:
        request.scope["path"] = re.sub(r"/+", "/", path)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/signals")
def read_signals(
    limit: int = Query(50, ge=1, le=500),
    category: str = Query(None, description="FOREX, SAHAM, CRYPTO, GENERAL, or ALL"),
    search: str = Query(None, description="Search term in message or channel"),
):
    """Mengembalikan daftar sinyal trading terbaru dalam format JSON."""
    raw_list = get_signals(limit, category, search)
    enriched = []
    for item in raw_list:
        parsed = parse_forex_signal(item.get("message_text", ""), item.get("channel_name", ""))
        item_copy = dict(item)
        item_copy["parsed"] = parsed
        enriched.append(item_copy)

    return {"status": "OK", "count": len(enriched), "data": enriched}


@app.get("/api/signals/laya-queue")
def read_laya_queue(limit: int = Query(10, ge=1, le=50), balance: float = Query(500.0, gt=0)):
    """
    Queue khusus untuk Laya Sentinel AI Fail-Closed Gatekeeper.
    Hanya mengembalikan sinyal valid XAUUSD & USTEC/NASDAQ dengan lot baku 0.10.
    """
    # Ambil jendela lebih lebar: chatter channel (saham, promo) menenggelamkan sinyal.
    # Filter simbol tetap dilakukan di parser, tapi kita tidak boleh hanya melihat 50 baris terakhir.
    SCAN_WINDOW = max(limit * 20, 500)
    raw_list = get_signals(SCAN_WINDOW, "FOREX")
    queue = []
    for item in raw_list:
        parsed = parse_forex_signal(item.get("message_text", ""), item.get("channel_name", ""))
        if parsed and parsed.get("action") and parsed.get("symbol") in ["XAUUSD", "USTEC"]:
            enriched = dict(parsed)
            enriched["timestamp"] = item["timestamp"]
            verdict = risk_gate.evaluate(enriched, balance=balance)
            _sesi = risk_gate.check_market_session(enriched)
            if _sesi:
                verdict["decision"] = "REJECTED"
                verdict["reasons"] = list(verdict["reasons"]) + [_sesi]
            queue.append(
                {
                    "id": item["id"],
                    "channel": item["channel_name"],
                    "timestamp": item["timestamp"],
                    "symbol": parsed["symbol"],
                    "action": parsed["action"],
                    "lot": verdict["lot"],  # sizing dari saldo, bukan hardcode
                    "entry_low": parsed["entry_low"],
                    "entry_high": parsed["entry_high"],
                    "sl": parsed["sl"],
                    "tp1": parsed["tp1"],
                    "rr": verdict["rr"],
                    "age_hours": verdict["age_h"],
                    "laya_gate": verdict["decision"],
                    "reject_reasons": verdict["reasons"],
                }
            )
            if len(queue) >= limit:
                break

    # --- Aturan portofolio lintas-sinyal (korelasi Gold-Nasdaq) ---
    approved = [x for x in queue if x["laya_gate"] == "APPROVED"]
    if len(approved) > 1:
        pairs = [
            {
                "signal": x,
                "verdict": {"decision": x["laya_gate"], "reasons": x["reject_reasons"], "rr": x["rr"]},
            }
            for x in approved
        ]
        risk_gate.apply_portfolio_rules(pairs)
        for pair in pairs:
            x = pair["signal"]
            if pair["verdict"]["decision"] != x["laya_gate"]:
                x["laya_gate"] = pair["verdict"]["decision"]
                x["reject_reasons"] = pair["verdict"]["reasons"]

    # --- Audit trail (hanya mencatat perubahan keputusan) ---
    for x in queue:
        gate_audit.record(
            x["id"],
            {
                "channel": x["channel"],
                "symbol": x["symbol"],
                "action": x["action"],
                "entry_low": x["entry_low"],
                "entry_high": x["entry_high"],
                "sl": x["sl"],
                "tp1": x["tp1"],
            },
            {
                "decision": x["laya_gate"],
                "reasons": x["reject_reasons"],
                "rr": x["rr"],
                "age_h": x["age_hours"],
                "lot": x["lot"],
                "policy": {"min_rr": risk_gate.MIN_RR, "max_age_hours": risk_gate.MAX_AGE_HOURS},
            },
            balance,
        )

    return {
        "status": "OK",
        "instrument_focus": ["XAUUSD", "USTEC"],
        "sizing": "dynamic_by_balance",
        "risk_policy": {"min_rr": risk_gate.MIN_RR, "max_age_hours": risk_gate.MAX_AGE_HOURS},
        "count": len(queue),
        "queue": queue,
    }


@app.get("/api/signals/gate-audit")
def read_gate_audit(limit: int = Query(20, ge=1, le=200)):
    # Riwayat keputusan gate untuk forensik: siapa ditolak, kapan, kenapa.
    rows = gate_audit.recent(limit)
    return {"status": "OK", "count": len(rows), "decisions": rows}


@app.get("/api/stats")
def read_stats():
    """Mengembalikan statistik jumlah sinyal per kategori."""
    return {"status": "OK", "stats": get_stats()}


@app.get("/", response_class=HTMLResponse)
def dashboard_html():
    return """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TG Trading Signals 24/7 Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0b0f19; color: #f1f5f9; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .glass { background: rgba(18, 24, 39, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .custom-scroll::-webkit-scrollbar { width: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: #0b0f19; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    </style>
</head>
<body class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="border-b border-slate-800 bg-slate-900/60 sticky top-0 z-50 backdrop-blur-md px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 via-rose-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-rose-500/20">
                <i class="fa-solid fa-satellite-dish text-white text-lg"></i>
            </div>
            <div>
                <h1 class="font-bold text-lg leading-tight flex items-center gap-2">
                    Telegram Signal Engine
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        LIVE 24/7
                    </span>
                </h1>
                <p class="text-xs text-slate-400">Listener Telethon Real-time • Auto-Captured Signals</p>
            </div>
        </div>

        <!-- Controls -->
        <div class="flex items-center gap-3">
            <div class="relative">
                <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                <input type="text" id="searchInput" placeholder="Cari pair, ticker, pesan..." 
                    class="bg-slate-800/80 border border-slate-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-indigo-500 text-slate-200 w-48 sm:w-64 transition-all">
            </div>
            <button onclick="fetchSignals()" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/20">
                <i class="fa-solid fa-arrows-rotate" id="refreshIcon"></i>
                <span>Refresh</span>
            </button>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        <!-- Stats Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-3" id="statsContainer">
            <div class="glass rounded-xl p-3.5 border-l-4 border-slate-500">
                <div class="text-xs text-slate-400 font-medium">Total Signals</div>
                <div class="text-xl font-bold font-mono text-white mt-1" id="statTotal">-</div>
            </div>
            <div class="glass rounded-xl p-3.5 border-l-4 border-amber-500">
                <div class="text-xs text-amber-400 font-medium">Gold / Forex</div>
                <div class="text-xl font-bold font-mono text-amber-300 mt-1" id="statForex">-</div>
            </div>
            <div class="glass rounded-xl p-3.5 border-l-4 border-emerald-500">
                <div class="text-xs text-emerald-400 font-medium">Saham IDX</div>
                <div class="text-xl font-bold font-mono text-emerald-300 mt-1" id="statSaham">-</div>
            </div>
            <div class="glass rounded-xl p-3.5 border-l-4 border-sky-500">
                <div class="text-xs text-sky-400 font-medium">Crypto</div>
                <div class="text-xl font-bold font-mono text-sky-300 mt-1" id="statCrypto">-</div>
            </div>
            <div class="glass rounded-xl p-3.5 border-l-4 border-purple-500">
                <div class="text-xs text-purple-400 font-medium">General</div>
                <div class="text-xl font-bold font-mono text-purple-300 mt-1" id="statGeneral">-</div>
            </div>
        </div>

        <!-- Filter Tabs -->
        <div class="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
            <button onclick="setCategory('ALL')" class="category-btn active px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-white transition-all" data-cat="ALL">Semua Sinyal</button>
            <button onclick="setCategory('FOREX')" class="category-btn px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all" data-cat="FOREX">🪙 Forex / Gold</button>
            <button onclick="setCategory('SAHAM')" class="category-btn px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all" data-cat="SAHAM">📊 Saham IHSG</button>
            <button onclick="setCategory('CRYPTO')" class="category-btn px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all" data-cat="CRYPTO">🚀 Crypto</button>
            <button onclick="setCategory('GENERAL')" class="category-btn px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all" data-cat="GENERAL">💬 General / Komunitas</button>
        </div>

        <!-- Sinyal Feed List -->
        <div id="signalsFeed" class="space-y-3">
            <div class="text-center py-16 text-slate-500">
                <i class="fa-solid fa-spinner fa-spin text-2xl mb-2"></i>
                <p class="text-xs">Memuat sinyal trading terbaru...</p>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-500 flex flex-wrap items-center justify-between gap-2">
        <span>Telegram Session: <strong class="text-slate-400">Sasc (@sasvc2314)</strong> • Target: Webdock Engine</span>
        <span>Auto-refresh setiap 15 detik • Built with Telethon & FastAPI</span>
    </footer>

    <script>
        const apiBase = (window.location.pathname.replace(/\/+$/, '') || '') + '/api';
        let currentCategory = 'ALL';
        let searchTimeout = null;

        function setCategory(cat) {
            currentCategory = cat;
            document.querySelectorAll('.category-btn').forEach(btn => {
                if (btn.dataset.cat === cat) {
                    btn.classList.add('bg-indigo-600', 'text-white');
                    btn.classList.remove('bg-slate-800', 'text-slate-400');
                } else {
                    btn.classList.remove('bg-indigo-600', 'text-white');
                    btn.classList.add('text-slate-400');
                }
            });
            fetchSignals();
        }

        async function fetchStats() {
            try {
                const res = await fetch(`${apiBase}/stats`);
                const data = await res.json();
                if (data.status === 'OK') {
                    document.getElementById('statTotal').innerText = data.stats.total;
                    document.getElementById('statForex').innerText = data.stats.forex;
                    document.getElementById('statSaham').innerText = data.stats.saham;
                    document.getElementById('statCrypto').innerText = data.stats.crypto;
                    document.getElementById('statGeneral').innerText = data.stats.general;
                }
            } catch (e) {
                console.error("Gagal load stats:", e);
            }
        }

        async function fetchSignals() {
            const icon = document.getElementById('refreshIcon');
            icon.classList.add('fa-spin');
            const searchVal = document.getElementById('searchInput').value.trim();

            let url = `${apiBase}/signals?limit=50&category=${currentCategory}`;
            if (searchVal) url += `&search=${encodeURIComponent(searchVal)}`;

            try {
                const res = await fetch(url);
                const data = await res.json();
                renderSignals(data.data || []);
            } catch (e) {
                document.getElementById('signalsFeed').innerHTML = `
                    <div class="glass p-6 rounded-xl text-center text-rose-400 text-xs">
                        Gagal memuat feed sinyal. Pastikan backend aktif.
                    </div>
                `;
            } finally {
                setTimeout(() => icon.classList.remove('fa-spin'), 600);
                fetchStats();
            }
        }

        function formatCategoryBadge(cat) {
            switch(cat) {
                case 'FOREX':
                    return '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">🪙 FOREX / GOLD</span>';
                case 'SAHAM':
                    return '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">📊 SAHAM IHSG</span>';
                case 'CRYPTO':
                    return '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">🚀 CRYPTO</span>';
                default:
                    return '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">💬 GENERAL</span>';
            }
        }

        function renderSignals(signals) {
            const container = document.getElementById('signalsFeed');
            if (!signals || signals.length === 0) {
                container.innerHTML = `
                    <div class="glass p-12 rounded-xl text-center text-slate-400 space-y-2">
                        <i class="fa-solid fa-inbox text-3xl text-slate-600 mb-1"></i>
                        <p class="text-sm font-semibold text-slate-300">Belum ada sinyal yang ditangkap</p>
                        <p class="text-xs text-slate-500 max-w-md mx-auto">Listener Telethon sedang aktif mendengarkan seluruh event pesan masuk dari channel Telegram terdaftar.</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = signals.map(s => {
                const dateStr = s.timestamp ? s.timestamp.replace('T', ' ') : '-';
                return `
                    <div class="glass rounded-xl p-4 sm:p-5 hover:border-slate-700 transition-all space-y-3">
                        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-2.5">
                            <div class="flex items-center gap-2">
                                ${formatCategoryBadge(s.category)}
                                <span class="font-bold text-sm text-slate-200">${escapeHtml(s.channel_name || 'Channel')}</span>
                            </div>
                            <div class="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                                <span><i class="fa-regular fa-clock mr-1"></i>${dateStr}</span>
                                ${s.views ? `<span><i class="fa-regular fa-eye mr-1"></i>${s.views}</span>` : ''}
                                ${s.forwards ? `<span><i class="fa-solid fa-share mr-1"></i>${s.forwards}</span>` : ''}
                            </div>
                        </div>
                        <div class="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed font-mono bg-slate-900/50 p-3.5 rounded-lg border border-slate-800/40 custom-scroll max-h-96 overflow-y-auto">
                            ${escapeHtml(s.message_text)}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function escapeHtml(str) {
            return (str || '').replace(/[&<>'"]/g, 
                tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
            );
        }

        document.getElementById('searchInput').addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(fetchSignals, 400);
        });

        // Initial fetch & loop 15 detik
        fetchSignals();
        setInterval(fetchSignals, 15000);
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8088, reload=False)
