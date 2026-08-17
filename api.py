import contextlib
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
 
from fastapi import Depends, FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
 
import cache
import majorretail as mr
 
_bearer = HTTPBearer(auto_error=False)
 
def require_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None:
        raise HTTPException(401, "Missing bearer token")
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Auth backend not configured")
    try:
        resp = sb.auth.get_user(creds.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired session")
    if not resp or not resp.user:
        raise HTTPException(401, "Invalid or expired session")
    return resp.user

def get_profile(user_id: str) -> dict | None:
    sb = cache.get_client()
    if not sb:
        return None
    rows = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute().data
    return rows[0] if rows else None

def require_staff(user=Depends(require_auth)):
    profile = get_profile(user.id)
    if not profile or profile.get("role") != "staff":
        raise HTTPException(403, "Staff permission required")
    return user
 
@dataclass
class Job:
    id: str
    city: str
    search_km: float
    rescrape_after_days: Optional[float]
    status: str = "queued"
    log: list = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event)
 
JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()
 
class _TeeWriter:
    def __init__(self, job: Job):
        self.job = job
        self._buf = ""
    
    def write(self, s:str):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n",1)
            if line.strip():
                with JOBS_LOCK:
                    self.job.log.append(line)
 
    def flush(self):
        pass
 
def _run_job(job_id: str):
    job = JOBS[job_id]
    with JOBS_LOCK:
        job.status = "running"
    writer = _TeeWriter(job)
    try:
        with contextlib.redirect_stdout(writer):
            result = mr.run_city_search(
                job.city,
                search_km = job.search_km,
                rescrape_after_days = job.rescrape_after_days,
                cancel_check = job.cancel_event.is_set,
            )
        with JOBS_LOCK:
            if job.cancel_event.is_set():
                job.status = "cancelled"
            else:
                job.result = result
                job.status = "done" if result.get("ok") else "empty"
        if result.get("ok") and result.get("excel_path") and result.get("run_id") and not job.cancel_event.is_set():
            cache.save_excel_export(result["run_id"], result["excel_path"])
    except Exception as e:
        with JOBS_LOCK:
            if job.cancel_event.is_set():
                job.status = "cancelled"
            else:
                job.status = "error"
                job.error = str(e)
                job.log.append(f"[error] {e}")
 
class SearchRequest(BaseModel):
    city: str
    search_km: float = mr.search_radius_km
    rescrape_after_days: Optional[float] = None
 
class PlazaRow(BaseModel):
    name: str
    state: str
    county: str
    city: str
    address: str
    num_anchors: int
    anchor_names: str
    num_tenants: int
    tenant_names: str
    score: float | str
    brokerages: str
    brokers: str
    broker_contacts: str
    broker_urls: str
 
class JobSummary(BaseModel):
    id: str
    city: str
    status: str
    created_at: float
    plaza_count: Optional[int] = None
 
class JobDetail(BaseModel):
    id: str
    city: str
    status: str
    created_at: float
    log: list[str]
    error: Optional[str] = None
    reason: Optional[str] = None
    display: Optional[str] = None
    plazas: Optional[list[PlazaRow]] = None
    map_available: bool = False
    excel_available: bool = False
    map_url: Optional[str] = None
 
class HistoryRun(BaseModel):
    id: str
    city: str
    display: str
    ran_at: str
    radius_km: float
    map_url: Optional[str] = None
    plaza_count: int = 0
    excel_available: bool = False
 
class HistoryDetail(HistoryRun):
    plazas: list[PlazaRow] = []

class UserProfile(BaseModel):
    id:str
    email:str
    role:str
    created_at:str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None

class InviteRequest(BaseModel):
    email:str
    role:str = "member"

class RoleUpdateRequest(BaseModel):
    role:str

class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
 
def _dict_plazas_to_rows(plazas: list[dict]) -> list[PlazaRow]:
    sorted_plazas = sorted(
        plazas,
        key=lambda p: (
            (p.get("county") or "zzz").lower(),
            (p.get("city") or "zzz").lower(),
        )
    )
    return [
        PlazaRow(
            name=p.get("name") or "-",
            state=p.get("state") or "-",
            county=p.get("county") or "-",
            city=p.get("city") or "-",
            address=p.get("address") or "-",
            num_anchors=p.get("num_anchors") or 0,
            anchor_names=p.get("anchor_names") or "-",
            num_tenants=p.get("num_tenants") or 0,
            tenant_names=p.get("tenant_names") or "-",
            score=round(p["aggregate_score"], 1) if p.get("aggregate_score") is not None else "-",
            brokerages=p.get("brokerages") or "-",
            brokers=p.get("brokers") or "-",
            broker_contacts=p.get("broker_contacts") or "-",
            broker_urls=p.get("broker_urls") or "-",
        )
        for p in sorted_plazas
    ]
 
def _plazas_to_rows(plazas, state: str) -> list[PlazaRow]:
    sorted_plazas = sorted(
        plazas,
        key=lambda p: (
            p.county.lower() if p.county and p.county != "-" else "zzz",
            p.display_city.lower() if p.display_city and p.display_city != "-" else "zzz",
        )
    )
    return [
        PlazaRow(
            name=p.label, 
            state=state, 
            county=p.county, 
            city=p.display_city,
            address=p.display_address, 
            num_anchors=len(p.anchors), anchor_names=p.anchor_names,
            num_tenants=len(p.tenants), tenant_names=p.tenant_names,
            score=round(p.scores.get("aggregate_score",0),1) if p.scores else "-",
            brokerages=p.brokerage_names, 
            brokers=p.broker_names,
            broker_contacts=p.broker_contacts, 
            broker_urls=p.broker_urls,
        )
        for p in sorted_plazas
    ]
 
def _job_to_detail(job:Job) -> JobDetail:
    detail = JobDetail(
        id=job.id, city=job.city, status=job.status, created_at=job.created_at,
        log=list(job.log), error=job.error,
    )
    if job.status == "empty" and job.result:
        detail.reason = job.result.get("reason")
    if job.status == "done" and job.result:
        r = job.result
        detail.display = r["display"]
        detail.plazas = _plazas_to_rows(r["plazas"],r["state"])
        detail.map_available = bool(r["map_path"] and os.path.exists(r["map_path"]))
        detail.excel_available = bool(r["excel_path"] and os.path.exists(r["excel_path"]))
        detail.map_url = r["map_url"]
    return detail
 
app = FastAPI(title="Plaza Finder API", dependencies=[Depends(require_auth)])

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()]
print(f"[cors] allowed origins: {_allowed_origins}")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
@app.get("/api/defaults")
def get_defaults():
    return {"search_km": mr.search_radius_km}
 
@app.post("/api/searches", response_model=JobSummary)
def create_search(req: SearchRequest):
    if not req.city.strip():
        raise HTTPException(400, "city is required")
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, city=req.city.strip(), search_km=req.search_km,
                rescrape_after_days=req.rescrape_after_days)
    with JOBS_LOCK:
        JOBS[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return JobSummary(id=job.id, city=job.city, status=job.status, created_at=job.created_at)
 
@app.get("/api/searches", response_model=list[JobSummary])
def list_searches():
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)
        return [
            JobSummary(
                id=j.id, city=j.city, status=j.status, created_at=j.created_at,
                plaza_count=len(j.result["plazas"]) if j.result and j.result.get("plazas") is not None else None
            )
            for j in jobs
        ]
    
@app.get("/api/searches/{job_id}", response_model=JobDetail)
def get_search(job_id:str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return _job_to_detail(job)
 
@app.delete("/api/searches/{job_id}")
def delete_search(job_id: str):
    with JOBS_LOCK:
        if job_id not in JOBS:
            raise HTTPException(404, "job not found")
        del JOBS[job_id]
    return {"ok": True}

@app.post("/api/searches/{job_id}/cancel")
def cancel_search(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(400, f"cannot cancel a job that's already done {job.status}")
    job.cancel_event.set()
    with JOBS_LOCK:
        job.lock.append("[cancelled] Stopping at the next checkpoint...")
    return {"ok": True}

@app.get("/api/searches/{job_id}/map", response_class=HTMLResponse)
def get_map(job_id:str):
    job = JOBS.get(job_id)
    if not job or not job.result or not job.result.get("map_path"):
        raise HTTPException(404, "map not available")
    path = job.result["map_path"]
    if not os.path.exists(path):
        raise HTTPException(404, "map file missing on disk")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())
 
@app.get("/api/searches/{job_id}/excel")
def get_excel(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.result or not job.result.get("excel_path"):
        raise HTTPException(404, "excel not available")
    path = job.result["excel_path"]
    if not os.path.exists(path):
        raise HTTPException(404, "excel file missing on disk")
    return FileResponse(
        path,
        media_type="application/vnd.opencmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(path),
    )
 
@app.get("/api/history", response_model=list[HistoryRun])
def list_history():
    runs = cache.list_history_runs()
    return [
        HistoryRun(
            id=r["id"], city=r["city"], display=r["display"], ran_at=str(r.get("ran_at")),
            radius_km=r.get("radius_km") or 0, map_url=r.get("map_url"),
            plaza_count=r.get("plaza_count", 0), excel_available=r.get("excel_available", False),
        )
        for r in runs
    ]
 
@app.get("/api/history/{run_id}", response_model=HistoryDetail)
def get_history(run_id: str):
    run = cache.get_history_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return HistoryDetail(
        id=run["id"], city=run["city"], display=run["display"], ran_at=str(run.get("ran_at")),
        radius_km=run.get("radius_km") or 0, map_url=run.get("map_url"),
        plaza_count=run.get("plaza_count", 0), excel_available=run.get("excel_available", False),
        plazas=_dict_plazas_to_rows(run.get("plazas", [])),
    )
 
@app.get("/api/history/{run_id}/excel")
def get_history_excel(run_id: str):
    run = cache.get_history_run(run_id)
    if not run or not run.get("excel_path"):
        raise HTTPException(404, "excel not available for this run")
    data = cache.download_excel_export(run["excel_path"])
    if not data:
        raise HTTPException(404, "excel file missing in storage")
    filename = os.path.basename(run["excel_path"])
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.get("/api/me", response_model=UserProfile)
def get_me(user = Depends(require_auth)):
    profile = get_profile(user.id)
    if not profile:
        raise HTTPException(404, "Profile Not Found")
    return UserProfile(**profile)

@app.patch("/api/me", response_model = UserProfile)
def update_me(req: ProfileUpdateRequest, user = Depends(require_auth)):
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured correctly")
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    if payload:
        sb.table("profiles").update(payload).eq("id", user.id).execute()
    profile = get_profile(user.id)
    if not profile:
        raise HTTPException(404,"Profile not found")
    return UserProfile(**profile)

@app.post("/api/me/avatar", response_model=UserProfile)
async def upload_my_avatar(file:UploadFile=File(...), user=Depends(require_auth)):
    ext = (file.filename or "").rsplit(".",1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        raise HTTPException(400, "Unsupported image type")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 5 MB)")
    avatar_url = cache.upload_avatar(user.id,data,file.content_type or "image/file",ext)
    if not avatar_url:
        raise HTTPException(500, "Avatar upload failed")
    sb = cache.get_client()
    if sb:
        sb.table("profiles").update({"avatar_url": avatar_url}).eq("id", user.id).execute()
    profile = get_profile(user.id)
    if not profile:
        raise HTTPException(404, "profile not found")
    return UserProfile(**profile)

@app.get("/api/users", response_model=list[UserProfile])
def list_users(user = Depends(require_staff)):
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")
    rows = sb.table("profiles").select("*").order("created_at").execute().data or []
    return [UserProfile(**r) for r in rows]

@app.post("/api/users/invite", response_model=UserProfile)
def invite_user(req: InviteRequest, user = Depends(require_staff)):
    if req.role not in ("staff", "member"):
        raise HTTPException(400, "Role must be 'staff' or 'member'")
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")
    try:
        frontend_url = os.getenv("FRONTEND_URL", "retail-maps.vercel.app")
        result = sb.auth.admin.invite_user_by_email(
            req.email,
            {"redirect_to": f"{frontend_url}/onboarding"}
        )
    except Exception as e:
        raise HTTPException(400, f"Invite failed: {e}")
    invited_id = result.user.id
    sb.table("profiles").upsert({
        "id": invited_id, "email": req.email, "role": req.role,
    }).execute()
    profile = get_profile(invited_id)
    return UserProfile(**profile)

@app.patch("/api/users/{user_id}/role", response_model=UserProfile)
def update_user_role(user_id:str, req: RoleUpdateRequest, user = Depends(require_staff)):
    if req.role not in ("staff", "member"):
        raise HTTPException(400, "role must be in 'staff' or 'member'")
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")
    sb.table("profiles").update({"role": req.role}).eq("id", user_id).execute()
    profile = get_profile(user_id)
    if not profile:
        raise HTTPException(404, "User not Found")
    return UserProfile(**profile)

@app.delete("/api/users/me")
def delete_own_account(user = Depends(require_auth)):
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")
    try:
        sb.auth.admin.delete_user(user.id)
    except Exception as e:
        raise HTTPException(400, f"Delete failed: {e}")
    return {"ok": True}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, user = Depends(require_staff)):
    if user_id == user.id:
        raise HTTPException(400, "Use DELETE /api/users/me to delete your own account")
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")
    try:
        sb.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(400, f"Delete failed: {e}")
    return {"ok": True}