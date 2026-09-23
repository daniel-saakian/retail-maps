import time
import sys
from pathlib import Path
 
_this_dir = Path(__file__).resolve().parent
for _candidate in (_this_dir, _this_dir.parent, _this_dir.parent.parent):
    if (_candidate / "majorretail.py").exists():
        sys.path.append(str(_candidate))
        break
else:
    print(f"[warning] majorretail.py not found in {_this_dir}, {_this_dir.parent}, "
          f"or {_this_dir.parent.parent} - the import below will likely fail.")
    
from majorretail import (
    get_fips_from_coords, build_store_query, build_mall_query, run_overpass,
    extract_stores, build_plazas, attach_mall_names, deduplicate_plaza_stores,
    merge_same_name_plazas, attach_plaza_radius, attach_counties, score_plazas,
    get_supabase, attach_existing_data, haversine_m,
    plaza_radius_mi, min_other_tenants,
)
 
default_search_km = 0.75
 
def find_single_plaza(lat,lng,search_km=default_search_km, radius_mi=None, use_cache=True):
    radius_mi = radius_mi if radius_mi is not None else plaza_radius_mi
 
    print(f"Searching {search_km}km around ({lat:.5f}, {lng:.5f})")
    state_fips, county_fips = get_fips_from_coords(lat, lng)
 
    # Unlike the mall-name lookup below, a failure here used to propagate
    # all the way up as an unhandled 500 -- a total Overpass outage (all 4
    # mirrors down/rate-limited at once, which does happen) took down the
    # whole site-presentations report instead of just leaving the
    # co-tenants section blank, the way a missing mall name already does.
    try:
        store_elements = run_overpass(build_store_query(lat, lng, search_km))
    except RuntimeError as e:
        print(f"  [warn] Store lookup failed ({e}). Treating this as no plaza found nearby.")
        return None
 
    try:
        mall_elements = run_overpass(build_mall_query(lat, lng, search_km))
    except RuntimeError as e:
        print(f"  [warn] Mall name lookup failed ({e}). Plaza may show as 'Unnamed'.")
        mall_elements = []
 
    stores = extract_stores(store_elements)
    n_anchors = sum(1 for s in stores if s.is_anchor_store)
    print(f"  {len(stores)} stores found ({n_anchors} anchors) within {search_km}km.")
    if n_anchors == 0:
        print("  No anchor stores nearby - this address doesn't appear to be in a tracked plaza.")
        return None
 
    plazas = build_plazas(stores, radius_mi, min_other_tenants)
    attach_mall_names(plazas, mall_elements)
    plazas = deduplicate_plaza_stores(plazas)
    plazas = merge_same_name_plazas(plazas)
    attach_plaza_radius(plazas, radius_mi * 1609.34)
 
    if not plazas:
        print("  No plaza clusters formed near this address.")
        return None
 
    print(f"  {len(plazas)} distinct plaza(s) found within {search_km}km:")
    for p in plazas:
        clat, clng = p.center
        d = haversine_m(lat, lng, clat, clng)
        print(f"    '{p.label}' - {d:.0f}m away, {len(p.anchors)} anchors, {len(p.tenants)} tenants: "
              f"{[s.name for s in (list(p.anchors) + list(p.tenants))]}")
 
    sb = get_supabase() if use_cache else None
    if sb:
        new_plazas, needs_scoring = attach_existing_data(sb, plazas)
        print(f"  {len(plazas) - len(new_plazas)} matched existing Supabase data, {len(new_plazas)} new.")
        if needs_scoring:
            score_plazas(needs_scoring, state_fips, county_fips)
        if new_plazas:
            attach_counties(new_plazas)
            score_plazas(new_plazas, state_fips, county_fips)
    else:
        attach_counties(plazas)
        score_plazas(plazas, state_fips, county_fips)
 
    best, best_dist = None, float("inf")
    for p in plazas:
        clat, clng = p.center
        d = haversine_m(lat, lng, clat, clng)
        if d < best_dist:
            best, best_dist = p, d
 
    print(f"  Nearest plaza: '{best.label}' ({best_dist:.0f}m away, "
          f"{len(best.anchors)} anchors, {len(best.tenants)} tenants)")
    return best
 
 
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: python find_single_plaza.py <lat> <lng> [search_km]")
        sys.exit(1)
    lat, lng = float(sys.argv[1]), float(sys.argv[2])
    search_km = float(sys.argv[3]) if len(sys.argv) > 3 else default_search_km
    plaza = find_single_plaza(lat, lng, search_km=search_km)
    if plaza:
        print(f"\nAnchors: {[a.name for a in plaza.anchors]}")
        print(f"Tenants: {[t.name for t in plaza.tenants]}")
        print(f"Scores: {plaza.scores}")