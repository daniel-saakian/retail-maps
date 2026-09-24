import time
from io import StringIO
from pathlib import Path
 
import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import ElasticNetCV, LinearRegression
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error
 
_DATA_DIR = Path(__file__).resolve().parent
tgg_csv = str(_DATA_DIR / "existing_tgg.csv")
competitor_csv = str(_DATA_DIR / "competitors_2.csv")
output_csv = "tgg_model_u_scores.csv"
 
revenue_col = "est_yearly_p1p8"
earth_radius_miles = 3958.8
 
excluded_brands = ["Potbelly", "Firehouse Subs", "Target"]
 

new_brand_competitor_csv = str(_DATA_DIR / "competitors_nosales.csv")
new_brands = ["Nick The Greek", "The Kebab Shop", "Luna Grill"]
 

BRAND_AUV_OVERRIDES = {
    "Nick The Greek": 1400000,
    "The Kebab Shop": 840000,
    "Luna Grill": 1800000,
}
direct_competitor_brand = "CAVA"
anchor_brands = ["Trader Joe's", "Vons", "Albertsons", "Shaw's", "Safeway",
                 "H-E-B", "Acme Markets", "Stop & Shop", "Whole Foods"]
market_signal_brands = ["sweetgreen", "BIBIBOP", "Jersey Mike's", "Panera Bread", "Chipotle"]
candidate_radii_miles = [0.5, 1, 1.5, 2, 3, 5, 7, 10, 15]
 
# 2026 weekly actuals, period by period (4-4-5-4-4-5-4-3 so far)
week_period_map = {
    "p1": ["p1-1", "p1-2", "p1-3", "p1-4"],
    "p2": ["p2-1", "p2-2", "p2-3", "p2-4"],
    "p3": ["p3-1", "p3-2", "p3-3", "p3-4", "p3-5"],
    "p4": ["p4-1", "p4-2", "p4-3", "p4-4"],
    "p5": ["p5-1", "p5-2", "p5-3", "p5-4"],
    "p6": ["p6-1", "p6-2", "p6-3", "p6-4", "p6-5"],
    "p7": ["p7-1", "p7-2", "p7-3", "p7-4"],
    "p8": ["p8-1", "p8-2", "p8-3"],
}
week_cols = [c for cols in week_period_map.values() for c in cols]
min_weeks_for_reliable_annual = 8
 
# tourism proxy - confirmed working (Las Vegas 29.6%, Orlando 26.0%, Ann Arbor 12.3%)
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
BLS_QCEW_URL = "https://data.bls.gov/cew/data/api/{year}/a/area/{fips}.csv"
QCEW_YEAR = 2024
TOTAL_INDUSTRY_CODE = "10"
LEISURE_HOSPITALITY_CODE = "1026"
TOURISM_OWNERSHIP_CODE = "5"  # Private - industry breakdowns only published here
 
# optional U2 test only
format_col = "format"
visibility_col = "visibility"
min_stores_for_own_format_dummy = 4
 
 
# ---------------- Demographic composite (fair, isolated retest only) ----------------
affluence_ring_cols = {
    "med_hh_income": ["med hh income 1 mi", "med hh income 3 mi", "med hh income 5 mi"],
    "discretionary_spend": ["hh discretionary spend 1 mi", "hh discretionary spend 3 mi", "hh discretionary spend 5 mi"],
    "dining_spend": ["hh dining spend 1 mi", "hh dining spend 3 mi", "hh dining spend 5 mi"],
}
 
 
def collapse_ring_family(df, cols):
    z_scores = []
    for col in cols:
        vals = clean_numeric(df[col])
        z_scores.append((vals - vals.mean()) / vals.std())
    return pd.concat(z_scores, axis=1).mean(axis=1)
 
 
def compute_affluence_spend(tgg):
    """Household income + discretionary spend + dining spend, collapsed
    across the 1/3/5mi rings into one composite - the single most
    theoretically-motivated demographic signal for a premium fast-casual
    concept, tested here in isolation rather than bundled with the other
    6 demographic composites the way every prior (failed) test did it."""
    if not all(c in tgg.columns for cols in affluence_ring_cols.values() for c in cols):
        return None
    collapsed = {name: collapse_ring_family(tgg, cols) for name, cols in affluence_ring_cols.items()}
    return pd.concat(collapsed.values(), axis=1).mean(axis=1)
 
 
# ---------------- Revenue target (from P1-P8 weekly actuals) ----------------
def clean_numeric(series):
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = series.astype(str).str.replace(r"[\$,%]", "", regex=True).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")
 
 
def compute_weekly_based_annual(df, week_cols):
    weekly_clean = df[week_cols].apply(clean_numeric)
    avg_weekly = weekly_clean.mean(axis=1, skipna=True)
    median_weekly = weekly_clean.median(axis=1, skipna=True)
    min_weekly = weekly_clean.min(axis=1, skipna=True)
    max_weekly = weekly_clean.max(axis=1, skipna=True)
    n_weeks = weekly_clean.notna().sum(axis=1)
    return avg_weekly * 52, avg_weekly, median_weekly, min_weekly, max_weekly, n_weeks
 
 
# ---------------- Competitor proximity (CAVA + anchors only) ----------------
def clean_competitor_revenue(df):
    revenue = clean_numeric(df["Revenue"])
    for brand in df["Brand"].unique():
        mask = df["Brand"] == brand
        med = revenue[mask].median()
        if pd.notna(med) and med > 0:
            revenue[mask & (revenue > med * 15)] = np.nan
    return revenue
 
 
def normalize_brand(name):
    name = str(name).strip()
    return "Acme Markets" if name.lower() == "acme markets" else name
 
 
def load_competitors():
    comp = pd.read_csv(competitor_csv)
    comp.columns = comp.columns.str.strip()
    comp["Brand"] = comp["Brand"].apply(normalize_brand)
    comp = comp[~comp["Brand"].isin(excluded_brands)].copy()
    comp["revenue_clean"] = clean_competitor_revenue(comp)
    return comp.dropna(subset=["Latitude", "Longitude"])
 
 
def load_new_brand_competitors():
    try:
        df = pd.read_csv(new_brand_competitor_csv)
    except FileNotFoundError:
        print(f"  '{new_brand_competitor_csv}' not found - new-brand presence feature will be skipped.")
        print(f"  Run geocode_nosales_competitors.py to enable it.")
        return pd.DataFrame(columns=["Brand", "State", "Latitude", "Longitude"])
    ok = df["Geocode_Status"] == "OK"
    df = df[ok & df["Brand"].isin(new_brands)].copy()
    return df[["Brand", "State", "Latitude", "Longitude"]]
 
 
def haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return earth_radius_miles * 2 * np.arcsin(np.sqrt(a))
 
 
def compute_proximity_features(tgg_lat, tgg_lon, comp):
    dist = haversine_miles(
        tgg_lat.values.reshape(-1, 1), tgg_lon.values.reshape(-1, 1),
        comp["Latitude"].values.reshape(1, -1), comp["Longitude"].values.reshape(1, -1),
    )
    comp_revenue = np.nan_to_num(comp["revenue_clean"].values, nan=0.0)
    dist_floor = np.maximum(dist, 0.1)
    is_cava = (comp["Brand"] == direct_competitor_brand).values
    is_anchor = comp["Brand"].isin(anchor_brands).values
    is_market_signal = comp["Brand"].isin(market_signal_brands).values
 
    out = pd.DataFrame(index=range(len(tgg_lat)))
    diagnostics = []
    for radius in candidate_radii_miles:
        within = dist <= radius
        for label, mask in [("cava", is_cava), ("anchor", is_anchor), ("market_signal", is_market_signal)]:
            group_within = within & mask
            count_col, gravity_col = f"{label}_count_{radius}mi", f"{label}_gravity_{radius}mi"
            out[count_col] = group_within.sum(axis=1)
            out[gravity_col] = np.where(group_within, comp_revenue / dist_floor, 0).sum(axis=1)
            diagnostics.append((label, radius, count_col, gravity_col))
    return out, diagnostics
 
 
def pick_best_radius(proximity_df, revenue, diagnostics, label):
    print(f"\n{label.capitalize()} index - correlation with revenue by radius:")
    best_col, best_corr, best_radius, best_metric = None, 0, None, None
    for lbl, radius, count_col, gravity_col in diagnostics:
        if lbl != label:
            continue
        c_count = proximity_df[count_col].corr(revenue)
        c_gravity = proximity_df[gravity_col].corr(revenue)
        print(f"  {radius:>4} mi   count corr: {c_count:+.3f}   gravity corr: {c_gravity:+.3f}")
        if abs(c_count) > abs(best_corr):
            best_col, best_corr, best_radius, best_metric = count_col, c_count, radius, "count"
        if abs(c_gravity) > abs(best_corr):
            best_col, best_corr, best_radius, best_metric = gravity_col, c_gravity, radius, "gravity"
    print(f"  -> best: {best_col} (corr {best_corr:+.3f})")
    return best_col, best_radius, best_metric
 
 
# ---------------- Tourism proxy ----------------
def latlong_to_county_fips(lat, lon, retries=3):
    params = {"x": lon, "y": lat, "benchmark": "Public_AR_Current",
              "vintage": "Current_Current", "format": "json"}
    for attempt in range(retries):
        try:
            r = requests.get(CENSUS_GEOCODER_URL, params=params, timeout=15)
            r.raise_for_status()
            geographies = r.json().get("result", {}).get("geographies", {})
            for entries in geographies.values():
                if entries and "STATE" in entries[0] and "COUNTY" in entries[0]:
                    return f"{entries[0]['STATE']}{entries[0]['COUNTY']}"
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"  county lookup failed for ({lat},{lon}): {e}")
            return None
    return None
 
 
def fetch_leisure_hospitality_share(county_fips, year=QCEW_YEAR):
    if county_fips is None:
        return None
    try:
        r = requests.get(BLS_QCEW_URL.format(year=year, fips=county_fips), timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text), dtype=str)
        df["own_code"] = df["own_code"].astype(str).str.strip()
        df["industry_code"] = df["industry_code"].astype(str).str.strip()
        total_row = df[(df["own_code"] == TOURISM_OWNERSHIP_CODE) & (df["industry_code"] == TOTAL_INDUSTRY_CODE)]
        lh_row = df[(df["own_code"] == TOURISM_OWNERSHIP_CODE) & (df["industry_code"] == LEISURE_HOSPITALITY_CODE)]
        if total_row.empty or lh_row.empty:
            return None
        total_emp = float(total_row.iloc[0]["annual_avg_emplvl"])
        lh_emp = float(lh_row.iloc[0]["annual_avg_emplvl"])
        return lh_emp / total_emp if total_emp > 0 else None
    except Exception as e:
        print(f"  BLS QCEW lookup failed for county {county_fips}: {e}")
        return None
 
 
def compute_tourism_index(tgg_lat, tgg_lon):
    fips_cache, share_cache, shares = {}, {}, []
    for lat, lon in zip(tgg_lat, tgg_lon):
        key = (round(lat, 3), round(lon, 3))
        if key not in fips_cache:
            fips_cache[key] = latlong_to_county_fips(lat, lon)
            time.sleep(0.2)
        fips = fips_cache[key]
        if fips not in share_cache:
            share_cache[fips] = fetch_leisure_hospitality_share(fips)
            time.sleep(0.2)
        shares.append(share_cache[fips])
    return pd.Series(shares, index=range(len(tgg_lat)))
 
 
# ---------------- Optional: format/visibility (U2 test only) ----------------
def build_format_features(tgg_format, min_count=min_stores_for_own_format_dummy):
    counts = tgg_format.value_counts()
    eligible = counts[counts >= min_count].index
    grouped = tgg_format.where(tgg_format.isin(eligible), other="OTHER_FORMAT")
    return pd.get_dummies(grouped, prefix="format", drop_first=True).astype(float)
 
 
def build_visibility_feature(visibility_raw):
    vals = clean_numeric(visibility_raw)
    z = (vals - vals.mean()) / vals.std() if vals.std() > 0 else vals * 0
    return z.fillna(z.median())
 
 
# ---------------- Modeling ----------------
def run_loocv_elasticnet(X, y):
    loo = LeaveOneOut()
    preds = np.zeros(len(y))
    for train_idx, test_idx in loo.split(X):
        scaler = StandardScaler().fit(X.iloc[train_idx])
        X_train = scaler.transform(X.iloc[train_idx])
        X_test = scaler.transform(X.iloc[test_idx])
        model = ElasticNetCV(l1_ratio=[.1, .5, .7, .9, .95, 1], cv=5, random_state=0, max_iter=5000)
        model.fit(X_train, y.iloc[train_idx])
        preds[test_idx] = model.predict(X_test)
    return preds, r2_score(y, preds), mean_absolute_error(y, preds)
 
 
def fit_full_model(X, y):
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)
    model = ElasticNetCV(l1_ratio=[.1, .5, .7, .9, .95, 1], cv=5, random_state=0, max_iter=5000)
    model.fit(X_scaled, y)
    fitted = model.predict(X_scaled)
    coefs = pd.Series(model.coef_, index=X.columns).sort_values(key=abs, ascending=False)
    return fitted, coefs
 
 
def run_loocv_linear_calibration(actual, loocv_preds):
    n = len(actual)
    actual = np.asarray(actual)
    calibrated = np.zeros(n)
    for i in range(n):
        mask = np.arange(n) != i
        calibrator = LinearRegression().fit(loocv_preds[mask].reshape(-1, 1), actual[mask])
        calibrated[i] = calibrator.predict(loocv_preds[i].reshape(1, -1))[0]
    full_calibrator = LinearRegression().fit(loocv_preds.reshape(-1, 1), actual)
    return calibrated, full_calibrator
 
 
def empirical_prediction_interval(actual, loocv_preds, confidence):
    residuals = actual - loocv_preds
    alpha = 1 - confidence
    return (np.percentile(residuals, 100 * (alpha / 2)),
            np.percentile(residuals, 100 * (1 - alpha / 2)))
 
 
def score_from_fitted(new_fitted_values, reference_fitted_values):
    ref = np.asarray(reference_fitted_values)
    return np.array([(ref < v).mean() * 100 for v in np.atleast_1d(new_fitted_values)])
 
 
def top10_probability(fitted_values, actual, loocv_preds, top_n=10):
    threshold = np.sort(np.asarray(actual))[-top_n]
    residuals = np.asarray(actual) - np.asarray(loocv_preds)
    probs = np.array([(fv + residuals >= threshold).mean() for fv in np.atleast_1d(fitted_values)])
    return probs, threshold
 
 
def build_score_conditional_intervals(actual, loocv_preds, score, confidence_levels,
                                       quantile_breaks=(0.0, 0.2, 0.8, 1.0)):
    residuals = np.asarray(actual) - np.asarray(loocv_preds)
    score = np.asarray(score)
    bin_edges = np.quantile(score, quantile_breaks)
    bin_edges[0], bin_edges[-1] = -np.inf, np.inf
    n_bins = len(quantile_breaks) - 1
    bin_idx = np.digitize(score, bin_edges[1:-1])
 
    offsets = {}
    for b in range(n_bins):
        mask = bin_idx == b
        bin_residuals = residuals[mask]
        if len(bin_residuals) == 0:
            bin_residuals = residuals  # degenerate bin - fall back to global
        offsets[b] = {"n": int(mask.sum())}
        for conf in confidence_levels:
            alpha = 1 - conf
            offsets[b][conf] = (np.percentile(bin_residuals, 100 * (alpha / 2)),
                                 np.percentile(bin_residuals, 100 * (1 - alpha / 2)))
    return bin_edges, bin_idx, offsets
 
 
def main():
    tgg = pd.read_csv(tgg_csv)
    tgg.columns = tgg.columns.str.strip()
 
    revenue, avg_weekly, median_weekly, min_weekly, max_weekly, n_weeks = compute_weekly_based_annual(tgg, week_cols)
    tgg[revenue_col] = revenue
    tgg["meets_min_weeks"] = n_weeks >= min_weeks_for_reliable_annual
    valid = revenue.notna() & tgg["Latitude"].notna() & tgg["Longitude"].notna() & tgg["meets_min_weeks"]
    if valid.sum() < len(tgg):
        print(f"Dropping {len(tgg) - valid.sum()} rows missing revenue, coordinates, or below min weeks.")
    tgg, revenue = tgg[valid].reset_index(drop=True), revenue[valid].reset_index(drop=True)
    avg_weekly, median_weekly = avg_weekly[valid].reset_index(drop=True), median_weekly[valid].reset_index(drop=True)
    min_weekly, max_weekly = min_weekly[valid].reset_index(drop=True), max_weekly[valid].reset_index(drop=True)
 
    # diagnostic: how much would the annual figure change if median replaced
    # mean as the extrapolation basis? median*52 is NOT a valid sum estimate
    # (only mean*52 is), so this is shown as a sanity check on skew, not as
    # an alternative target - flags which stores have the most skewed weeks
    median_based_annual = median_weekly * 52
    pct_diff = ((revenue - median_based_annual) / revenue * 100)
    print(f"\nMean-based vs median-based annual estimate: mean absolute difference {pct_diff.abs().mean():.1f}% of revenue")
    biggest = pct_diff.abs().sort_values(ascending=False).head(5).index
    print("Stores with the most skewed weekly pattern (mean-based annual vs median-based):")
    print(tgg.loc[biggest, ["state", "city"]].assign(
        mean_based=revenue[biggest].round(0), median_based=median_based_annual[biggest].round(0)
    ).to_string(index=False))
 
    comp = load_competitors()
    print(f"Competitor file: {len(comp)} rows after excluding {excluded_brands}.")
 
    proximity_df, diagnostics = compute_proximity_features(tgg["Latitude"], tgg["Longitude"], comp)
    best_cava_col, best_cava_radius, best_cava_metric = pick_best_radius(proximity_df, revenue, diagnostics, "cava")
    best_anchor_col, best_anchor_radius, best_anchor_metric = pick_best_radius(proximity_df, revenue, diagnostics, "anchor")
    best_market_signal_col, _, _ = pick_best_radius(proximity_df, revenue, diagnostics, "market_signal")
 
    print("\nComputing tourism index (live Census + BLS QCEW lookups, cached by county)...")
    tourism_share = compute_tourism_index(tgg["Latitude"], tgg["Longitude"])
    if tourism_share.isna().any():
        print(f"  {tourism_share.isna().sum()} store(s) missing a tourism value - filled with portfolio median.")
    tourism_share = tourism_share.fillna(tourism_share.median())
    print(f"Tourism index - correlation with revenue: {tourism_share.corr(revenue):+.3f}")
 
    features = pd.DataFrame(index=range(len(tgg)))
    for name, col in [("cava_pressure", best_cava_col), ("anchor_cotenancy", best_anchor_col)]:
        vals = proximity_df[col]
        features[name] = (vals - vals.mean()) / vals.std()
    features["tourism_index"] = (tourism_share - tourism_share.mean()) / tourism_share.std()
    features = features.fillna(features.median())
 
    preds_u, r2_u, mae_u = run_loocv_elasticnet(features, revenue)
    fitted_u, coefs_u = fit_full_model(features, revenue)
    print(f"\n=== Model U: cava_pressure + anchor_cotenancy + tourism_index ===")
    print(f"LOOCV R^2: {r2_u:.3f}   LOOCV MAE: ${mae_u:,.0f}")
    print(coefs_u.to_string())
 
    # U2: fair retest of format/visibility against the ACTUAL current best,
    # not the old, noisy Model D baseline they lost to previously
    final_features, final_preds, final_fitted, final_name, final_r2, final_coefs = features, preds_u, fitted_u, "U", r2_u, coefs_u
    if format_col in tgg.columns and visibility_col in tgg.columns:
        tgg_format = tgg[format_col].astype(str).str.strip().str.lower()
        format_features = build_format_features(tgg_format)
        format_features.index = features.index
        visibility_features = pd.DataFrame(index=features.index)
        visibility_features["visibility_rating"] = build_visibility_feature(tgg[visibility_col]).values
 
        features_u2 = pd.concat([features, format_features, visibility_features], axis=1)
        features_u2.columns = features_u2.columns.astype(str)
        preds_u2, r2_u2, mae_u2 = run_loocv_elasticnet(features_u2, revenue)
        fitted_u2, coefs_u2 = fit_full_model(features_u2, revenue)
        print(f"\n=== Model U2: Model U + format + visibility ===")
        print(f"LOOCV R^2: {r2_u2:.3f}   LOOCV MAE: ${mae_u2:,.0f}   (vs Model U: {r2_u:.3f})")
        print(coefs_u2.to_string())
        if r2_u2 > r2_u:
            print("\nModel U2 beats Model U - using it for the saved output.")
            final_features, final_preds, final_fitted, final_name, final_r2, final_coefs = features_u2, preds_u2, fitted_u2, "U2", r2_u2, coefs_u2
        else:
            print("\nModel U still wins - using it for the saved output.")
 
    # U3: fair, isolated retest of the market-signal brands (sweetgreen,
    # BIBIBOP, Jersey Mike's, Panera Bread, Chipotle) against Model U
    # specifically - every prior test of these brands was bundled into much
    # larger, noisier feature sets where they were consistently zeroed out;
    # they never got the same fair, minimal shot format/visibility just got
    market_signal_vals = proximity_df[best_market_signal_col]
    market_signal_features = pd.DataFrame(index=features.index)
    market_signal_features["fast_casual_local_density"] = (
        (market_signal_vals - market_signal_vals.mean()) / market_signal_vals.std()
    )
    features_u3 = pd.concat([final_features, market_signal_features], axis=1)
    features_u3.columns = features_u3.columns.astype(str)
    preds_u3, r2_u3, mae_u3 = run_loocv_elasticnet(features_u3, revenue)
    fitted_u3, coefs_u3 = fit_full_model(features_u3, revenue)
    print(f"\n=== Model U3: {final_name} + market-signal proximity ===")
    print(f"LOOCV R^2: {r2_u3:.3f}   LOOCV MAE: ${mae_u3:,.0f}   (vs Model {final_name}: {final_r2:.3f})")
    print(coefs_u3.to_string())
    if r2_u3 > final_r2:
        print(f"\nModel U3 beats Model {final_name} - using it for the saved output.")
        final_features, final_preds, final_fitted, final_name, final_r2, final_coefs = features_u3, preds_u3, fitted_u3, "U3", r2_u3, coefs_u3
    else:
        print(f"\nModel {final_name} still wins - market-signal proximity does not help even in isolation.")
 
    # U4: fair, isolated retest of demographics - specifically the single
    # most theoretically-motivated composite (income + discretionary +
    # dining spend), against the ACTUAL current best. Every prior
    # demographic test (A, C, D, E, F, G, M, N) bundled 7 composites into
    # much larger, noisier feature sets - this is the fair shot they never got.
    affluence_spend = compute_affluence_spend(tgg)
    if affluence_spend is not None:
        affluence_features = pd.DataFrame(index=final_features.index)
        vals = affluence_spend
        affluence_features["affluence_spend"] = (vals - vals.mean()) / vals.std()
        affluence_features = affluence_features.fillna(affluence_features.median())
 
        features_u4 = pd.concat([final_features, affluence_features], axis=1)
        features_u4.columns = features_u4.columns.astype(str)
        preds_u4, r2_u4, mae_u4 = run_loocv_elasticnet(features_u4, revenue)
        fitted_u4, coefs_u4 = fit_full_model(features_u4, revenue)
        print(f"\n=== Model U4: {final_name} + affluence/spend composite ===")
        print(f"LOOCV R^2: {r2_u4:.3f}   LOOCV MAE: ${mae_u4:,.0f}   (vs Model {final_name}: {final_r2:.3f})")
        print(coefs_u4.to_string())
        if r2_u4 > final_r2:
            print(f"\nModel U4 beats Model {final_name} - using it for the saved output.")
            final_features, final_preds, final_fitted, final_name, final_r2, final_coefs = features_u4, preds_u4, fitted_u4, "U4", r2_u4, coefs_u4
        else:
            print(f"\nModel {final_name} still wins - affluence/spend does not help even in isolation.")
    else:
        print("\nModel U4 skipped - income/spend ring columns not found in this file.")
 
    new_brand_comp = load_new_brand_competitors()
    if len(new_brand_comp) > 0:
        dist_new_brand = haversine_miles(
            tgg["Latitude"].values.reshape(-1, 1), tgg["Longitude"].values.reshape(-1, 1),
            new_brand_comp["Latitude"].values.reshape(1, -1), new_brand_comp["Longitude"].values.reshape(1, -1),
        )
        new_brand_presence_raw = (dist_new_brand <= 1).sum(axis=1)
        new_brand_features = pd.DataFrame(index=final_features.index)
        vals = pd.Series(new_brand_presence_raw)
        new_brand_features["new_brand_presence"] = (vals - vals.mean()) / vals.std() if vals.std() > 0 else 0.0
        new_brand_features = new_brand_features.fillna(0)
        features_u5 = pd.concat([final_features, new_brand_features], axis=1)
        features_u5.columns = features_u5.columns.astype(str)
        preds_u5, r2_u5, mae_u5 = run_loocv_elasticnet(features_u5, revenue)
        fitted_u5, coefs_u5 = fit_full_model(features_u5, revenue)
        print(f"\n=== Model U5: {final_name} + new-brand presence (Nick The Greek/Kebab Shop/Luna Grill, 1mi) ===")
        print(f"LOOCV R^2: {r2_u5:.3f}   LOOCV MAE: ${mae_u5:,.0f}   (vs Model {final_name}: {final_r2:.3f})")
        print(coefs_u5.to_string())
        if r2_u5 > final_r2:
            print(f"\nModel U5 beats Model {final_name} - using it for the saved output.")
            final_features, final_preds, final_fitted, final_name, final_r2, final_coefs = features_u5, preds_u5, fitted_u5, "U5", r2_u5, coefs_u5
        else:
            print(f"\nModel {final_name} still wins - new-brand presence does not help on this run.")
    else:
        print("\nModel U5 skipped - new-brand competitor file not available.")
 
    print(f"\nFinal model before calibration check: {final_name}  LOOCV R^2: {final_r2:.3f}")
 
    is_degenerate = np.allclose(final_coefs.values, 0)
    if is_degenerate:
        print(f"Model {final_name} found no real signal (all coefficients are zero) - it's")
        print(f"effectively just predicting the average revenue for every site.")
        print(f"Skipping calibration: recalibrating a near-constant signal produces a")
        print(f"misleadingly high R^2 from leave-one-out arithmetic, not real accuracy.")
    else:
        lin_calibrated, full_linear = run_loocv_linear_calibration(revenue.values, final_preds)
        r2_lin = r2_score(revenue, lin_calibrated)
        if r2_lin > final_r2:
            print(f"\nLinear recalibration improves R^2 ({final_r2:.3f} -> {r2_lin:.3f}) - applying it.")
            final_preds = lin_calibrated
            final_fitted = full_linear.predict(final_fitted.reshape(-1, 1)).ravel()
            final_r2 = r2_lin
        else:
            print(f"\nLinear recalibration does not improve R^2 ({r2_lin:.3f} vs {final_r2:.3f}) - keeping uncalibrated.")
 
    print(f"\nFinal model: {final_name}  LOOCV R^2: {final_r2:.3f}")
 
    score = score_from_fitted(final_fitted, final_fitted)
    top10_probs, top10_threshold = top10_probability(final_fitted, revenue.values, final_preds, top_n=10)
    print(f"Top-10 revenue threshold: ${top10_threshold:,.0f}")
 
    out = tgg[["state", "city", "address"]].copy()
    # weekly view: actual historical weekly range for this specific location,
    # alongside the model's predicted range converted to weekly terms
    # (dividing the annual interval by 52) so both are on the same footing -
    # this is a presentation change only, not a new model: the underlying
    # prediction is still fit on annual revenue, just reported per-week here
    out["lowest_week_actual"] = min_weekly.round(0)
    out["highest_week_actual"] = max_weekly.round(0)
    out["avg_week_actual"] = avg_weekly.round(0)
    out["median_week_actual"] = median_weekly.round(0)
    out["predicted_weekly_revenue"] = (final_preds / 52).round(0)
    for conf in (0.75, 0.85, 0.90, 0.95):
        lo, hi = empirical_prediction_interval(revenue, final_preds, conf)
        out[f"pred_weekly_{int(conf*100)}pct_low"] = ((final_fitted + lo) / 52).round(0)
        out[f"pred_weekly_{int(conf*100)}pct_high"] = ((final_fitted + hi) / 52).round(0)
        print(f"{int(conf*100)}% empirical interval width (annual): ${hi - lo:,.0f}  (weekly: ${(hi - lo)/52:,.0f})")
    out["site_score_0_100"] = score.round(1)
    out["top10_probability_pct"] = (top10_probs * 100).round(1)
 
    quantile_breaks = (0.0, 0.2, 0.8, 1.0)
    bin_edges, bin_idx, score_bin_offsets = build_score_conditional_intervals(
        revenue.values, final_preds, score, [0.75, 0.85, 0.90, 0.95], quantile_breaks=quantile_breaks
    )
    n_bands = len(quantile_breaks) - 1
    band_labels = ["bottom 20%", "middle 60%", "top 20%"] if n_bands == 3 else [f"band {b}" for b in range(n_bands)]
    print(f"\nAggressive interval bands (n backing each band's estimate):")
    for b in range(n_bands):
        print(f"  {band_labels[b]}: n={score_bin_offsets[b]['n']}, score range ~[{bin_edges[b]:.0f}, {bin_edges[b+1]:.0f}]")
 
    shrink_factors = [1.0, 0.85, 0.70, 0.55, 0.40]
    print("\nShrink-factor tradeoff (aggressive interval, further tightened):")
    for conf in (0.75, 0.85, 0.90, 0.95):
        lo_arr = np.array([score_bin_offsets[b][conf][0] for b in bin_idx])
        hi_arr = np.array([score_bin_offsets[b][conf][1] for b in bin_idx])
        print(f"  {int(conf*100)}% nominal:")
        for s in shrink_factors:
            lo_s, hi_s = lo_arr * s, hi_arr * s
            low, high = final_fitted + lo_s, final_fitted + hi_s
            covered = ((revenue.values >= low) & (revenue.values <= high)).mean()
            width = (hi_s - lo_s).mean()
            print(f"    shrink={s:.2f}   avg width: ${width:,.0f}   coverage: {covered*100:.1f}% ({int(round(covered*len(revenue)))}/{len(revenue)})")
 
    SHRINK_FACTOR_USED = 1
    for conf in (0.75, 0.85, 0.90, 0.95):
        lo_arr = np.array([score_bin_offsets[b][conf][0] for b in bin_idx]) * SHRINK_FACTOR_USED
        hi_arr = np.array([score_bin_offsets[b][conf][1] for b in bin_idx]) * SHRINK_FACTOR_USED
        out[f"aggressive_pred_weekly_{int(conf*100)}pct_low"] = ((final_fitted + lo_arr) / 52).round(0)
        out[f"aggressive_pred_weekly_{int(conf*100)}pct_high"] = ((final_fitted + hi_arr) / 52).round(0)
 
    for col in final_features.columns:
        out[f"feature_{col}"] = final_features[col].values
    out.to_csv(output_csv, index=False)
    print(f"\nSaved per-store results to {output_csv}")
 
 
if __name__ == "__main__":
    main()