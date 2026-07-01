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
    

