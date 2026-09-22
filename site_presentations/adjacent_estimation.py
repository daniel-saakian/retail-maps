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
 
def adjacent_road_traffic(address,n_roads=num_roads):
    try:
        geo = geocode_address(address)
    except Exception as e:
        return {"error": f"Geocoding failed: {e}"}
 
    lat,lon = geo["lat"],geo["lon"]
    state_abbr = FIPS_TO_STATE_ABBR.get(geo.get("state_fips"))
    raw_src = STATE_AADT_SOURCES.get(state_abbr)
    src = raw_src if (raw_src and raw_src.get("verified")) else None
 
    roads = find_nearby_roads(lat,lon,n=n_roads)
    if not roads:
        return {
            "address": geo["matched_address"],
            "lat": lat, "lon": lon,
            "roads": [],
            "note": "No named roads found near address",
        }
    model = _load_model()
 
    state_stations = _state_counts_near_cached(state_abbr,lat,lon,measured_radius_m) if src else tuple()
    results = []
    for road in roads:
        measured = _match_station_to_road(road,state_stations,lat,lon) if src else None
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
            est = estimate_aadt_for_road(road,lat,lon,model=model) if model else None
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
                    "high" if medape <30 else
                    "medium" if medape <45 else
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
    return {
        "address": geo["matched_address"],
        "lat":lat,
        "lon": lon,
        "roads": results
    }
 
def adjacent_road_traffic_from_coords(lat, lon, n_roads=num_roads):
    try:
        geo = reverse_geocode_coords(lat, lon)
    except Exception as e:
        return {"error": f"Reverse geocoding failed: {e}"}
 
    state_abbr = FIPS_TO_STATE_ABBR.get(geo.get("state_fips"))
    raw_src = STATE_AADT_SOURCES.get(state_abbr)
    src = raw_src if (raw_src and raw_src.get("verified")) else None
 
    roads = find_nearby_roads(lat, lon, n=n_roads)
    if not roads:
        return {
            "address": f"{lat:.6f}, {lon:.6f}",
            "lat": lat, "lon": lon,
            "roads": [],
            "note": "No named roads found near coordinates",
        }
    model = _load_model()
 
    state_stations = _state_counts_near_cached(state_abbr, lat, lon, measured_radius_m) if src else tuple()
    results = []
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
    return {
        "address": f"{lat:.6f}, {lon:.6f}",
        "lat": lat,
        "lon": lon,
        "roads": results
    }
 
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