from __future__ import annotations

import copy
import io
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

try:
    from hb_review_fields import FIELDS, TABLES, SWOT, MIRRORS, FIELD_BY_ID, TABLE_BY_ID
except ImportError:
    from .hb_review_fields import FIELDS, TABLES, SWOT, MIRRORS, FIELD_BY_ID, TABLE_BY_ID

TEMPLATE_PATH = Path(__file__).parent / "templates" / "HB_Site_Review_Form.docx"
FONT_HALF_POINTS = "16"

def _tc(table, row, col):
    tr = table.rows[row]._tr
    return tr.tc_lst[col]

def _make_run(text: str, rpr_template=None):
    r = OxmlElement("w:r")
    if rpr_template is not None:
        r.append(copy.deepcopy(rpr_template))
    else:
        rpr = OxmlElement("w:rPr")
        for tag in ("w:sz", "w:szCs"):
            el = OxmlElement(tag)
            el.set(qn("w:val"), FONT_HALF_POINTS)
            rpr.append(el)
        r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r

def _clear_runs(p):
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)


def write_cell(tc, value: str, *, keep_blank_lines: bool = False):
    lines = [ln.rstrip() for ln in str(value).replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return
    paras = tc.findall(qn("w:p"))
    base = paras[0]
    for i, line in enumerate(lines):
        if i < len(paras):
            p = paras[i]
        else:
            p = copy.deepcopy(base)
            tc.findall(qn("w:p"))[-1].addnext(p)
        _clear_runs(p)
        if line:
            p.append(_make_run(line))
    if not keep_blank_lines:
        for p in tc.findall(qn("w:p"))[len(lines):]:
            tc.remove(p)


def _write_numbered_lines(tc, items: list[str], start_index: int):
    paras = tc.findall(qn("w:p"))[start_index:]
    for i, p in enumerate(paras):
        text = items[i].strip() if i < len(items) and items[i] else ""
        if not text:
            continue
        runs = p.findall(qn("w:r"))
        rpr = runs[0].find(qn("w:rPr")) if runs else None
        _clear_runs(p)
        p.append(_make_run(f"{i + 1}. {text}", rpr))

def _ensure_rows(table, first_row: int, needed: int):
    have = len(table.rows) - first_row
    last = table.rows[-1]._tr
    for _ in range(max(0, needed - have)):
        clone = copy.deepcopy(last)
        for tc in clone.findall(qn("w:tc")):
            for p in tc.findall(qn("w:p")):
                _clear_runs(p)
        table._tbl.append(clone)
        last = clone

def swot_to_text(swot:dict) -> str:
    out = []
    for key, title in (("strengths", "Strengths"), ("weaknesses", "Weaknesses"),
                       ("opportunities", "Opportunities"), ("threats", "Threats")):
        items = [s for s in (swot or {}).get(key, []) if s and s.strip()][:3]
        if items:
            out.append(f"{title}: " + "; ".join(items))
    return "\n".join(out)

def wt_rows_from_swot(swot: dict) -> list[dict]:
    rows = []
    for key, prefix in (("weaknesses", "W"), ("threats", "T")):
        for s in (swot or {}).get(key, []):
            if s and s.strip():
                rows.append({"item": f"{prefix}: {s.strip()}", "tactic": ""})
    return rows


def _resolve(fields: dict, tables: dict, swot: dict) -> tuple[dict, dict]:
    fields = dict(fields or {})
    tables = dict(tables or {})
    for target, src in MIRRORS.items():
        if not str(fields.get(target) or "").strip() and str(fields.get(src) or "").strip():
            fields[target] = fields[src]
    if not str(fields.get("site_swot") or "").strip():
        built = swot_to_text(swot)
        if built:
            fields["site_swot"] = built
    if not tables.get("wt_tactics"):
        rows = wt_rows_from_swot(swot)
        if rows:
            tables["wt_tactics"] = rows
    return fields, tables

def render_docx(fields:dict, tables:dict | None = None, swot:dict | None = None, template_path: Path | str=TEMPLATE_PATH) -> bytes:
    doc = Document(str(template_path))
    fields, tables = _resolve(fields, tables or {}, swot or {})
    for fid, value in fields.items():
        f = FIELD_BY_ID.get(fid)
        if not f or value is None or not str(value).strip():
            continue
        t, r, c = f["loc"]
        write_cell(_tc(doc.tables[t], r, c), str(value))

    for tid, rows in (tables or {}).items():
        spec = TABLE_BY_ID.get(tid)
        if not spec or not rows:
            continue
        rows = [r for r in rows if any(str(v or "").strip() for v in r.values())]
        rows = rows[: spec.get("max_rows", len(rows))]
        if not rows:
            continue
        tbl = doc.tables[spec["table"]]
        if not spec.get("fixed_rows"):
            _ensure_rows(tbl, spec["first_row"], len(rows))
        for i, row in enumerate(rows):
            r_idx = spec["first_row"] + i
            if r_idx >= len(tbl.rows):
                break
            for key, _label, col in spec["columns"]:
                v = row.get(key)
                if v is not None and str(v).strip():
                    write_cell(_tc(tbl, r_idx, col), str(v))

    if swot:
        tbl = doc.tables[SWOT["table"]]
        for key, (r, c) in SWOT["quadrants"].items():
            items = [s for s in swot.get(key, []) if s and str(s).strip()][: SWOT["max_items"]]
            if items:
                _write_numbered_lines(_tc(tbl, r, c), items, start_index=2)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def dump_template(template_path=TEMPLATE_PATH):
    doc = Document(str(template_path))
    for ti, t in enumerate(doc.tables):
        print(f"=== table {ti} ({len(t.rows)} rows)")
        for ri, row in enumerate(t.rows):
            cells = []
            for tc in row._tr.tc_lst:
                txt = "".join(x.text or "" for x in tc.iter(qn("w:t")))
                cells.append(repr(txt[:30]))
            print(f"  r{ri}: " + " | ".join(cells))

if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump_template()
    elif "--sample" in sys.argv:
        out = sys.argv[sys.argv.index("--sample") + 1]
        sample_fields = {f["id"]: f["label"] for f in FIELDS}
        sample_tables = {t["id"]: [{c[0]: f"{c[1]} {i+1}" for c in t["columns"]} for i in range(3)] for t in TABLES}
        sample_swot = {q: [f"{q} {i+1}" for i in range(3)] for q in SWOT["quadrants"]}
        Path(out).write_bytes(render_docx(sample_fields, sample_tables, sample_swot))
        print(f"wrote {out}")
    else:
        print(__doc__)