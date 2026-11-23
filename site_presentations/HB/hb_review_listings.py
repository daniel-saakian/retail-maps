from __future__ import annotations

import math
import sys
from pathlib import Path

_HB_DIR = Path(__file__).resolve().parent
for _p in (_HB_DIR, _HB_DIR.parent.parent,):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

SEARCH_RADIUS_MI = 0.2
VIEW = "digest_inventory"

def _haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def _f(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None

def _client():
    import cache
    return cache.get_client()

def find_listings(lat: float, lon: float, radius_mi: float = SEARCH_RADIUS_MI, log=print) -> list[dict]:
    sb = _client()
    if not sb:
        log("  [listings] supabase not configured - skipping")
        return []
    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * max(0.2, math.cos(math.radians(lat))))
    try:
        rows = (sb.table(VIEW).select("*").eq("active", True)
                .gte("lat", lat-dlat).lte("lat", lat+dlat)
                .gte("lng", lon-dlon).lte("lng", lon+dlon)
                .limit(200).execute().data) or []
    except Exception as e:
        log(f"  [listings] {VIEW} query failed: {e}")
        return []

    rows = [r for r in rows if _f(r.get("lat")) is not None and _f(r.get("lng")) is not None]
    for r in rows:
        r["_distance_mi"] = round(_haversine_mi(lat, lon, _f(r["lat"]), _f(r["lng"])), 3)
    rows = [r for r in rows if r["_distance_mi"] <= radius_mi]
    rows.sort(key=lambda r: (r["_distance_mi"], -(r.get("sf_max") or 0)))

    # digest_inventory ids look like "space:14742"; the spaces table wants 14742
    def _space_id(r):
        raw = str(r.get("row_id") or "")
        tail = raw.split(":")[-1]
        return int(tail) if tail.isdigit() else None
    for r in rows:
        r["_space_id"] = _space_id(r) if (r.get("kind") or "space") == "space" else None
    space_ids = sorted({r["_space_id"] for r in rows if r["_space_id"] is not None})
    detail, props = {}, {}
    if space_ids:
        try:
            for s in sb.table("spaces").select("*").in_("id", space_ids).execute().data or []:
                detail[str(s["id"])] = s
        except Exception as e:
            log(f"  [listings] spaces detail unavailable: {e}")
        prop_ids = list({s.get("property_id") for s in detail.values() if s.get("property_id")})
        if prop_ids:
            try:
                for p in sb.table("properties").select("*").in_("id", prop_ids).execute().data or []:
                    props[str(p["id"])] = p
            except Exception as e:
                log(f"  [listings] properties detail unavailable: {e}")

    out = []
    for r in rows:
        s = detail.get(str(r.get("_space_id")), {}) if r.get("_space_id") is not None else {}
        p = props.get(str(s.get("property_id")), {}) if s else {}
        merged = {**r, **{k: v for k, v in s.items() if v not in (None, "", [])}}
        merged["_property"] = p
        out.append(_to_candidate(merged))
    return _dedupe_candidates(out)


def _dedupe_candidates(cands: list[dict]) -> list[dict]:
    """The same space is often listed by more than one source (legacy listings
    table + new scrapers, or one row per broker). Collapse identical ones, keep
    the one with the most usable fields, and say how many were merged."""
    groups: dict[tuple, list[dict]] = {}
    for c in cands:
        groups.setdefault(c["facts_key"], []).append(c)
    out = []
    for same in groups.values():
        best = dict(max(same, key=lambda c: (len(c["fields"]), -(c.get("distance_mi") or 0))))
        best["duplicates"] = len(same) - 1
        if best["duplicates"]:
            best["summary"] += f" (+{best['duplicates']} duplicate listing{'s' if best['duplicates'] > 1 else ''})"
        out.append(best)
    # spaces with real size/rent data first, then by distance
    out.sort(key=lambda c: (-min(len(c["fields"]), 3), c.get("distance_mi") or 0))
    for c in out:
        c.pop("facts_key", None)
    return out

def _annual_psf(rate, unit, sf):
    if rate is None:
        return None
    if unit == "sf_yr":
        return rate
    if unit == "sf_mo":
        return rate * 12
    if unit == "month" and sf:
        return rate * 12 / sf
    if unit == "year" and sf:
        return rate / sf
    return None

def _sf_text(lo, hi):
    if lo and hi and lo != hi:
        return f"{lo:,}-{hi:,} SF (divisible; confirm the size you're taking)"
    v = hi or lo
    return f"{v:,} SF" if v else None

def _to_candidate(r: dict):
    sf_lo, sf_hi = r.get("sf_min"), r.get("sf_max")
    sf_single = sf_hi if (sf_hi and (not sf_lo or sf_lo == sf_hi)) else None
    unit = r.get("rate_unit")
    base_lo = _annual_psf(_f(r.get("rate_min")), unit, sf_single)
    base_hi = _annual_psf(_f(r.get("rate_max")), unit, sf_single)
    nnn = _f(r.get("nnn_charges"))
    firm = r.get("brokerage") or "listing broker"
    src = f"asking, per {firm} listing"
    prop = r.get("_property") or {}

    v: dict = {}

    def put(fid, value, note=None):
        if value not in (None, ""):
            v[fid] = {"value": value, "source": "listing", "note": note}

    put("total_sf", _sf_text(sf_lo, sf_hi) and f"{_sf_text(sf_lo, sf_hi)} ({src})")
    if unit == "negotiable":
        put("base_rent_psf", f"Negotiable ({src})")
    elif base_lo is not None:
        rng = f"${base_lo:,.2f}" if base_hi in (None, base_lo) else f"${base_lo:,.2f}-${base_hi:,.2f}"
        lt = f", {r['lease_type']}" if r.get("lease_type") else ""
        put("base_rent_psf", f"{rng}/SF/yr{lt} ({src})")
    if nnn is not None:
        put("nnn_psf", f"${nnn:,.2f}/SF/yr ({src}; confirm current-year CAM/tax/insurance)")
    if base_lo is not None and nnn is not None and sf_single:
        put("annual_gross_rent", f"${(base_lo + nnn) * sf_single:,.0f} (calculated: asking base + NNN x {sf_single:,} SF)")

    dims = []
    if r.get("frontage_street"):
        dims.append(f"Frontage on {r['frontage_street']}")
    if r.get("corner"):
        dims.append("corner unit")
    if r.get("space_type"):
        dims.append(str(r["space_type"]))
    if dims:
        put("dimensions_frontage", "; ".join(dims) + " (per listing; add L x W from floor plan)")

    addr = r.get("address") or ""
    if r.get("suite"):
        addr = f"{addr}, Suite {r['suite']}" if addr else f"Suite {r['suite']}"
    put ("street_suite", addr or None)

    rep = ", ".join(x for x in [r.get("agent_name"), r.get("brokerage"), r.get("phone"), r.get("email")] if x)
    put("landlord_rep", rep or None, "Listing broker (represents the landlord).")

    if prop.get("parking_ratio"):
        extra = f", {prop['parking_spaces']:,} spaces" if prop.get("parking_spaces") else ""
        put("parking_ratio", f"{prop['parking_ratio']}/1,000 SF{extra} (per listing)")
    elif prop.get("parking_spaces"):
        put("parking_ratio", f"{prop['parking_spaces']:,} spaces (per listing; ratio not stated)")

    if r.get("signage"):
        put("alt_signage", f"Per listing: {r['signage']}. Confirm sign criteria with landlord.")
    cond = []
    if r.get("second_gen_restaurant"):
        cond.append("second-generation restaurant")
    if r.get("hood"):
        cond.append("hood in place")
    if r.get("grease_trap"):
        cond.append("grease trap/interceptor")
    if r.get("ceiling_height_ft"):
        cond.append(f"{r['ceiling_height_ft']:g} ft ceilings")
    if r.get("available_date"):
        cond.append(f"available {r['available_date']}")
    elif r.get("available_now"):
        cond.append("available now")
    if cond:
        put("delivery_condition", "Per listing (unverified): " + ", ".join(cond) + ". Confirm in LOI and with GC.")


    links = [x for x in [r.get("flyer_url") and f"Flyer: {r['flyer_url']}",
                         r.get("listing_url") and f"Listing: {r['listing_url']}"] if x]
    if links:
        put("attachments_link", " | ".join(links), "Listing links. Replace with your Drive folder.")

    rent_short = v.get("base_rent_psf", {}).get("value", "").split(" (")[0]
    sf_short = (_sf_text(sf_lo, sf_hi) or "").split(" (")[0]
    bits = [
        r.get("name") or "Unnamed center",
        f"Suite {r['suite']}" if r.get("suite") else None,
        sf_short or None,
        rent_short or None,
        firm,
    ]
    if not (sf_short or rent_short):
        bits.append("no size/rent on file")
    if r.get("kind") == "legacy":
        bits.append("older listing")
    summary = " | ".join(x for x in bits if x)
    facts_key = (
        (r.get("name") or "").strip().lower(), str(r.get("suite") or "").strip().lower(),
        sf_lo, sf_hi, _f(r.get("rate_min")), (firm or "").split(" - ")[0].strip().lower(),
    )

    return {
        "id": str(r.get("row_id")),
        "kind": r.get("kind"),
        "summary": summary,
        "facts_key": facts_key,
        "distance_mi": r.get("_distance_mi"),
        "center_name": r.get("name"),
        "listing_url": r.get("listing_url"),
        "flyer_url": r.get("flyer_url"),
        "photo_url": r.get("photo_url"),
        "facts": {k: r.get(k) for k in ("space_type", "street_facing", "street_facing_source", "frontage_street",
                                        "corner", "drive_thru", "patio", "signage", "second_gen_restaurant",
                                        "hood", "grease_trap", "description", "highlights") if r.get(k) not in (None, "", [])}
                 | ({"published_traffic": f"{prop['traffic_count']:,} on {prop.get('traffic_street') or 'adjacent road'}"}
                    if prop.get("traffic_count") else {}),
        "fields": v,
    }

if __name__ == "__main__":
    import json
    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    print(json.dumps(find_listings(lat, lon), indent=2, default=str))