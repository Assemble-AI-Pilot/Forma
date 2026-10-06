#!/usr/bin/env python3
"""Make the plugin's Entity Bible extract from the master Entity Bible.

The master workbook carries far more than contract-bot needs - tax file
numbers, ASIC corporate keys, officeholders, shareholders and beneficiaries,
insurance policies, portal notes and comments. None of that belongs in a plugin
that is installed on many machines and kept in a GitHub repository.

This writes a workbook holding ONLY what lookup.py reads, at the same sheet
name, header row and column positions, so lookup.py works unchanged:

    entity name, group, purpose, project address, ACN, ABN, registered address

Values are copied, never formulas, so the registered addresses (formulas in the
master) survive. Every other column is left empty, and no other sheet, comment
or defined name is carried across.

Usage:
    python make_entity_extract.py <master Entity Bible.xlsx> <output.xlsx>

Run it whenever finance updates the master, then replace
skills/contract-bot/assets/Entity_Bible.xlsx with the output.
"""
import datetime as dt
import re
import sys

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl --break-system-packages")

SHEET = "Summary of Assemble Entities"
HEADER_ROW = 6
# Column positions as lookup.py reads them (1-based). Group is kept for context.
KEEP = {1: "Entity Name", 3: "Group", 4: "Purpose", 5: "Project Address",
        6: "ACN", 7: "ABN", 11: "Registered Address"}
# Headers that must never be carried, whatever column they sit in.
NEVER = re.compile(r"\bTFN\b|tax file|corporate key|password|portal access", re.I)


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    master, out = sys.argv[1], sys.argv[2]

    src = load_workbook(master, data_only=True)  # cached values, not formulas
    if SHEET not in src.sheetnames:
        sys.exit(f"No sheet named {SHEET!r} in {master}")
    ws = src[SHEET]

    # Refuse a master whose layout has moved: lookup.py reads fixed columns.
    for col, label in KEEP.items():
        got = str(ws.cell(HEADER_ROW, col).value or "").strip()
        if got.lower() != label.lower():
            sys.exit(f"Column {col} header is {got!r}, expected {label!r} - the master's "
                     "layout has changed; update KEEP here and COL in lookup.py together.")
        if NEVER.search(got):
            sys.exit(f"Refusing to copy column {col} ({got!r}).")

    dst = Workbook()
    out_ws = dst.active
    out_ws.title = SHEET
    out_ws.cell(1, 1, "Entity Bible - extract for the forma-user plugin").font = Font(bold=True)
    # Worded so it names none of the dropped fields: the release check refuses any
    # workbook that mentions them, and this note should never be the reason.
    out_ws.cell(2, 1, "Only the seven columns contract-bot reads. Nothing else from the "
                      "master is carried across.")
    out_ws.cell(3, 1, f"Made {dt.date.today():%d %b %Y} by scripts/make_entity_extract.py "
                      "from the master Entity Bible. Regenerate it; never edit it by hand.")
    for col, label in KEEP.items():
        out_ws.cell(HEADER_ROW, col, label).font = Font(bold=True)

    rows = 0
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        values = {c: ws.cell(r, c).value for c in KEEP}
        if not any(v not in (None, "") for v in values.values()):
            continue
        rows += 1
        for c, v in values.items():
            if v not in (None, ""):
                out_ws.cell(HEADER_ROW + rows, c, str(v).strip() if isinstance(v, str) else v)
    dst.save(out)
    print(f"Wrote {rows} entities, {len(KEEP)} columns, to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
