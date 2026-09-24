import requests
import json
import sys
import re
from pathlib import Path
from functools import lru_cache
import numpy as np
from geopy.distance import geodesic

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
 
def _safe_str(v):
    """Some state ArcGIS layers type their route/name fields as numbers
    (int/float) instead of strings -- .strip() blows up on those. Coerce
    to string first so every caller can treat these fields uniformly.
    """
    if v is None:
        return ""
    if isinstance(v, float) and v != v:  # NaN
        return ""
    return str(v).strip()
 
 
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
 
 
_DIVIDED_TRUE_VALUES = {"y", "yes", "true", "1", "d", "divided"}
 
 
def _is_divided(value):
    """Loosely interpret a state's own divided-highway flag field (e.g.
    Arizona ATIS_Roads' ISDIVIDED) -- states encode this differently
    (Y/N, true/false, 1/0, "Divided"/"Undivided"), so match common
    spellings case-insensitively rather than assuming one exact format.
    """
    if value is None:
        return False
    return str(value).strip().lower() in _DIVIDED_TRUE_VALUES
 
 
def _feature_point(feat):
    """A representative (lat, lon) for one ArcGIS feature's own geometry --
    point geometry directly, or the midpoint of the first path for a
    polyline (road segments are usually lines, not points). Returns None
    if the feature has no usable geometry, so callers can fall back to the
    original query point.
    """
    geom = feat.get("geometry") or {}
    x, y = geom.get("x"), geom.get("y")
    if x is not None and y is not None:
        return y, x
    paths = geom.get("paths")
    if paths and paths[0]:
        pts = paths[0]
        mid = pts[len(pts) // 2]
        return mid[1], mid[0]
    return None
 
 
def _tiger_lookup_at(lat, lon, radius_m=100):
    """Best-effort road name + classification from Census TIGER, used to
    fill in whatever a DOT roadway match is missing:
      - no usable functional-class (true for ~19 of the configured states,
        including CA and TX) -- without this, every such match defaulted
        to "unclassified" (rank 2) regardless of whether it's actually an
        interstate, which is what wrecked the first nationwide calibration
        run: a majority of training points all landing on the same
        flattened class, decorrelating the model's single most informative
        feature from real traffic volume.
      - no real street name (true for 21 of the configured states) -- the
        old fallback was the raw route/LRS field, which for a state like
        this isn't a name at all: Arizona's ROUTE is a packed fixed-width
        string ("07  6TH  AVE  01 SCOTTSDALE"), Texas' RTE_NM is an opaque
        internal control-section id ("CS1262366-KG"). Neither is something
        a person reading a site report would recognize as a street.
    One call covers a whole batch of nearby DOT features (they're all
    within radius_m of the same query point), so callers should fetch this
    once per point rather than once per feature.
    """
    tiger = find_nearby_roads_tiger(lat, lon, n=1, radius_m=radius_m)
    return tiger[0] if tiger else None
 
 
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
    if not features:
        return []
 
    needs_tiger = not roadway.get("name_field") or not roadway.get("class_field")
 
    roads, seen = [], set()
    for feat in features:
        a = feat.get("attributes", {})
        route = _safe_str(a.get(roadway["route_field"])) if roadway.get("route_field") else ""
        name = _safe_str(a.get(roadway.get("name_field"))) if roadway.get("name_field") else ""
 
        highway = None
        if roadway.get("class_field"):
            highway = _fhwa_class_to_highway(a.get(roadway["class_field"]))
 
        if needs_tiger and (not name or highway is None):
            # Look up TIGER at THIS feature's own geometry, not the shared
            # site coordinate -- a single point-level lookup reused across
            # every candidate made two genuinely different streets (e.g.
            # Arizona has no name/class/lanes/speed fields at all, so
            # everything fell back to TIGER) collapse onto the identical
            # borrowed name+class, which then produced identical fallback
            # lanes/speed, which produced identical predicted AADT for two
            # different roads. Querying each feature's own location keeps
            # distinct roads distinct.
            feat_lat, feat_lon = _feature_point(feat) or (lat, lon)
            tiger_road = _tiger_lookup_at(feat_lat, feat_lon, radius_m=min(radius_m, 100))
            if not name and tiger_road:
                # Don't fall back to the raw route/LRS field as the display
                # name -- see _tiger_lookup_at's docstring for why that's
                # often not a name at all.
                name = tiger_road.get("name") or ""
            if highway is None and tiger_road:
                highway = tiger_road.get("highway")
 
        feat_point = _feature_point(feat)
        distance_m = _distance_m(lat, lon, feat_point)
 
        if roadway.get("divided_field") and _is_divided(a.get(roadway["divided_field"])):
            # A divided road (physical median) is essentially always at
            # least a secondary arterial in practice, whatever TIGER's own
            # coarse local-road bucket guessed -- and this comes straight
            # from the state's own roadway layer, not a borrowed nationwide
            # approximation. Arizona's ATIS_Roads carries ISDIVIDED but
            # nothing was reading it before, which is exactly the field
            # that would tell "N Marshall Way" (a divided arterial) apart
            # from an ordinary undivided side street.
            if _class_rank(highway or "residential") < _class_rank("secondary"):
                highway = "secondary"
 
        label = name or route
        if not label or label in seen:
            continue
        seen.add(label)
 
        roads.append({
            "name": label,
            "highway": highway or "unclassified",
            "lanes": a.get(roadway["lanes_field"]) if roadway.get("lanes_field") else None,
            "maxspeed": a.get(roadway["speed_field"]) if roadway.get("speed_field") else None,
            "ref": route,
            "distance_m": distance_m,
        })
    return roads
 
 
def _distance_m(lat, lon, point):
    """Distance in meters from the query point to a feature's own point,
    or None if the feature had no usable geometry -- used only to decide
    which of two functionally-tied roads is physically closer to the site,
    never fed into the AADT model itself.
    """
    if point is None:
        return None
    try:
        return geodesic((lat, lon), point).meters
    except Exception:
        return None
 
 
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
            name = _safe_str(a.get("NAME"))
            if not name or name in seen:
                continue
            seen.add(name)
            highway = _MTFCC_TO_HIGHWAY.get(a.get("MTFCC"), "unclassified")
            distance_m = _distance_m(lat, lon, _feature_point(feat))
            roads.append({
                "name": name, "highway": highway, "lanes": None, "maxspeed": None,
                "ref": None, "distance_m": distance_m,
            })
        if len(roads) >= n:
            break
 
    if len(roads) < n and radius_m < 300:
        return find_nearby_roads_tiger(lat, lon, n=n, radius_m=radius_m * 2)
 
    roads.sort(key=lambda r: _class_rank(r["highway"]), reverse=True)
    return roads[:n]
 
 
def _roads_tied(roads):
    """True if 2+ of the final roads would feed build_feature_vector an
    identical (highway, lanes, maxspeed) -- the exact case that produces
    two different streets showing the identical "estimated" AADT, e.g.
    Arizona and Texas: neither state's DOT roadway layer publishes class,
    lanes or speed for city streets, so both fall back to the same coarse
    TIGER bucket with no lanes/speed at all.
    """
    seen = set()
    for r in roads:
        key = (r["highway"], r.get("lanes"), r.get("maxspeed"))
        if key in seen:
            return True
        seen.add(key)
    return False
 
 
def _name_search_pattern(name):
    """Loosen a road name into a regex core for an Overpass name-tag match.
    DOT/TIGER and OSM don't always agree on abbreviation vs. full word for
    the suffix (Ave/Avenue, Blvd/Boulevard, Way, ...), so drop the last
    token and match on the distinctive part of the name instead.
    """
    tokens = name.strip().split()
    core = " ".join(tokens[:-1]) if len(tokens) > 1 else name
    return re.escape(core.strip() or name.strip())
 
 
# The DOT/TIGER point a tied road is keyed off of is often not ON that
# road -- it's the site's own coordinate, or a TIGER segment's midpoint,
# which can easily be 100-200m from the actual centerline. Confirmed live:
# an 80m Overpass search around such a point came back with 0 elements for
# a real, correctly-named road ("Arlington Highlands Blvd") that a wider
# radius would have caught. Enrichment radius is intentionally independent
# of (and floors above) the DOT-layer search radius that triggered it.
_ENRICH_RADIUS_MIN_M = 300
 
 
def _enrich_road_via_overpass(road, lat, lon, radius_m):
    """Best-effort ONLY: ask OSM/Overpass for finer lanes/speed/class data
    for one SPECIFIC named road, used solely to break a tie DOT+TIGER
    couldn't resolve on their own (see _roads_tied). Never on the critical
    path -- tries up to 2 mirrors with a short per-request timeout, wrapped
    so any failure (both mirrors down/timing out, no match) just returns
    the road unchanged. Making Overpass required is exactly what caused
    the site-presentations 500s earlier in this project; as a pure
    enrichment step that only runs when there's already a tie to fix, it
    can't break a report even if every public mirror is down.
    """
    if not road.get("name"):
        return road
 
    search_radius = max(radius_m, _ENRICH_RADIUS_MIN_M)
    pattern = _name_search_pattern(road["name"])
    query = f"""
    [out:json][timeout:8];
    way(around:{search_radius},{lat},{lon})
        ["name"~"{pattern}", i]
        [highway];
    out tags;
    """
    tag = f"[overpass-enrich] '{road['name']}' (pattern={pattern!r}, radius={search_radius}m)"
 
    elements = None
    for mirror in OVERPASS_MIRRORS[:2]:
        try:
            r = requests.post(
                mirror,
                data=query.encode("utf-8"),
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "Accept": "application/json",
                    "User-Agent": "site-scoring-tool/0.1",
                },
                timeout=9,
            )
            r.raise_for_status()
            elements = r.json().get("elements", [])
            print(f"{tag}: {mirror} -> HTTP {r.status_code}, {len(elements)} element(s) matched")
            if elements:
                break
            # 0 elements from this mirror isn't necessarily wrong (OSM data
            # is the same across mirrors), but a second mirror is cheap
            # insurance against a stale/lagging replica -- keep trying.
        except Exception as e:
            print(f"{tag}: {mirror} FAILED - {type(e).__name__}: {e}")
            continue
 
    if not elements:
        return road  # best-effort only -- both mirrors failed or found nothing
 
    best_tags, best_rank = None, _class_rank(road["highway"])
    for el in elements:
        tags = el.get("tags", {})
        hw = tags.get("highway")
        if not hw:
            continue
        rank = _class_rank(hw)
        if rank > best_rank or (rank == best_rank and (tags.get("lanes") or tags.get("maxspeed"))):
            best_rank, best_tags = rank, tags
 
    if not best_tags:
        print(f"{tag}: no element had a usable highway tag beating rank {best_rank} "
              f"-> leaving road unchanged (raw elements: "
              f"{[el.get('tags', {}) for el in elements][:5]})")
        return road
 
    enriched = dict(road)
    if road.get("lanes") is None and best_tags.get("lanes"):
        enriched["lanes"] = best_tags["lanes"]
    if road.get("maxspeed") is None and best_tags.get("maxspeed"):
        enriched["maxspeed"] = best_tags["maxspeed"]
    if best_tags.get("highway") and _class_rank(best_tags["highway"]) > _class_rank(road["highway"]):
        enriched["highway"] = best_tags["highway"]
    print(f"{tag}: enriched {road} -> {enriched} (best_tags={best_tags})")
    return enriched
 
 
def find_nearby_roads_no_overpass(state_abbr, lat, lon, n=num_roads, radius_m=road_search_rad, max_radius_m=640):
    """Replaces the OSM/Overpass lookup as the REQUIRED path: try the state
    DOT's own roadway layer first (best -- same system as the AADT layer,
    sometimes with real lanes/speed like Ohio's), then top up with Census
    TIGER roads if that didn't return enough candidates.
 
    Widens the search radius (doubling, up to max_radius_m) when there
    still aren't n distinct roads -- dot_road_candidates_near has no
    widening of its own, and a fixed 80m radius routinely misses the
    actual major cross streets a plaza sits between: a shopping center's
    parking lot commonly sets the building/address point 100-300m+ back
    from the real bounding arterials, so without this a report was
    finding one minor access road and stopping instead of the two major
    streets a person would actually describe the site by. (The retired
    Overpass-based find_nearby_roads() below had this same escalation --
    it was dropped when this function replaced it.)
 
    Finally, if the resulting roads would tie (identical class/lanes/
    speed -- happens in states like AZ/TX whose DOT data doesn't cover
    city streets and whose TIGER classification is too coarse to tell two
    local streets apart), makes one best-effort Overpass enrichment pass
    per road to see if OSM has something finer. See _enrich_road_via_
    overpass's docstring for why this can't reintroduce the reliability
    problems that got Overpass removed from the required path.
    """
    roads = dot_road_candidates_near(state_abbr, lat, lon, radius_m) if state_abbr else []
    if len(roads) < n:
        seen_names = {r["name"] for r in roads}
        extra = find_nearby_roads_tiger(lat, lon, n=n - len(roads), radius_m=radius_m)
        roads.extend(r for r in extra if r["name"] not in seen_names)
 
    if len(roads) < n and radius_m < max_radius_m:
        return find_nearby_roads_no_overpass(
            state_abbr, lat, lon, n=n, radius_m=radius_m * 2, max_radius_m=max_radius_m
        )
 
    roads.sort(key=lambda r: _class_rank(r["highway"]), reverse=True)
    roads = roads[:n]
 
    if _roads_tied(roads):
        print(f"[adjacent_est] tie detected near ({lat},{lon}) state={state_abbr}: "
              f"{[(r['name'], r['highway'], r.get('lanes'), r.get('maxspeed')) for r in roads]} "
              f"-> attempting Overpass enrichment")
        roads = [_enrich_road_via_overpass(r, lat, lon, radius_m) for r in roads]
        print(f"[adjacent_est] post-enrichment: "
              f"{[(r['name'], r['highway'], r.get('lanes'), r.get('maxspeed')) for r in roads]}")
 
        if _roads_tied(roads):
            # DOT data, TIGER, and a best-effort OSM lookup all failed to
            # tell these roads apart -- there's no real basis to report them
            # as two separate numbers, so keep only the one physically
            # closest to the site and drop the other(s) in the tied group,
            # rather than showing duplicate "independent" estimates.
            print(f"[adjacent_est] tie UNRESOLVED after enrichment near ({lat},{lon}) "
                  f"state={state_abbr}: {[r['name'] for r in roads]} -> keeping closest only")
            roads = _collapse_tied_roads(roads)
            print(f"[adjacent_est] after collapsing tie: {[r['name'] for r in roads]}")
 
    return roads
 
 
def _collapse_tied_roads(roads):
    """For each group of roads sharing an identical (highway, lanes,
    maxspeed) -- i.e. a tie that survived Overpass enrichment -- keep only
    the one physically closest to the query point (distance_m) and drop the
    rest. A road with unknown distance (no usable geometry) is treated as
    farthest, so a road we can actually measure is always preferred.
    """
    groups = {}
    order = []
    for r in roads:
        key = (r["highway"], r.get("lanes"), r.get("maxspeed"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
 
    kept = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            kept.append(group[0])
        else:
            original_best = min(group, key=lambda r: r["distance_m"] if r.get("distance_m") is not None else float("inf"))
            # Note that this road was kept over an indistinguishable
            # neighbor, so the report can say why only one road shows up
            # here instead of the usual two.
            best = dict(original_best)
            best["_tie_resolved_by_proximity"] = [r["name"] for r in group if r is not original_best]
            kept.append(best)
    return kept
 
 
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
            route = _safe_str(a.get(route_field)) if route_field else ""
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
        route = _safe_str(a.get(roadway["route_field"]))
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
 
                dropped = road.get("_tie_resolved_by_proximity")
                if dropped:
                    # DOT/TIGER/OSM all failed to distinguish this road from
                    # one or more nearby candidates -- rather than show
                    # duplicate "independent" numbers, only the closest of
                    # the tied roads is reported here; say so explicitly.
                    others = ", ".join(dropped)
                    source_detail = (
                        f"{no_measured_reason} - classification indistinguishable from nearby "
                        f"{'road' if len(dropped) == 1 else 'roads'} ({others}); showing the "
                        f"closer one only (±{medape:.0f}% typical error)"
                    )
                    confidence = "low"
                else:
                    source_detail = f"{no_measured_reason} - est. ±{medape:.0f}% typical error"
 
                results.append({
                    "road_name": road["name"],
                    "road_class": road["highway"],
                    "aadt": est["aadt"],
                    "source": "estimated",
                    "source_detail": source_detail,
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