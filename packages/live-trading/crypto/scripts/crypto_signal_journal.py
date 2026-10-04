#!/usr/bin/env python3
"""Append a crypto signal scan/signal row to the Excel trading journal.

Used by the crypto-signal-653 cron job: after composing the Telegram post,
the agent logs the outcome here so every scan is journalled in .xlsx.

Usage:
  crypto_signal_journal.py --status SIGNAL --pair BTC_USDT --arah LONG \
      --entry 79000 --sl 78400 --tp1 80200 --tp2 81400 --funding 0.01 \
      --alasan "1D bullish, pullback discount 4H OB"
  crypto_signal_journal.py --status NO_TRADE --alasan "semua premium, MTF conflict"

Output file: ~/.hermes/crypto-journal/crypto_journal.xlsx
Columns Hasil / P-L / Skor Disiplin are left blank for manual fill-in.

Rule v2 (reset 21 Sep 2026):
  - Gate POI crypto diturunkan: butuh 2 dari 4 POI (OB 1H, SR teruji,
    trendline >=3 touch, FVG) + 1 confirmation (CISD atau iFVG) — sebelumnya
    semua POI wajib sehingga cron sering [SILENT] tanpa signal.
  - Hold tetap intraday 4-12 jam (max 24 jam), TP1=1R/TP2=2R.
"""
import argparse
import datetime
import os
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

JOURNAL_DIR = os.path.expanduser("~/.hermes/crypto-journal")
XLSX = os.path.join(JOURNAL_DIR, "crypto_journal.xlsx")

HEADERS = [
    "Tanggal", "Jam WIB", "Status", "Pair", "Arah",
    "Entry Est.", "SL Est.", "TP1 Est.", "TP2 Est.",
    "Funding %", "Alasan / Bias MTF", "Hasil", "P/L %", "Skor Disiplin",
]
WIDTHS = [12, 9, 10, 12, 7, 12, 12, 12, 12, 10, 46, 12, 9, 13]


def style_sheet(ws):
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin = Side(style="thin", color="B0B0B0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, (head, width) in enumerate(zip(HEADERS, WIDTHS), start=1):
        cell = ws.cell(row=1, column=col, value=head)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--status", required=True, choices=["SIGNAL", "NO_TRADE"])
    p.add_argument("--pair", default="-")
    p.add_argument("--arah", default="-")
    p.add_argument("--entry", default="")
    p.add_argument("--sl", default="")
    p.add_argument("--tp1", default="")
    p.add_argument("--tp2", default="")
    p.add_argument("--funding", default="")
    p.add_argument("--alasan", default="")
    args = p.parse_args()

    os.makedirs(JOURNAL_DIR, exist_ok=True)
    if os.path.exists(XLSX):
        wb = load_workbook(XLSX)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Journal"
        style_sheet(ws)

    now = datetime.datetime.now()
    row = [
        now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
        args.status, args.pair, args.arah,
        args.entry, args.sl, args.tp1, args.tp2,
        args.funding, args.alasan, "", "", "",
    ]
    ws.append(row)
    wb.save(XLSX)
    print(f"logged: {args.status} {args.pair} row {ws.max_row}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
