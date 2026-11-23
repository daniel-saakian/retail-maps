from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from api import require_auth, get_profile


_HB_DIR = Path(__file__).resolve().parent
for _p in (_HB_DIR, _HB_DIR.parent, _HB_DIR.parent.parent):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))
import hb_review_fields as F

router = APIRouter(prefix="/api/hb-review")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

def _hb_access(user=Depends(require_auth)):
    profile=get_profile(user.id)
    if profile and profile.get("role") == "sco":
        raise HTTPException(403, "This account can't open HB Protein Forms")
    return user

class PrefillRequest(BaseModel):
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None

class FormState(BaseModel):
    fields: dict[str, str] = {}
    tables: dict[str, list[dict[str, Any]]] = {}
    swot: dict[str, list[str]] = {}

class RenderRequest(FormState):
    filename: Optional[str] = None

@router.get("/schema")
def get_schema(user=Depends(_hb_access)):
    return F.schema()

@router.post("/prefill")
def prefill(req: PrefillRequest, user=Depends(_hb_access)):
    import hb_review_data as D
    import hb_review_listings as L

    address = req.address.strip()
    if not address:
        raise HTTPException(400, "Address is required")
    try:
        ctx = D.collect(address, req.lat, req.lon)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Prefill failed: {e}")

    fields, tables = D.prefill_from_context(ctx)
    try:
        listings = L.find_listings(ctx["geo"]["lat"], ctx["geo"]["lon"])
    except Exception as e:
        ctx["warnings"].append(f"Listings lookup failed: {e}")
        listings = []

    if listings and "tenant_roster" in fields:
        fields["tenant_roster"]["value"] = fields["tenant_roster"]["value"].replace(
            "Vacancy / pending departures / dark space: [verify on site and with leasing]",
            f"Vacancy: {len(listings)} space(s) currently listed at this center "
            f"({'; '.join(l['summary'] for l in listings[:4])}). Pending departures / dark space: [verify]",
        )

    ctx_out = {k: v for k, v in ctx.items() if k != "poi"}
    ctx_out["poi"] = {k: [{"name": p["name"], "distance_mi": p["distance_mi"]} for p in v]
                      for k, v in (ctx.get("poi") or {}).items()}
    return {"fields": fields, "tables": tables, "listings": listings,
            "context": ctx_out, "warnings": ctx["warnings"]}

@router.post("/render")
def render(req: RenderRequest, user=Depends(_hb_access)):
    import hb_review_docx as X
    try:
        data = X.render_docx(req.fields, req.tables, req.swot)
    except Exception as e:
        raise HTTPException(500, f"Could not build the word file: {e}")
    name = (req.filename or "").strip()
    if not name:
        center = re.sub(r"[^a-zA-Z0-9]+", "_", req.fields.get("center_name") or req.fields.get("street_suite") or "site").strip("_")
        name = f"HB_Site_Review_{center or 'site'}.docx"
    if not name.lower().endswith(".docx"):
        name += ".docx"
    return Response(content=data, media_type=DOCX_MIME, headers={"Content-Disposition": f'attachment; filename="{name}"'})