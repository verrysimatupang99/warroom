# Product Steering — War Room (MaximaLabs)

## What this is

War Room is a multi-market quant trading cockpit: one screen that puts crypto,
forex/gold, Indonesian stocks (IDX), prediction markets (Polymarket), and
memecoins (DEX) side by side. It is built to give a retail trader the kind of
instrument panel that used to be locked behind a Bloomberg-class terminal.

## Who it is for

A regular-to-intermediate trader who wants institutional-grade visibility
without an institutional budget. Every screen answers one question: *what is
happening right now, and is it worth acting on?*

## Product principles

1. **Every number has a source.** Each signal links to where it came from
   (OKX, Yahoo Finance, idx-edge, MT5 telemetry). If a number is not
   available, the UI shows `—`, never a fabricated placeholder.
2. **Honest states.** Every data view has loading, empty, and error states.
   A standby market says it is standby and why. A dead source says it is dead.
3. **Measured, not claimed.** Win rate, profit factor, and R-multiples come
   from the trade ledger, not from a config constant or a hopeful guess.
4. **Consistent rhythm across markets.** Every market page follows the same
   skeleton (MarketShell + Ringkas / Sinyal / Uji / Eksekusi) so a user learns
   it once and can navigate any market.

## What we deliberately do NOT do

- No auto-execution without the owner arming it. Live trading is gated behind
  an explicit activation.
- No fabricated statistics, testimonials, or performance claims.
- No hiding a dead source behind a green "healthy" badge.

## Success looks like

A trader opens War Room, sees every market's status in one screen, can drill
into any signal's source, and trusts that what is shown is what the data says.
