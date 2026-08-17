import csv
import os

LSAD_SUFFIXES = {
    "00": "",
    "21": "borough",
    "25": "city",
    "37": "minicipality",
    "43": "town",
    "47": "village",
    "53": "city and borough",
    "55": "comunidad",
    "57": "CDP",
    "62": "zona urbana",
    "CG": "consolidated government",
    "CN": "corporation",
    "MG": "metropolitan government",
    "UC": "urban county",
    "UG": "unified government",
}


_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "2025_Gaz_place_national.txt")
_cache: dict | None = None

def strip_lsad_suffix(name:str, lsad: str) -> str:
    suffix = LSAD_SUFFIXES.get(lsad, "")
    if not suffix:
        return name.strip()
    if name.lower().endswith(" " + suffix.lower()):
        return name[: -(len(suffix) + 1)].strip()
    return name.strip()

def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()

def load_gazetteer(path:str | None = None) -> dict:
    global _cache
    if _cache is not None:
        return _cache
    
    path = path or _DEFAULT_PATH
    if not os.path.exists(path):
        _cache = {}
        return _cache
    
    gaz: dict = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            state = (row.get("USPS") or "").strip().upper()
            lsad = (row.get("LSAD") or "").strip()
            raw_name = (row.get("NAME") or "").strip()
            if not state or not raw_name:
                continue
            clean_name = strip_lsad_suffix(raw_name, lsad)
            try:
                lat = float(row["INTPTLAT"])
                lng = float(row["INTPTLONG"])
            except (KeyError, ValueError):
                continue

            key = (state, _norm(clean_name))
            existing = gaz.get(key)

            if existing is None or (existing["lsad"] == "57" and lsad != "57"):
                gaz[key] = {"name": clean_name, "lat": lat, "lng": lng, "lsad": lsad}
    
    _cache = gaz
    return gaz

def lookup_city(city: str, state:str, path: str | None = None):
    if not state:
        return None
    gaz = load_gazetteer(path)
    if not gaz:
        return None
    hit = gaz.get((state.strip().upper(), _norm(city)))
    if not hit:
        return None
    return hit["lat"], hit["lng"], f"{hit['name']}, {state.strip().upper()}"