import sys
from pathlib import Path
import numpy as np
import pandas as pd

_this_dir = Path(__file__).resolve().parent
_candidates = (_this_dir, _this_dir.parent, _this_dir.parent.parent, _this_dir.parent / "TGG")
for _candidate in _candidates:
    if (_candidate / "tgg_model.py").exists():
        sys.path.append(str(_candidate))

from tgg_model import clean_numeric, normalize_brand, haversine_miles
competitor_csv = str(_this_dir / "competitors_pb.csv")

pinkberry_primary_competitor_brands = [
    "Salt & Straw", "Jeni's", "Handel's", "Menchie's"
]

def load_pinkberry_competitor():
    comp = pd.read_csv(competitor_csv)
    comp.columns = comp.columns.str.strip()
    comp = comp.rename(columns={
        "brand": "Brand", "sales": "Revenue", "lat": "Latitude", "lon": "Longitude", "address": "Address", "city": "City", "state": "State", "zip": "Zip"
    })
    comp["Brand"] = comp["Brand"].apply(normalize_brand)

    revenue = clean_numeric(comp["Revenue"])
    for brand in comp["Brand"].unique():
        mask = comp["Brand"] == brand
        med = revenue[mask].median()
        if pd.notna(med) and med > 0:
            revenue[mask & (revenue > med * 15)] = np.nan
    comp["revenue_clean"] = revenue
    comp = comp.dropna(subset=["Latitude", "Longitude"])

    state_col = comp["State"].astype(str).str.strip().str.upper()
    rank_display = pd.Series(None, index = comp.index, dtype = object)
    for brand in comp["Brand"].unique():
        brand_mask = (comp["Brand"] == brand).values
        for state in state_col[brand_mask].unique():
            group_mask = brand_mask & (state_col == state).values
            group_idx = comp.index[group_mask]
            group_revenue = comp.loc[group_idx, "revenue_clean"]
            n = group_revenue.notna().sum()
            if n == 0:
                continue
            ranks = group_revenue.rank(ascending=False, method="min")
            for idx in group_idx:
                r = ranks.loc[idx]
                if pd.notna(r):
                    rank_display.loc[idx] = f"Rank #{int(r)} of {n} in {state}"
    comp["rank_display"] = rank_display
    return comp

if __name__ == "__main__":
    comp = load_pinkberry_competitor()
    print(f"Loaded {len(comp)} rows.")
    print(comp.groupby("Brand")["revenue_clean"].apply(lambda s: f"{s.notna().sum()}/{len(s)} have sales data"))