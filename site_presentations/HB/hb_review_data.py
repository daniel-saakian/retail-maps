from __future__ import annotations

import math
import os
import re
import sys
from pathlib import Path

import pandas as pd

_HB_DIR = Path(__file__).resolve().parent
_SP_DIR = _HB_DIR.parent
for _p in (_HB_DIR, _SP_DIR, _SP_DIR.parent, _SP_DIR / "Sourdough", _SP_DIR / "TGG"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

from sourdough_demographics import (
    geocode_address, profile_address, reverse_geocode_coords, profile_from_coords, ACS_YEAR,
)


DRIVER_RADIUS_MI = 2.0
COMPETITOR_RADIUS_MI = 3.0
CSV_COMPETITOR_RADIUS_MI = 5.0
CENTER_RADIUS_MI = 0.3
ROWS_PER_A1_TABLE = 6

CENTERCHECK_PATHS = [
    os.getenv("HB_CENTERCHECK_CSV") or "",
    str(_HB_DIR / "centercheck_stats.csv"),
    str(_SP_DIR / "TGG" / "competitors_2.csv")
]

DIRECT_NAME_RE = re.compile(
    r"smoothie|juice|jamba|robeks|nekter|n[eé]kter|playa bowl|vitality bowl|acai|a[cç]a[ií]|"
    r"rush bowl|frutta bowl|everbowl|main squeeze|clean juice|pressed|joe ?& ?the juice|"
    r"protein|shake|nutrition club|herbalife|bowl ?bar|grabbagreen|juice it up|tropical smoothie",
    re.I,
)
SUPPLEMENT_RE = re.compile(r"gnc|vitamin shoppe|nutrition|supplement|vitamin", re.I)


def _haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return 2 * r * math.asin(math.sqrt(a))


def _fmt_mi(d):
    return f"{d:.1f} mi" if d >= 0.1 else "<0.1 mi"

def _fmt_int(n):
    return f"{int(n):,}" if n is not None else "n/a"

def _title(s: str) -> str:
    return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in (s or "").split())


def geocode(address: str, manual_lat = None, manual_lon = None) -> dict:
    try:
        g = geocode_address(address)
        parts = [p.strip() for p in g["matched_address"].split(",")]
        street = _title(parts[0]) if parts else address
        city = _title(parts[1]) if len(parts) > 1 else ""
        state = parts[2] if len(parts) > 2 else ""
        zip_ = parts[3] if len(parts) > 3 else ""
        return {"lat": g["lat"], "lon": g["lon"], "matched_address": g["matched_address"],
                "street": street, "city": city, "state": state, "zip": zip_,
                "state_fips": g["state_fips"], "county_fips": g["county_fips"], "manual": False}
    except Exception as e:
        if manual_lat is None or manual_lon is None:
            raise ValueError(f"Geocoding failed for '{address}' ({e}). Enter coordinates in "
                             f"Advanced Settings and keep the address typed in.") from e
        rg = reverse_geocode_coords(manual_lat, manual_lon)
        parts = [p.strip() for p in address.split(",")]
        return {"lat": manual_lat, "lon": manual_lon, "matched_address": address,
                "street": parts[0], "city": parts[1] if len(parts) > 1 else "",
                "state": parts[2].split()[0] if len(parts) > 2 and parts[2] else "",
                "zip": "", "state_fips": rg["state_fips"], "county_fips": rg["county_fips"], "manual": True}

def demographics(address: str, geo: dict) -> dict:
    if geo["manual"]:
        return profile_from_coords(geo["lat"], geo["lon"], geo["state_fips"], geo["county_fips"])
    return profile_address(address)

def traffic(lat, lon) -> list[dict]:
    from adjacent_estimation import adjacent_road_traffic_from_coords
    out = adjacent_road_traffic_from_coords(lat, lon) or {}
    if out.get("error"):
        raise RuntimeError(out["error"])
    roads = [r for r in out.get("roads", []) if r.get("road_name")]
    roads.sort(key=lambda r: (r.get("aadt") is None, -(r.get("aadt") or 0)))
    return roads

def plaza(lat, lon) -> dict | None:
    from find_single_plaza import find_single_plaza
    p = find_single_plaza(lat, lon, search_km = 1.0)
    if p is None:
        return None
    clat, clng = p.center
    return {
        "name": getattr(p, "label", None) or "Unnamed center",
        "distance_mi": round(_haversine_mi(lat, lon, clat, clng), 2),
        "anchors": sorted({s.name for s in p.anchors}),
        "tenants": sorted({s.name for s in p.tenants}),
    }

def nearest_hb(lat, lon) -> list[dict]:
    from hb_proximity import nearest_hb_locations
    return nearest_hb_locations(lat, lon, n=5)

# ---- OSM (Overpass) -------------------------------------------------------
# Public Overpass servers are often overloaded or down. To get through:
#   - three small searches instead of one big one (a failure loses one group, not all)
#   - each search is sent to every mirror at once and the first good answer wins
#   - the three searches run at the same time, under one time budget
#   - successful groups are cached on disk, so pressing Prefill again only
#     retries what failed

OSM_TIME_BUDGET_S = 90        # whole OSM step gives up after this
OSM_QUERY_TIMEOUT_S = 25      # Overpass-side timeout per search
OSM_CACHE_DIR = _HB_DIR / ".osm_cache"
OSM_CACHE_DAYS = 14


def _osm_queries(lat, lon) -> dict[str, str]:
    def around(mi):
        return f"(around:{int(mi * 1609.34)},{lat},{lon})"
    near, drv, cmp_ = around(1.0), around(DRIVER_RADIUS_MI), around(COMPETITOR_RADIUS_MI)
    head = f"[out:json][timeout:{OSM_QUERY_TIMEOUT_S}];"
    return {
        "competitors": head + f"""(
  nwr["amenity"~"^(cafe|fast_food|restaurant|ice_cream)$"]["name"~"smoothie|juice|nekter|jamba|robeks|playa|acai|protein|shake|nutrition|bowl",i]{cmp_};
  nwr["amenity"~"^(cafe|fast_food)$"]["cuisine"~"smoothie|juice|acai",i]["name"]{cmp_};
  nwr["shop"~"^(nutrition_supplements|health_food)$"]["name"]{cmp_};
  nwr["leisure"~"^(fitness_centre|sports_centre)$"]["name"]{drv};
);out center tags;""",
        "schools_health": head + f"""(
  nwr["amenity"~"^(school|university|college|library|hospital|community_centre)$"]["name"]{drv};
);out center tags;""",
        "local_places": head + f"""(
  nwr["amenity"~"^(place_of_worship|clinic|doctors|cinema|theatre|conference_centre)$"]["name"]{near};
  nwr["leisure"~"^(park|stadium)$"]["name"]{near};
  nwr["tourism"="hotel"]["name"]{near};
  nwr["shop"="mall"]["name"]{drv};
);out center tags;""",
        "offices_residential": head + f"""(
  nw["office"]["name"]{near};
  nw["building"~"^(apartments|dormitory)$"]["name"]{near};
  nw["landuse"="residential"]["name"]{near};
  node["place"~"^(neighbourhood|suburb)$"]["name"]{drv};
);out center tags;""",
    }


def _post_one(mirror: str, query: str, timeout: float) -> list:
    import requests
    from majorretail import headers
    r = requests.post(mirror, data={"data": query}, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from {mirror.split('/')[2]}")
    data = r.json()
    remark = str(data.get("remark") or "")
    if "runtime error" in remark.lower() or "timed out" in remark.lower():
        raise RuntimeError(f"query timed out on {mirror.split('/')[2]}")
    return data.get("elements", [])


def _race_mirrors(query: str, deadline: float) -> list:
    """Send the query to every mirror at once; return the first good answer."""
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutTimeout
    from majorretail import overpass_mirrors
    timeout = max(5.0, deadline - time.time())
    pool = ThreadPoolExecutor(max_workers=len(overpass_mirrors))
    futures = {pool.submit(_post_one, m, query, timeout): m for m in overpass_mirrors}
    errors = []
    try:
        for fut in as_completed(futures, timeout=max(1.0, deadline - time.time())):
            try:
                return fut.result()
            except Exception as e:
                host = futures[fut].split("/")[2]
                msg = str(e)
                if msg.startswith("HTTP ") or msg.startswith("query timed out"):
                    errors.append(msg.replace(f" from {host}", "").replace(f" on {host}", "") + f" ({host})")
                elif "timed out" in msg.lower() or "Timeout" in type(e).__name__:
                    errors.append(f"timed out ({host})")
                else:
                    errors.append(f"unreachable ({host})")
    except FutTimeout:
        errors.append("no server answered in time")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    raise RuntimeError(", ".join(errors) or "no server answered in time")


def _cache_path(lat, lon):
    return OSM_CACHE_DIR / f"{lat:.4f}_{lon:.4f}.json"


def _cache_read(lat, lon) -> dict:
    import json, time
    p = _cache_path(lat, lon)
    try:
        if p.exists() and time.time() - p.stat().st_mtime < OSM_CACHE_DAYS * 86400:
            return json.loads(p.read_text())
    except Exception:
        pass
    return {}


def _cache_write(lat, lon, data: dict):
    import json
    try:
        OSM_CACHE_DIR.mkdir(exist_ok=True)
        _cache_path(lat, lon).write_text(json.dumps(data))
    except Exception:
        pass


def osm_pois(lat, lon, warnings: list | None = None) -> list[dict]:
    """Demand drivers + competitors from OSM. Groups that fail are reported in
    `warnings` and simply missing from the result; groups that succeed are cached."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    deadline = time.time() + OSM_TIME_BUDGET_S
    cached = _cache_read(lat, lon)
    groups = dict(cached)
    todo = {k: q for k, q in _osm_queries(lat, lon).items() if k not in groups}

    def run(item):
        name, q = item
        try:
            return name, _race_mirrors(q, deadline), None
        except Exception as e:
            return name, None, e

    if todo:
        with ThreadPoolExecutor(max_workers=len(todo)) as pool:
            for name, els, err in pool.map(run, todo.items()):
                if err is None:
                    groups[name] = els
                    print(f"  [osm] {name}: {len(els)} features")
                else:
                    msg = (f"OSM {name.replace('_', ' ')}: Overpass servers busy [{err}]. "
                           f"Press Prefill again later; the groups that loaded are saved.")
                    print(f"  [warn] {msg}")
                    if warnings is not None:
                        warnings.append(msg)
    if set(groups) - set(cached):
        _cache_write(lat, lon, groups)

    pois, seen = [], set()
    for els in groups.values():
        for el in els:
            key = (el.get("type"), el.get("id"))
            if key in seen:
                continue
            seen.add(key)
            tags = el.get("tags") or {}
            plat = el.get("lat") or (el.get("center") or {}).get("lat")
            plon = el.get("lon") or (el.get("center") or {}).get("lon")
            if plat is None or plon is None or not tags.get("name"):
                continue
            pois.append({"name": tags["name"], "tags": tags,
                         "distance_mi": round(_haversine_mi(lat, lon, plat, plon), 2)})
    pois.sort(key=lambda p: p["distance_mi"])
    return pois

def _dedupe(rows, key = lambda r: r["name"].lower()):
    seen, out = set(), []
    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out

def classify_pois(pois: list[dict]) -> dict:
    business, community, residential, gyms, direct, indirect = [], [], [], [], [], []
    for p in pois:
        t, n = p["tags"], p["name"]
        amen, leis, shop = t.get("amenity", ""), t.get("leisure", ""), t.get("shop", "")
        cuisine = t.get("cuisine", "")
        is_food = amen in ("cafe", "fast_food", "restaurant", "ice_cream")
        if is_food and (DIRECT_NAME_RE.search(n) or re.search(r"smoothie|juice|acai", cuisine, re.I)):
            direct.append({**p, "format": t.get("brand") and "Chain" or "Independent / unconfirmed"})
            continue
        if shop in ("nutrition_supplements", "health_food") or (shop == "beverages"):
            indirect.append({**p, "format": "Supplement / health retail (check for blend bar)"})
            continue
        if leis in ("fitness_centre", "sports_centre"):
            gyms.append(p)
            if p["distance_mi"] <= 1.5:
                indirect.append({**p, "format": "Gym / studio (check for in-house nutrition bar)"})
            continue
        if p["distance_mi"] > DRIVER_RADIUS_MI:
            continue
        if amen in ("school", "university", "college", "library", "place_of_worship", "fire_station",
                    "police", "community_centre") or leis in ("park", "stadium"):
            community.append(p)
        elif t.get("building") in ("apartments", "dormitory") or t.get("landuse") == "residential" \
                or t.get("place") in ("neighbourhood", "suburb"):
            residential.append(p)
        else:
            business.append(p)
    return {
        "business": _dedupe(business), "community": _dedupe(community),
        "residential": _dedupe(residential), "gyms": _dedupe(gyms),
        "direct": _dedupe(direct), "indirect": _dedupe(indirect),
    }

def csv_competitors(lat, lon) -> list[dict]:
    from hb_model import load_hb_competitor
    comp = load_hb_competitor()
    out = []
    for _, r in comp.iterrows():
        d = _haversine_mi(lat, lon, r["Latitude"], r["Longitude"])
        if d <= CSV_COMPETITOR_RADIUS_MI:
            out.append({"name": r["Brand"], "address": f"{r.get('Address', '')}, {r.get('City', '')}",
                        "distance_mi": round(d, 2), "format": "Chain (tracked)"})
    out.sort(key=lambda x: x["distance_mi"])
    return out


def _load_centercheck() -> pd.DataFrame | None:
    for p in CENTERCHECK_PATHS:
        if p and Path(p).exists():
            df = pd.read_csv(p, usecols=lambda c: c in {"Brand", "Plaza", "Address", "City", "State",
                                                        "Ranking", "Latitude", "Longitude"})
            df = df.dropna(subset=["Latitude", "Longitude", "Ranking"])
            df.attrs["path"] = p
            return df
    return None

_CC_CACHE: dict={}

def cotenant_rankings(lat, lon) -> list[dict]:
    if "df" not in _CC_CACHE:
        _CC_CACHE["df"] = _load_centercheck()
    df = _CC_CACHE["df"]
    if df is None:
        return []
    box = 0.01
    near = df[(df["Latitude"].between(lat - box, lat + box)) & (df["Longitude"].between(lon - box, lon + box))]
    out = []
    for _, r in near.iterrows():
        d = _haversine_mi(lat, lon, r["Latitude"], r["Longitude"])
        if d > CENTER_RADIUS_MI:
            continue
        m = re.match(r"\s*(\d+)\s*/\s*(\d+)", str(r["Ranking"]))
        if not m:
            continue
        rank, total = int(m.group(1)), int(m.group(2))
        pct = rank / total
        out.append({"brand": r["Brand"], "rank": rank, "total": total,
                    "top_pct": round(pct * 100), "distance_mi": round(d, 2),
                    "index": "over-indexes" if pct <= 0.5 else "under-indexes"})
    out.sort(key=lambda x: x["rank"] / x["total"])
    return _dedupe(out, key=lambda x: x["brand"])


def collect(address: str, manual_lat = None, manual_lon = None, log=print) -> dict:
    warnings: list[str] = []
    ctx: dict = {"address_input": address}

    log("Geocoding...")
    geo = geocode(address, manual_lat, manual_lon)
    ctx["geo"] = geo
    lat, lon = geo["lat"], geo["lon"]

    def step(name, fn, *a):
        log(f"{name}...")
        try:
            return fn(*a)
        except Exception as e:
            warnings.append(f"{name} unavailable: {e}")
            log(f"  [warn] {name}: {e}")
            return None

    ctx["demographics"] = step("Demographics", demographics, address, geo)
    ctx["traffic"] = step("Traffic counts", traffic, lat, lon) or []
    ctx["plaza"] = step("Plaza and co-tenants", plaza, lat, lon)
    ctx["nearest_hb"] = step("Nearest HB stores", nearest_hb, lat, lon) or []
    pois = step("OSM demand drivers and competitors", osm_pois, lat, lon, warnings) or []
    ctx["poi"] = classify_pois(pois)
    ctx["csv_competitors"] = step("Tracked competitors", csv_competitors, lat, lon) or []
    ctx["cotenant_rankings"] = step("CenterCheck rankings", cotenant_rankings, lat, lon) or []
    ctx["warnings"] = warnings
    return ctx

def _v(value, source, note=None):
    return {"value": value, "source": source, "note": note}

def prefill_from_context(ctx:dict) -> tuple[dict, dict]:
    f: dict={}
    t: dict={}
    geo=ctx["geo"]

    f["street_suite"] = _v(geo["street"], "auto", "Census geocoder match. Add the suite.")
    f["city_state_zip"] = _v(", ".join(x for x in [geo["city"], f"{geo['state']} {geo['zip']}".strip()] if x), "auto")

    pl = ctx.get("plaza")
    if pl:
        f["center_name"] = _v(pl["name"], "auto", f"OpenStreetMap plaza match, {pl['distance_mi']} mi from the geocoded point.")
        roster=[]
        if pl["anchors"]:
            roster.append("Anchors: " + ", ".join(pl["anchors"]))
        if pl["tenants"]:
            roster.append("Tenants: " + ", ".join(pl["tenants"]))
        roster.append("Vacancy / pending departures / dark space: [verify on site and with leasing]")
        roster.append("Source: OpenStreetMap tenant list (may be incomplete); confirm against the leasing site plan.")
        f["tenant_roster"] = _v("\n".join(roster), "auto")

    roads = ctx.get("traffic") or []

    def road_line(r):
        aadt = r.get("aadt")
        if aadt is None:
            return f"{r['road_name']}: no count available"
        if r.get("source") == "measured":
            return f"{r['road_name']}: {aadt:,} ADT (measured; {r.get('source_detail', '')}; count year: [add])"
        return f"{r['road_name']}: ~{aadt:,} ADT (ESTIMATE, Stone traffic model; {r.get('source_detail', '')})"

    named = _dedupe([r for r in roads], key=lambda r: r["road_name"].lower())
    if named:
        f["adt_primary"] = _v(road_line(named[0]), "auto")
        f["access_street"] = _v(named[0]["road_name"], "auto", "Highest-volume adjacent road. Confirm the driveway is on it.")
    if len(named) > 1:
        f["adt_secondary"] = _v(road_line(named[1]), "auto")
        f["exit_street"] = _v(named[1]["road_name"], "auto", "Second adjacent road. Confirm on site.")
        f["cross_streets"] = _v(f"{named[0]['road_name']} & {named[1]['road_name']}", "auto")
        f["store_locator"] = _v(f"{named[0]['road_name']} and {named[1]['road_name']}", "auto")
    if len(named) > 2:
        f["other_roads"] = _v(", ".join(r["road_name"] for r in named[2:6]), "auto")

    demo = ctx.get("demographics") or {}
    r1, r3, r5 = (demo.get(k) or {} for k in ("ring_1mi", "ring_3mi", "ring_5mi"))
    src = f"(ACS {ACS_YEAR} 5-yr block groups; LODES jobs)"
    if r3:
        f["population_135"] = _v(f"{_fmt_int(r1.get('population'))} / {_fmt_int(r3.get('population'))} / "
                                 f"{_fmt_int(r5.get('population'))} {src}", "auto")
        f["daytime_pop_135"] = _v(f"{_fmt_int(r1.get('daytime_population'))} / {_fmt_int(r3.get('daytime_population'))} / "
                                  f"{_fmt_int(r5.get('daytime_population'))} {src}", "auto")
        if r3.get("median_hh_income"):
            f["median_income_3"] = _v(f"${r3['median_hh_income']:,} (ACS {ACS_YEAR} 5-yr, pop-weighted)", "auto")
        if r3.get("median_age"):
            f["median_age_3"] = _v(f"{r3['median_age']} (ACS {ACS_YEAR} 5-yr, pop-weighted)", "auto")

    ranks = ctx.get("cotenant_rankings") or []
    if ranks:
        lines = [f"{r['brand']}: #{r['rank']:,} of {r['total']:,} chain-wide (top {r['top_pct']}%) - {r['index']}"
                 for r in ranks]
        over = sum(1 for r in ranks if r["index"] == "over-indexes")
        lines.append(f"{over} of {len(ranks)} ranked tenants here over-index against their own chain.")
        lines.append("Source: CenterCheck chain sales rankings (not Placer visits). Add Placer rankings if you have them.")
        f["cotenant_ranking"] = _v("\n".join(lines), "auto")

    poi = ctx.get("poi") or {}

    def label(p):
        t_ = p["tags"]
        kind = (t_.get("amenity") or t_.get("leisure") or t_.get("tourism") or t_.get("shop")
                or ("office" if t_.get("office") else None) or t_.get("building") or t_.get("landuse")
                or t_.get("place") or "")
        return f"{p['name']} ({kind.replace('_', ' ')})" if kind else p["name"]

    drivers = []
    for key, title in (("gyms", "Gyms / studios"), ("community", "Schools, parks, community"),
                       ("business", "Employment, medical, retail"), ("residential", "Residential")):
        items = (poi.get(key) or [])[:6]
        if items:
            drivers.append(f"{title}: " + "; ".join(f"{label(p)} {_fmt_mi(p['distance_mi'])}" for p in items))
    if drivers:
        drivers.append(f"Source: OpenStreetMap within {DRIVER_RADIUS_MI:g} mi (straight-line distance).")
        f["demand_drivers"] = _v("\n".join(drivers), "auto")

    for tid, key in (("nearby_business", "business"), ("nearby_community", "community"),
                     ("nearby_residential", "residential")):
        rows = [{"name": label(p), "distance": _fmt_mi(p["distance_mi"])}
                for p in (poi.get(key) or [])[:ROWS_PER_A1_TABLE]]
        if rows:
            t[tid] = rows

    direct = _dedupe(
        [{"name": c["name"], "distance_mi": c["distance_mi"], "format": c["format"]} for c in ctx.get("csv_competitors") or []]
        + [{"name": p["name"], "distance_mi": p["distance_mi"], "format": p["format"]} for p in poi.get("direct") or []],
        key=lambda c: (re.sub(r"[^a-z]", "", c["name"].lower()), round(c["distance_mi"], 1)),
    )
    direct.sort(key=lambda c: c["distance_mi"])
    indirect = [{"name": p["name"], "distance_mi": p["distance_mi"], "format": p["format"]} for p in poi.get("indirect") or []]

    if direct:
        t["comp_direct"] = [{"name": c["name"], "distance": _fmt_mi(c["distance_mi"]), "price": "",
                             "strength": "", "weakness": ""} for c in direct[:6]]
    if indirect:
        t["comp_indirect"] = [{"name": c["name"], "distance": _fmt_mi(c["distance_mi"]), "price": "",
                               "strength": "", "weakness": ""} for c in indirect[:6]]
    if direct or indirect:
        lines = ["Direct: " + ("; ".join(f"{c['name']} ({c['format']}) {_fmt_mi(c['distance_mi'])}" for c in direct[:8]) or "none found")]
        lines.append("Indirect: " + ("; ".join(f"{c['name']} {_fmt_mi(c['distance_mi'])}" for c in indirect[:8]) or "none found"))
        lines.append("Placer visits/trend and comparable-item price range: [add per competitor]")
        lines.append("Source: tracked brand list + OpenStreetMap. Verify each is open.")
        f["competitors_summary"] = _v("\n".join(lines), "auto")

    return f, t

if __name__ == "__main__":
    import json
    addr = sys.argv[1] if len(sys.argv) > 1 else "5530 Douglas Blvd, Granite Bay, CA 95746"
    ctx = collect(addr)
    fields, tables = prefill_from_context(ctx)
    print(json.dumps({"fields": fields, "tables": tables, "warnings": ctx["warnings"]}, indent=2, default=str))