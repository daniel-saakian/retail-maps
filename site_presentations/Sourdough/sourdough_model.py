import sys
from pathlib import Path
 
import numpy as np
import pandas as pd
 
_this_dir = Path(__file__).resolve().parent
_candidates = (_this_dir, _this_dir.parent, _this_dir.parent.parent, _this_dir.parent / "TGG")
for _candidate in _candidates:
    if (_candidate / "tgg_model.py").exists():
        sys.path.append(str(_candidate))
 
from tgg_model import clean_numeric, clean_competitor_revenue, normalize_brand, haversine_miles
 
_competitor_csv_candidates = [_this_dir / "competitors_2.csv", _this_dir.parent / "TGG" / "competitors_2.csv"]
competitor_csv = str(next((p for p in _competitor_csv_candidates if p.exists()), _competitor_csv_candidates[0]))

sourdough_primary_competitor_brands = ["Jersey Mike's", "Panera Bread", "Firehouse Subs", "Potbelly"]
 

sourdough_excluded_brands = ["Target"]
 
 
def load_sourdough_competitors():
    comp = pd.read_csv(competitor_csv)
    comp.columns = comp.columns.str.strip()
    comp["Brand"] = comp["Brand"].apply(normalize_brand)
    comp = comp[~comp["Brand"].isin(sourdough_excluded_brands)].copy()
    comp["revenue_clean"] = clean_competitor_revenue(comp)
    comp = comp.dropna(subset=["Latitude", "Longitude"])
 
    state_col = comp["State"].astype(str).str.strip().str.upper()
    rank_display = pd.Series(None, index=comp.index, dtype=object)
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