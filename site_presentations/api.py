from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from site_presentations import registry
from site_presentations.export_xlsx import build_xlsx_from_luckysheet

router = APIRouter()

class BrandOption(BaseModel):
    code: str
    label: str

class SitePresentationRequest(BaseModel):
    brand: str
    address: str
    lat: float | None = None
    lon: float | None = None

class ExportRequest(BaseModel):
    filename: str = "site_summary.xlsx"
    sheets: list[dict]

from api import require_auth

@router.get("/api/site-presentations/brands", response_model=list[BrandOption])
def get_brands(user=Depends(require_auth)):
    return [BrandOption(code=b.code, label=b.label) for b in registry.list_brands()]

@router.post("/api/site-presentations/generate")
def generate_site_presentation(req: SitePresentationRequest, user=Depends(require_auth)):
    brand = req.brand.strip()
    address = req.address.strip()
    if not brand:
        raise HTTPException(400, "brand is required")
    if not address:
        raise HTTPException(400, "address is required")
    if not registry.get_brand(brand):
        raise HTTPException(404, f"unknown brand: '{brand}'")

    try:
        data, filename = registry.generate(
            brand, address, manual_lat=req.lat, manual_lon=req.lon
            )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Site presentation generation failed: {e}")

    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/api/site-presentations/export")
def export_edited_presentation(req:ExportRequest, user=Depends(require_auth)):
    if not req.sheets:
        raise HTTPException(400, "sheets is required")

    try:
        data = build_xlsx_from_luckysheet(req.sheets)
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}")

    filename = req.filename.strip() or "site_summary.xlsx"
    if not filename.lower().endswith(".xlsx"):
        filename += ".xlsx"

    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )