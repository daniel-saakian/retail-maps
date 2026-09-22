from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_HALIGN = {0:"center", 1:"left", 2: "right"}
_VALIGN = {0:"center", 1:"top", 2: "bottom"}

_DEFAULT_BORDER_STYLE = "thin"

def _argb(hex_color: str | None) -> str | None:
    if not hex_color:
        return None
    h = hex_color.lstrip("#").upper()
    if len(h) == 6:
        return "FF" + h
    if len(h) == 8:
        return h
    return None

def _side(border_spec: dict | None):
    if not border_spec:
        return None
    color = _argb(border_spec.get("color")) or "FF000000"
    return Side(border_style=_DEFAULT_BORDER_STYLE, color=color)

def build_xlsx_from_luckysheet(sheets:list[dict]) -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
 
    for sheet in sheets:
        title = (sheet.get("name") or "Sheet")[:31] or "Sheet"
        ws = wb.create_sheet(title=title)

        borders_by_cell: dict[tuple[int,int], Border] = {}
        config = sheet.get("config") or {}
        for entry in config.get("borderInfo") or []:
            if entry.get("rangeType") != "cell":
                continue
            value = entry.get("value") or {}
            r, c = value.get("row_index"), value.get("col_index")
            if r is None or c is None:
                continue
            borders_by_cell[(r, c)] = Border(
                left=_side(value.get("l")),
                right=_side(value.get("r")),
                top=_side(value.get("t")),
                bottom=_side(value.get("b")),
            )
 
        for cell in sheet.get("celldata") or []:
            r, c = cell.get("r"), cell.get("c")
            v = cell.get("v")
            if r is None or c is None:
                continue
 
            border = borders_by_cell.pop((r, c), None)
 
            if not isinstance(v, dict):
                if v is None and border is None:
                    continue
                excel_cell = ws.cell(row=r + 1, column=c + 1, value=v)
                if border:
                    excel_cell.border = border
                continue
 
            excel_cell = ws.cell(row=r + 1, column=c + 1, value=v.get("v"))
 
            font_kwargs = {}
            if v.get("bl"):
                font_kwargs["bold"] = True
            if v.get("it"):
                font_kwargs["italic"] = True
            if v.get("un"):
                font_kwargs["underline"] = "single"
            color = _argb(v.get("fc"))
            if color:
                font_kwargs["color"] = color
            if v.get("fs"):
                try:
                    font_kwargs["size"] = float(v["fs"])
                except (TypeError, ValueError):
                    pass
            if font_kwargs:
                excel_cell.font = Font(**font_kwargs)
 
            bg = _argb(v.get("bg"))
            if bg:
                excel_cell.fill = PatternFill("solid", fgColor=bg)
 
            ht, vt = v.get("ht"), v.get("vt")
            if ht is not None or vt is not None:
                excel_cell.alignment = Alignment(
                    horizontal=_HALIGN.get(ht, "general"),
                    vertical=_VALIGN.get(vt, "center"),
                    wrap_text=True,
                )
 
            fmt = (v.get("ct") or {}).get("fa")
            if fmt and fmt != "General":
                excel_cell.number_format = fmt
 
            if border:
                excel_cell.border = border

        for (r, c), border in borders_by_cell.items():
            ws.cell(row=r + 1, column=c + 1).border = border
 
        for merge in (config.get("merge") or {}).values():
            r, c = merge.get("r"), merge.get("c")
            rs, cs = merge.get("rs", 1) or 1, merge.get("cs", 1) or 1
            if r is None or c is None:
                continue
            try:
                ws.merge_cells(
                    start_row=r + 1, start_column=c + 1,
                    end_row=r + rs, end_column=c + cs,
                )
            except Exception:
                pass
 
        for col_idx, width_px in (config.get("columnlen") or {}).items():
            try:
                width_chars = max(2.0, (float(width_px) - 5.0) / 7.0)
                ws.column_dimensions[get_column_letter(int(col_idx) + 1)].width = round(width_chars, 2)
            except (TypeError, ValueError):
                continue
 
        for row_idx, height_px in (config.get("rowlen") or {}).items():
            try:
                height_pt = float(height_px) * 0.75
                ws.row_dimensions[int(row_idx) + 1].height = round(height_pt, 2)
            except (TypeError, ValueError):
                continue
 
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()