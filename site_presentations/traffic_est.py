import sys
import json
import math
import time
from pathlib import Path
 
_this_dir = Path(__file__).resolve().parent
_candidates = (_this_dir, _this_dir.parent, _this_dir.parent.parent, _this_dir / "TGG", _this_dir / "Sourdough")
for _candidate in _candidates:
    if (_candidate / "tgg_demographics.py").exists() or (_candidate / "sourdough_demographics.py").exists():
        sys.path.append(str(_candidate))
 
try:
    from tgg_demographics import geocode_address, fetch_lodes_wac, STATE_FIPS_TO_ABBR
except ImportError:
    from sourdough_demographics import geocode_address, fetch_lodes_wac, STATE_FIPS_TO_ABBR
 
import numpy as np
import requests
import functools
 
caltrans_aadt_url = (
    "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/"
    "CHhighway/Traffic_AADT/MapServer/0/query"
)
overpass_url = "https://overpass-api.de/api/interpreter"
CENSUS_KEY = "0be3a0e2fd8c0e5bce91c7ecc632787c6d5449e5"
 
model_path = Path(__file__).parent / "traffic_model.json"
 
road_class_rank = {
    "motorway": 7, "motorway_link": 6,
    "trunk": 6, "trunk_link": 5,
    "primary": 5, "primary_link": 4,
    "secondary": 4, "secondary_link": 3,
    "tertiary": 3, "tertiary_link": 2,
    "unclassified": 2,
    "residential": 1,
    "service": 0, "living_street": 0 
}
 
def _parse_lanes(tag):
    if tag is None:
        return None
    s = str(tag).split(";")[0].strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None
def _parse_maxspeed(tag):
    if tag is None:
        return None
    s = str(tag).lower().strip()
    try:
        if "km/h" in s or "kmh" in s:
            val = float(s.split("km")[0].strip())
            return int(val * 0.621371)
        if "mph" in s:
            return int(float(s.replace("mph","").strip()))
        return int(float(s))
    except (ValueError, TypeError):
        return None
def _class_rank(highway_tag):
    return road_class_rank.get(str(highway_tag).strip(),-1)
 
def _to_int(val):
    if val is None:
        return None
    if isinstance(val,(int,float)):
        try:
            return int(val) if not (isinstance(val,float) and math.isnan(val)) else None
        except (ValueError,TypeError):
            return None
    s = str(val).strip().replace(",","")
    if s == "" or s.lower() in ("na", "n/a", "null", "none"):
        return None
    try:
        return int(float(s))
    except (ValueError,TypeError):
        return None
 
@functools.lru_cache(maxsize=4000)
def _tract_at(lat, lon):
    """Return (state_fips, county_fips, tract) for a coordinate, or None."""
    url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    params = {
        "x": lon, "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "Census Tracts",
        "format": "json",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            tracts = data["result"]["geographies"].get("Census Tracts", [])
            if not tracts:
                return None
            t = tracts[0]
            return (t["STATE"], t["COUNTY"], t["TRACT"])
        except Exception as e:
            print(f"[traffic_estimation] _tract_at attempt {attempt+1}/3 failed: {type(e).__name__}: {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1)) 
    return None
 
 
@functools.lru_cache(maxsize=4000)
def _tract_population(state, county, tract):
    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {
        "get": "B01003_001E",
        "for": f"tract:{tract}",
        "in": f"state:{state} county:{county}",
        "key": CENSUS_KEY,
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            header, *rows = r.json()
            if not rows:
                return None
            return float(rows[0][header.index("B01003_001E")] or 0)
        except Exception as e:
            print(f"[traffic_estimation] _tract_population attempt {attempt+1}/3 failed: {type(e).__name__}: {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1)) 
 
    return None
 
 
@functools.lru_cache(maxsize=4000)
def _tract_area_sqmi(state, county, tract):
    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query"
    geoid = f"{state}{county}{tract}"
    params = {
        "where": f"GEOID='{geoid}'",
        "outFields": "AREALAND",
        "returnGeometry": "false",
        "f": "json",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            feats = r.json().get("features", [])
            if not feats:
                return None
            aland_sq_meters = float(feats[0]["attributes"]["AREALAND"] or 0)
            if aland_sq_meters <= 0:
                return None
            return aland_sq_meters / 2_589_988.11  # sq m -> sq mi
        except Exception as e:
            print(f"[traffic_estimation] _tract_area_sqmi attempt {attempt+1}/3 failed: {type(e).__name__}: {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1)) 
    return None
    
 
 
@functools.lru_cache(maxsize=4000)
def _block_group_at(lat, lon):
    url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    params = {
        "x": lon, "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "2020 Census Blocks",
        "format": "json",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            blocks = r.json()["result"]["geographies"].get("2020 Census Blocks", [])
            if not blocks:
                return None
            b = blocks[0]
            block_geoid = b.get("GEOID") or b.get("GEOID20")
            if block_geoid and len(block_geoid) >= 12:
                return (block_geoid[:12], b["STATE"])
            return (b["STATE"] + b["COUNTY"] + b["TRACT"] + b["BLKGRP"], b["STATE"])
        except Exception as e:
            print(f"[traffic_estimation] _block_group_at attempt {attempt+1}/3 failed: {type(e).__name__}: {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1)) 
    return None
 
 
def jobs_at_point(lat, lon):
    bg = _block_group_at(lat, lon)
    if bg is None:
        return 0.0
    geoid, state_fips = bg
    abbr = STATE_FIPS_TO_ABBR.get(state_fips)
    if abbr is None:
        return 0.0
    try:
        df = fetch_lodes_wac(abbr)  # cached after first call per state
        match = df[df["geoid"] == geoid]
        if match.empty:
            return 0.0
        return float(match["jobs"].iloc[0])
    except Exception:
        return 0.0
 
 
 
def density_at_point(lat, lon):
    tract = _tract_at(lat,lon)
 
    if tract is None:
        pop_density = 0.0
        pop_ok = False
    else:
        pop = _tract_population(*tract)
        area = _tract_area_sqmi(*tract)
        if pop is None or area is None or area <= 0:
            pop_density = 0.0
            pop_ok = False
        else:
            pop_density = pop / area
            pop_ok = True
    jobs_raw = jobs_at_point(lat,lon)
    jobs_density = (jobs_raw or 0.0) / 0.3
 
    return pop_density, jobs_density, pop_ok
 
 
 
def build_feature_vector(highway,lanes,maxspeed,pop_density,emp_density):
    rank = _class_rank(highway)
    lanes_val = _parse_lanes(lanes)
    if lanes_val is None:
        lanes_val = {7:6,6:4,5:4,4:2,3:2,2:2,1:2,0:1}.get(rank,2)
    speed_val = _parse_maxspeed(maxspeed)
    if speed_val is None:
        speed_val = {7:65, 6:55, 5:45, 4:40, 3:35, 2:30, 1:25, 0:15}.get(rank,30)
    pop_density = pop_density if pop_density is not None else 0.0
    emp_density = emp_density if emp_density is not None else 0.0
 
    log_pop = math.log1p(max(pop_density,0))
    log_emp = math.log1p(max(emp_density,0))
 
    rank_x_pop = rank * log_pop
 
    return [
        1.0,
        float(rank),
        float(lanes_val),
        float(speed_val),
        log_pop,
        log_emp, # car density
        rank_x_pop
    ]
feature_names = [
    "intercept", "class_rank", "lanes", "speed_mph", "log_pop_density", "log_emp_density", "rank_x_logpop"
]
 
def fit_ols(X,y_log):
    X = np.asarray(X,dtype=float)
    y = np.asarray(y_log, dtype = float)
    k = X.shape[1]
    ridge = 1e-6 * np.eye(k)
    beta = np.linalg.solve(X.T @ X + ridge, X.T @ y)
    return beta
def predict_log(beta,X):
    return np.asarray(X,dtype=float) @ np.asarray(beta,dtype=float)
def evaluate(beta,X_test,y_test_log):
    pred_log = predict_log(beta,X_test)
    ss_res = np.sum((y_test_log - pred_log) ** 2)
    ss_tot = np.sum((y_test_log - np.mean(y_test_log)) ** 2)
    r2 = 1-ss_res / ss_tot if ss_tot >0 else float("nan")
    pred_real = np.expm1(pred_log)
    true_real = np.expm1(y_test_log)
    with np.errstate(divide = "ignore", invalid = "ignore"):
        ape = np.abs(pred_real - true_real)/np.where(true_real > 0, true_real, np.nan)
    medape = np.nanmedian(ape) * 100
    return r2, medape
 
def fetch_caltrans_sample(max_points=500):
    params = {
        "where": "1=1",
        "outFields": "AHEAD_AADT,BACK_AADT,RTE",
        "returnGeometry": "true",
        "outSR": "4326",
        "orderByFields": "OBJECTID",
        "resultRecordCount": str(max_points * 3),
        "f": "json"
    }
    r=requests.get(caltrans_aadt_url,params=params,timeout=60)
    r.raise_for_status()
    data = r.json()
 
    seen = set()
    out = []
    for feat in data.get("features", []):
        a = feat.get("attributes", {})
        g = feat.get("geometry", {})
        gx,gy = g.get("x"), g.get("y")
        if gx is None or gy is None:
            continue
        aadt = _to_int(a.get("AHEAD_AADT")) or _to_int(a.get("BACK_AADT"))
        if aadt is None or aadt <= 0:
            continue
        key = (round(gy,5), round(gx,5))
        if key in seen:
            continue
        seen.add(key)
 
        out.append({"lat": gy, "lon": gx, "aadt": aadt})
        if len(out) >= max_points:
            break
    return out
 
 
def fetch_osm_road_at(lat, lon, radius_m=40):
    query = f"""
    [out:json][timeout:60];
    way(around:{radius_m},{lat},{lon})
        [highway~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|living_street|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"];
    out tags;
    """
 
    r = None
    elements = []
    for attempt in range(3):
        try:
            r = requests.post(
                overpass_url,
                data=query.encode("utf-8"),
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "Accept": "application/json",
                    "User-Agent": "site-scoring-tool/0.1",
                },
                timeout=60,
            )
            if r.status_code == 429 or r.status_code >= 500:
                wait = 10 * (attempt + 1)
                print(f"[overpass fetch_osm_road_at] HTTP {r.status_code}, "
                      f"attempt {attempt+1}/3, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            elements = r.json().get("elements", [])
            break
        except Exception as e:
            print(f"[overpass fetch_osm_road_at] attempt {attempt+1}/3 failed: "
                  f"{type(e).__name__}: {e}")
            if r is not None:
                print(f"[overpass fetch_osm_road_at] body head: {r.text[:300]}")
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            return None
    else:
        return None
 
    best = None
    best_rank = -1
    for el in elements:
        tags = el.get("tags", {})
        hw = tags.get("highway")
        if not hw:
            continue
        rank = _class_rank(hw)
        if rank > best_rank:
            best_rank = rank
            best = {
                "highway": hw,
                "lanes": tags.get("lanes"),
                "maxspeed": tags.get("maxspeed"),
                "name": tags.get("name"),
            }
    return best
 
def run_selftest():
    print("=" *64)
    print("SELF-TEST - synthetic data")
    print("=" * 64)
 
    rng = np.random.default_rng(42)
    n=800
 
    classes = list(road_class_rank.keys())
    rows,y = [],[]
    for _ in range(n):
        hw = rng.choice(classes)
        rank = _class_rank(hw)
        lanes = max(1,int(rng.normal(rank,1)))
        speed = 15 + rank * 7 + int(rng.normal(0,5))
        pop_density = max(0,rng.normal(5000,3000))
        emp_density = max(0, rng.normal(2000,1500))
 
        true_log = (
            5.0+0.45 * rank + 0.12 * lanes +0.015 * speed + 0.3 * math.log1p(pop_density)+0.2 *math.log1p(emp_density) +0.05 *rank*math.log1p(pop_density) +rng.normal(0,0.35)
        )
        rows.append(build_feature_vector(hw,lanes,speed,pop_density,emp_density))
        y.append(true_log)
    X=np.array(rows)
    y=np.array(y)
 
    idx = rng.permutation(n)
    cut = int(0.8*n)
    tr,te = idx[:cut], idx[cut:]
    beta = fit_ols(X[tr],y[tr])
    r2,medape=evaluate(beta,X[te],y[te])
 
    print(f"\nFitted coefficients:")
    for name,b in zip(feature_names,beta):
        print(f"  {name:>18}: {b:+.4f}")
    print(f"\nHeld-out R^2 (log space): {r2:.3f}")
    print(f"median abs % error: {medape:.1f}%")
    print("\n with ~35% noise, this is the accuracy you'd expect, time to calibrate")
 
def run_calibrate(max_points=300, min_required = 30):
    print("="*64)
    print("Calibrate with caltrans data")
    print("="*64)
 
    print(f"\n[1/3] Pulling up to {max_points} caltrans count points")
    pts = fetch_caltrans_sample(max_points = max_points)
    print(f"  got {len(pts)} measured aadt points")
    if len(pts) <min_required:
        print("   Not enough points to fit a model")
        return
    print(f"\n[2/3] Looking up OSM road attributes")
    rows, y, kept = [],[],0
    for i, p in enumerate(pts):
        road = fetch_osm_road_at(p["lat"], p["lon"])
        if road is None:
            print(f"      [{i+1:>3}/{len(pts)}] ·  kept={kept}", flush=True)
            time.sleep(0.5)
            continue
 
        pop_d, emp_d, pop_ok = density_at_point(p["lat"], p["lon"])
        if not pop_ok:
            print(f"      [{i+1:>3}/{len(pts)}] ·  density lookup failed  kept={kept}", flush=True)
            time.sleep(0.5)
            continue
 
        rows.append(build_feature_vector(
            road["highway"], road["lanes"], road["maxspeed"],
            pop_density=pop_d, emp_density=emp_d,
        ))
        y.append(math.log1p(p["aadt"]))
        kept += 1
        print(
            f"      [{i+1:>3}/{len(pts)}] ✓  kept={kept}  "
            f"class={road['highway']:<12}  pop_d={pop_d:>7.0f}  emp_d={emp_d:>7.0f}",
            flush=True,
        )
        time.sleep(0.5)
    print(f" matched {kept} with OSM roads")
    if kept < min_required:
        print("too few matches")
        return
    X = np.array(rows)
    yv = np.array(y)
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(yv))
    cut = int(0.8 * len(yv))
    tr,te = idx[:cut], idx[cut:]
 
    print(f"\n[3/3] fitting on {len(tr)} pts testing on {len(te)} pts")
    beta = fit_ols(X[tr],yv[tr])
    r2,medape = evaluate(beta, X[te], yv[te])
 
    print(f"\nFitted coefficients:")
    for name, b in zip(feature_names, beta):
        print(f" {name:>18}: {b:+.4f}")
    print(f"\nR^2 log space:  {r2:.3f}")
    print(f"median abs % error:   {medape:.1f}%")
 
    model_path.write_text(json.dumps({
        "coefficients": list(beta),
        "feature_names":feature_names,
        "r2": r2,
        "median_abs_pct_error": medape,
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
    }, indent = 2))
    print(f"\nSaved model::::: {model_path}")
 
def run_estimate(address):
    if not model_path.exists():
        print("no saved model")
        return
    print(f"Geocoding address: {address}")
    try:
        geo = geocode_address(address)
    except Exception as e:
        print(f"Geocoding failed: {e}")
        return
    lat, lon = geo["lat"], geo["lon"]
 
    model = json.loads(model_path.read_text())
    beta = np.array(model["coefficients"])
    medape = model.get("median_abs_pct_error", 40.0)
 
    road = fetch_osm_road_at(lat, lon)
    if road is None:
        print("No osm road found")
        return
 
    pop_d, emp_d, pop_ok = density_at_point(lat, lon)
    if not pop_ok:
        print("Density lookup failed")
        return
 
    # ---- DEBUG OUTPUT ----
    print(f"\n--- Inputs the model is using ---")
    print(f"  road found:   {road}")
    print(f"  pop_density:  {pop_d:.0f}")
    print(f"  emp_density:  {emp_d:.0f}")
 
    x = build_feature_vector(
        road["highway"], road["lanes"], road["maxspeed"],
        pop_density=pop_d, emp_density=emp_d,
    )
    print(f"  feature vec:  {[f'{v:.3f}' for v in x]}")
    print(f"  feature nms:  {feature_names}")
 
    log_pred = float(predict_log(beta, [x])[0])
    aadt = int(np.expm1(log_pred))
    print(f"  log_pred:     {log_pred:.3f}")
    print(f"  aadt:         {aadt}")
    print(f"--- End debug ---\n")
 
    lo = int(aadt * (1 - medape / 100))
    hi = int(aadt * (1 + medape / 100))
 
    print(json.dumps({
        "road_name": road.get("name") or f"{road['highway']} (unnamed)",
        "road_class": road["highway"],
        "estimated_aadt": aadt,
        "estimated_range": [max(0, lo), hi],
        "confidence": "low" if medape > 40 else "medium",
        "method": "Regression on road class/lanes/speed + local density, "
                  f"calibrated on Caltrans counts (±{medape:.0f}% typical error)",
        "is_estimate": True,
    }, indent=2))
 
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if mode == "selftest":
        run_selftest()
    elif mode == "calibrate":
        n = int(sys.argv[2]) if len(sys.argv) >2 else 300
        min_req = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        run_calibrate(max_points=n, min_required = min_req)
    elif mode == "estimate":
        if len(sys.argv) < 3:
            print("usage: python traffic_estimation.py estimate <address>")
        else:
            address = " ".join(sys.argv[2:])
            run_estimate(address)
    else:
        print(__doc__)