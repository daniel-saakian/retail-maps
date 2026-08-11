import argparse
import sys
import time
from datetime import datetime, timezone
 
import majorretail as mr
from load_to_supabase import upsert_listing, mark_stale_inactive
from ca_anchors import anchors_by_state
 
def discover_and_scrape(label:str, lat: float, lng: float, radius_km:float, sb=None, max_age_days:float | None=None):
    state_fips, county_fips = mr.get_fips_from_coords(lat, lng)
    state = mr.FIPS_TO_STATE.get(
        state_fips.zfill(2) if state_fips and state_fips != "-" else "", "-"
    )
    print(f"  -> FIPS: state={state_fips} ({state}), county={county_fips}")
    time.sleep(1)
 
    print(f"  [2/5] Querying OpenStreetMap for stores within {radius_km}km...")
    store_elements = mr.run_overpass(mr.build_store_query(lat,lng,radius_km))
    print(f"   -> {len(store_elements)} raw elements returned")
 
    print("  [3/5] querying for mall/retail area names...")
    try:
        mall_elements = mr.run_overpass(mr.build_mall_query(lat,lng,radius_km))
        print(f"   -> {len(mall_elements)} mall/retail areas found")
    except RuntimeError as e:
        print(f"  [warn] Mall name lookup failed ({e}). Centers will show as 'Unnamed'.")
        mall_elements = []
 
    stores = mr.extract_stores(store_elements)
    n_anchors = sum(1 for s in stores if s.is_anchor_store)
    print(f"  Total shops identified: {len(stores)} ({n_anchors} are anchors)")
    if n_anchors == 0 or not stores:
        print(f"  [skip] {label}: no anchor stores found - OSM data may be sparse")
        return [], state
    
    print("  [4/5] Building plazas around each anchor and gathering tenants...")
    plazas = mr.build_plazas(stores, mr.plaza_radius_mi, mr.min_other_tenants)
    mr.attach_mall_names(plazas, mall_elements)
    plazas = mr.deduplicate_plaza_stores(plazas)
    plazas = mr.merge_same_name_plazas(plazas)
    mr.attach_plaza_radius(plazas, mr.plaza_radius_mi * 1609.34)
 
    print(f"  Checking Supabase for {len(plazas)} known plazas...")
    new_plazas, needs_scoring = mr.attach_existing_data(sb, plazas, max_age_days) if sb else (plazas, [])
    print(f"  -> {len(plazas) - len(new_plazas)} matched existing "
          f"(county + listings reused), {len(new_plazas)} need a fresh look")
    
    if needs_scoring:
        print(f"  Scoring {len(needs_scoring)} previously-unscored matched plaza(s)...")

    if new_plazas:
        print(f"  Looking up counties for {len(new_plazas)} new/stale plaza(s)...")
        mr.attach_counties(new_plazas)

        print(f"  [5/5] Searching brokerage sites for leasing broker contacts...")
        try:
            from scraper import scrape_listings
            scrape_listings(new_plazas, label, state)
        except Exception as e:
            print(f"  [warn] Scraping failed or warning: {e}")
    else:
        print(f"  [5/5] Nothing new to scrape - all plazas matched existing Supabase data")
    return plazas, state
 
def push_anchor_results(sb, plazas: list, label:str, lat: float, lng: float,
                        radius_km: float, state:str) -> tuple[int,int,int]:
    run = (sb.table("city_runs")
             .upsert({
                 "city": label, "display": label,
                 "lat": lat, "lng": lng, "radius_km": radius_km
             }, on_conflict = "city")
             .execute())
    run_id = run.data[0]["id"]
 
    new_plazas = 0
    existing_plazas = 0
    new_listings = 0
 
    for p in plazas:
        plaza_id, was_new = mr.save_one_plaza(sb, p, run_id, state)
        if was_new:
            new_plazas += 1
        else:
            existing_plazas += 1
        if not plaza_id:
            continue

        if getattr(p,"freshly_scraped", False):
            sb.table("plazas").update({
                "last_scraped_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", plaza_id).execute()
 
        touched = set()
        for record in getattr(p, "agents", []):
            is_new = upsert_listing(sb,plaza_id,record,touched)
            if is_new:
                new_listings += 1
        mark_stale_inactive(sb, plaza_id, touched)
    
    return new_plazas, existing_plazas, new_listings
 
def main():
    parser = argparse.ArgumentParser(description = "Statewide plaza discovery + broker scrape, anchor by anchor")
    parser.add_argument("--state", required=True, help = "Two-letter state code")
    parser.add_argument("--only", default=None,
                         help = "Comma-separated substrings to filter anchor labels (ex 'Fresno,Bakersfield')")
    parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to sleep between anchors")
    parser.add_argument("--rescrape-after-days", type=float, default=None,
                        help="Re-scrape a plaza's brokers even if it's already in supabase, default to never rescrape")
    args = parser.parse_args()
 
    state_code = args.state.strip().upper()
    anchors = anchors_by_state.get(state_code)
    if anchors is None:
        available = ", ".join(sorted(anchors_by_state))
        print(f"  No anchors defined for --state {state_code} in ca_anchors.py. "
              f"Add a \"{state_code}\": [...] entry to anchors_by_state first. "
              f"Currently defined: {available}")
        sys.exit(1)
    if args.only:
        wanted = [w.strip().lower() for w in args.only.split(",")]
        anchors = [a for a in anchors if any(w in a[0].lower() for w in wanted)]
        if not anchors:
            print(f"  No anchors matched --only {args.only!r}")
            sys.exit(1)
 
    sb = mr.get_supabase()
    if not sb:
        print("  Supabase not configured (SUPABASE_URL/SUPABASE_KEY) - aborting, nothing would be saved.")
        sys.exit(1)
 
    print(f"  {len(anchors)} anchor point(s) to run\n")
 
    totals = {"plazas_new": 0, "plazas_existing": 0, "listings_new": 0, "anchors_failed": 0}
 
    for i, (label, lat,lng, radius_km) in enumerate(anchors):
        print(f"\n{'='*70}")
        print(f"  [{i+1}/{len(anchors)}] {label}  ({lat}, {lng})  radius={radius_km}km")
        print(f"{'='*70}")
 
        try:
            plazas,state = discover_and_scrape(label, lat, lng, radius_km, sb=sb, max_age_days=args.rescrape_after_days)
        except Exception as e:
            print(f"  [error] {label} failed during discovery/scrape: {e}")
            totals["anchors_failed"] += 1
            continue
 
        if not plazas:
            continue
 
        try:
            new_p,existing_p,new_l = push_anchor_results(sb,plazas,label,lat,lng,radius_km,state)
            print(f"  [saved] {label}: {new_p} new plaza(s), {existing_p} already existed, "
                  f"{new_l} new listing(s)")
            totals["plazas_new"] += new_p
            totals["plazas_existing"] += existing_p
            totals["listings_new"] += new_l
        except Exception as e:
            print(f"  [error] {label}: failed to save to Supabase: {e}")
            totals["anchors_failed"] += 1
 
        if args.sleep:
            time.sleep(args.sleep)
 
    print(f"\n{'='*70}")
    print(f"  Done - {totals['plazas_new']} new plazas, {totals['plazas_existing']} already existing, "
          f"{totals['listings_new']} new listings, {totals['anchors_failed']} anchor(s) failed")
    print(f"{'='*70}")
 
if __name__ == "__main__":
    main()