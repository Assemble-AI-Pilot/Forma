#!/usr/bin/env python3
"""Fill Assemble's Variation Approval (Recommendation for Approval) template from a values JSON.

Why a script: the variation approval is the same three tables every time, so the fill is
deterministic. Doing it in code removes the yellow instruction prompts reliably, keeps the table
formatting intact, and computes the three things nobody should re-decide by hand each run — the
revised budget, the Position against Budget state, and who has to sign.

Usage:
    python fill_variation.py <values.json> <output.docx> [--template path]

The template defaults to ../assets/Variation_Approval_Template.docx (bundled).

THE TOP PANEL IS THE DOCUMENT. Most readers look at Table 0 and nothing else. Total Cost is a
bare figure; Position against Budget is one of four states and nothing more.

POSITION AGAINST BUDGET — four states, waterfalling down:

    Within Budget                        funded from the line itself, a budget transfer, or the
                                         cost category's own contingency bucket
    Drawn from Project Contingency       reportable
    Drawn from Construction Contingency  reportable
    NO BUDGET REMAINING                  neither reportable bucket can cover it — rendered RED
                                         AND BOLD, because it almost always means a mistake

Reportable contingency is Project and Construction ONLY. A subcategory bucket such as
"Contingency for Professional Fees" is NOT reportable, so drawing on it is still Within Budget —
that is where a contract's gain or loss normally settles. Escalation tries the reportable bucket
matching the cost category first (construction costs -> Construction Contingency, everything else
-> Project Contingency), then the other one.

Pass `position_state` to set it explicitly, or `funded_from` as one of:
    "category" | "transfer" | "project_contingency" | "construction_contingency" | "none"
and the state is derived. Given neither, the state is inferred from the transfer sources.

CONVENTIONS
  * All dollar figures are EXCL GST.
  * Revised Budget = uncommitted budget available + transfers in. When that equals Cost Required,
    the variation is funded and the panel says so.
  * Signature thresholds (ex GST): the preparer always signs under "Recommendation for
    Signature". The "Approval" section is ALWAYS present — at or below $25,000 the project lead
    approves it themselves, above $25,000 it is Head of Delivery, and above $1,000,000 the CEO
    signs as well.
  * [square brackets] mark something unresolved and render HIGHLIGHTED YELLOW. Use [[double
    brackets]] for brackets belonging to the text itself (an email subject) — they render as
    [single] with no highlight.
  * A list value renders as one "- " prefixed paragraph per item.
  * An omitted field is left BLANK, not left as the yellow prompt, so an empty cell is itself a
    visible signal that something still needs input.

VALUES JSON KEYS (all optional):
  project, reference, prepared_by, purpose,
  total_cost           - narrative override; auto-built from `cost_required` if omitted
  position_state       - override; otherwise derived from funded_from / transfers
  funded_from          - see above
  cost_code, cost_required, uncommitted_budget,
  transfers            - list of {amount, from, to}; renders "Budget Transfers"
  revised_budget       - auto-computed from uncommitted_budget + transfers if omitted
  comments             - str or list; two or three points is the target
  programme_impact,
  contingency          - {project:{code,amount}, construction:{code,amount}, basis?} -> renders
                         the "Project and Construction Position" row in house format
  project_construction_position - free-text override of that row (bullets written by you)
  delegated_authority  - auto-built from cost_required if omitted
  supporting_documents - list
  preparer_name, preparer_position, footer,
  approved_in_forma    - true when the sheet is going into Forma: writes "Approved in FORMA"
                         into the Signature and Date columns instead of leaving them blank
  hod_required / ceo_required - optional overrides of the thresholds
"""
import argparse, json, os, re, sys

try:
    import docx
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_COLOR_INDEX
    from docx.oxml.ns import qn
except ImportError:
    sys.exit("python-docx is required: pip install python-docx --break-system-packages")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(os.path.dirname(HERE), "assets", "Variation_Approval_Template.docx")
CELL_FONT_PT = 8

HOD_THRESHOLD = 25_000
CEO_THRESHOLD = 1_000_000

WITHIN = "Within Budget"
PROJECT_CONT = "Drawn from Project Contingency"
CONSTRUCTION_CONT = "Drawn from Construction Contingency"
NO_BUDGET = "NO BUDGET REMAINING"

FUNDED_FROM_STATE = {
    "category": WITHIN,
    "transfer": WITHIN,
    "within": WITHIN,
    "project_contingency": PROJECT_CONT,
    "construction_contingency": CONSTRUCTION_CONT,
    "none": NO_BUDGET,
}

# key -> (table index, row index). The value goes in the row's last cell.
FIELD_CELLS = {
    "project": (0, 1), "reference": (0, 2), "prepared_by": (0, 3),
    "total_cost": (0, 4), "position_state": (0, 5), "purpose": (0, 7),
    "cost_code": (1, 2), "cost_required": (1, 3), "uncommitted_budget": (1, 4),
    "budget_transfers": (1, 5), "revised_budget": (1, 6), "comments": (1, 7),
    "programme_impact": (1, 9), "project_construction_position": (1, 10),
    "delegated_authority": (1, 12), "supporting_documents": (1, 13),
}
# Auto-prefixed with "- ", one paragraph per item. project_construction_position is NOT here:
# it carries an unbulleted lead-in line, so its bullets are written explicitly.
LIST_FIELDS = {"comments", "delegated_authority", "supporting_documents", "budget_transfers"}

SIG_PREPARER_ROW, SIG_HOD_ROW, SIG_CEO_ROW = 2, 4, 5
SIG_PERSON_ROWS = (SIG_PREPARER_ROW, SIG_HOD_ROW, SIG_CEO_ROW)
APPROVED_IN_FORMA = "Approved in FORMA"


def money(v):
    """Format an amount. Cents are kept only when they are actually there."""
    n = parse_amount(v)
    if n is None:
        return str(v)
    cents = abs(n - round(n)) > 0.004
    body = f"{abs(n):,.2f}" if cents else f"{abs(n):,.0f}"
    return f"-${body}" if n < 0 else f"${body}"


def parse_amount(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\s*\$?\s*[\d,]+(?:\.\d+)?", str(v))
    if not m:
        return None
    n = float(re.sub(r"[^\d.]", "", m.group()))
    return -n if m.group().lstrip().startswith("-") else n


def truthy(v):
    return v if isinstance(v, bool) else str(v).strip().lower() in {"yes", "true", "y", "1"}


def _strip_para_mark_highlight(p):
    pPr = p._p.find(qn('w:pPr'))
    rPr = pPr.find(qn('w:rPr')) if pPr is not None else None
    if rPr is not None:
        for h in rPr.findall(qn('w:highlight')):
            rPr.remove(h)


def reset_cell(cell):
    for p in cell.paragraphs[1:]:
        p._element.getparent().remove(p._element)
    p0 = cell.paragraphs[0]
    for r in list(p0.runs):
        r._element.getparent().remove(r._element)
    _strip_para_mark_highlight(p0)
    return p0


def add_runs_with_highlight(p, text):
    """[bracketed] spans highlight yellow; [[double]] render as literal [single], unhighlighted."""
    for seg in re.split(r'(\[\[[^\]]*\]\]|\[[^\]]*\])', str(text)):
        if seg == "":
            continue
        literal = seg.startswith('[[') and seg.endswith(']]')
        run = p.add_run(seg[1:-1] if literal else seg)
        run.font.size = Pt(CELL_FONT_PT)
        run.font.highlight_color = (WD_COLOR_INDEX.YELLOW
                                    if seg.startswith('[') and not literal
                                    else WD_COLOR_INDEX.AUTO)


def value_cell(table, row_idx):
    row = table.rows[row_idx]
    distinct = list(dict.fromkeys(c._tc for c in row.cells))
    return row.cells[-1] if len(distinct) > 1 else row.cells[0]


def write_text(cell, value, bulleted=False):
    lines = value if isinstance(value, list) else [value]
    p0 = reset_cell(cell)
    for i, line in enumerate(lines):
        p = p0 if i == 0 else cell.add_paragraph()
        p.style = "Table Text"
        _strip_para_mark_highlight(p)
        text = str(line).strip()
        if bulleted and len(lines) > 1 and not text.startswith("-"):
            text = "- " + text
        add_runs_with_highlight(p, text)


def write_state(cell, state):
    """NO BUDGET REMAINING goes red and bold — it nearly always means something is wrong."""
    p = reset_cell(cell)
    p.style = "Table Text"
    run = p.add_run(state)
    run.font.size = Pt(CELL_FONT_PT)
    if state == NO_BUDGET:
        run.bold = True
        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)


def render_transfers(transfers):
    """[{amount, from, to}] -> the lines the document shows."""
    out = []
    for t in transfers:
        if isinstance(t, str):
            out.append(t)
            continue
        amt = parse_amount(t.get("amount"))
        line = f"{money(-abs(amt)) if amt is not None else t.get('amount')} from {t.get('from', '[source]')}"
        if t.get("to"):
            line += f" to {t['to']}"
        out.append(line)
    return out


def render_contingency(c):
    """Both reportable buckets, always, on a conservative basis — lead-in then two bullets."""
    lines = [c.get("basis", "After accounting for other transfers already raised but not yet "
                            "approved.")]
    for key, label in (("project", "project contingency"),
                       ("construction", "construction contingency")):
        b = c.get(key)
        if not b:
            continue
        code = f" ({b['code']})" if isinstance(b, dict) and b.get("code") else ""
        amt = b.get("amount") if isinstance(b, dict) else b
        lines.append(f"- {money(amt)} of {label} remaining{code}")
    return lines


def derive_state(v):
    """Explicit state wins, then funded_from, then an inference from the transfer sources."""
    if v.get("position_state"):
        return v["position_state"]
    ff = str(v.get("funded_from", "")).strip().lower()
    if ff in FUNDED_FROM_STATE:
        return FUNDED_FROM_STATE[ff]
    sources = " ".join(str(t.get("from", "")) for t in v.get("transfers", [])
                       if isinstance(t, dict)).lower()
    # Only the two REPORTABLE buckets change the state. A category bucket such as
    # "Contingency for Professional Fees" is not reportable and stays Within Budget.
    if "construction contingency" in sources:
        return CONSTRUCTION_CONT
    if "project contingency" in sources:
        return PROJECT_CONT
    return WITHIN


def build_delegated_authority(cost):
    n = parse_amount(cost)
    if n is None:
        return None
    if n > CEO_THRESHOLD:
        return f"Value ({money(n)}) > {money(CEO_THRESHOLD)} – CEO sign-off required"
    if n > HOD_THRESHOLD:
        return f"Value ({money(n)}) < {money(CEO_THRESHOLD)} – Head of Delivery sign-off required"
    return (f"Value ({money(n)}) < {money(HOD_THRESHOLD)} – Project Lead may approve "
            f"without higher approval")


def delete_row(table, idx):
    tr = table.rows[idx]._tr
    tr.getparent().remove(tr)


def set_sig(cell, text):
    p = reset_cell(cell)
    p.style = "Table Text"
    r = p.add_run(text)
    r.font.size = Pt(CELL_FONT_PT)
    r.font.highlight_color = WD_COLOR_INDEX.AUTO


def distinct_cells(row):
    """A person row grid-spans its Position cell, so row.cells repeats it. Collapse to
    [Name, Position, Signature, Date]."""
    seen, out = set(), []
    for c in row.cells:
        if c._tc in seen:
            continue
        seen.add(c._tc)
        out.append(c)
    return out


def mark_approved_in_forma(sig):
    """The sheet is attached to the Forma record and approved through Forma's workflow, so
    there is no wet signature — say so in the Signature and Date columns rather than leaving
    two empty boxes that invite one."""
    for ri in SIG_PERSON_ROWS:
        if ri >= len(sig.rows):
            continue
        cells = distinct_cells(sig.rows[ri])
        if len(cells) < 4:
            continue
        for c in cells[2:4]:
            set_sig(c, APPROVED_IN_FORMA)


def set_footer(doc, text):
    for p in doc.sections[0].footer.paragraphs:
        if "Variation Approval" in p.text or "(Project code" in p.text:
            for i, r in enumerate(p.runs):
                r.text = text if i == 0 else ""
                r.font.highlight_color = WD_COLOR_INDEX.AUTO
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("values")
    ap.add_argument("output")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    args = ap.parse_args()

    v = dict(json.load(open(args.values, encoding="utf-8")))
    d = docx.Document(args.template)
    t = d.tables

    cost = parse_amount(v.get("cost_required"))
    uncommitted = parse_amount(v.get("uncommitted_budget"))
    transfers_in = sum(abs(parse_amount(x.get("amount")) or 0)
                       for x in v.get("transfers", []) if isinstance(x, dict))

    if "revised_budget" not in v and uncommitted is not None:
        v["revised_budget"] = money(uncommitted + transfers_in)
    if "total_cost" not in v and cost is not None:
        v["total_cost"] = f"{money(cost)} (excl. GST)"
    if v.get("transfers"):
        v["budget_transfers"] = render_transfers(v["transfers"])
    if v.get("contingency") and "project_construction_position" not in v:
        v["project_construction_position"] = render_contingency(v["contingency"])
    if "delegated_authority" not in v:
        da = build_delegated_authority(cost)
        if da:
            v["delegated_authority"] = da

    state = derive_state(v)
    v["position_state"] = state

    # Only reformat a bare number; a string the author wrote is left alone.
    for key in ("cost_required", "uncommitted_budget"):
        if isinstance(v.get(key), (int, float)) and not isinstance(v.get(key), bool):
            v[key] = money(v[key])

    missing = []
    for key, (ti, ri) in FIELD_CELLS.items():
        cell = value_cell(t[ti], ri)
        if key == "position_state":
            write_state(cell, state)
        elif key in v and v[key] not in (None, "", []):
            write_text(cell, v[key], bulleted=key in LIST_FIELDS)
        else:
            reset_cell(cell)
            missing.append(key)

    hod = truthy(v["hod_required"]) if "hod_required" in v else (cost is not None and cost > HOD_THRESHOLD)
    ceo = truthy(v["ceo_required"]) if "ceo_required" in v else (cost is not None and cost > CEO_THRESHOLD)

    sig = t[2]
    if v.get("preparer_name"):
        set_sig(sig.rows[SIG_PREPARER_ROW].cells[0], v["preparer_name"])
    if v.get("preparer_position"):
        set_sig(sig.rows[SIG_PREPARER_ROW].cells[1], v["preparer_position"])
    # The Approval section is always present. At or below $25,000 the project lead approves it.
    if not ceo:
        delete_row(sig, SIG_CEO_ROW)
    if not hod:
        set_sig(sig.rows[SIG_HOD_ROW].cells[0], v.get("preparer_name", ""))
        set_sig(sig.rows[SIG_HOD_ROW].cells[1], v.get("preparer_position", ""))

    if truthy(v.get("approved_in_forma", False)):
        mark_approved_in_forma(sig)

    set_footer(d, v.get("footer") or f"{v.get('project', '')} – {v.get('reference', '')}".strip(" –"))

    d.save(args.output)
    print(f"Saved: {args.output}")
    if cost is not None:
        funded = uncommitted is not None and (uncommitted + transfers_in) >= cost - 0.005
        print(f"Cost required: {money(cost)} | Position: {state}"
              + (f" | Revised budget: {money(uncommitted + transfers_in)}"
                 f" ({'funded' if funded else 'SHORTFALL'})" if uncommitted is not None else "")
              + f" | Approval: {'CEO' if ceo else 'Head of Delivery' if hod else 'Project Lead'}")
    if state == NO_BUDGET:
        print("WARNING: position is NO BUDGET REMAINING — check this is not an error.")
    if missing:
        print(f"BLANK cells ({len(missing)}) — still need input: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
