import os
from supabase import create_client
from datetime import datetime, timedelta, timezone
 
cache_ttl_days = 30
 
def get_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url,key)
 
def get_cached_run(lat:float, lng:float, radius_km: float):
    sb = get_client()
    if not sb:
        return None, None
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days = cache_ttl_days)).isoformat()
        import math
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
 
        runs = (sb.table("city_runs")
                  .select("*")
                  .gte("lat",lat-lat_delta)
                  .lte("lat",lat+lat_delta)
                  .gte("lng",lng-lng_delta)
                  .lte("lng",lng+lng_delta)
                  .gte("ran_at",cutoff)
                  .order("ran_at",desc=True)
                  .limit(1)
                  .execute())
        if not runs.data:
            return None, None
        
        run = runs.data[0]
        plazas = (sb.table("plazas")
                    .select("*")
                    .eq("city_run_id",run["id"])
                    .execute())
        return run, plazas.data
    except Exception as e:
        print(f"  [cache] read error: {e}")
        return None, None
 
def save_run(display: str, lat: float, lng: float, radius_km: float, map_url: str, plazas: list, state: str):
    sb = get_client()
    if not sb:
        return
    try:
        run = (sb.table("city_runs")
                 .insert({
                     "city": display,
                     "display": display,
                     "lat": lat,
                     "lng": lng,
                     "radius_km": radius_km,
                     "map_url": map_url,
                 })
                 .execute())
        run_id = run.data[0]["id"]
 
        rows = [
            {
                "city_run_id": run_id,
                "name": p["name"],
                "state": state,
                "county": p["county"],
                "city": p["city"],
                "address": p["address"],
                "num_anchors": p["num_anchors"],
                "anchor_names": p["anchor_names"],
                "num_tenants": p["num_tenants"],
                "tenant_names": p["tenant_names"],
            } for p in plazas
        ]
 
        if rows:
            sb.table("plazas").insert(rows).execute()
        print(f"  [cache] saved {len(rows)} plazas for {display}")
    except Exception as e:
        print(f"  [cache] write error: {e}")
 
def get_cached_county(lat: float, lng: float):
    sb = get_client()
    if not sb:
        return None
    try:
        lat_key = round(lat,1)
        lng_key = round(lng,1)
        result = (sb.table("county_cache")
                     .select("county")
                     .eq("lat_key", lat_key)
                     .eq("lng_key", lng_key)
                     .limit(1)
                     .execute())
        if result.data:
            return result.data[0]["county"]
        return None
    except Exception as e:
        print(f"  [cache] county read error: {e}")
        return None
 
def save_county(lat: float, lng: float, county: str):
    sb = get_client()
    if not sb:
        return
    try:
        lat_key = round(lat,1)
        lng_key = round(lng,1)
        sb.table("county_cache").upsert({
            "lat_key": lat_key,
            "lng_key": lng_key,
            "county": county,
        }, on_conflict = "lat_key,lng_key").execute()
    except Exception as e:
        print(f"  [cache] county write error: {e}")
 
EXCEL_BUCKET = "run-exports"

AVATAR_BUCKET = "avatars"

def upload_avatar(user_id: str, file_bytes: bytes, content_type: str, ext:str) -> str | None:
    sb = get_client()
    if not sb:
        return None
    try:
        storage_path = f"{user_id}/avatar.{ext}"
        sb.storage.from_(AVATAR_BUCKET).upload(
            storage_path,
            file_bytes,
            {"content-type": content_type, "upsert": "true"},
        )
        return sb.storage.from_(AVATAR_BUCKET).get_public_url(storage_path)
    except Exception as e:
        print(f"  [cache] avatar upload error: {e}")
        return None
 
 
def list_history_runs() -> list[dict]:
    sb = get_client()
    if not sb:
        return []
    try:
        runs = (sb.table("city_runs")
                  .select("*")
                  .order("ran_at", desc=True)
                  .execute()).data or []
        for run in runs:
            count = (sb.table("run_plazas")
                        .select("plaza_id", count="exact")
                        .eq("city_run_id", run["id"])
                        .execute())
            run["plaza_count"] = count.count or 0
            run["excel_available"] = bool(run.get("excel_path"))
        return runs
    except Exception as e:
        print(f"  [cache] history list error: {e}")
        return []
 
 
def get_history_run(run_id: str) -> dict | None:
    sb = get_client()
    if not sb:
        return None
    try:
        rows = (sb.table("city_runs").select("*").eq("id", run_id).limit(1).execute()).data
        if not rows:
            return None
        run = rows[0]
        run["excel_available"] = bool(run.get("excel_path"))
 
        membership = (sb.table("run_plazas")
                        .select("plaza_id")
                        .eq("city_run_id", run_id)
                        .execute()).data or []
        plaza_ids = [m["plaza_id"] for m in membership]
        plazas = (sb.table("plazas").select("*").in_("id", plaza_ids).execute()).data if plaza_ids else []
 
        listings_by_plaza: dict = {}
        if plaza_ids:
            listing_rows = (sb.table("listings")
                               .select("plaza_id, brokerage, agent_name, phone, email, listing_url")
                               .in_("plaza_id", plaza_ids)
                               .eq("active", True)
                               .execute()).data or []
            for lr in listing_rows:
                listings_by_plaza.setdefault(lr["plaza_id"], []).append(lr)
 
        def _joined(values: list[str | None]) -> str:
            seen, out = set(), []
            for v in values:
                if v and v not in seen:
                    seen.add(v)
                    out.append(v)
            return "; ".join(out) if out else "-"
 
        for p in plazas:
            agents = listings_by_plaza.get(p.get("id"), [])
            p["brokerages"] = _joined([a.get("brokerage") for a in agents])
            p["brokers"] = _joined([a.get("agent_name") for a in agents])
            p["broker_contacts"] = _joined([a.get("phone") or a.get("email") for a in agents])
            p["broker_urls"] = _joined([a.get("listing_url") for a in agents])
 
        run["plazas"] = plazas
        run["plaza_count"] = len(plazas)
        return run
    except Exception as e:
        print(f"  [cache] history detail error: {e}")
        return None
 
 
def save_excel_export(run_id: str, local_path: str) -> str | None:
    sb = get_client()
    if not sb or not os.path.exists(local_path):
        return None
    try:
        storage_path = f"{run_id}/{os.path.basename(local_path)}"
        with open(local_path, "rb") as f:
            sb.storage.from_(EXCEL_BUCKET).upload(
                storage_path,
                f.read(),
                {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 "upsert": "true"},
            )
        sb.table("city_runs").update({"excel_path": storage_path}).eq("id", run_id).execute()
        return storage_path
    except Exception as e:
        print(f"  [cache] excel upload error: {e}")
        return None
 
 
def download_excel_export(storage_path: str) -> bytes | None:
    sb = get_client()
    if not sb:
        return None
    try:
        return sb.storage.from_(EXCEL_BUCKET).download(storage_path)
    except Exception as e:
        print(f"  [cache] excel download error: {e}")
        return None