import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd
 
_this_dir = Path(__file__).resolve().parent
_candidates = (_this_dir, _this_dir.parent, _this_dir.parent.parent)
for _candidate in _candidates:
    if (_candidate / "find_single_plaza.py").exists():
        sys.path.append(str(_candidate))
        break
else:
    print(f"[warning] find_single_plaza.py not found in {_candidates} - "
          f"the import below will likely fail.")
for _candidate in _candidates:
    if (_candidate / "adjacent_estimation.py").exists():
        sys.path.append(str(_candidate))
        break
else:
    print(f"[warning] adjacent_estimation.py not found in {_candidates} - "
          f"traffic data will be unavailable.")
from tgg_demographics import geocode_address, profile_address
from tgg_model import (
    tgg_csv, haversine_miles, load_competitors, load_new_brand_competitors,
    direct_competitor_brand, anchor_brands, market_signal_brands, new_brands,
)
from find_single_plaza import find_single_plaza
from tgg_site_template import build_excel_report
try:
    from adjacent_estimation import adjacent_road_traffic_from_coords
except ImportError as e:
    print(f"[warning] Could not import adjacent_estimation ({e}) - traffic section will be left blank.")
    adjacent_road_traffic_from_coords = None
 
n_nearest_stores = 7
n_competitors = 5
n_co_tenants = 5
plaza_search_km = 1.5
 
def _normalize_name(name):
    n = (name or "").lower()
    n = re.sub(r"#\s*\d+", "",n)
    n = re.sub(r"\b\d+\b", "", n)
    n = re.sub(r"[^a-z\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n
 
def _match_tenant_to_brand(tenant_name, known_brands):
    norm_tenant = _normalize_name(tenant_name)
    if not norm_tenant:
        return None
    for brand in known_brands:
        norm_brand = _normalize_name(brand)
        if norm_brand and (norm_brand in norm_tenant or norm_tenant in norm_brand):
            return brand
    return None
 
def build_competitor_lookup():
    comp = load_competitors()
    new_brand_comp = load_new_brand_competitors()
    if len(new_brand_comp) > 0:
        new_brand_comp = new_brand_comp.copy()
        new_brand_comp["revenue_clean"] = np.nan
        comp = pd.concat([comp, new_brand_comp], ignore_index=True)
 
    state_col = comp["State"].astype(str).str.strip().str.upper()
    rank_display = pd.Series(None, index=comp.index, dtype=object)
    for brand in comp["Brand"].unique():
        brand_mask = (comp["Brand"] == brand).values
        for state in state_col[brand_mask].unique():
            group_mask = brand_mask & (state_col == state).values
            group_idx = comp.index[group_mask]
            group_revenue = comp.loc[group_idx, "revenue_clean"]
            n = group_revenue.notna().sum()
            if n == 0:
                continue
            ranks = group_revenue.rank(ascending=False, method="min")
            for idx in group_idx:
                r = ranks.loc[idx]
                if pd.notna(r):
                    rank_display.loc[idx] = f"Rank #{int(r)} of {n} in {state}"
    comp["rank_display"] = rank_display
    return comp
 
def find_nearest_stores(lat, lon, n=n_nearest_stores):
    tgg = pd.read_csv(tgg_csv)
    tgg.columns = tgg.columns.str.strip()
    tgg = tgg.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
 
    dist = haversine_miles(
        np.array([[lat]]), np.array([[lon]]),
        tgg["Latitude"].values.reshape(1,-1), tgg["Longitude"].values.reshape(1,-1)
    )[0]
    tgg["_distance_mi"] = dist
    nearest = tgg.nsmallest(n, "_distance_mi")
 
    return [
        {
            "name": f"Great Greek. -{row.get('City', row.get('city', 'Unknown'))}",
            "distance_mi": round(row["_distance_mi"], 1),
            "address": row.get("Address", row.get("address", "")),
            "city": row.get("City", row.get("city", "")),
            "state": row.get("State", row.get("state", "")),
        }
        for _, row in nearest.iterrows()
    ]
 
primary_competitor_brands = ["CAVA", "Nick The Greek", "Luna Grill"]
 
 
def find_nearest_competitors(lat, lon, comp, n=n_competitors):
    comp = comp[comp["Brand"].isin(primary_competitor_brands)]
    if len(comp) == 0:
        return []
    dist = haversine_miles(
        np.array([[lat]]), np.array([[lon]]),
        comp["Latitude"].values.reshape(1,-1), comp["Longitude"].values.reshape(1,-1)
    )[0]
    comp = comp.copy()
    comp["_distance_mi"] = dist
    nearest = comp.nsmallest(n, "_distance_mi")
 
    results = []
    for _, row in nearest.iterrows():
        results.append({
            "name": row["Brand"],
            "distance_mi": round(row["_distance_mi"], 2),
            "city": row["City"] if pd.notna(row.get("City")) else "",
            "street_address": row["Address"] if pd.notna(row.get("Address")) else row.get("City", "") if pd.notna(row.get("City")) else "",
            "estimated_sales": row["revenue_clean"] if pd.notna(row["revenue_clean"]) else None,
            "rank_display": row["rank_display"] if pd.notna(row["rank_display"]) else None,
        })
    return results
 
 
def find_co_tenants(lat,lon, comp, n=n_co_tenants):
    all_known_brands = list(set(
        [direct_competitor_brand] + anchor_brands + market_signal_brands + new_brands
    ))
 
    plaza = find_single_plaza(lat,lon,search_km=plaza_search_km)
    if plaza is None:
        return [], None
 
    stores = list(plaza.anchors) + list(plaza.tenants)
    print(f"  Checking {len(stores)} stores in '{getattr(plaza, 'label', '?')}' against {len(all_known_brands)} tracked brands:")
    co_tenants = []
    for s in stores:
        matched_brand = _match_tenant_to_brand(s.name, all_known_brands)
        print(f"    '{s.name}' -> {matched_brand or 'NO MATCH'}")
        entry = {
            "name": s.name,
            "category": "Anchor" if s in plaza.anchors else "Tenant",
            "estimated_sales": None,
            "rank_display": None,
        }
        if matched_brand:
            brand_rows = comp[comp["Brand"] == matched_brand]
            if len(brand_rows) > 0 and brand_rows["revenue_clean"].notna().any():
                with_revenue = brand_rows[brand_rows["revenue_clean"].notna()]
                dist = haversine_miles(
                    np.array([[s.lat]]), np.array([[s.lng]]),
                    with_revenue["Latitude"].values.reshape(1, -1),
                    with_revenue["Longitude"].values.reshape(1, -1),
                )[0]
                nearest_idx = dist.argmin()
                nearest_dist = dist[nearest_idx]
                if nearest_dist <= 0.5:
                    nearest_row = with_revenue.iloc[nearest_idx]
                    entry["estimated_sales"] = nearest_row["revenue_clean"]
                    entry["rank_display"] = nearest_row["rank_display"] or f"{matched_brand}"
                    print(f"      matched '{matched_brand}' to a specific location {nearest_dist:.2f}mi away - using its real sales")
                else:
                    median_rev = with_revenue["revenue_clean"].median()
                    entry["estimated_sales"] = median_rev
                    entry["rank_display"] = f"{matched_brand} state median (nearest tracked location {nearest_dist:.1f}mi away)"
            else:
                print(f"      matched '{matched_brand}' but {len(brand_rows)} rows in comp, "
                      f"none with revenue data - sales will stay blank")
        co_tenants.append(entry)
    co_tenants.sort(key=lambda t: t["estimated_sales"] is None)
    return co_tenants[:n], getattr(plaza, "label", None)
 
def generate_site_report(address, used_names=None):
    print(f"Geocoding: {address}")
    geo = geocode_address(address)
    lat,lon = geo["lat"], geo["lon"]
    matched_address = geo["matched_address"]
    print(f" Matched: {matched_address} ({lat:.5f}, {lon:.5f})")
 
    print("Pulling demographics...")
    demo = profile_address(address)
 
    profile = {
        "address": matched_address,
        "ring_1mi": demo.get("ring_1mi", {}),
        "ring_3mi": demo.get("ring_3mi", {}),
        "ring_5mi": demo.get("ring_5mi", {})
    }
 
    print("Finding nearest existing Great Greek locations...")
    proximity = find_nearest_stores(lat,lon)
    for p in proximity:
        print(f"  {p['name']}: {p['distance_mi']} mi")
 
    print("Loading Competitor Data...")
    comp = build_competitor_lookup()
    competitors = find_nearest_competitors(lat,lon,comp)
    for c in competitors:
        sales_str = f"${c['estimated_sales']:,.0f}" if c["estimated_sales"] else "no sales data"
        print(f" {c['name']} ({c['distance_mi']} mi): {sales_str}, {c['rank_display']}")
 
    print("Finding Plaza and co-tenants...")
    co_tenants, plaza_name = find_co_tenants(lat, lon, comp)
    for t in co_tenants:
        print(f"  {t['name']} ({t['category']})")
 
    print("Finding adjacent road traffic...")
    traffic = None
    if adjacent_road_traffic_from_coords is not None:
        try:
            traffic = adjacent_road_traffic_from_coords(lat, lon)
            if traffic and traffic.get("error"):
                print(f"  {traffic['error']}")
                traffic = None
            elif traffic:
                for r in traffic.get("roads", []):
                    print(f"  {r['road_name']}: {r['aadt']} ({r['source']})")
        except Exception as e:
            print(f"  Traffic lookup failed ({e}) - leaving traffic section blank.")
    else:
        print("  adjacent_estimation not available - leaving traffic section blank.")
 
    print("Building Excel report...")
    data, filename = build_excel_report(
        profile=profile, scores={}, address=matched_address,
        traffic=traffic, proximity=proximity, competitors=competitors,
        co_tenants=co_tenants, plaza_name=plaza_name, used_names=used_names,
    )
    print(f"Done: {filename} ({len(data)} bytes)")
    return data, filename
 
 
if __name__ == "__main__":
    import sys
    from pathlib import Path
 
    if len(sys.argv) < 2:
        print("usage: python generate_site_report.py \"<address>\"")
        sys.exit(1)
 
    address = sys.argv[1]
    data, filename = generate_site_report(address, used_names=set())
    out = Path.home() / "Downloads" / filename
    out.write_bytes(data)
    print(f"\nWrote {out}")