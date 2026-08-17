"""
Pull the 1,3,5 mile demographic profiles
Census Geocoder for addresses, lat & long
TIGERweb Rest for creating radii and blocking group geometries near point
ACS 5 year detailed tables for demographics by block group (zip)
(MAYBE) LEHD Lodes for employment counts by workplace for white and blue collar employees
"""
import os
import math
import requests
import pandas as pd
from functools import lru_cache
from geopy.distance import geodesic

CENSUS_KEY = os.getenv("CENSUS_API_KEY","0be3a0e2fd8c0e5bce91c7ecc632787c6d5449e5")
ACS_YEAR = 2024
LODES_YEAR = 2022
LODES_FALLBACK_YEAR = 2019

def geocode_address(address:str):
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json"
    }
    response = requests.get(url, params = params, timeout = 30)
    print("Status code:", response.status_code)
    print("Response text:", response.text[:500])
    r = response.json()
    matches = r["result"]["addressMatches"]
    if not matches:
        raise ValueError(f"could not geocode {address}")
    m = matches[0]
    coords = m["coordinates"]
    geos = m["geographies"]["2020 Census Blocks"][0]
    return {
        "lat": coords["y"],
        "lon": coords["x"],
        "state_fips": geos["STATE"],
        "county_fips": geos["COUNTY"],
        "tract": geos["TRACT"],
        "matched_address": m["matchedAddress"]
    }

def _bbox(lat,lon,radius_miles):
    #bounding box for a radius in miles around lat/lon
    #69 miles per degree of latitude/longitude
    dlat = radius_miles / 69.0
    dlon = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat

def block_groups_in_radius(lat,lon,radius_miles):
    #query through Tigerweb, this helps in the creation of the 5 mi rings
    minx,miny,maxx,maxy = _bbox(lat,lon,radius_miles)
    url = f"https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/1/query"
    params = {
        "where": "1=1",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "STATE,COUNTY,TRACT,BLKGRP,GEOID,CENTLAT,CENTLON",
        "returnGeometry": "false",
        "f": "json",
    }
    response = requests.get(url, params=params, timeout=60)
    print("TIGERweb URL:", response.url)
    print("TIGERweb status:", response.status_code)
    print("TIGERweb response (first 300 chars):", repr(response.text[:300]))
    r = response.json()
    rows = []
    for feat in r.get("features",[]):
        a = feat["attributes"]
        #check if the center of the block in the radius
        c_lat = float(a["CENTLAT"])
        c_lon = float(a["CENTLON"])
        dist = geodesic((lat,lon),(c_lat,c_lon)).miles
        if dist <= radius_miles:
            rows.append({
                "geoid": a["GEOID"],
                "state": a["STATE"],
                "county": a["COUNTY"],
                "tract": a["TRACT"],
                "bg": a["BLKGRP"],
                "dist_mi": dist,
            })
    return pd.DataFrame(rows)

def fetch_wfh_pct(state_fips, county_fips):
    base = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    params = {"get": "B08301_001E,B08301_021E,NAME", "for": f"county:{county_fips}", "in": f"state:{state_fips}", "key": CENSUS_KEY}
    r = requests.get(base,params=params, timeout=30).json()
    header,*rows=r
    if not rows:
        return None
    row = rows[0]
    total = float(row[header.index("B08301_001E")])
    wfh = float(row[header.index("B08301_021E")])
    if total <= 0:
        return None
    return round((wfh/total)*100,1)

#pull data from ACS
ACS_VARS = {
    #pop
    "B01003_001E": "pop_total",
    #Median Age
    "B01002_001E": "median_age",
    #Race
    "B03002_003E": "race_white",
    "B03002_004E": "race_black",
    "B03002_006E": "race_asian",
    #Hispanic, not in the race category
    "B03002_012E": "hispanic",
    #Median HH inc
    "B19013_001E": "median_hh_income",
    #Households
    "B11001_001E": "households_total",
    #Occupation Totals
    "C24010_001E": "occ_total",
    #White Collar
    "C24010_003E": "occ_mgmt_male",
    "C24010_039E": "occ_mgmt_female",
    # white collar = mgmt/bus/sci/arts/office/sales
    #blue collar = service/construction/maintenance/production
    "C24010_027E": "occ_sales_male",
    "C24010_063E": "occ_sales_female",
    "C24010_019E": "occ_service_male",
    "C24010_055E": "occ_service_female",
    "C24010_030E": "occ_natres_male",
    "C24010_066E": "occ_natres_female",
    "C24010_034E": "occ_prod_male",
    "C24010_070E": "occ_prod_female",

    "B25003_001E": "occupied_units",
    "B25003_003E": "renter_units"
}

def fetch_acs_for_state(state_fips,county_fips_list):
    #pulls acs data for all block groups in counties of a state. One API call per state.
    if not CENSUS_KEY:
        raise RuntimeError("set CENSUS_API_KEY env var (api.census.gov/data/key_signup.html)")
    var_str = ",".join(ACS_VARS.keys())
    base = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    out = []
    for cty in county_fips_list:
        params = {
            "get": var_str,
            "for": "block group:*",
            "in": f"state:{state_fips} county:{cty}",
            "key": CENSUS_KEY,
        }
        r = requests.get(base,params=params,timeout=120).json()
        header,*rows = r
        df = pd.DataFrame(rows,columns=header)
        out.append(df)
    df = pd.concat(out,ignore_index = True)
    df["geoid"] = df["state"] + df["county"] + df["tract"] + df["block group"]
    df = df.rename(columns = ACS_VARS)
    for col in ACS_VARS.values():
        df[col] = pd.to_numeric(df[col],errors="coerce")
    return df

def fetch_renter_pct(state_fips, county_fips):
    base = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    params = {
        "get": "B25003_001E,B25003_003E,NAME",
        "for": f"county:{county_fips}",
        "in": f"state:{state_fips}",
        "key": CENSUS_KEY,
    }
    r = requests.get(base,params=params, timeout=30).json()
    header,*rows=r
    if not rows:
        return None
    row = rows[0]
    total = float(row[header.index("B25003_001E")])
    renter = float(row[header.index("B25003_003E")])
    if total <= 0:
        return None
    return round((renter/total)*100,1)

#Employment data
@lru_cache(maxsize=8)
def fetch_lodes_wac(state_abbr:str):
    state_abbr = state_abbr.lower()
    blue_cols = ["CNS01","CNS02","CNS04","CNS05"]
    white_cols = ["CNS03","CNS06","CNS07","CNS08","CNS09","CNS10","CNS11","CNS12","CNS13","CNS14","CNS15","CNS16","CNS17","CNS18","CNS19","CNS20"]
    for year in (LODES_YEAR, LODES_FALLBACK_YEAR):
        url = f"https://lehd.ces.census.gov/data/lodes/LODES8/{state_abbr}/wac/{state_abbr}_wac_S000_JT00_{year}.csv.gz"
        try:
            df = pd.read_csv(url, compression="gzip", dtype={"w_geocode": str})
            if year != LODES_YEAR:
                print(f"  Note: {state_abbr.upper()} LODES not available for {LODES_YEAR}, using {year} instead")
            df["bg_geoid"] = df["w_geocode"].str[:12]
            df["blue_jobs"] = df[blue_cols].sum(axis=1)
            df["white_jobs"] = df[white_cols].sum(axis=1)
            agg = df.groupby("bg_geoid", as_index=False)[["C000", "blue_jobs", "white_jobs"]].sum()
            agg = agg.rename(columns={"C000": "jobs", "bg_geoid": "geoid"})
            return agg
        except Exception as e:
            if year == LODES_FALLBACK_YEAR:
                print(f"  WARNING: No LODES data available for {state_abbr.upper()} in any year. Returning empty employment data.")
                return pd.DataFrame(columns=["geoid", "jobs", "blue_jobs", "white_jobs"])
            continue  # try fallback year

STATE_FIPS_TO_ABBR = {"01": "al", "02": "ak", "04":"az", "05": "ar", "06": "ca", "08": "co", "09": "ct", "10": "de", "11": "dc", "12": "fl", "13": "ga", "15": "hi",
                      "16": "id", "17": "il", "18": "in", "19": "ia", "20": "ks", "21": "ky", "22": "la", "23": "me", "24": "md", "25": "ma", "26": "mi",
                      "27": "mn", "28": "ms", "29": "mo", "30": "mt", "31": "ne", "32": "nv", "33": "nh", "34": "nj", "35": "nm", "36": "ny",
                      "37": "nc", "38": "nd", "39": "oh", "40": "ok", "41": "or", "42": "pa", "44": "ri", "45": "sc", "46": "sd", "47": "tn", "48": "tx", "49": "ut",
                      "50": "vt", "51": "va", "53": "wa", "54": "wv", "55": "wi", "56": "wy"}


#calculate spending amounts from income
DINING_A = 5.6083
DINING_B = 0.5764
DISC_A = 2.7516
DISC_B = 0.7225

STATE_RPP_2023 = {
    "AL": 88.5, "AK": 105.4, "AZ": 102.0, "AR": 86.5, "CA": 112.6, "CO": 103.0,
    "CT": 107.4, "DE": 100.7, "DC": 110.8, "FL": 100.7, "GA": 95.5, "HI": 108.6,
    "ID": 94.6, "IL": 99.4, "IN": 90.4, "IA": 88.4, "KS": 90.5, "KY": 89.4,
    "LA": 91.2, "ME": 99.2, "MD": 106.6, "MA": 109.6, "MI": 92.7, "MN": 96.7,
    "MS": 87.3, "MO": 90.7, "MT": 95.0, "NE": 90.2, "NV": 99.4, "NH": 105.6,
    "NJ": 108.9, "NM": 92.0, "NY": 108.3, "NC": 95.5, "ND": 89.5, "OH": 89.9,
    "OK": 88.3, "OR": 102.6, "PA": 96.7, "RI": 100.5, "SC": 95.0, "SD": 88.1,
    "TN": 91.9, "TX": 96.6, "UT": 98.8, "VT": 102.6, "VA": 101.0, "WA": 107.7,
    "WV": 88.4, "WI": 92.0, "WY": 92.6,
}
FIPS_TO_STATE_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
RPP_ELASTICITY = 0.85
def state_rpp_multiplier(state_fips):
    abbr = FIPS_TO_STATE_ABBR.get(state_fips)
    rpp = STATE_RPP_2023.get(abbr,100.0)
    return (rpp/ 100.0) ** RPP_ELASTICITY

def estimate_dining_spending(median_hh_income, state_fips=None):
    if pd.isna(median_hh_income) or median_hh_income <= 0 or pd.isna(median_hh_income):
        return None
    #dining spend is about 3.4% of median hh income raised to the 0.92 power, based on BLS Consumer Expenditure Survey data
    base = DINING_A * (median_hh_income ** DINING_B)
    if state_fips:
        base *= state_rpp_multiplier(state_fips)
    return round(base,0)


def estimate_discretionary_spending(median_hh_income, state_fips=None):
    #(entertainment+apparell+dining+personal care)
    if pd.isna(median_hh_income) or median_hh_income <= 0 or pd.isna(median_hh_income):
        return None
    base = DISC_A * (median_hh_income ** DISC_B)
    if state_fips:
        base *= state_rpp_multiplier(state_fips)
    return round(base,0)

def aggregate_ring(bg_df,acs_df,lodes_df,state_fips=None, radius = 3):
    df=bg_df.merge(acs_df,on="geoid",how="left")
    df=df.merge(lodes_df,on="geoid",how="left")
    df["jobs"] = df["jobs"].fillna(0)
    
    pop =df["pop_total"].sum()
    households = df["households_total"].sum()
    jobs = df["jobs"].sum()

    valid_age = df[(df["median_age"] > 0) & (df["median_age"] < 120)]
    age_pop = valid_age["pop_total"].sum()
    w_age = float((valid_age["median_age"] * valid_age["pop_total"]).sum() / age_pop) if age_pop else None
    valid_inc = df[(df["median_hh_income"] >0 )& (df["median_hh_income"] < 1_000_000)]
    inc_hh = valid_inc["households_total"].sum()
    w_inc = float((valid_inc["median_hh_income"] * valid_inc["households_total"]).sum() / inc_hh) * 0.89 if inc_hh else None

    pct = lambda col: (df[col].sum()/pop * 100 if pop else None)
    white_pct = pct("race_white")
    black_pct = pct("race_black")
    asian_pct = pct("race_asian")
    hispanic_pct = pct("hispanic")

    
    df["white_jobs"] = df["white_jobs"].fillna(0)
    df["blue_jobs"] = df["blue_jobs"].fillna(0)
    white_jobs_total = df["white_jobs"].sum()
    blue_jobs_total = df["blue_jobs"].sum()
    wb_total = white_jobs_total + blue_jobs_total
    wc_pct = (white_jobs_total / wb_total * 100) if wb_total else None
    bc_pct = (blue_jobs_total / wb_total * 100) if wb_total else None

    workers_per_job = 0.88
    daytime_workers = jobs * workers_per_job
    daytime_pop = int(daytime_workers + max(pop-wb_total,0))

    dining = estimate_dining_spending(w_inc,state_fips = state_fips)
    disc = estimate_discretionary_spending(w_inc,state_fips = state_fips)

    return {
        "population": int(pop) if pop else 0,
        "daytime_population": daytime_pop,
        "median_age": round(w_age,1) if w_age else None,
        "white_pct": round(white_pct,1) if white_pct else None,
        "black_pct": round(black_pct,1) if black_pct else None,
        "hispanic_pct": round(hispanic_pct,1) if hispanic_pct else None,
        "asian_pct": round(asian_pct,1) if asian_pct else None,
        "employee_count": int(jobs),
        "white_collar_pct": round(wc_pct,1) if wc_pct else None,
        "blue_collar_pct": round(bc_pct,1) if bc_pct else None,
        "median_hh_income": int(w_inc) if w_inc else None,
        "hh_discretionary_spend": int(disc) if disc else None,
        "hh_dining_spend": int(dining) if dining else None,
        "n_block_groups": len(df),
    }

#now for 1/3/5 mi rings, we can pull the block groups in the radius, then aggregate for block groups
def profile_address(address:str, radii: list[float]| None=None):
    radii = sorted(set(radii)) if radii else [1,2,3,5]
    geo = geocode_address(address)
    lat,lon = geo["lat"], geo["lon"]
    wfh_pct = fetch_wfh_pct(geo["state_fips"], geo["county_fips"])
    renter_pct = fetch_renter_pct(geo["state_fips"],geo["county_fips"])

    bg_widest = block_groups_in_radius(lat,lon,max(radii))

    state_county = bg_widest.groupby("state")["county"].unique().to_dict()

    acs_frames = []
    lodes_frames = []
    for state, counties in state_county.items():
        acs_frames.append(fetch_acs_for_state(state,list(counties)))
        abbr = STATE_FIPS_TO_ABBR.get(state)
        if abbr:
            lodes_frames.append(fetch_lodes_wac(abbr))
    acs_df = pd.concat(acs_frames, ignore_index=True) if acs_frames else pd.DataFrame()
    lodes_df = pd.concat(lodes_frames,ignore_index=True) if lodes_frames else pd.DataFrame(columns=["geoid", "jobs"])

    rings = {}
    for r in radii:
        bg_r = bg_widest[bg_widest["dist_mi"] <= r].copy()
        rings[r] = aggregate_ring(bg_r, acs_df, lodes_df, state_fips=geo["state_fips"], radius=r)

    return {
        "address": geo["matched_address"],
        "lat": lat,
        "lon": lon,
        "renter_pct": renter_pct,
        "wfh_pct": wfh_pct,
        "rings": rings,
    }

if __name__ == "__main__":
    import json,sys
    addr = sys.argv[1] if len(sys.argv) > 1 else "1600 Pennsylvania Ave NW, Washington, DC 20500"
    print(json.dumps(profile_address(addr), indent=2))