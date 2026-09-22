from pathlib import Path
import functools

import pandas as pd
from geopy.distance import geodesic

locations_csv = Path(__file__).parent / "existing_madyolks.csv"

@functools.lru_cache(maxsize=1)
def _load_functions():
    if not locations_csv.exists():
        return {}
    df = pd.read_csv(locations_csv)
    required = {"name", "address", "city", "state", "zip", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"existing_madyolks.csv is missing columns: {missing}")
    df = df.dropna(subset=["lat", "lon"])
    return df.to_dict(orient="records")

def nearest_madyolks_locations(lat,lon,n=7):
    if lat is None or lon is None:
        return []
    locations = _load_functions()
    if not locations:
        return []
    enriched = []
    for loc in locations:
        try:
            d = geodesic((lat,lon), (loc["lat"], loc["lon"])).miles
        except Exception:
            continue
        enriched.append({
            "name": loc["name"],
            "address": loc["address"],
            "city": loc["city"],
            "state": loc["state"],
            "zip": loc["zip"],
            "distance_mi": round(d, 2)
        })
    enriched.sort(key=lambda r: r["distance_mi"])
    return enriched[:n]
if __name__ == "__main__":
    import json
    result = nearest_madyolks_locations(33.2435,-96.8643,n=7)
    print(json.dumps(result, indent=2))