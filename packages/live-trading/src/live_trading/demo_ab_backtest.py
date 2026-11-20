"""Simulator backtest A/B untuk 2 akun Exness Demo Standard USD ($1.000).

Membandingkan 4 metode secara deterministik (anti-lookahead, hari kerja saja,
spread $0.30/oz, aturan ragu SL-dulu) pada data historis 15m emas/PAXG:
  1. martingale_2x            : grid $6, lot 0.01 * 2^k, tanpa SL keras -> ukur blowup.
  2. bounded_avg_counter      : flat 0.01 counter-trend RSI, Basket SL -$60.
  3. trend_bounded_avg (Demo2): flat 0.01 searah EMA200 + pullback RSI,
     spacing max($15, 2.2*ATR), maks 4 layer, TP +$12 / Hard Basket SL -$45.
  4. trend_twin_order  (Demo1): Twin-Order 0.01+0.01
     (Scalp +1.0R & Runner +3.0R + BE Lock + ATR Trail), Daily Cap -$30.
"""
from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Bar15m:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float

    @property
    def dt_utc(self) -> datetime:
        return datetime.fromtimestamp(self.ts_ms / 1000.0, tz=UTC)


@dataclass
class SimResult:
    strategy: str
    initial_deposit: float
    final_equity: float
    net_profit: float
    return_pct: float
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    profit_factor: float
    max_dd_usd: float
    max_dd_pct: float
    blown_up: bool
    avg_win: float
    avg_loss: float
    max_layers_used: int


def load_bars_15m(csv_path: Path, *, weekdays_only: bool = True, max_bars: int | None = None) -> list[Bar15m]:
    bars: list[Bar15m] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = int(float(row["timestamp"]))
            dt = datetime.fromtimestamp(ts / 1000.0, tz=UTC)
            if weekdays_only and dt.weekday() >= 5:
                continue
            o = float(row["open"])
            h = float(row["high"])
            low_px = float(row["low"])
            c = float(row["close"])
            if o <= 0 or h <= 0 or low_px <= 0 or c <= 0:
                continue
            if (h - low_px) / o > 0.08:
                continue
            bars.append(Bar15m(ts_ms=ts, open=o, high=h, low=low_px, close=c))
    if max_bars is not None and len(bars) > max_bars:
        bars = bars[-max_bars:]
    return bars


def _ema_series(closes: Sequence[float], period: int) -> list[float]:
    k = 2.0 / (period + 1)
    out = [closes[0]]
    for c in closes[1:]:
        out.append(c * k + out[-1] * (1.0 - k))
    return out


def _atr_series(bars: Sequence[Bar15m], period: int = 14) -> list[float]:
    trs: list[float] = [bars[0].high - bars[0].low]
    for i in range(1, len(bars)):
        b = bars[i]
        pc = bars[i - 1].close
        trs.append(max(b.high - b.low, abs(b.high - pc), abs(b.low - pc)))
    atrs = [trs[0]]
    alpha = 1.0 / period
    for tr in trs[1:]:
        atrs.append(tr * alpha + atrs[-1] * (1.0 - alpha))
    return atrs


def _rsi_series(closes: Sequence[float], period: int = 14) -> list[float]:
    out = [50.0] * len(closes)
    if len(closes) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    avg_g = gains / period
    avg_l = losses / period
    out[period] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0.0)) / period
        out[i] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out


def _finalize(
    name: str,
    deposit: float,
    equity: float,
    pnls: list[float],
    max_dd_usd: float,
    max_dd_pct: float,
    blown: bool,
    max_layers_used: int,
) -> SimResult:
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_w = sum(wins)
    gross_l = abs(sum(losses))
    pf = round(gross_w / gross_l, 2) if gross_l > 0 else (99.0 if gross_w > 0 else 0.0)
    wr = round((len(wins) / len(pnls)) * 100.0, 2) if pnls else 0.0
    return SimResult(
        strategy=name,
        initial_deposit=deposit,
        final_equity=round(equity, 2),
        net_profit=round(equity - deposit, 2),
        return_pct=round(((equity - deposit) / deposit) * 100.0, 2),
        trades=len(pnls),
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=wr,
        profit_factor=pf,
        max_dd_usd=round(max_dd_usd, 2),
        max_dd_pct=round(max_dd_pct, 2),
        blown_up=blown,
        avg_win=round(sum(wins) / len(wins), 2) if wins else 0.0,
        avg_loss=round(sum(losses) / len(losses), 2) if losses else 0.0,
        max_layers_used=max_layers_used,
    )


def simulate_martingale_2x(
    bars: Sequence[Bar15m],
    *,
    deposit: float = 1000.0,
    spread: float = 0.30,
    grid_step: float = 6.0,
    basket_tp_usd: float = 6.0,
    base_lot: float = 0.01,
    max_layers: int = 8,
) -> SimResult:
    """Martingale klasik 2x lot tanpa SL keras."""
    closes = [b.close for b in bars]
    ema50 = _ema_series(closes, 50)
    equity = deposit
    peak_eq = deposit
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    pnls: list[float] = []
    blown = False
    max_layers_used = 0
    basket: list[tuple[float, float]] = []
    side = 0
    last_entry = 0.0

    for i in range(60, len(bars)):
        b = bars[i]
        if basket:
            worst_price = b.low if side == 1 else b.high
            best_price = b.high if side == 1 else b.low
            worst_flt = sum(((worst_price - p) * side - spread) * (lot * 100.0) for p, lot in basket)
            eq_low = equity + worst_flt
            peak_eq = max(peak_eq, equity)
            dd = max(0.0, peak_eq - eq_low)
            if dd > max_dd_usd:
                max_dd_usd = dd
                max_dd_pct = max(max_dd_pct, (dd / peak_eq) * 100.0 if peak_eq > 0 else 100.0)
            if eq_low <= deposit * 0.15:
                loss = -(equity - deposit * 0.15)
                pnls.append(loss)
                equity = deposit * 0.15
                basket.clear()
                blown = True
                break

            best_flt = sum(((best_price - p) * side - spread) * (lot * 100.0) for p, lot in basket)
            if best_flt >= basket_tp_usd:
                pnls.append(basket_tp_usd)
                equity += basket_tp_usd
                peak_eq = max(peak_eq, equity)
                basket.clear()
                side = 0
                continue

            if len(basket) < max_layers:
                adverse_move = (last_entry - b.close) if side == 1 else (b.close - last_entry)
                if adverse_move >= grid_step:
                    next_lot = round(base_lot * (2 ** len(basket)), 2)
                    entry = b.close + (spread * 0.5 * side)
                    basket.append((entry, next_lot))
                    last_entry = b.close
                    max_layers_used = max(max_layers_used, len(basket))
        else:
            side = 1 if bars[i - 1].close >= ema50[i - 1] else -1
            entry = b.open + (spread * 0.5 * side)
            basket.append((entry, base_lot))
            last_entry = b.open
            max_layers_used = max(max_layers_used, 1)

    return _finalize("martingale_2x", deposit, equity, pnls, max_dd_usd, max_dd_pct, blown, max_layers_used)


def simulate_bounded_averaging(
    bars: Sequence[Bar15m],
    *,
    deposit: float = 1000.0,
    spread: float = 0.30,
    min_step: float = 12.0,
    atr_mult: float = 2.0,
    lot: float = 0.01,
    max_layers: int = 4,
    basket_tp_usd: float = 8.0,
    hard_basket_sl_usd: float = 60.0,
) -> SimResult:
    """Averaging counter-trend tanpa filter tren makro (pembanding negatif)."""
    closes = [b.close for b in bars]
    atrs = _atr_series(bars, 14)
    rsis = _rsi_series(closes, 14)
    equity = deposit
    peak_eq = deposit
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    pnls: list[float] = []
    max_layers_used = 0
    blown = False
    basket: list[tuple[float, float]] = []
    side = 0
    last_entry = 0.0

    for i in range(60, len(bars)):
        b = bars[i]
        if equity <= deposit * 0.15:
            blown = True
            break
        if basket:
            worst_price = b.low if side == 1 else b.high
            best_price = b.high if side == 1 else b.low
            worst_flt = sum(((worst_price - p) * side - spread) * (lot * 100.0) for p, lot in basket)
            best_flt = sum(((best_price - p) * side - spread) * (lot * 100.0) for p, lot in basket)

            peak_eq = max(peak_eq, equity)
            dd_bar = max(0.0, peak_eq - (equity + worst_flt))
            if dd_bar > max_dd_usd:
                max_dd_usd = dd_bar
                max_dd_pct = max(max_dd_pct, (dd_bar / peak_eq) * 100.0 if peak_eq > 0 else 100.0)

            if worst_flt <= -hard_basket_sl_usd:
                pnls.append(-hard_basket_sl_usd)
                equity -= hard_basket_sl_usd
                basket.clear()
                side = 0
                continue
            if best_flt >= basket_tp_usd:
                pnls.append(basket_tp_usd)
                equity += basket_tp_usd
                peak_eq = max(peak_eq, equity)
                basket.clear()
                side = 0
                continue
            if len(basket) < max_layers:
                step = max(min_step, atr_mult * atrs[i - 1])
                adverse = (last_entry - b.close) if side == 1 else (b.close - last_entry)
                if adverse >= step:
                    basket.append((b.close + (spread * 0.5 * side), lot))
                    last_entry = b.close
                    max_layers_used = max(max_layers_used, len(basket))
        else:
            if b.dt_utc.hour >= 21:
                continue
            if rsis[i - 1] <= 28.0:
                side = 1
            elif rsis[i - 1] >= 72.0:
                side = -1
            else:
                continue
            basket.append((b.open + (spread * 0.5 * side), lot))
            last_entry = b.open
            max_layers_used = max(max_layers_used, 1)

    return _finalize("bounded_avg_counter", deposit, equity, pnls, max_dd_usd, max_dd_pct, blown, max_layers_used)


def _worst_floating(leg, bar, spread):
    """Estimasi floating P/L terburuk untuk satu leg, pakai low/high bar."""
    open_px = bar.low if leg.side == 1 else bar.high
    return ((open_px - leg.entry) * leg.side - spread) * (leg.lot * 100.0)


def simulate_trend_bounded_averaging(
    bars: Sequence[Bar15m],
    *,
    deposit: float = 1000.0,
    spread: float = 0.30,
    min_step: float = 15.0,
    atr_mult: float = 2.2,
    lot: float = 0.01,
    max_layers: int = 4,
    basket_tp_usd: float = 12.0,
    hard_basket_sl_usd: float = 45.0,
) -> SimResult:
    """Demo-2 (#464202979): Bounded Averaging searah EMA200 (pullback searah tren makro)."""
    closes = [b.close for b in bars]
    ema200 = _ema_series(closes, 200)
    atrs = _atr_series(bars, 14)
    rsis = _rsi_series(closes, 14)
    equity = deposit
    peak_eq = deposit
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    pnls: list[float] = []
    basket: list[float] = []
    side = 0
    last_e = 0.0
    max_layers_used = 0
    blown = False

    start_idx = min(210, max(15, len(bars) - 1))
    for i in range(start_idx, len(bars)):
        b = bars[i]
        if equity <= deposit * 0.15:
            blown = True
            break
        if basket:
            wp = b.low if side == 1 else b.high
            bp = b.high if side == 1 else b.low
            wf = sum(((wp - p) * side - spread) * (lot * 100.0) for p in basket)
            bf = sum(((bp - p) * side - spread) * (lot * 100.0) for p in basket)
            peak_eq = max(peak_eq, equity)
            dd = max(0.0, peak_eq - (equity + wf))
            if dd > max_dd_usd:
                max_dd_usd = dd
                max_dd_pct = max(max_dd_pct, (dd / peak_eq) * 100.0 if peak_eq > 0 else 100.0)
            if wf <= -hard_basket_sl_usd:
                pnls.append(-hard_basket_sl_usd)
                equity -= hard_basket_sl_usd
                basket.clear()
                side = 0
                continue
            if bf >= basket_tp_usd:
                pnls.append(basket_tp_usd)
                equity += basket_tp_usd
                peak_eq = max(peak_eq, equity)
                basket.clear()
                side = 0
                continue
            if len(basket) < max_layers:
                step = max(min_step, atr_mult * atrs[i - 1])
                adverse = (last_e - b.close) if side == 1 else (b.close - last_e)
                if adverse >= step:
                    basket.append(b.close + (spread * 0.5 * side))
                    last_e = b.close
                    max_layers_used = max(max_layers_used, len(basket))
        else:
            if b.dt_utc.hour >= 20:
                continue
            if bars[i - 1].close > ema200[i - 1] and rsis[i - 1] <= 30.0:
                side = 1
            elif bars[i - 1].close < ema200[i - 1] and rsis[i - 1] >= 70.0:
                side = -1
            else:
                continue
            basket.append(b.open + (spread * 0.5 * side))
            last_e = b.open
            max_layers_used = max(max_layers_used, 1)

    return _finalize("trend_bounded_avg", deposit, equity, pnls, max_dd_usd, max_dd_pct, blown, max_layers_used)


@dataclass
class _Leg:
    side: int
    entry: float
    sl: float
    tp: float
    lot: float
    is_scalp: bool


def simulate_trend_twin_order(
    bars: Sequence[Bar15m],
    *,
    deposit: float = 1000.0,
    spread: float = 0.30,
    sl_atr_mult: float = 1.6,
    scalp_rr: float = 1.0,
    runner_rr: float = 3.0,
    daily_loss_cap_usd: float = 30.0,
) -> SimResult:
    """Demo-1 (#434446792): Twin-Order Layering 0.01+0.01 + BE Lock + ATR Trailing."""
    closes = [b.close for b in bars]
    ema20 = _ema_series(closes, 20)
    ema50 = _ema_series(closes, 50)
    atrs = _atr_series(bars, 14)
    rsis = _rsi_series(closes, 14)

    equity = deposit
    peak_eq = deposit
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    pnls: list[float] = []
    legs: list[_Leg] = []
    daily_pnl = 0.0
    current_day = None
    setup_pnl = 0.0
    blown = False

    start_idx = min(60, max(15, len(bars) - 1))
    for i in range(start_idx, len(bars)):
        b = bars[i]
        if equity <= deposit * 0.15:
            blown = True
            break
        day = b.dt_utc.date()
        if current_day != day:
            current_day = day
            daily_pnl = 0.0

        if legs:
            worst_flt = sum(_worst_floating(leg, b, spread) for leg in legs)
            peak_eq = max(peak_eq, equity)
            dd_bar = max(0.0, peak_eq - (equity + worst_flt))
            if dd_bar > max_dd_usd:
                max_dd_usd = dd_bar
                max_dd_pct = max(max_dd_pct, (dd_bar / peak_eq) * 100.0 if peak_eq > 0 else 100.0)

            remaining: list[_Leg] = []
            scalp_hit_tp = False
            for leg in legs:
                hit_sl = (b.low <= leg.sl) if leg.side == 1 else (b.high >= leg.sl)
                hit_tp = (b.high >= leg.tp) if leg.side == 1 else (b.low <= leg.tp)
                if hit_sl:
                    realized = ((leg.sl - leg.entry) * leg.side - spread) * (leg.lot * 100.0)
                    equity += realized
                    daily_pnl += realized
                    setup_pnl += realized
                elif hit_tp:
                    realized = ((leg.tp - leg.entry) * leg.side - spread) * (leg.lot * 100.0)
                    equity += realized
                    daily_pnl += realized
                    setup_pnl += realized
                    if leg.is_scalp:
                        scalp_hit_tp = True
                else:
                    be_ok = (leg.side == 1 and leg.sl >= leg.entry) or (leg.side == -1 and leg.sl <= leg.entry)
                    if not leg.is_scalp and be_ok:
                        trail = b.close - atrs[i - 1] * 1.5 * leg.side
                        if (leg.side == 1 and trail > leg.sl) or (leg.side == -1 and trail < leg.sl):
                            leg.sl = trail
                    remaining.append(leg)

            legs = remaining
            if scalp_hit_tp and legs:
                for rleg in legs:
                    be_price = rleg.entry + (spread * 1.2 * rleg.side)
                    if (rleg.side == 1 and be_price > rleg.sl) or (rleg.side == -1 and be_price < rleg.sl):
                        rleg.sl = be_price

            if not legs:
                pnls.append(round(setup_pnl, 2))
                setup_pnl = 0.0
                peak_eq = max(peak_eq, equity)
        else:
            if daily_pnl <= -daily_loss_cap_usd:
                continue
            if b.dt_utc.hour not in (8, 9, 13, 14):
                continue
            atr_p = atrs[i - 1]
            if atr_p < 2.0 or atr_p > 15.0:
                continue
            sl_d = min(max(atr_p * sl_atr_mult, 3.5), 8.0)
            hi8 = max(x.high for x in bars[i - 9:i - 1])
            lo8 = min(x.low for x in bars[i - 9:i - 1])
            pc = bars[i - 1].close
            side = 0
            if ema20[i - 1] > ema50[i - 1] and pc > hi8 and rsis[i - 1] <= 70.0:
                side = 1
            elif ema20[i - 1] < ema50[i - 1] and pc < lo8 and rsis[i - 1] >= 30.0:
                side = -1
            if side == 0:
                continue
            entry = b.open + (spread * 0.5 * side)
            sl = entry - sl_d * side
            legs = [
                _Leg(side=side, entry=entry, sl=sl, tp=entry + (sl_d * scalp_rr) * side, lot=0.01, is_scalp=True),
                _Leg(side=side, entry=entry, sl=sl, tp=entry + (sl_d * runner_rr) * side, lot=0.01, is_scalp=False),
            ]
            setup_pnl = 0.0

    return _finalize("trend_twin_order", deposit, equity, pnls, max_dd_usd, max_dd_pct, blown, 2)


def run_benchmark(data_root: Path) -> dict:
    report = {}
    for label, fname in [("PAXGUSDT_15m_multiyear", "PAXGUSDT_15m.csv"), ("XAUUSD_15m_recent", "XAUUSD_15m.csv")]:
        p = data_root / fname
        if not p.exists():
            continue
        bars = load_bars_15m(p, weekdays_only=True)
        report[label] = {
            "bars": len(bars),
            "start": bars[0].dt_utc.strftime("%Y-%m-%d"),
            "end": bars[-1].dt_utc.strftime("%Y-%m-%d"),
            "martingale_2x": asdict(simulate_martingale_2x(bars)),
            "bounded_avg_counter": asdict(simulate_bounded_averaging(bars)),
            "trend_bounded_avg": asdict(simulate_trend_bounded_averaging(bars)),
            "trend_twin_order": asdict(simulate_trend_twin_order(bars)),
        }
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(run_benchmark(Path("/home/admin/warroom/data/hist")), indent=2))
