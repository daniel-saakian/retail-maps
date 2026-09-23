import requests
import json
import sys
from pathlib import Path
from functools import lru_cache
import numpy as np
from geopy.distance import geodesic
 
# these modules may live in a different folder than this file, based on
# where things have actually ended up during setup - check a few plausible
# locations rather than assuming one fixed layout
_this_dir = Path(__file__).resolve().parent
_candidates = (_this_dir, _this_dir.parent, _this_dir.parent.parent, _this_dir / "TGG", _this_dir / "Sourdough")
for _candidate in _candidates:
    if (_candidate / "tgg_demographics.py").exists() or (_candidate / "sourdough_demographics.py").exists() or (_candidate / "traffic_est.py").exists() or (_candidate / "traffic_sources.py").exists():
        sys.path.append(str(_candidate))
 
try:
    from tgg_demographics import geocode_address, reverse_geocode_coords, FIPS_TO_STATE_ABBR
except ImportError:
    from sourdough_demographics import geocode_address, reverse_geocode_coords, FIPS_TO_STATE_ABBR
from traffic_est import (
    overpass_url,
    _class_rank,
    build_feature_vector,
    predict_log,
    density_at_point,
    model_path
)
from traffic_sources import STATE_AADT_SOURCES
import time
 
measured_radius_m = 200
num_roads = 2
road_search_rad = 80
 
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
 
# Standard FHWA functional-classification scheme (1-7 rural, 11-17 the
# urban equivalents of the same 7 categories) -- this is the field almost
# every state DOT roadway layer uses under some name like FUNCTION_CLASS_CD.
# Mapped onto the same OSM-style tag strings traffic_est.py's road_class_rank
# already understands, so a DOT-sourced road and an OSM-sourced road feed
# build_feature_vector identically.
_FHWA_CLASS_TO_HIGHWAY = {
    1: "motorway", 2: "trunk", 3: "primary",
    4: "secondary", 5: "tertiary", 6: "unclassified", 7: "residential",
}
 
def _fhwa_class_to_highway(code):
    try:
        code = int(code) % 10
    except (TypeError, ValueError):
        return None
    return _FHWA_CLASS_TO_HIGHWAY.get(code)
 
 
# MTFCC (Census TIGER/Line's own road classification) mapped the same way,
# for the nationwide fallback when a state has no roadway layer configured.
_MTFCC_TO_HIGHWAY = {
    "S1100": "trunk",          # Primary road (US/state highway)
    "S1200": "secondary",      # Secondary road
    "S1400": "residential",    # Local neighborhood road / city street
    "S1500": "unclassified",   # Vehicular trail
    "S1630": "motorway_link",  # Ramp
    "S1640": "service",        # Service drive
    "S1730": "service",        # Alley
    "S1780": "service",        # Parking lot road
}
 
TIGERWEB_ROAD_LAYERS = [
    # Primary Roads first (interstates/US/state highways), then Local
    # Roads (everything else) -- stop early once enough candidates are found.
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/2/query",
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query",
]
 
 
def dot_road_candidates_near(state_abbr, lat, lon, radius_m=road_search_rad):
    """Ask the state DOT's own roadway layer for nearby roads, in the same
    {name, highway, lanes, maxspeed, ref} shape find_nearby_roads (OSM/
    Overpass) used to return, so downstream matching/estimation code can't
    tell the difference. Returns [] when the state has no roadway layer
    configured -- callers fall back to find_nearby_roads_tiger.
    """
    src = STATE_AADT_SOURCES.get(state_abbr)
    roadway = (src or {}).get("roadway")
    if not roadway or not roadway.get("verified"):
        return []
 
    features = _fetch_layer_features(
        roadway["url"], roadway.get("where"), roadway["out_fields"], lat, lon, radius_m
    )
    roads, seen = [], set()
    for feat in features:
        a = feat.get("attributes", {})
        route = (a.get(roadway["route_field"]) or "").strip() if roadway.get("route_field") else ""
        name = (a.get(roadway.get("name_field")) or "").strip() if roadway.get("name_field") else ""
        label = name or route
        if not label or label in seen:
            continue
        seen.add(label)
 
        highway = None
        if roadway.get("class_field"):
            highway = _fhwa_class_to_highway(a.get(roadway["class_field"]))
 
        roads.append({
            "name": label,
            "highway": highway or "unclassified",
            "lanes": a.get(roadway["lanes_field"]) if roadway.get("lanes_field") else None,
            "maxspeed": a.get(roadway["speed_field"]) if roadway.get("speed_field") else None,
            "ref": route,
        })
    return roads
 
 
def find_nearby_roads_tiger(lat, lon, n=num_roads, radius_m=road_search_rad):
    """Nationwide fallback for states with no DOT roadway layer configured:
    Census TIGER/Line roads, government-hosted, no rate limits or mirror
    juggling like the public Overpass instances. Gives name + a coarse
    class from MTFCC; no lanes/speed, so those default the same way
    build_feature_vector already handles a road with unknown lanes/speed.
    """
    roads, seen = [], set()
    for layer_url in TIGERWEB_ROAD_LAYERS:
        features = _fetch_layer_features(layer_url, None, "NAME,MTFCC,RTTYP", lat, lon, radius_m)
        for feat in features:
            a = feat.get("attributes", {})
            name = (a.get("NAME") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            highway = _MTFCC_TO_HIGHWAY.get(a.get("MTFCC"), "unclassified")
            roads.append({"name": name, "highway": highway, "lanes": None, "maxspeed": None, "ref": None})
        if len(roads) >= n:
            break
 
    if len(roads) < n and radius_m < 300:
        return find_nearby_roads_tiger(lat, lon, n=n, radius_m=radius_m * 2)
 
    roads.sort(key=lambda r: _class_rank(r["highway"]), reverse=True)
    return roads[:n]
 
 
def find_nearby_roads_no_overpass(state_abbr, lat, lon, n=num_roads, radius_m=road_search_rad):
    """Replaces the OSM/Overpass lookup entirely: try the state DOT's own
    roadway layer first (best -- same system as the AADT layer, sometimes
    with real lanes/speed like Ohio's), then top up with Census TIGER
    roads if that didn't return enough candidates.
    """
    roads = dot_road_candidates_near(state_abbr, lat, lon, radius_m) if state_abbr else []
    if len(roads) < n:
        seen_names = {r["name"] for r in roads}
        extra = find_nearby_roads_tiger(lat, lon, n=n - len(roads), radius_m=radius_m)
        roads.extend(r for r in extra if r["name"] not in seen_names)
    roads.sort(key=lambda r: _class_rank(r["highway"]), reverse=True)
    return roads[:n]
 
 
# Kept for manual/CLI use only -- nothing in the live site-presentations
# path calls this anymore. find_nearby_roads_no_overpass() above replaced
# it as the default so a public Overpass mirror outage (as happened
# searching Ohio) can no longer take down traffic lookups app-wide.
def find_nearby_roads(lat, lon, n=num_roads, radius_m=road_search_rad):
    query = f"""
    [out:json][timeout:60];
    way(around:{radius_m},{lat},{lon})
        [highway~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]
        [name];
    out tags center;
    """
 
    elements = []
    for mirror in OVERPASS_MIRRORS:
        r = None
        for attempt in range(2):  # fewer retries per mirror since we have several mirrors
            try:
                r = requests.post(
                    mirror,
                    data=query.encode("utf-8"),
                    headers={
                        "Content-Type": "text/plain; charset=utf-8",
                        "Accept": "application/json",
                        "User-Agent": "site-scoring-tool/0.1",
                    },
                    timeout=30,
                )
                if r.status_code == 429 or r.status_code >= 500:
                    wait = 5 * (attempt + 1)
                    print(f"[overpass find_nearby_roads] {mirror} HTTP {r.status_code}, "
                          f"attempt {attempt+1}/2, waiting {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                elements = r.json().get("elements", [])
                break
            except Exception as e:
                print(f"[overpass find_nearby_roads] {mirror} attempt {attempt+1}/2 failed: "
                      f"{type(e).__name__}: {e}")
                if r is not None:
                    print(f"[overpass find_nearby_roads] body head: {r.text[:300]}")
                time.sleep(5 * (attempt + 1))
        if elements:
            break  # got data, stop trying other mirrors
    else:
        pass  # exhausted all mirrors without a break inside — fall through with elements=[]
 
    if not elements:
        return []
 
    by_name = {}
    for el in elements:
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip()
        hw = tags.get("highway")
        if not name or not hw:
            continue
        rank = _class_rank(hw)
        if rank < 0:
            continue
        if name not in by_name or rank > _class_rank(by_name[name]["highway"]):
            by_name[name] = {
                "name": name,
                "highway": hw,
                "lanes": tags.get("lanes"),
                "maxspeed": tags.get("maxspeed"),
                "ref": tags.get("ref"),
            }
 
    roads = sorted(by_name.values(), key=lambda r: _class_rank(r["highway"]), reverse=True)
 
    if len(roads) < n and radius_m < 200:
        return find_nearby_roads(lat, lon, n=n, radius_m=radius_m * 2)
 
    return roads[:n]
 
def _parse_number(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s.lower() in ("null", "n/a", "na"):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None
 
def _fetch_layer_features(url,where,out_fields,lat,lon,radius_m):
    params = {
        "where": where or "1=1",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "outSR": "4326",
        "distance": str(radius_m),
        "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "true",
        "f": "json",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception:
            data = None
        if isinstance(data,dict) and "error" not in data:
            return data.get("features", [])
        
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    return []
 
_state_counts_cache = {}
_state_counts_cache_max = 500
_state_counts_failure_ttl = 300
def _state_counts_near_cached(state_abbr,lat,lon,radius_m):
    key = (state_abbr,lat,lon,radius_m)
    cached = _state_counts_cache.get(key)
    if cached is not None:
        counts, cached_at, had_failure = cached
        if not had_failure or (time.time() - cached_at) < _state_counts_failure_ttl:
            return counts
        # a past failure's TTL expired - fall through and retry the fetch
 
    src = STATE_AADT_SOURCES.get(state_abbr)
    if src is None or not src.get("verified"):
        _state_counts_cache[key] = (tuple(), time.time(), False)
        return tuple()
 
    urls = src["urls"] if "urls" in src else [src["url"]]
    where = src.get("where")
    route_field = src.get("route_field")
 
    out = []
    had_failure = False
    for url in urls:
        features = _fetch_layer_features(url,where,src["out_fields"],lat,lon,radius_m)
        if features is None:
            had_failure = True
            continue
        for feat in features:
            a = feat.get("attributes", {})
            g = feat.get("geometry", {})
            gx, gy = g.get("x"), g.get("y")
            if gx is None or gy is None:
                continue
            aadt = None
            for field in src["aadt_fields"]:
                aadt = _parse_number(a.get(field))
                if aadt:
                    break
            if aadt is None or aadt <= 0:
                continue
            route = (a.get(route_field) or "").strip() if route_field else ""
            out.append((aadt,gy,gx,route))
 
    out = tuple(out)
    if had_failure and not out:
        print(f"[adjacent_est] {src['label']} fetch failed near ({lat},{lon}) - "
              f"will retry in <= {_state_counts_failure_ttl}s instead of caching forever")
 
    if len(_state_counts_cache) >= _state_counts_cache_max:
        _state_counts_cache.pop(next(iter(_state_counts_cache)))
    _state_counts_cache[key] = (out, time.time(), had_failure)
    return out
    
def route_candidates_near(state_abbr, lat, lon, radius_m=road_search_rad):
    """Ask the state DOT's own roadway/LRS layer what route is near this
    point -- when that layer is configured, this replaces the OSM/Overpass
    lookup for the single most important case: matching to a *measured*
    AADT station. Both layers come from the same DOT and speak the same
    route vocabulary (e.g. Caltrans' RouteS vs its AADT layer's RTE), so
    the match is exact instead of a fuzzy digit-guess against an OSM name
    string, and it needs no OSM/Overpass round trip at all.
    """
    src = STATE_AADT_SOURCES.get(state_abbr)
    roadway = (src or {}).get("roadway")
    if not roadway or not roadway.get("verified"):
        return []
 
    features = _fetch_layer_features(
        roadway["url"], roadway.get("where"), roadway["out_fields"], lat, lon, radius_m
    )
    routes, seen = [], set()
    for feat in features:
        a = feat.get("attributes", {})
        route = (a.get(roadway["route_field"]) or "").strip()
        if not route or route in seen:
            continue
        seen.add(route)
        routes.append(route)
    return routes
 
 
def measured_aadt_by_dot_route(state_abbr, lat, lon, radius_m=measured_radius_m):
    """Look up a measured AADT count using only the DOT's own systems --
    its roadway layer to identify the route, then its AADT layer to find
    a station on that same route. No OSM/Overpass dependency, so this
    still works even when every public Overpass mirror is down.
    """
    routes = route_candidates_near(state_abbr, lat, lon, radius_m)
    if not routes:
        return None
    stations = _state_counts_near_cached(state_abbr, lat, lon, radius_m)
    if not stations:
        return None
 
    norm_routes = {r.lstrip("0") or "0" for r in routes}
    best, best_dist = None, float("inf")
    for aadt, c_lat, c_lon, station_route in stations:
        if str(station_route).lstrip("0") not in norm_routes:
            continue
        try:
            d = geodesic((lat, lon), (c_lat, c_lon)).meters
        except Exception:
            continue
        if d < best_dist:
            best_dist, best = d, {"aadt": aadt, "distance_m": d, "route": station_route}
    return best
 
 
def _road_matches_route(road, route_str):
    """True if a road candidate (DOT- or TIGER-sourced) looks like the same
    route already resolved via measured_aadt_by_dot_route -- used to avoid
    listing the same physical road twice.
    """
    if not route_str:
        return False
    import re
    digits = set()
    for field in (road.get("ref"), road.get("name")):
        if field:
            digits.update(re.findall(r"\d+", str(field)))
    route_digits = set(re.findall(r"\d+", str(route_str)))
    norm = {d.lstrip("0") or "0" for d in digits}
    return any((d.lstrip("0") or "0") in norm for d in route_digits)
 
 
def measured_aadt_for_point(state_abbr,lat,lon,radius_m = measured_radius_m):
    counts = _state_counts_near_cached(state_abbr,lat,lon,radius_m)
    if not counts:
        return None
    best = None
    best_dist = float("inf")
    for aadt,c_lat,c_lon,route in counts:
        try:
            d= geodesic((lat,lon), (c_lat,c_lon)).meters
        except Exception:
            continue
        if d < best_dist:
            best_dist = d
            best = {"aadt": aadt, "distance_m": d, "route": route}
    return best
 
def _load_model():
    if not model_path.exists():
        return None
    model = json.loads(model_path.read_text())
    return {
        "beta": np.array(model["coefficients"]),
        "medape": model.get("median_abs_pct_error") or 50.0,
    }
 
def estimate_aadt_for_road(road,lat,lon,model=None):
    if model is None:
        model = _load_model()
        if model is None:
            return None
        
    density_result = density_at_point(lat,lon)
    if len(density_result) == 3:
        pop_d,emp_d,pop_ok = density_result
        if not pop_ok:
            return None
    else:
        pop_d,emp_d = density_result[:2]
    
    x = build_feature_vector(
        road["highway"], road.get("lanes"),road.get("maxspeed"),
        pop_density = pop_d, emp_density = emp_d
    )
    log_pred = float(predict_log(model["beta"], [x])[0])
    aadt = int(np.expm1(log_pred))
    medape = model["medape"]
    lo = max(0,int(aadt * (1-medape/100)))
    hi = int(aadt*(1+medape/100))
    return {"aadt": aadt, "range": [lo,hi], "medape": medape}
 
def _match_station_to_road(road, stations, lat, lon):
 
    if not stations:
        return None
    import re
 
    digits = set()
    for src in (road.get("ref"), road.get("name")):
        if src:
            digits.update(re.findall(r"\d+", str(src)))
 
    if not digits:
        return None
 
    norm = {d.lstrip("0") or "0" for d in digits}
    matching = [
        s for s in stations
        if str(s[3]).lstrip("0") in norm
    ]
    if not matching:
        return None
    best = None
    best_dist = float("inf")
    for aadt, c_lat, c_lon, route in matching:
        try:
            d = geodesic((lat, lon), (c_lat, c_lon)).meters
        except Exception:
            continue
        if d < best_dist:
            best_dist = d
            best = {"aadt": aadt, "distance_m": d, "route": route}
    return best
 
def _traffic_results_for(lat, lon, state_abbr, n_roads):
    """Shared core for both entry points below. No OSM/Overpass involved
    anywhere in this path -- order of operations:
      1. Try the DOT's own roadway layer for an exact measured match.
      2. Get named roads nearby via find_nearby_roads_no_overpass (state
         DOT roadway layer first, Census TIGER as the nationwide topper),
         for two reasons: it gives the human-readable road name/class the
         UI shows, and it's the source for lanes/speed feeding the
         regression estimate when there's no measured station.
      3. Skip any road from step 2 that's really the same route already
         resolved in step 1, so it isn't listed twice.
    """
    raw_src = STATE_AADT_SOURCES.get(state_abbr)
    src = raw_src if (raw_src and raw_src.get("verified")) else None
 
    dot_measured = measured_aadt_by_dot_route(state_abbr, lat, lon) if src else None
 
    results = []
    if dot_measured is not None:
        results.append({
            "road_name": f"Route {dot_measured['route']}",
            "road_class": None,
            "aadt": dot_measured["aadt"],
            "source": "measured",
            "source_detail": (
                f"{src['label']} station on the same route, "
                f"{dot_measured['distance_m']:.0f}m away "
                f"(matched via {src['label']}'s own roadway layer)"
            ),
            "confidence": "high",
            "range": None,
        })
 
    roads = find_nearby_roads_no_overpass(state_abbr, lat, lon, n=n_roads)
    if dot_measured is not None:
        roads = [r for r in roads if not _road_matches_route(r, dot_measured["route"])]
 
    if not roads and not results:
        return results, "No named roads found nearby"
 
    model = _load_model()
    state_stations = _state_counts_near_cached(state_abbr, lat, lon, measured_radius_m) if src else tuple()
 
    for road in roads:
        measured = _match_station_to_road(road, state_stations, lat, lon) if src else None
        if measured is not None:
            results.append({
                "road_name": road["name"],
                "road_class": road["highway"],
                "aadt": measured["aadt"],
                "source": "measured",
                "source_detail": (
                    f"{src['label']} station measured {measured['distance_m']:.0f}m away"
                ),
                "confidence": "high",
                "range": None,
            })
        else:
            est = estimate_aadt_for_road(road, lat, lon, model=model) if model else None
            if est is None:
                results.append({
                    "road_name": road["name"],
                    "road_class": road["highway"],
                    "aadt": None,
                    "source": "unavailable",
                    "source_detail": "No measured count, model unavailable",
                    "confidence": "none",
                    "range": None,
                })
            else:
                medape = est["medape"]
                confidence = (
                    "high" if medape < 30 else
                    "medium" if medape < 45 else
                    "low"
                )
                if src is None:
                    no_measured_reason = f"No DOT source configured for {state_abbr or 'this state'}"
                else:
                    no_measured_reason = f"No {src['label']} station nearby"
                results.append({
                    "road_name": road["name"],
                    "road_class": road["highway"],
                    "aadt": est["aadt"],
                    "source": "estimated",
                    "source_detail": f"{no_measured_reason} - est. ±{medape:.0f}% typical error",
                    "confidence": confidence,
                    "range": est["range"],
                })
    return results, None
 
 
def adjacent_road_traffic(address, n_roads=num_roads):
    try:
        geo = geocode_address(address)
    except Exception as e:
        return {"error": f"Geocoding failed: {e}"}
 
    lat, lon = geo["lat"], geo["lon"]
    state_abbr = FIPS_TO_STATE_ABBR.get(geo.get("state_fips"))
 
    results, note = _traffic_results_for(lat, lon, state_abbr, n_roads)
    out = {"address": geo["matched_address"], "lat": lat, "lon": lon, "roads": results}
    if note:
        out["note"] = note
    return out
 
 
def adjacent_road_traffic_from_coords(lat, lon, n_roads=num_roads):
    try:
        geo = reverse_geocode_coords(lat, lon)
    except Exception as e:
        return {"error": f"Reverse geocoding failed: {e}"}
 
    state_abbr = FIPS_TO_STATE_ABBR.get(geo.get("state_fips"))
 
    results, note = _traffic_results_for(lat, lon, state_abbr, n_roads)
    out = {"address": f"{lat:.6f}, {lon:.6f}", "lat": lat, "lon": lon, "roads": results}
    if note:
        out["note"] = note
    return out
 
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print('usage: python adjacent_est.py "<address>" OR "<lat, lon>"')
        sys.exit(1)
 
    arg = " ".join(sys.argv[1:])
    parts = [p.strip() for p in arg.split(",")]
 
    is_coords = False
    if len(parts) == 2:
        try:
            lat, lon = float(parts[0]), float(parts[1])
            is_coords = True
        except ValueError:
            is_coords = False
 
    if is_coords:
        result = adjacent_road_traffic_from_coords(lat, lon)
    else:
        result = adjacent_road_traffic(arg)
 
    print(json.dumps(result, indent=2))