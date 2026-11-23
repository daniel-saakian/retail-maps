import argparse
import base64
import json
import os
import sys
 
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
 
OK, WARN, FAIL = "  OK  ", " WARN ", " FAIL "
problems = 0
 
 
def line(status: str, msg: str) -> None:
    global problems
    if status == FAIL:
        problems += 1
    print(f"[{status}] {msg}")
 
 
def key_role(key: str) -> str:
    if key.startswith("sb_secret_"):
        return "service_role"
    if key.startswith("sb_publishable_"):
        return "anon"
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role", "unknown")
    except Exception:
        return "unknown"
 
 
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true", help="Skip the save/search/delete test")
    args = ap.parse_args()
 
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not url or not key:
        line(FAIL, "SUPABASE_URL / SUPABASE_KEY not found. Run this from the Plazas folder (where .env is).")
        sys.exit(1)
    line(OK, f"Supabase project: {url}")
 
    role = key_role(key)
    if role == "service_role":
        line(OK, "SUPABASE_KEY is the service-role (secret) key -- scrapers can write")
    elif role == "anon":
        line(FAIL, "SUPABASE_KEY is the public anon key. The new tables only accept the service-role key. "
                   "Use the secret key from Supabase > Project Settings > API Keys.")
    else:
        line(WARN, "Couldn't tell which kind of key SUPABASE_KEY is; the tests below will show if it works.")
 
    from supabase import create_client
    sb = create_client(url, key)
 
    for table, col in (("brokerages", "id"), ("properties", "id"), ("spaces", "id"),
                       ("brokers", "id"), ("space_brokers", "space_id")):
        try:
            sb.table(table).select(col).limit(1).execute()
            line(OK, f"table {table}")
        except Exception as e:
            msg = str(e)
            hint = ("the key doesn't have access -- see the key check above" if "permission denied" in msg
                    else "run property_search_schema.sql in the SQL editor")
            line(FAIL, f"table {table}: {hint}")
 
    try:
        sb.rpc("search_spaces", {"p_city": "__setup_check__"}).execute()
        line(OK, "search function search_spaces")
    except Exception as e:
        msg = str(e)
        hint = ("the key doesn't have access -- see the key check above" if "permission denied" in msg
                else "run property_search_schema.sql in the SQL editor")
        line(FAIL, f"search function search_spaces: {hint}")
 
    try:
        active = sb.table("spaces").select("id", count="exact").eq("active", True).limit(1).execute().count
        props = sb.table("properties").select("id", count="exact").limit(1).execute().count
        line(OK, f"currently {active or 0:,} active spaces in {props or 0:,} properties")
    except Exception:
        pass
 
    if not args.no_write and problems == 0:
        try:
            from listing_record import BrokerContact, SpaceRecord, save_records
        except ImportError:
            line(FAIL, "listing_record.py not found in this folder -- copy it next to this script")
            sys.exit(1)
        src = "setup-check"
        rec = SpaceRecord(source=src, source_listing_id="setup-check-1", brokerage="Setup Check (test)",
                          address="1 Setup Check Way", city="Setupville", state="NC", zip="00000",
                          lat=35.7796, lng=-78.6382, sf_text="1,500 SF", rate_text="$30/SF/YR NNN",
                          description="Endcap test record", brokers=[BrokerContact("Test Broker", "test@example.com")])
        try:
            res = save_records(sb, src, [rec])
            found = sb.rpc("search_spaces", {"p_lat": 35.7796, "p_lng": -78.6382, "p_radius_m": 100}).execute().data
            hit = [r for r in found if r["address"] == "1 Setup Check Way"]
            if res.get("new") == 1 and hit and hit[0]["sf_min"] == 1500 and hit[0]["brokers"]:
                line(OK, "saved a test listing, found it within 100 m by map search, broker attached")
            else:
                line(FAIL, f"save/search test didn't round-trip: saved={res}, found={len(hit)}")
        except Exception as e:
            line(FAIL, f"save test failed: {str(e)[:200]}")
        finally:
            # clean up everything the test created
            try:
                sids = [r["id"] for r in sb.table("spaces").select("id").eq("source", src).execute().data or []]
                if sids:
                    sb.table("space_brokers").delete().in_("space_id", sids).execute()
                    sb.table("spaces").delete().in_("id", sids).execute()
                sb.table("properties").delete().eq("address", "1 Setup Check Way").execute()
                firm = sb.table("brokerages").select("id").eq("name", "Setup Check (test)").execute().data
                if firm:
                    sb.table("brokers").delete().eq("brokerage_id", firm[0]["id"]).execute()
                    sb.table("brokerages").delete().eq("id", firm[0]["id"]).execute()
                line(OK, "test listing removed")
            except Exception as e:
                line(WARN, f"couldn't fully remove the test listing: {str(e)[:160]}")
 
    print("\nAll set." if problems == 0 else f"\n{problems} problem(s) to fix above.")
    sys.exit(1 if problems else 0)
 
 
if __name__ == "__main__":
    main()