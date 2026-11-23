import csv
import math
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import cache
from site_presentations import registry

router = APIRouter()

VIEW = "digest_inventory"
MAX_ROWS = 1000
# If the newest listing/space touch is older than this, the page warns that
# the nightly run(s) probably didn't happen.
STALE_RUN_HOURS = 36
# Closer than this to an existing brand store = possible cannibalization.
BRAND_OVERLAP_MI = 3.0

us_states = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", 
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)

_site_presentations_dir = Path(__file__).parent / "site_presentations"

_MISSING_VIEW_HINT = (
    "The digest_inventory view doesn't exist yet. Run "
    "migrations/2026-11-10_digest_inventory.sql once in the Supabase SQL editor."
)


class DigestListing(BaseModel):
    id: str
    kind: str  # "space" (new scraper) or "legacy" (older listings table)
    brokerage: Optional[str] = None
    agent_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    listing_url: Optional[str] = None
    flyer_url: Optional[str] = None
    photo_url: Optional[str] = None
    source: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    deactivated_at: Optional[str] = None
    # Space-only details (None for legacy listings)
    suite: Optional[str] = None
    listing_type: Optional[str] = None
    space_type: Optional[str] = None
    sf_min: Optional[int] = None
    sf_max: Optional[int] = None
    rate_min: Optional[float] = None
    rate_max: Optional[float] = None
    rate_unit: Optional[str] = None
    available_now: Optional[bool] = None


class DigestPlaza(BaseModel):
    id: str
    name: str
    city: str
    state: str
    county: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    anchor_names: Optional[str] = None
    num_anchors: int = 0
    num_tenants: int = 0
    score: Optional[float] = None
    property_type: Optional[str] = None
    nearest_brand_store: Optional[str] = None
    nearest_brand_store_mi: Optional[float] = None
    listings: list[DigestListing]


class DigestResponse(BaseModel):
    window_start: str
    generated_at: str
    last_run_at: Optional[str] = None
    run_is_stale: bool
    brand: Optional[str] = None
    brand_label: Optional[str] = None
    brand_store_count: int = 0
    brand_overlap_mi: float = BRAND_OVERLAP_MI
    new_listing_count: int
    # Total new in the window; new_listing_count is capped at MAX_ROWS.
    new_total: int = 0
    new_truncated: bool = False
    removed_listing_count: int
    active_listing_count: Optional[int] = None
    active_space_count: Optional[int] = None
    active_legacy_count: Optional[int] = None
    removed_tracking_enabled: bool = True
    new: list[DigestPlaza]
    removed: list[DigestPlaza]


class InventoryItem(DigestListing):
    group_id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    property_type: Optional[str] = None
    anchor_names: Optional[str] = None
    num_anchors: int = 0
    num_tenants: int = 0
    score: Optional[float] = None
    nearest_brand_store: Optional[str] = None
    nearest_brand_store_mi: Optional[float] = None


class InventoryResponse(BaseModel):
    items: list[InventoryItem]
    total: int
    limit: int
    offset: int
    brand: Optional[str] = None
    brand_label: Optional[str] = None
    brand_store_count: int = 0
    brand_overlap_mi: float = BRAND_OVERLAP_MI


def _haversine_mi(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _pick(row: dict, *names: str):
    lowered = {k.strip().lower(): v for k, v in row.items() if k}
    for n in names:
        v = lowered.get(n)
        if v not in (None, ""):
            return v
    return None


@lru_cache(maxsize=32)
def _brand_stores(folder: str) -> tuple[tuple[str, float, float], ...]:
    """Existing store coordinates from site_presentations/<Brand>/existing_*.csv."""
    brand_dir = _site_presentations_dir / folder
    stores = []
    for path in sorted(brand_dir.glob("existing_*.csv")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                lat = _pick(row, "lat", "latitude")
                lng = _pick(row, "lon", "lng", "long", "longitude")
                try:
                    lat, lng = float(lat), float(lng)
                except (TypeError, ValueError):
                    continue
                label = _pick(row, "name", "store", "location", "city") or "Existing store"
                city = _pick(row, "city")
                state = _pick(row, "state")
                if city and city not in label:
                    label = f"{label} ({city}{', ' + state if state else ''})"
                stores.append((str(label), lat, lng))
    return tuple(stores)


def _nearest(stores, lat, lng):
    if lat is None or lng is None or not stores:
        return None, None
    best = min(stores, key=lambda s: _haversine_mi(lat, lng, s[1], s[2]))
    return best[0], round(_haversine_mi(lat, lng, best[1], best[2]), 1)


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _db_error(e: Exception, what: str) -> HTTPException:
    msg = str(e)
    if "PGRST205" in msg or "does not exist" in msg or "Could not find the table" in msg:
        return HTTPException(503, _MISSING_VIEW_HINT)
    return HTTPException(500, f"Could not read {what}: {msg}")


def _listing_from_row(r: dict) -> DigestListing:
    return DigestListing(
        id=str(r.get("row_id")),
        kind=r.get("kind") or "space",
        brokerage=r.get("brokerage"),
        agent_name=r.get("agent_name"),
        phone=r.get("phone"),
        email=r.get("email"),
        listing_url=r.get("listing_url"),
        flyer_url=r.get("flyer_url"),
        photo_url=r.get("photo_url"),
        source=r.get("source"),
        first_seen_at=r.get("first_seen_at"),
        last_seen_at=r.get("last_seen_at"),
        deactivated_at=r.get("deactivated_at"),
        suite=r.get("suite"),
        listing_type=r.get("listing_type"),
        space_type=r.get("space_type"),
        sf_min=r.get("sf_min"),
        sf_max=r.get("sf_max"),
        rate_min=_to_float(r.get("rate_min")),
        rate_max=_to_float(r.get("rate_max")),
        rate_unit=r.get("rate_unit"),
        available_now=r.get("available_now"),
    )


def _group_rows(rows: list[dict], stores) -> list[DigestPlaza]:
    by_id: dict[str, DigestPlaza] = {}
    for r in rows:
        gid = str(r.get("group_id"))
        if gid not in by_id:
            lat, lng = _to_float(r.get("lat")), _to_float(r.get("lng"))
            near_name, near_mi = _nearest(stores, lat, lng)
            score = _to_float(r.get("score"))
            by_id[gid] = DigestPlaza(
                id=gid,
                name=r.get("name") or "Unnamed retail center",
                city=r.get("city") or "-",
                state=r.get("state") or "-",
                county=r.get("county"),
                address=r.get("address"),
                lat=lat,
                lng=lng,
                anchor_names=r.get("anchor_names"),
                num_anchors=r.get("num_anchors") or 0,
                num_tenants=r.get("num_tenants") or 0,
                score=round(score, 1) if score is not None else None,
                property_type=r.get("property_type"),
                nearest_brand_store=near_name,
                nearest_brand_store_mi=near_mi,
                listings=[],
            )
        by_id[gid].listings.append(_listing_from_row(r))
    return sorted(by_id.values(), key=lambda p: (p.state, p.city, p.name))


def _latest(sb, table: str) -> Optional[str]:
    try:
        rows = (sb.table(table).select("last_seen_at")
                  .order("last_seen_at", desc=True).limit(1).execute()).data or []
        return rows[0]["last_seen_at"] if rows else None
    except Exception:
        return None


def _count(sb, **eq) -> Optional[int]:
    try:
        q = sb.table(VIEW).select("row_id", count="exact").in_("state", us_states)
        for k, v in eq.items():
            q = q.eq(k, v)
        return q.limit(1).execute().count
    except Exception:
        return None


from api import require_full_access  # noqa: E402  (api.py imports this module after defining require_full_access)


@router.get("/api/digest", response_model=DigestResponse)
def get_digest(
    days: float = Query(1, gt=0, le=31, description="Look-back window in days"),
    brand: Optional[str] = Query(None, description="Brand code from the site-presentations registry"),
    user=Depends(require_full_access),
):
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")

    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()

    brand_cfg = registry.get_brand(brand) if brand else None
    if brand and not brand_cfg:
        raise HTTPException(404, f"unknown brand: '{brand}'")
    stores = _brand_stores(brand_cfg.folder) if brand_cfg else ()

    try:
        new_res = (sb.table(VIEW)
                     .select("*", count="exact")
                     .eq("active", True)
                     .in_("state", us_states)
                     .gte("first_seen_at", since)
                     .order("first_seen_at", desc=True)
                     .limit(MAX_ROWS)
                     .execute())
    except Exception as e:
        raise _db_error(e, "listings")
    new_rows = new_res.data or []
    new_total = new_res.count if new_res.count is not None else len(new_rows)

    # Removed/leased: only scraped spaces carry a deactivated_at.
    removed_rows: list[dict] = []
    try:
        removed_rows = (sb.table(VIEW)
                          .select("*")
                          .eq("active", False)
                          .in_("state", us_states)
                          .gte("deactivated_at", since)
                          .order("deactivated_at", desc=True)
                          .limit(MAX_ROWS)
                          .execute()).data or []
    except Exception:
        pass

    # The refresh is "fresh" if EITHER source was touched recently -- the
    # scraper writes spaces, the older loader writes listings.
    candidates = [c for c in (_latest(sb, "spaces"), _latest(sb, "listings")) if c]
    parsed = sorted(((dt, raw) for raw in candidates for dt in [_parse_ts(raw)] if dt), reverse=True)
    last_run_at = parsed[0][1] if parsed else None
    last_run_dt = parsed[0][0] if parsed else None
    run_is_stale = last_run_dt is None or (now - last_run_dt) > timedelta(hours=STALE_RUN_HOURS)

    active_space = _count(sb, active=True, kind="space")
    active_legacy = _count(sb, active=True, kind="legacy")
    active_total = None
    if active_space is not None or active_legacy is not None:
        active_total = (active_space or 0) + (active_legacy or 0)

    return DigestResponse(
        window_start=since,
        generated_at=now.isoformat(),
        last_run_at=last_run_at,
        run_is_stale=run_is_stale,
        brand=brand_cfg.code if brand_cfg else None,
        brand_label=brand_cfg.label if brand_cfg else None,
        brand_store_count=len(stores),
        new_listing_count=len(new_rows),
        new_total=new_total,
        new_truncated=new_total > len(new_rows),
        removed_listing_count=len(removed_rows),
        active_listing_count=active_total,
        active_space_count=active_space,
        active_legacy_count=active_legacy,
        removed_tracking_enabled=True,
        new=_group_rows(new_rows, stores),
        removed=_group_rows(removed_rows, stores),
    )


# column, descending
_SORTS = {
    "newest": ("first_seen_at", True),
    "updated": ("last_seen_at", True),
    "sf_desc": ("sf_hi", True),
    "sf_asc": ("sf_lo", False),
    "score": ("score", True),
}


def _words(q: Optional[str]) -> list[str]:
    if not q:
        return []
    cleaned = re.sub(r"[%_*\\,()]", " ", q)
    return [w[:40] for w in cleaned.split() if w][:8]


@router.get("/api/inventory", response_model=InventoryResponse)
def get_inventory(
    q: Optional[str] = Query(None, description="Words to match against center, address, city, anchors, brokerage, agent, suite"),
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    city: Optional[str] = Query(None, max_length=80),
    kind: Optional[str] = Query(None, pattern="^(space|legacy)$"),
    space_type: Optional[str] = Query(None, max_length=40),
    listing_type: Optional[str] = Query(None, pattern="^(lease|sublease|sale)$"),
    min_sf: Optional[int] = Query(None, ge=0),
    max_sf: Optional[int] = Query(None, ge=0),
    has_photo: bool = False,
    has_flyer: bool = False,
    active: bool = True,
    sort: str = Query("newest"),
    brand: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(require_full_access),
):
    sb = cache.get_client()
    if not sb:
        raise HTTPException(500, "Supabase not configured")
    if sort not in _SORTS:
        raise HTTPException(400, f"sort must be one of {', '.join(_SORTS)}")

    brand_cfg = registry.get_brand(brand) if brand else None
    if brand and not brand_cfg:
        raise HTTPException(404, f"unknown brand: '{brand}'")
    stores = _brand_stores(brand_cfg.folder) if brand_cfg else ()

    qb = sb.table(VIEW).select("*", count="exact").eq("active", active).in_("state", us_states)
    if state:
        qb = qb.eq("state", state.upper())
    city_words = _words(city)
    if city_words:
        qb = qb.ilike("city", "%" + " ".join(city_words) + "%")
    for w in _words(q):
        qb = qb.ilike("search_text", f"%{w.lower()}%")
    if kind:
        qb = qb.eq("kind", kind)
    if space_type:
        qb = qb.eq("space_type", space_type)
    if listing_type:
        qb = qb.eq("listing_type", listing_type)
    # "Size": a space matches if its size range overlaps what was asked for.
    if min_sf is not None:
        qb = qb.gte("sf_hi", min_sf)
    if max_sf is not None:
        qb = qb.lte("sf_lo", max_sf)
    if has_photo:
        qb = qb.not_.is_("photo_url", "null")
    if has_flyer:
        qb = qb.not_.is_("flyer_url", "null")

    col, desc = _SORTS[sort]
    qb = qb.order(col, desc=desc, nullsfirst=False).order("row_id").range(offset, offset + limit - 1)

    try:
        res = qb.execute()
    except Exception as e:
        raise _db_error(e, "listings")

    items = []
    for r in res.data or []:
        base = _listing_from_row(r)
        lat, lng = _to_float(r.get("lat")), _to_float(r.get("lng"))
        near_name, near_mi = _nearest(stores, lat, lng)
        score = _to_float(r.get("score"))
        items.append(InventoryItem(
            **base.model_dump(),
            group_id=str(r.get("group_id")),
            name=r.get("name") or "Unnamed retail center",
            address=r.get("address"),
            city=r.get("city"),
            state=r.get("state"),
            county=r.get("county"),
            lat=lat,
            lng=lng,
            property_type=r.get("property_type"),
            anchor_names=r.get("anchor_names"),
            num_anchors=r.get("num_anchors") or 0,
            num_tenants=r.get("num_tenants") or 0,
            score=round(score, 1) if score is not None else None,
            nearest_brand_store=near_name,
            nearest_brand_store_mi=near_mi,
        ))

    return InventoryResponse(
        items=items,
        total=res.count if res.count is not None else len(items),
        limit=limit,
        offset=offset,
        brand=brand_cfg.code if brand_cfg else None,
        brand_label=brand_cfg.label if brand_cfg else None,
        brand_store_count=len(stores),
    )