import os
import time
import requests
import pandas as pd

input_csv = "centercheck_stats_-_Sheet1__1_.csv"
output_xlsx = "centercheck_stats_geocoded.xlsx"

address_col = "Address"
city_col = "City"
state_col = "State"
lat_col = "Latitude"
lon_col = "Longitude"
status_col = "Geocode_Status"
notes_col = "Geocode_Notes"
regeocode_all = False
save_every = 250

api_key = "AIzaSyAGo2sHxjGYYlP2UNFtK59vNu7Ruvgi5O4"
geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
def geocode(address, city, state, retries = 3):
    full_address = f"{address}, {city}, {state}"
    params = {"address": full_address, "components": "country:US", "key": api_key}

    for attempt in range(retries):
        try:
            r = requests.get(geocode_url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None, None, "REQUEST_FAILED", f"{type(e).__name__}: {e}"

        status = data.get("status")

        if status == "OK" and data.get("results"):
            result = data["results"][0]
            loc = result["geometry"]["location"]
            lat, lon = loc["lat"], loc["lng"]

            returned_city, returned_state = None, None
            for comp in result.get("address_components", []):
                if "locality" in comp["types"]:
                    returned_city = comp["long_name"]
                if "administrative_area_level_1" in comp["types"]:
                    returned_state = comp["short_name"]

            notes = []
            if result.get("partial_match"):
                notes.append("partial match - Google could not match the address exactly")
            if returned_city and returned_city.lower() != str(city).strip().lower():
                notes.append(f"city mismatch: typed '{city}', Google matched '{returned_city}'")
            if returned_state and returned_state.lower() != str(state).strip().upper():
                notes.append(f"state mismatch: typed '{state}', Google matched '{returned_state}'")

            return lat, lon, "OK", "; ".join(notes)

        if status == "ZERO_RESULTS":
            return None, None, "ZERO_RESULTS", "no match found - check address/city/state for typos"

        if status == "OVER_QUERY_LIMIT":
            time.sleep(2 * (attempt + 1))
            continue

        return None, None, status, ""
    return None, None, "FAILED_AFTER_RETRIES", ""

def main():
    if not api_key:
        raise SystemExit(
            "set google api key"
        )
    df = pd.read_csv(input_csv)

    core_cols = ["Brand", "Plaza", "Address", "City", "State", "Revenue", "Ranking"]
    df = df[core_cols].copy()
    for col in (lat_col, lon_col, status_col):
        if col not in df.columns:
            df[col] = None

    if regeocode_all:
        needs_geocode = pd.Series(True, index=df.index)
    else:
        needs_geocode = df[lat_col].isna()

    total = needs_geocode.sum()
    print(f"{len(df)} total rows, {total} need geocoding")

    done = 0
    for i in df[needs_geocode].index:
        address = df.at[i, address_col]
        city = df.at[i,city_col]
        state = df.at[i,state_col]

        if pd.isna(address) or pd.isna(city) or pd.isna(state):
            df.at[i, status_col] = "Skipped_missing_input"
            continue

        lat, lon, status, notes = geocode(address, city, state)
        df.at[i, lat_col] = lat
        df.at[i, lon_col] = lon
        df.at[i, status_col] = status
        df.at[i, notes_col] = notes

        done += 1
        flag = f" -> {notes}" if notes else ""
        print(f"  [{done}/{total}] row {i}: {address}, {city}, {state} -> ({lat}, {lon}) [{status}] {flag}")

        if done % save_every == 0:
            df.to_excel(output_xlsx, index=False)
            print(f"  ...checkpoint saved at {done}/{total}")

        time.sleep(0.05)
    df.to_excel(output_xlsx, index=False)

    ok = (df[status_col] == "OK").sum()
    flagged = (df[notes_col].fillna("").fillna("") != "").sum()
    failed = len(df) - ok
    print(f"\nDone. {ok} geocoded successfully, {flagged} flagged for review, {failed} failed/skipped")
    print(f"saved to {output_xlsx}")

if __name__ == "__main__":
    main()
