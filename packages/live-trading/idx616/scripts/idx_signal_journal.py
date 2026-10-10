#!/usr/bin/env python3
"""IDX (BEI) trading journal logger — separate from crypto_journal.xlsx.

Per request: IDX uses a different sheet because evaluation criteria are
different (liquidity, ATR%, market session context — not funding rate
like crypto perps). Columns reflect the IDX micro-momentum playbook.

Usage:
  idx_signal_journal.py --status SIGNAL --emiten BMRI.JK --arah LONG \
      --entry 4200 --sl 4074 --tp1 4326 --tp2 4452 --alasan "5d mid-band, AT 1.68%"
  idx_signal_journal.py --status NO_TRADE --alasan "market closed, weekend"
  idx_signal_journal.py --status EVAL --emiten BMRI.JK --result TP1 --pnl 3.0

Output file: ~/.hermes/idx-journal/idx_journal.xlsx
"""
import argparse
import datetime
import fcntl
import os
import sys
import tempfile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

JOURNAL_DIR = os.path.expanduser("~/.hermes/idx-journal")
XLSX = os.path.join(JOURNAL_DIR, "idx_journal.xlsx")

HEADERS = [
    "Tanggal", "Jam WIB", "Session", "Status", "Emiten", "Arah",
    "Entry", "SL", "TP1", "TP2", "Size (lot)", "Estim Modal",
    "Alasan / Set", "Hasil", "P/L %", "Skor Disiplin", "Catatan", "Mode",
]
WIDTHS = [12, 8, 10, 10, 10, 7, 10, 10, 10, 10, 9, 13, 38, 10, 9, 13, 22, 10]


def style_sheet(ws):
    header_fill = PatternFill("solid", fgColor="0F5132")  # green for BEI
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


def session_label(now_wib):
    wd = now_wib.weekday()
    if wd >= 5:
        return "WEEKEND"
    h = now_wib.hour
    if h < 8:
        return "PRE"
    if 8 <= h < 9:
        return "PRE-MKT"
    if 9 <= h < 15:
        return "INTRADAY"
    if 15 <= h < 16:
        return "POST"
    return "CLOSED"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--status", required=True, choices=["SIGNAL", "NO_TRADE", "EVAL"])
    p.add_argument("--emiten", default="-")
    p.add_argument("--arah", default="-")
    p.add_argument("--entry", default="")
    p.add_argument("--sl", default="")
    p.add_argument("--tp1", default="")
    p.add_argument("--tp2", default="")
    p.add_argument("--size", default="")
    p.add_argument("--modal", default="")
    p.add_argument("--alasan", default="")
    p.add_argument("--result", default="", help="TP1/TP2/SL/OPEN (for EVAL)")
    p.add_argument("--pnl", default="", help="P/L % (for EVAL)")
    p.add_argument("--note", default="")
    p.add_argument("--mode", default="INTRADAY",
                   help="Strategy mode: SCALPING | INTRADAY | BSJP")
    p.add_argument("--journal", default=XLSX)
    p.add_argument("--event-id", default="")
    args = p.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.journal)), exist_ok=True)
    with open(args.journal + ".lock", "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        append_locked(args)


def append_locked(args):
    now_wib = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    sess = session_label(now_wib)

    if os.path.exists(args.journal):
        wb = load_workbook(args.journal)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Jurnal IDX"
        style_sheet(ws)

    if args.event_id:
        marker = "[event:" + args.event_id + "]"
        if any(marker in str(r[16]) for r in ws.iter_rows(min_row=2, values_only=True) if len(r) >= 17):
            wb.close()
            print("ALREADY " + args.event_id)
            return
        args.note = (args.note + " " + marker).strip()
    fill = None
    if args.status == "NO_TRADE":
        fill = PatternFill("solid", fgColor="EDEDED")
    elif args.status == "EVAL":
        fill = PatternFill("solid", fgColor="FFF3CD")
    else:
        fill = PatternFill("solid", fgColor="D1ECF1" if args.arah.upper() == "LONG" else "F8D7DA")

    row = ws.max_row + 1 if ws.max_row > 1 or ws.cell(row=1, column=1).value else 2
    status_disp = {"SIGNAL": "SIGNAL", "NO_TRADE": "NO TRADE", "EVAL": "EVAL"}[args.status]
    values = [
        now_wib.strftime("%Y-%m-%d"), now_wib.strftime("%H:%M"), sess, status_disp,
        args.emiten, args.arah, args.entry, args.sl, args.tp1, args.tp2,
        args.size, args.modal, args.alasan, args.result, args.pnl, "", args.note,
        args.mode.upper(),
    ]
    for col, val in enumerate(values, start=1):
        c = ws.cell(row=row, column=col, value=val)
        c.border = Border(
            left=Side(style="thin", color="B0B0B0"), right=Side(style="thin", color="B0B0B0"),
            top=Side(style="thin", color="B0B0B0"), bottom=Side(style="thin", color="B0B0B0"),
        )
        c.alignment = Alignment(vertical="center", wrap_text=(col in (13, 17)))
        if fill:
            c.fill = fill
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=os.path.dirname(os.path.abspath(args.journal)))
    os.close(fd)
    try:
        wb.save(tmp)
        wb.close()
        with open(tmp, "rb") as saved:
            os.fsync(saved.fileno())
        os.replace(tmp, args.journal)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"OK logged -> {args.journal} (row {row})")


if __name__ == "__main__":
    sys.exit(main())
