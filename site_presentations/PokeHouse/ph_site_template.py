from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from pathlib import Path
from openpyxl.styles import Font, PatternFill, Alignment, Side, Border
from openpyxl.utils import get_column_letter
import pandas as pd
 
dark_orange = "FF9B0003"
 
red = "FFFD2626"
 
coral = "FFF8A45F"
 
white = "FFFFFFFF"
 
burgundy = "FF630F0F"
 
sand = "FFF4E3C1"
 
offwhite = "FFFAF8FF"
 
title_orange = "FFF6DCC0"
 
 
thin_side = Side(border_style = "thin", color = "FF000000")
box = Border(top = thin_side, left = thin_side, right=thin_side, bottom=thin_side)
center = Alignment(horizontal = "center", vertical = "center")
leftc = Alignment(horizontal = "left", vertical = "center")
vcenter = Alignment(vertical = "center")
 
fbanner_title = Font(name = "Montserrat", size = 20, bold = True, color = white)
fbanner_sub = Font(name = "Montserrat", size = 12, bold = True, color = burgundy)
faddress = Font(name = "Georgia", size = 14, bold = True, color = red)
fsubtit = Font(name = "Arial", size = 10, bold = False, color = coral)
fsection_head = Font(name = "Montserrat", size = 11, bold = True, color = white)
ftable_head = Font(name = "Arial", size = 10, bold = True, color = burgundy)
fbody = Font(name = "Roboto", size = 10, bold = False)
 
fill_darkred = PatternFill("solid", start_color = dark_orange)
fill_titlesub = PatternFill("solid", start_color = title_orange)
fill_sand = PatternFill("solid", start_color = sand)
fill_offwhite = PatternFill("solid", start_color = offwhite)
 
def _extract_city_state(matched_address:str) -> str:
    if not matched_address:
        return "unknown"
    parts = [p.strip() for p in matched_address.split(",")]
    if len(parts) >= 3:
        city = parts[-3].title()
        state = parts[-2].upper()
        return f"{city}, {state}"
    return "unknown"
def _disambiguate(base:str, used:set) -> str:
    if base not in used:
        return base
    prefix, rest = base.split(" - ", 1)
    n=2
    while f"{prefix} - {n} {rest}" in used:
        n += 1
    return f"{prefix} - {n} {rest}"
def _set_column_widths(ws):
    widths = {"A": 2.71, "B": 33.71, "C": 24, "D": 17.57, "E": 13.57, "F": 6.71}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
def _style_row(ws,row,*,fill=None, font = fbody, align= vcenter,border=box,cols=("B","C","D","E","F")):
    for col in cols:
        cell = ws[f"{col}{row}"]
        cell.font = font
        cell.alignment = align
        cell.border = border
        if fill is not None:
            cell.fill = fill
 
def _label_row(ws, row, label, *, stripe, value=None, value_align=leftc, number_format = None):
    fill = fill_offwhite if stripe else None
    ws[f"B{row}"]=label
    ws.merge_cells(f"C{row}:F{row}")
    if value is not None:
        ws[f"C{row}"]=value
    _style_row(ws,row,fill=fill,cols=("B","C","D","E","F"))
    ws[f"C{row}"].alignment = value_align
    if number_format:
        ws[f"C{row}"].number_format = number_format
 
def _section_header(ws,row,text,span=("B","F")):
    rng = f"{span[0]}{row}:{span[1]}{row}"
    ws.merge_cells(rng)
    cell = ws[f"{span[0]}{row}"]
    cell.value = text
    cell.font = fsection_head
    cell.fill = fill_darkred
    cell.alignment = leftc
    for col_letter in [get_column_letter(c) for c in range(ord(span[0]) - 64, ord(span[1]) - 64 +1)]:
        ws[f"{col_letter}{row}"].border = box
        ws[f"{col_letter}{row}"].fill = fill_darkred
 
def _table_header_row(ws, row, headers):
    for col, text in headers.items():
        cell = ws[f"{col}{row}"]
        cell.value = text
        cell.font = ftable_head
        cell.fill = fill_sand
        cell.alignment = center
        cell.border = box
 
def _build_top_banner(ws, profile:dict, plaza_name: str|None=None):
    ws.merge_cells("B2:F3")
    cell = ws["B2"]
    cell.value = "Poke House"
    cell.font = fbanner_title
    cell.fill = fill_darkred
    cell.alignment = center
    for col in ("B","C","D","E","F"):
        for row in (2,3):
            ws[f"{col}{row}"].border = box
            ws[f"{col}{row}"].fill = fill_darkred
    ws.merge_cells("B4:F4")
    sub = ws["B4"]
    sub.value = "Site Summary"
    sub.font = fbanner_sub
    sub.fill = fill_titlesub
    sub.alignment = center
    for col in ("B","C","D","E","F"):
        ws[f"{col}4"].border = box
        ws[f"{col}4"].fill = fill_titlesub
    
    ws.row_dimensions[5].height = 6
 
    ws.merge_cells("B6:F6")
    addr = ws["B6"]
    addr.value = profile.get("address") or "Address | City, St Zip"
    addr.font = faddress
    addr.alignment = center
 
    ws.merge_cells("B7:F7")
    sub2 = ws["B7"]
    today = datetime.now().strftime("%B %d, %Y")
    plaza_label = plaza_name or "Shopping Plaza Name"
    sub2.value = f"{plaza_label} • {today} • Square Footage"
    sub2.font = fsubtit
    sub2.alignment = center
 
def _build_section_space(ws, profile:dict, plaza_name:str|None=None):
    _section_header(ws, 8, "I. Space Information & Property Details")
    labels = [
        ("Property Address", True),
        ("Shopping Center Name", False),
        ("Total Square Footage", True),
        ("Projected Delivery Date", False),
        ("Notes & Technical Specs", True),
    ]
    for i, (label, stripe) in enumerate(labels):
        row = 9+i
        nf = "mmmm yyyy" if label == "Projected Delivery Date" else None
        if label == "Property Address":
            value = profile.get("address")
        elif label == "Shopping Center Name":
            value = plaza_name
        else:
            value = None
        _label_row(ws, row, label, stripe = stripe, value = value, number_format = nf)
 
def _build_section_rent(ws):
    _section_header(ws, 15, "II. Rent Economics")
    labels = [
        ("Base Asking Rent ($/SF/Yr)", True),
        ("NNN Expenses ($/SF/Yr)", False),
        ("Total Rent ($/SF/Yr)", True),
        ("Total Annual Rent", False),
    ]
    for i, (label, stripe) in enumerate(labels):
        row = 16+i
        _label_row(ws,row,label,stripe=stripe, number_format = '$#,##0.00')
 
def _build_section_proximity(ws, proximity = None):
    _section_header(ws,21, "III. Regional Proximity")
    _table_header_row(ws, 22, {
        "B": "Nearby Location / City",
        "C": "Distance (Miles)",
        "D": "Notes"
    })
    ws.merge_cells("D22:F22")
    ws["D22"].fill = fill_sand
    ws["D22"].font = ftable_head
    ws["D22"].alignment = center
    for col in ("E","F"):
        ws[f"{col}22"].border = box
        ws[f"{col}22"].fill = fill_sand
    rows_data = list(proximity or [])
    while len(rows_data) < 7:
        rows_data.append(None)
    for i, loc in enumerate(rows_data[:7]):
        row = 23+i
        stripe = (row % 2 == 0)
        ws.merge_cells(f"D{row}:F{row}")
        if loc is not None:
            ws[f"B{row}"] = f"{loc['name']}"
            ws[f"C{row}"] = loc["distance_mi"]
            ws[f"D{row}"] = f"{loc.get('address','')}, {loc['city']}, {loc['state']} {loc.get('zip','')}"
        _style_row(ws,row,fill = fill_offwhite if stripe else None, cols = ("B","C","D","E","F"))
        ws[f"C{row}"].number_format = '##.# "Mi"'
        ws[f"C{row}"].alignment = center
 
def _build_section_market(ws, competitors = None, co_tenants=None):
    _section_header(ws,31, "IV. Market Information & Co-Tenancy")
    _table_header_row(ws, 32, {
        "B": "Co-Tenants (Same Center)",
        "C": "Category", 
        "D": "Estimated Sales",
        "E": "National/Regional Rank",
    })
    ws.merge_cells("E32:F32")
    ws["E32"].fill = fill_sand
    ws["E32"].font = ftable_head
    ws["E32"].alignment = center
    ws["E32"].border = box
    ws["F32"].fill = fill_sand
    ws["F32"].border = box
 
    tenant_list = list(co_tenants or [])
    while len(tenant_list) < 5:
        tenant_list.append(None)
    
    for i, tenant in enumerate(tenant_list[:5]):
        row = 33+i
        stripe = (row % 2 == 0)
        ws.merge_cells(f"E{row}:F{row}")
        if tenant is not None:
            ws[f"B{row}"] = tenant.get("name", "-")
            ws[f"C{row}"] = tenant.get("category", "-")
            sales = tenant.get("estimated_sales")
            if sales is not None:
                ws[f"D{row}"] = sales
                ws[f"D{row}"].number_format = '$#,##0'
            rank = tenant.get("rank_display")
            if rank:
                ws[f"E{row}"] = rank
        _style_row(ws,row, fill = fill_offwhite if stripe else None, cols = ("B","C","D","E","F"))
        ws[f"C{row}"].alignment = center
        ws[f"E{row}"].alignment = center
    _table_header_row(ws,38, {
        "B": "Primary Competitor",
        "C": "Distance (Miles)",
        "D": "Estimated Sales",
        "E": "Notes",
    })
    ws.merge_cells("E38:F38")
    ws["E38"].fill = fill_sand
    ws["E38"].font = ftable_head
    ws["E38"].alignment = center
    ws["E38"].border = box
    ws["F38"].fill = fill_sand
    ws["F38"].border = box
 
    comp_list = list(competitors or [])
    while len(comp_list) < 5:
        comp_list.append(None)
 
    for i,comp in enumerate(comp_list[:5]):
        row = 39+i
        stripe = (row % 2 == 0)
        ws.merge_cells(f"E{row}:F{row}")
 
        if comp is not None:
            ws[f"B{row}"] = comp.get("name", "-")
            ws[f"C{row}"] = comp.get("distance_mi")
            city_value = comp.get("city", "") or ""
            if isinstance(city_value, str) and "," in city_value:
                city_value = city_value.split(",")[0].strip()
            sales = comp.get("estimated_sales")
            if sales is not None:
                ws[f"D{row}"] = sales
                ws[f"D{row}"].number_format = '$#,##0'
            note_parts = [comp.get("street_address", "")]
            if comp.get("rank_display"):
                note_parts.append(comp["rank_display"])
            ws[f"E{row}"] = " | ".join(p for p in note_parts if p)
        _style_row(ws,row,fill=fill_offwhite if stripe else None, cols = ("B","C","D","E","F"))
        ws[f"C{row}"].number_format = '##.## "Mi"'
        ws[f"C{row}"].alignment = center
 
def _build_section_traffic(ws, traffic:dict | None=None):
    _section_header(ws,45, "V. Traffic & Infrastructure")
    _table_header_row(ws,46, {
        "B": "Adjacent Road/Highway",
        "C": "Daily Traffic Volume (VPD)",
        "D": "Notes",
    })
    ws.merge_cells("D46:F46")
    ws["D46"].fill = fill_sand
    ws["D46"].font = ftable_head
    ws["D46"].alignment = center
    ws["D46"].border = box
    for col in ("E","F"):
        ws[f"{col}46"].border = box
        ws[f"{col}46"].fill = fill_sand
    roads = (traffic or {}).get("roads",[]) if traffic else []
    while len(roads) < 1:
        roads.append(None)
    for i, road in enumerate(roads[:2]):
        row = 47+i
        stripe = (row==47)
        ws.merge_cells(f"D{row}:F{row}")
        if road is not None:
            ws[f"B{row}"] = road.get("road_name") or "-"
 
            aadt = road.get("aadt")
            if aadt is not None:
                if road.get("source") == "estimated":
                    ws[f"C{row}"] = f"~{aadt:,}"
                else:
                    ws[f"C{row}"] = f"{aadt:,}"
            else:
                ws[f"C{row}"] = "-"
            
            source = road.get("source", "")
            detail = road.get("source_detail", "")
            if source == "measured":
                note = detail or ""
            elif source == "estimated":
                note = detail or ""
            elif source == "unavailable":
                note = "No data available"
            else:
                note = detail or ""
            ws[f"D{row}"] = note
        _style_row(ws,row,fill=fill_offwhite if stripe else None, cols = ("B","C","D","E","F"))
        ws[f"C{row}"].alignment = center
 
def _build_section_demographics(ws,profile):
    _section_header(ws, 50, "VI. Demographic Analysis")
    _table_header_row(ws, 51, {
        "B": "Metric",
        "C": "1-Mile Radius", 
        "D": "2-Mile Radius",
        "E": "3-Mile Radius",
    })
    ws.merge_cells("E51:F51")
    ws["E51"].fill = fill_sand
    ws["E51"].font = ftable_head
    ws["E51"].alignment = center
    ws["E51"].border = box
    ws["F51"].fill = fill_sand
    ws["F51"].border = box
    rows_spec = [
        ("Total Population", "population", "#,##0", True),
        ("Daytime Population", "daytime_population", "#,##0", False),
        ("Daytime Employee Density", "employee_count", "#,##0", True),
        ("Average Household Income", "median_hh_income", "$#,##0", False),
        ("Median Age", "median_age", "0.0", True),
        ("Food & Alcohol Spending", "hh_dining_spend", "$#,##0", False),
    ]
    rings = [
        ("C", profile.get("ring_1mi") or {}),
        ("D", profile.get("ring_2mi") or {}),
        ("E", profile.get("ring_3mi") or {}),
    ]
    for i, (label,key,nf,stripe) in enumerate(rows_spec):
        row = 52+i
        fill = fill_offwhite if stripe else None
        ws[f"B{row}"] = label
        ws.merge_cells(f"E{row}:F{row}")
        for col, ring in rings:
            if key is not None:
                val = ring.get(key)
                if val is not None:
                    ws[f"{col}{row}"] = val
            ws[f"{col}{row}"].number_format = nf
        _style_row(ws,row, fill = fill, cols = ("B","C","D","E","F"))
        for col, _ in rings:
            ws[f"{col}{row}"].alignment = center
 
def build_excel_report(profile:dict, scores:dict, address:str, traffic:dict|None = None,proximity:list|None= None, competitors:list|None = None,
                       co_tenants:list|None=None,plaza_name:str|None=None,used_names:set|None = None) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Site Summary"
 
    ws.sheet_view.showGridLines = False
 
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = 0.4
    ws.page_margins.right = 0.4
    ws.page_margins.top = 0.4
    ws.page_margins.bottom = 0.4    
    ws.print_area= "A1:F54"
 
    display_plaza_name = plaza_name if plaza_name and plaza_name != "Unnamed Retail Center" else None
 
    _set_column_widths(ws)
    _build_top_banner(ws,profile, display_plaza_name)
    _build_section_space(ws,profile, display_plaza_name)
    _build_section_rent(ws)
    _build_section_proximity(ws,proximity)
    _build_section_market(ws, competitors, co_tenants)
    _build_section_traffic(ws,traffic)
    _build_section_demographics(ws,profile)
 
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
 
    city_state = _extract_city_state(profile.get("address", ""))
    base = f"Poke House - {city_state} Site Summary"
    final_name = _disambiguate(base, used_names or set())
    if used_names is not None:
        used_names.add(final_name)
    filename = f"{final_name}.xlsx"
    return buffer.getvalue(), filename
 
if __name__ == "__main__":
    la_profile = {
        "address": "100 N MAIN ST, LOS ANGELES, CA, 90012",
        "ring_1mi": {
            "population": 12500, "daytime_population": 14800,
            "median_hh_income": 78000, "median_age": 38.4, "employee_count": 5400,
        },
        "ring_2mi": {
            "population": 42000, "daytime_population": 47500,
            "median_hh_income": 80500, "median_age": 38.8, "employee_count": 18500,
        },
        "ring_3mi": {
            "population": 85000, "daytime_population": 92000,
            "median_hh_income": 82000, "median_age": 39.1, "employee_count": 32000,
        },
        "ring_5mi": {
            "population": 180000, "daytime_population": 195000,
            "median_hh_income": 84500, "median_age": 40.2, "employee_count": 68000,
        },
    }
 
    used = set()
    for i in range(3):
        data,name = build_excel_report(la_profile, {}, "100 N Main St", used_names = used)
        print(f"  run {i+1}: {name}")
    out = Path.home() / "Downloads" / "test_site_summary.xlsx"    
    out.write_bytes(data)
    print(f"\nWrote {out} ({len(data)} bytes)")
    print(f"Used names tracked: {used}")