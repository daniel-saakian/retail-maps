from __future__ import annotations
 
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable, Optional
 
# ============================================================== the record
 
 
@dataclass
class BrokerContact:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    profile_url: Optional[str] = None
 
 
@dataclass
class SpaceRecord:
    # identity (required)
    source: str                       # scraper name, e.g. "cbre", "buildout:lee-associates"
    source_listing_id: str            # stable per space: the site's id, or listing URL + suite
    brokerage: str
    address: str
 
    # property / location
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    county: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    property_name: Optional[str] = None
    property_type: Optional[str] = None
    center_type: Optional[str] = None
    anchors: list[str] = field(default_factory=list)
    tenants: list[str] = field(default_factory=list)
    building_sf: Optional[int] = None
    lot_acres: Optional[float] = None
    year_built: Optional[int] = None
    parking_spaces: Optional[int] = None
    parking_ratio: Optional[float] = None
    traffic_count: Optional[int] = None
    traffic_street: Optional[str] = None
    zoning: Optional[str] = None
 
    # the space
    suite: Optional[str] = None
    listing_type: str = "lease"       # lease | sublease | sale
    space_use: Optional[str] = None   # retail | restaurant | medical | office | flex
    space_type: Optional[str] = None  # inline | endcap | pad | freestanding | anchor | junior anchor | kiosk | second floor | other
    sf_min: Optional[int] = None
    sf_max: Optional[int] = None
    sf_text: Optional[str] = None     # raw size text; parsed into sf_min/sf_max if those are empty
    rate_min: Optional[float] = None
    rate_max: Optional[float] = None
    rate_unit: Optional[str] = None   # sf_yr | sf_mo | month | year | negotiable
    lease_type: Optional[str] = None  # NNN | Modified Gross | Full Service | Gross
    rate_text: Optional[str] = None   # raw rent text; parsed if rate fields are empty
    nnn_charges: Optional[float] = None
    sale_price: Optional[float] = None
 
    street_facing: Optional[str] = None        # yes | no | unknown  (left empty -> inferred from text)
    street_facing_source: Optional[str] = None # listing | inferred | ai | manual
    frontage_street: Optional[str] = None
    corner: Optional[bool] = None
    drive_thru: Optional[bool] = None
    patio: Optional[bool] = None
    signage: Optional[str] = None
    second_gen_restaurant: Optional[bool] = None
    hood: Optional[bool] = None
    grease_trap: Optional[bool] = None
    ceiling_height_ft: Optional[float] = None
 
    available_date: Optional[date] = None
    available_now: Optional[bool] = None
    description: Optional[str] = None
    highlights: list[str] = field(default_factory=list)
    listing_url: Optional[str] = None
    flyer_url: Optional[str] = None
    photo_urls: list[str] = field(default_factory=list)
 
    brokers: list[BrokerContact] = field(default_factory=list)
    raw: Optional[dict] = None        # the site's original record, kept for re-parsing
 
 
# ============================================================== text parsing
 
_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
STATE_CODES = set(_STATES.values())
 
 
def normalize_state(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    t = s.strip()
    if t.upper() in STATE_CODES:
        return t.upper()
    return _STATES.get(t.lower())
 
 
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
 
 
def _num(s: str) -> float:
    return float(s.replace(",", ""))
 
 
def parse_sf(text: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """'1,200 - 3,500 SF' -> (1200, 3500); '2,400 SF' -> (2400, 2400); '0.85 AC' -> (None, None)."""
    if not text:
        return None, None
    t = text.lower().replace("±", "").replace("+/-", "").replace("approx.", "")
    if re.search(r"\b(ac|acre|acres)\b", t) and not re.search(r"\b(sf|sq|square)", t):
        return None, None
    nums = [_num(n) for n in re.findall(_NUM, t)]
    nums = [n for n in nums if 50 <= n <= 5_000_000]
    if not nums:
        return None, None
    lo, hi = min(nums[:2]), max(nums[:2])
    return int(lo), int(hi)
 
 
def parse_rate(text: Optional[str]) -> dict:
    """'$32.00/SF/YR NNN' -> rate 32, unit sf_yr, lease NNN. 'Negotiable' / 'Call for pricing' -> negotiable."""
    out: dict = {}
    if not text:
        return out
    t = text.lower()
    if re.search(r"negotiable|call|contact|upon request|tbd|withheld|n/a", t) and not re.search(r"\$\s*\d", t):
        out["rate_unit"] = "negotiable"
    nums = [_num(n) for n in re.findall(r"\$\s*" + _NUM, t)] or [_num(n) for n in re.findall(_NUM, t)]
    nums = [n for n in nums if n > 0]
    if nums:
        out["rate_min"], out["rate_max"] = min(nums[:2]), max(nums[:2])
        if re.search(r"(/|per)\s*(sf|sq\.?\s*ft|square foot|ft)\s*(/|per)?\s*(mo|month)", t) or "sf/mo" in t:
            out["rate_unit"] = "sf_mo"
        elif re.search(r"(/|per)\s*(sf|sq\.?\s*ft|square foot|ft)", t) or "psf" in t or "sf/yr" in t:
            out["rate_unit"] = "sf_yr"
        elif re.search(r"(/|per)\s*(mo|month)", t):
            out["rate_unit"] = "month"
        elif re.search(r"(/|per)\s*(yr|year|annum)", t):
            out["rate_unit"] = "year"
        elif max(nums) < 200:
            out["rate_unit"] = "sf_yr"   # retail asking rents are almost always $/SF/yr
    for pat, name in ((r"\bnnn\b|triple net", "NNN"), (r"modified gross|\bmg\b", "Modified Gross"),
                      (r"full service|\bfsg?\b", "Full Service"), (r"\bgross\b", "Gross"), (r"\bnn\b", "NN")):
        if re.search(pat, t):
            out["lease_type"] = name
            break
    return out
 
 
_SPACE_TYPES = (
    (r"junior anchor|jr\.? anchor", "junior anchor"),
    (r"\banchor\b(?! tenant)", "anchor"),
    (r"end[\s-]?cap", "endcap"),
    (r"\bpad\b|outparcel|out[\s-]parcel|pad site", "pad"),
    (r"free[\s-]?standing|stand[\s-]?alone", "freestanding"),
    (r"second floor|2nd floor|upper level", "second floor"),
    (r"\bkiosk\b", "kiosk"),
    (r"in[\s-]?line\b", "inline"),
)
 
 
def infer_space_type(*texts: Optional[str]) -> Optional[str]:
    t = " ".join(x for x in texts if x).lower()
    for pat, name in _SPACE_TYPES:
        if re.search(pat, t):
            return name
    return None
 
 
_FACING_YES = re.compile(
    r"street[\s-]?front|street[\s-]?facing|fronts? on|frontage|visible from|visibility (on|from|to)|"
    r"hard corner|corner (location|lot|unit|space)|drive[\s-]?thru|drive[\s-]?through|pylon", re.I)
_FACING_NO = re.compile(
    r"interior (space|unit|suite)|rear (of|facing)|faces? (the )?(rear|parking garage|courtyard)|"
    r"no street (frontage|visibility)|lower level|below grade|basement|second floor|2nd floor", re.I)
 
 
def infer_street_facing(space_type: Optional[str], *texts: Optional[str]) -> tuple[str, Optional[str]]:
    """Best guess from the listing itself. Returns (yes|no|unknown, source)."""
    t = " ".join(x for x in texts if x)
    if space_type in ("pad", "freestanding", "endcap"):
        return "yes", "inferred"
    if _FACING_NO.search(t):
        return "no", "inferred"
    if _FACING_YES.search(t):
        return "yes", "inferred"
    if space_type == "second floor":
        return "no", "inferred"
    return "unknown", None
 
 
def _flag(pattern: str, text: str) -> Optional[bool]:
    return True if re.search(pattern, text, re.I) else None
 
 
def infer_features(text: str) -> dict:
    return {
        "drive_thru": _flag(r"drive[\s-]?(thru|through|up window)", text),
        "second_gen_restaurant": _flag(r"(second|2nd)[\s-]?gen(eration)?\b.{0,25}(restaurant|food|qsr|cafe|kitchen)|former (restaurant|qsr)|restaurant (build[\s-]?out|improvements) in place", text),
        "hood": _flag(r"\bhood\b", text),
        "grease_trap": _flag(r"grease (trap|interceptor)", text),
        "patio": _flag(r"\bpatio\b|outdoor (seating|dining)", text),
        "corner": _flag(r"hard corner|corner (location|lot|unit|space|suite)|signalized corner", text),
    }
 
 
_SUFFIXES = {
    "street": "st", "avenue": "ave", "road": "rd", "boulevard": "blvd", "drive": "dr", "parkway": "pkwy",
    "highway": "hwy", "lane": "ln", "court": "ct", "place": "pl", "circle": "cir", "trail": "trl",
    "square": "sq", "turnpike": "tpke", "north": "n", "south": "s", "east": "e", "west": "w",
    "suite": "", "ste": "", "unit": "", "building": "", "bldg": "",
}
 
 
def address_key(address: str, city: Optional[str], state: Optional[str]) -> str:
    """Normalized key so '1013 Galleria Blvd, Ste 200' and '1013 GALLERIA BOULEVARD' merge."""
    a = (address or "").lower()
    a = re.split(r",|#|\b(?:suite|ste|unit|bldg|building)\b", a)[0]
    words = [_SUFFIXES.get(w.strip("."), w.strip(".")) for w in re.findall(r"[a-z0-9.]+", a)]
    return "|".join([" ".join(w for w in words if w), (city or "").strip().lower(), (normalize_state(state) or "").lower()])
 
 
def finalize(rec: SpaceRecord) -> SpaceRecord:
    """Fill parsed/inferred fields from raw text, without overwriting what the scraper set."""
    rec.state = normalize_state(rec.state) or rec.state
    for f in ("building_sf", "year_built", "parking_spaces", "traffic_count", "sf_min", "sf_max"):
        v = getattr(rec, f)
        if v is not None and not isinstance(v, int):      # some feeds send 4784.0 or "258098.55"
            try:
                setattr(rec, f, int(round(float(str(v).replace(",", "")))) or None)
            except ValueError:
                setattr(rec, f, None)
    # A bad feed value (e.g. 4,305,560,000 SF) overflows the integer column and fails the
    # whole source's save -- treat anything past the column limit as "not provided".
    for f in ("building_sf", "year_built", "parking_spaces", "traffic_count", "sf_min", "sf_max"):
        v = getattr(rec, f)
        if isinstance(v, int) and abs(v) > 2_147_483_647:
            setattr(rec, f, None)
    if rec.sf_min is None and rec.sf_max is None:
        rec.sf_min, rec.sf_max = parse_sf(rec.sf_text)
    elif rec.sf_min is None:
        rec.sf_min = rec.sf_max
    elif rec.sf_max is None:
        rec.sf_max = rec.sf_min
    if rec.sf_min and rec.sf_max and rec.sf_min > rec.sf_max:
        rec.sf_min, rec.sf_max = rec.sf_max, rec.sf_min
 
    if rec.rate_min is None and rec.rate_max is None and rec.rate_unit is None:
        for k, v in parse_rate(rec.rate_text).items():
            setattr(rec, k, v)
    elif rec.lease_type is None and rec.rate_text:
        rec.lease_type = parse_rate(rec.rate_text).get("lease_type")
    if rec.rate_min is not None and rec.rate_max is None:
        rec.rate_max = rec.rate_min
 
    text = " ".join(x for x in [rec.suite, rec.description, " ".join(rec.highlights or []), rec.sf_text] if x)
    # listing titles often say the most ("2nd Gen QSR with Drive Through", "Endcap w/ Patio")
    title = " ".join(x for x in [rec.property_name, rec.property_type] if x)
    if not rec.space_type:
        rec.space_type = infer_space_type(text) or infer_space_type(title)
    if not rec.street_facing:
        rec.street_facing, rec.street_facing_source = infer_street_facing(rec.space_type, text)
    elif rec.street_facing in ("yes", "no") and not rec.street_facing_source:
        rec.street_facing_source = "listing"
    for k, v in infer_features(" ".join([text, title])).items():
        if getattr(rec, k) is None and v is not None:
            setattr(rec, k, v)
    return rec
 
 
# ============================================================== saving
 
_PROPERTY_FIELDS = ("name", "address", "city", "state", "zip", "county", "lat", "lng", "property_type",
                    "center_type", "anchors", "tenants", "building_sf", "lot_acres", "year_built",
                    "parking_spaces", "parking_ratio", "traffic_count", "traffic_street", "zoning")
_SPACE_FIELDS = ("suite", "listing_type", "space_use", "space_type", "sf_min", "sf_max", "rate_min", "rate_max",
                 "rate_unit", "lease_type", "nnn_charges", "sale_price", "street_facing", "street_facing_source",
                 "frontage_street", "corner", "drive_thru", "patio", "signage", "second_gen_restaurant", "hood",
                 "grease_trap", "ceiling_height_ft", "available_date", "available_now", "description",
                 "highlights", "listing_url", "flyer_url", "photo_urls")
 
# If a run finds far fewer spaces than were active before, the scraper is
# probably broken (site redesign, block) -- don't mark everything "removed".
MIN_SHARE_TO_DEACTIVATE = 0.5
 
 
def _clean(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        if v in (None, "", [], {}):
            continue
        out[k] = v
    return out
 
 
def _chunks(items: list, n: int = 200):
    for i in range(0, len(items), n):
        yield items[i:i + n]
 
 
def _upsert_grouped(sb, table: str, rows: list[dict], on_conflict: str) -> list[dict]:
    """Upsert rows in groups that share the same columns.
 
    A bulk upsert sends the union of all rows' columns, so a column missing from
    one row would be written as NULL and wipe what's stored. Grouping by column
    set means each row only updates the fields it actually has.
    """
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault(tuple(sorted(r)), []).append(r)
    out: list[dict] = []
    for cols, group in groups.items():
        for chunk in _chunks(group):
            out.extend(sb.table(table).upsert(chunk, on_conflict=on_conflict).execute().data or [])
    return out
 
 
def save_records(sb, source: str, records: Iterable[SpaceRecord], deactivate_missing: bool = True,
                 force_remove: bool = False) -> dict:
    """Upsert one scraper run's records. Returns counts for logging.
 
    `sb` is a supabase client using the service-role key (same as your other scripts).
    Spaces from this `source` that were active but not in this run are marked
    removed (active=false, deactivated_at=now), unless the run looks broken.
    force_remove=True skips that check -- for a run you've looked at and know is right
    (e.g. a scraper that now lists each suite instead of one row per property).
    """
    now = datetime.now(timezone.utc).isoformat()
    records = [finalize(r) for r in records if r.address and r.source_listing_id]
    for r in records:
        if r.source != source:
            raise ValueError(f"record source {r.source!r} doesn't match run source {source!r}")
 
    # brokerages
    firm_names = sorted({r.brokerage for r in records})
    firm_ids: dict[str, int] = {}
    if firm_names:
        sb.table("brokerages").upsert([{"name": n} for n in firm_names], on_conflict="name",
                                      ignore_duplicates=True).execute()
        for chunk in _chunks(firm_names):
            for row in sb.table("brokerages").select("id,name").in_("name", chunk).execute().data or []:
                firm_ids[row["name"]] = row["id"]
 
    # properties (merged by normalized address)
    by_key: dict[str, dict] = {}
    for r in records:
        key = address_key(r.address, r.city, r.state)
        prop = by_key.setdefault(key, {"address_key": key})
        values = {"name": r.property_name, **{f: getattr(r, f) for f in _PROPERTY_FIELDS if f != "name"}}
        for k, v in _clean(values).items():
            prop.setdefault(k, v)          # first non-empty value wins
    prop_ids: dict[str, int] = {}
    for row in _upsert_grouped(sb, "properties", list(by_key.values()), "address_key"):
        prop_ids[row["address_key"]] = row["id"]
 
    # existing spaces for this source (to count new vs refreshed)
    existing: dict[str, dict] = {}
    start = 0
    while True:
        page = (sb.table("spaces").select("id,source_listing_id,active,street_facing_source")
                  .eq("source", source).range(start, start + 999).execute().data or [])
        for row in page:
            existing[row["source_listing_id"]] = row
        if len(page) < 1000:
            break
        start += 1000
 
    # spaces
    space_rows = []
    for r in records:
        row = {f: getattr(r, f) for f in _SPACE_FIELDS}
        row = _clean(row)
        row.update({
            "property_id": prop_ids[address_key(r.address, r.city, r.state)],
            "brokerage_id": firm_ids.get(r.brokerage),
            "source": source,
            "source_listing_id": r.source_listing_id,
            "last_seen_at": now,
            "active": True,
            "deactivated_at": None,
            "raw": r.raw,
        })
        # first_seen_at is left out on purpose: set once by the database default on insert
        prev = existing.get(r.source_listing_id)
        if prev and prev.get("street_facing_source") in ("ai", "manual"):
            # a checked answer beats today's text guess
            row.pop("street_facing", None)
            row.pop("street_facing_source", None)
        space_rows.append(row)
    # de-duplicate within the run (same id listed twice on a site)
    space_rows = list({r["source_listing_id"]: r for r in space_rows}.values())
    space_ids: dict[str, int] = {}
    for row in _upsert_grouped(sb, "spaces", space_rows, "source,source_listing_id"):
        space_ids[row["source_listing_id"]] = row["id"]
 
    # brokers + links -- load this firm's known brokers once, match in memory, write in bulk
    fids = sorted({v for v in firm_ids.values() if v})
    known: dict[tuple, dict] = {}
    for chunk in _chunks(fids, 50):
        start = 0
        while True:
            page = (sb.table("brokers").select("id,brokerage_id,name,email,phone,title,profile_url")
                      .in_("brokerage_id", chunk).range(start, start + 999).execute().data or [])
            for row in page:
                known[(row["brokerage_id"], row["name"].strip().lower(), (row.get("email") or "").strip().lower())] = row
            if len(page) < 1000:
                break
            start += 1000
 
    wanted: dict[tuple, dict] = {}
    for r in records:
        fid = firm_ids.get(r.brokerage)
        for b in r.brokers:
            if not b.name or not b.name.strip():
                continue
            key = (fid, b.name.strip().lower(), (b.email or "").strip().lower())
            cur = wanted.setdefault(key, {"brokerage_id": fid, "name": b.name.strip(), "email": b.email})
            for f in ("phone", "title", "profile_url"):
                if getattr(b, f) and not cur.get(f):
                    cur[f] = getattr(b, f)
 
    to_insert = [_clean(v) for k, v in wanted.items() if k not in known]
    to_update = []
    for k, v in wanted.items():
        row = known.get(k)
        if row:
            changes = {f: v[f] for f in ("phone", "title", "profile_url") if v.get(f) and v.get(f) != row.get(f)}
            if changes:
                to_update.append({"id": row["id"], **changes})
    for chunk in _chunks(to_insert):
        for row in sb.table("brokers").insert(chunk).execute().data or []:
            known[(row["brokerage_id"], row["name"].strip().lower(), (row.get("email") or "").strip().lower())] = row
    for row in to_update:                     # usually only a handful per run
        sb.table("brokers").update({k: v for k, v in row.items() if k != "id"}).eq("id", row["id"]).execute()
 
    links = []
    for r in records:
        sid = space_ids.get(r.source_listing_id)
        if not sid:
            continue
        fid = firm_ids.get(r.brokerage)
        for order, b in enumerate(r.brokers):
            if not b.name or not b.name.strip():
                continue
            row = known.get((fid, b.name.strip().lower(), (b.email or "").strip().lower()))
            if row:
                links.append({"space_id": sid, "broker_id": row["id"], "sort_order": order})
    touched = list(space_ids.values())
    for chunk in _chunks(touched):
        sb.table("space_brokers").delete().in_("space_id", chunk).execute()
    links = list({(l["space_id"], l["broker_id"]): l for l in links}.values())
    for chunk in _chunks(links):
        sb.table("space_brokers").insert(chunk).execute()
 
    # removed / leased
    seen = set(space_ids)
    was_active = {k for k, v in existing.items() if v.get("active")}
    missing = [existing[k]["id"] for k in was_active - seen]
    deactivated = 0
    skipped_reason = None
    if deactivate_missing and missing:
        if not force_remove and was_active and len(seen & was_active) < MIN_SHARE_TO_DEACTIVATE * len(was_active):
            skipped_reason = (f"only {len(seen & was_active)} of {len(was_active)} previously active spaces "
                              f"found -- scraper may be broken, not marking any as removed")
        else:
            for chunk in _chunks(missing):
                sb.table("spaces").update({"active": False, "deactivated_at": now}).in_("id", chunk).execute()
            deactivated = len(missing)
 
    result = {
        "source": source,
        "records": len(records),
        "new": len(seen - set(existing)),
        "reactivated": len({k for k in seen & set(existing) if not existing[k].get("active")}),
        "refreshed": len(seen & was_active),
        "removed": deactivated,
        "properties": len(prop_ids),
    }
    if skipped_reason:
        result["warning"] = skipped_reason
    return result