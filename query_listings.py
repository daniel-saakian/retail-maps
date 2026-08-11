import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set")
    return create_client(url,key)

def _with_plaza_fields(sb):
    return (
        sb.table("listings")
          .select("*, plazas!inner(name, city, address, state)")
    )

def _flatten(row: dict) -> dict:
    plaza = row.pop("plazas", {}) or {}
    row["plaza_name"] = plaza.get("name")
    row["plaza_city"] = plaza.get("city")
    row["plaza_address"] = plaza.get("address")
    row["plazas_state"] = plaza.get("state")
    return row

def listings_for_plaza(plaza_name: str, city:str, active_only:bool=True) -> list[dict]:
    sb = get_supabase()
    q = (_with_plaza_fields(sb)
         .eq("plazas.name", plaza_name)
         .eq("plazas.city", city))
    if active_only:
        q = q.eq("active", True)
    return [_flatten(r) for r in (q.execute().data or [])]

def listings_for_city(city:str, state:str | None=None, active_only: bool = True) -> list[dict]:
    sb = get_supabase()
    q = _with_plaza_fields(sb).eq("plazas.city",city)
    if state:
        q = q.eq("plazas.state", state)
    if active_only:
        q = q.eq("active", True)
    return [_flatten(r) for r in (q.execute().data or [])]

def listings_for_brokerage(brokerage:str, state:str | None=None, active_only: bool = True) -> list[dict]:
    sb = get_supabase()
    q = _with_plaza_fields(sb).eq("brokerage", brokerage)
    if state:
        q = q.eq("plazas.state", state)
    return [_flatten(r) for r in (q.execute().data or [])]

if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else "Roseville"
    for l in listings_for_city(city):
        print(f"  [{l['brokerage']}] {l['plaza_name']} - {l['agent_name']} - {l.get('phone') or l.get('email')}")