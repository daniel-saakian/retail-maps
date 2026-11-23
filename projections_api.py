import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any,Optional
 
import os
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
 
import cache
 
TABLE = "projection_saves"
AUDIT = "projection_audit"
 
# Add the next brand here later: same shape, its own service URL / key.
BRANDS = {
    "tgg": {
        "label": "The Great Greek",
        "url_env": "TGG_SERVICE_URL",
        "key_env": "TGG_SERVICE_KEY",
        "fields": [
            {"id": "format", "type": "select", "label": "Format",
             "options": ["in line", "end cap", "standalone"], "default": "in line"},
            {"id": "visibility", "type": "bool", "label": "Visible from main road", "default": True}
        ],
        "payload": lambda row, inp: {
            "address": row["address"], "format": inp["format"], 
            "visibility": 1 if inp["visibility"] else 0, "corporate": False,
        },
    },
    "sourdough": {
        "label": "Sourdough & Co.",
        "url_env": "SOURDOUGH_SERVICE_URL",
        "key_env": "SOURDOUGH_SERVICE_KEY",
        "fields": [
            {"id": "format", "type": "select", "label": "Format",
             "options": ["in line", "end cap", "standalone"], "default": "in line"},
            {"id": "mall", "type": "bool", "label": "Mall, mixed-use or college", "default": False},
        ],
        "payload": lambda row, inp: {"address": row["address"], "mall": bool(inp["mall"])},
    },
}

def default_inputs(brand: str) -> dict:
    return {f["id"]: f["default"] for f in BRANDS[brand]["fields"]}

def clean_inputs(brand: str, raw: Optional[dict]) -> dict:
    raw = raw or {}
    out = {}
    for f in BRANDS[brand]["fields"]:
        v = raw.get(f["id"], f["default"])
        if f["type"] == "select":
            v = str(v).strip().lower()
            if v not in f["options"]:
                raise HTTPException(422, f"{f['label']} must be one of {f['options']}")
        else:
            v = bool(v)
        out[f["id"]] = v
    return out

def row_inputs(row: dict) -> dict:
    inp = row.get("inputs")
    if inp:
        return inp
    return {"format": row.get("format") or "in line", "visibility": bool(row.get("visibility", 1))}
 
NEW_COMPUTES_PER_HOUR = 30      # per user
WAIT_FOR_MODEL_SECONDS = 15 * 60
STALE_RUNNING_MINUTES = 20
 
FRIENDLY_ERRORS = {
    "existing_store": "This address is an existing store, so it can't be projected.",
    "address_not_found": "Couldn't match that address. Check the street, city and state.",
    "unavailable": "The projection service isn't reachable right now. Try re-running in a few minutes.",
    "failed": "The projection service had a problem with this address. Try re-running.",
}
 
_pool = ThreadPoolExecutor(max_workers=2)
_rate_lock = threading.Lock()
_rate: dict[str, deque] = defaultdict(deque)
 
 
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
 
 
class MarkBody(BaseModel):
    key: str = Field(min_length=3, max_length=300)
    address: str = Field(min_length=5, max_length=300)
    name: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=10)
    source: str = Field(default="manual", pattern="^(digest|manual)$")
    brands: list[str] = Field(default_factory=list, max_length=10)
    inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
 
 
class RerunBody(BaseModel):
    inputs: Optional[dict[str, Any]] = None
 
 
def _public(row: dict) -> dict:
    keep = (
        "id", "brand", "address_key", "address", "name", "city", "state", "source",
        "status", "error", "result", "saved_by_email", "created_at", "updated_at"
    )
    out = {k: row.get(k) for k in keep}
    out["inputs"] = row_inputs(row)
    return out
 
 
def make_router(require_auth, get_profile, require_full_access) -> APIRouter:
    router = APIRouter()
 
    def sb():
        client = cache.get_client()
        if not client:
            raise HTTPException(500, "Supabase not configured correctly")
        return client
 
    def allowed_brands(user) -> list[str]:
        profile = get_profile(user.id) or {}
        if profile.get("role") == "staff":
            return list(BRANDS)
        granted = profile.get("projection_brands") or []
        return [b for b in granted if b in BRANDS]
 
    def need_brand(user, brand: str) -> None:
        if brand not in BRANDS:
            raise HTTPException(404, "Unknown brand")
        if brand not in allowed_brands(user):
            raise HTTPException(403, "You don't have access to this brand's projections.")
 
    def audit(user, brand: Optional[str], action: str, address: Optional[str] = None) -> None:
        try:
            sb().table(AUDIT).insert({
                "user_id": user.id, "user_email": getattr(user, "email", None),
                "brand": brand, "action": action, "address": address,
            }).execute()
        except Exception as e:
            print(f"[projections] audit failed: {e}")
 
    def charge_rate_limit(user_id: str, n: int) -> None:
        cutoff = time.time() - 3600
        with _rate_lock:
            q = _rate[user_id]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) + n > NEW_COMPUTES_PER_HOUR:
                raise HTTPException(429, "Too many projections requested in the last hour. Try again later.")
            q.extend([time.time()] * n)
 
 
    def set_row(row_id: str, **fields) -> None:
        fields["updated_at"] = _now()
        sb().table(TABLE).update(fields).eq("id", row_id).execute()
 
    def compute(row_id: str) -> None:
        try:
            rows = sb().table(TABLE).select("*").eq("id", row_id).limit(1).execute().data
            if not rows:
                return
            row = rows[0]
            cfg = BRANDS[row["brand"]]
            base = (os.environ.get(cfg["url_env"]) or "").rstrip("/")
            key = os.environ.get(cfg["key_env"]) or ""
            if not base or not key:
                set_row(row_id, status="error", error=FRIENDLY_ERRORS["unavailable"])
                return
            set_row(row_id, status="running", error=None)
            headers = {"X-Service-Key": key}
 
            deadline = time.time() + WAIT_FOR_MODEL_SECONDS
            while True:
                try:
                    h = requests.get(f"{base}/health", timeout=10).json()
                    if h.get("ready"):
                        break
                    if h.get("error"):
                        set_row(row_id, status="error", error=FRIENDLY_ERRORS["unavailable"])
                        return
                except requests.RequestException:
                    pass
                if time.time() > deadline:
                    set_row(row_id, status="error", error=FRIENDLY_ERRORS["unavailable"])
                    return
                time.sleep(5)
 
            try:
                r = requests.post(
                    f"{base}/predict", headers=headers, timeout=240,
                    json=cfg["payload"](row, row_inputs(row)),
                )
            except requests.RequestException:
                set_row(row_id, status="error", error=FRIENDLY_ERRORS["unavailable"])
                return
 
            if r.status_code == 200:
                set_row(row_id, status="done", error=None, result=r.json())
            elif r.status_code == 409:
                set_row(row_id, status="error", error=FRIENDLY_ERRORS["existing_store"], result=None)
            elif r.status_code == 422:
                set_row(row_id, status="error", error=FRIENDLY_ERRORS["address_not_found"], result=None)
            else:
                set_row(row_id, status="error", error=FRIENDLY_ERRORS["failed"], result=None)
        except Exception as e:  # noqa: BLE001
            print(f"[projections] compute failed for {row_id}: {e}")
            try:
                set_row(row_id, status="error", error=FRIENDLY_ERRORS["failed"])
            except Exception:  # noqa: BLE001
                pass
 
    # -- routes ------------------------------------------------------------
 
    @router.get("/api/projections/access")
    def access(user=Depends(require_full_access)):
        return {"brands": [{"id": b, "label": BRANDS[b]["label"], "fields": BRANDS[b]["fields"]}
                           for b in allowed_brands(user)]}
 
    @router.get("/api/projections/marks")
    def marks(user=Depends(require_full_access)):
        """address_key -> brands it is saved under. Light, for the digest checkboxes."""
        brands = allowed_brands(user)
        if not brands:
            return {"marks": {}}
        rows = (sb().table(TABLE).select("address_key,brand").in_("brand", brands).limit(5000).execute().data) or []
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(r["address_key"], []).append(r["brand"])
        return {"marks": out}
 
    @router.put("/api/projections/mark")
    def put_mark(body: MarkBody, user=Depends(require_full_access)):
        """Set which brands this address is saved under. Anything not listed is removed."""
        mine = allowed_brands(user)
        wanted = [b for b in dict.fromkeys(body.brands)]
        for b in wanted:
            need_brand(user, b)
        if not mine:
            raise HTTPException(403, "You don't have access to projections.")
 
        existing = (sb().table(TABLE).select("*").eq("address_key", body.key).in_("brand", mine).execute().data) or []
        by_brand = {r["brand"]: r for r in existing}
 
        for b, row in by_brand.items():
            if b not in wanted:
                sb().table(TABLE).delete().eq("id", row["id"]).execute()
                audit(user, b, "remove", row["address"])
 
        to_run: list[str] = []
        new_brands = [b for b in wanted if b not in by_brand]
        if new_brands:
            charge_rate_limit(user.id, len(new_brands))
        for b in new_brands:
            inp = clean_inputs(b, body.inputs.get(b))
            ins = sb().table(TABLE).insert({
                "brand": b, "address_key": body.key, "address": body.address.strip(),
                "name": body.name, "city": body.city, "state": body.state, "source": body.source,
                "inputs": inp, "status": "pending", "saved_by": user.id,
                "saved_by_email": getattr(user, "email", None)
            }).execute().data
            audit(user, b, "save", body.address)
            if ins:
                to_run.append(ins[0]["id"])
        for rid in to_run:
            _pool.submit(compute, rid)
 
        rows = (sb().table(TABLE).select("*").eq("address_key", body.key).in_("brand", mine).execute().data) or []
        return {"key": body.key, "brands": [r["brand"] for r in rows], "saves": [_public(r) for r in rows]}
 
    @router.get("/api/projections")
    def list_saves(brand: str = Query(...), user=Depends(require_full_access)):
        need_brand(user, brand)
        rows = (sb().table(TABLE).select("*").eq("brand", brand)
                .order("created_at", desc=True).limit(500).execute().data) or []
        stale = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUNNING_MINUTES)
        for r in rows:
            if r["status"] in ("pending", "running"):
                try:
                    if datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) < stale:
                        set_row(r["id"], status="error", error=FRIENDLY_ERRORS["failed"])
                        r["status"], r["error"] = "error", FRIENDLY_ERRORS["failed"]
                except Exception:
                    pass
        audit(user, brand, "view_list")
        return {"brand": brand, "label": BRANDS[brand]["label"], "fields": BRANDS[brand]["fields"],
                "saves": [_public(r) for r in rows]}
 
    @router.post("/api/projections/{save_id}/rerun")
    def rerun(save_id: str, body: RerunBody, user=Depends(require_full_access)):
        rows = sb().table(TABLE).select("*").eq("id", save_id).limit(1).execute().data
        if not rows:
            raise HTTPException(404, "Not found")
        row = rows[0]
        need_brand(user, row["brand"])
        if row["status"] in ("pending", "running"):
            return _public(row)
        fields: dict = {"status": "pending", "error": None}
        if body.inputs is not None:
            fields["inputs"] = clean_inputs(row["brand"], {**row_inputs(row), **body.inputs})
        charge_rate_limit(user.id, 1)
        set_row(save_id, **fields)
        audit(user, row["brand"], "rerun", row["address"])
        _pool.submit(compute, save_id)
        row.update(fields)
        return _public(row)
 
    @router.delete("/api/projections/{save_id}")
    def remove(save_id: str, user=Depends(require_full_access)):
        rows = sb().table(TABLE).select("*").eq("id", save_id).limit(1).execute().data
        if not rows:
            return {"ok": True}
        need_brand(user, rows[0]["brand"])
        sb().table(TABLE).delete().eq("id", save_id).execute()
        audit(user, rows[0]["brand"], "remove", rows[0]["address"])
        return {"ok": True}
 
    return router