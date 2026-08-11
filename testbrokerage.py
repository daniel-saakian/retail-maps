import sys
import webbrowser
import os
from brokerages import find_listings, brokerage
 
# ── Test config ───────────────────────────────────────────────────────────────
# Change these or pass as command line args
DEFAULT_CITY  = "Roseville"
DEFAULT_STATE = "CA"
 
# Approximate coords — close enough for URL testing
# (doesn't need to be exact since we're just checking URL structure)
TEST_COORDS = {
    "Roseville, CA":    (38.7521, -121.2880),
    "Sacramento, CA":   (38.5816, -121.4944),
    "Chicago, IL":      (41.8781, -87.6298),
    "Dallas, TX":       (32.7767, -96.7970),
    "Los Angeles, CA":  (34.0522, -118.2437),
    "New York, NY":     (40.7128, -74.0060),
    "Seattle, WA":      (47.6062, -122.3321),
}
 
 
def get_coords(city: str, state: str) -> tuple:
    key = f"{city}, {state}"
    if key in TEST_COORDS:
        return TEST_COORDS[key]
    # Default fallback — center of US
    print(f"  [warn] No test coords for {key}, using US center as fallback")
    return (39.5, -98.35)
 
 
def run_test(city: str, state: str, open_browser: bool = False,
             save_report: bool = True):
 
    lat, lng = get_coords(city, state)
    location = f"{city}, {state}"
 
    print(f"\n{'='*65}")
    print(f"  Brokerage URL Test — {location}")
    print(f"  Coords: {lat}, {lng}")
    print(f"{'='*65}\n")
 
    results = find_listings(
        plaza_name     = f"Test Plaza in {location}",
        address        = f"123 Main St, {location}",
        lat            = lat,
        lng            = lng,
        radius_miles   = 0.5,
        location_label = location,
        city           = city,
        state          = state,
        specialties    = ["retail"],
    )
 
    # ── Print results ─────────────────────────────────────────────────────────
    scrapeable  = []
    js_rendered = []
    static_url  = []
 
    for name, data in results.items():
        url          = data["url"]
        scrape_type  = data["scrape_type"]
        tier         = data["tier"]
        owner_known  = data["owner_known"]
        owner        = data.get("owner") or "Unknown"
        status       = data["listing_status"]
 
        tier_label   = {-1: "SEARCH", 0: "AGG", 1: "T1", 2: "T2", 3: "T3"}.get(tier, "??")
        owner_label  = f"✅ {owner}" if owner_known else "❓ Unknown"
 
        line = (
            f"  [{scrape_type.upper():12}] [{tier_label}] {name}\n"
            f"    Owner:  {owner_label}\n"
            f"    Status: {status}\n"
            f"    URL:    {url[:90]}{'...' if len(url) > 90 else ''}\n"
        )
        print(line)
 
        if scrape_type in ("open", "semi_open"):
            scrapeable.append((name, data))
        elif scrape_type == "js_rendered" and url != data.get("website", ""):
            js_rendered.append((name, data))
        else:
            static_url.append((name, data))
 
    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  Summary for {location}:")
    print(f"    ✅ Open/semi-open (scrapeable):  {len(scrapeable)}")
    print(f"    ⚠️  JS-rendered (headless needed): {len(js_rendered)}")
    print(f"    🔗 Static base URL only:          {len(static_url)}")
    print(f"    📊 Total:                         {len(results)}")
    print(f"{'─'*65}\n")
 
    # ── Optionally open in browser ────────────────────────────────────────────
    if open_browser:
        print("\n  Opening scrapeable URLs in browser...")
        for name, data in scrapeable[:5]:  # limit to 5 to avoid tab explosion
            print(f"    → {name}")
            webbrowser.open(data["url"])
 
    # ── Save HTML report ──────────────────────────────────────────────────────
    if save_report:
        report_path = f"brokerage_test_{city.lower().replace(' ', '_')}_{state.lower()}.html"
        save_html_report(results, location, report_path)
        print(f"  📄 Report saved: {report_path}")
        if open_browser:
            webbrowser.open(f"file://{os.path.abspath(report_path)}")
 
    return results
 
 
def save_html_report(results: dict, location: str, path: str):
    """Save a clickable HTML report of all brokerage URLs."""
 
    rows = ""
    for name, data in results.items():
        url         = data["url"]
        scrape_type = data["scrape_type"]
        tier        = data["tier"]
        owner       = data.get("owner") or "Unknown"
        status      = data["listing_status"]
 
        color = {
            "open":        "#27AE60",
            "semi_open":   "#F39C12",
            "js_rendered": "#E74C3C",
        }.get(scrape_type, "#95A5A6")
 
        tier_label = {-1: "Search", 0: "Aggregator", 1: "Tier 1 Global",
                      2: "Tier 2 National", 3: "Tier 3 Regional"}.get(tier, "")
 
        rows += f"""
        <tr>
            <td><a href="{url}" target="_blank"><b>{name}</b></a></td>
            <td>{tier_label}</td>
            <td><span style="color:{color};font-weight:bold">{scrape_type}</span></td>
            <td>{owner}</td>
            <td>{status}</td>
            <td style="max-width:300px;word-break:break-all;font-size:11px">
                <a href="{url}" target="_blank">{url[:80]}{'...' if len(url) > 80 else ''}</a>
            </td>
        </tr>"""
 
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Brokerage URL Test — {location}</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
    h1   {{ color: #2C3E50; }}
    table {{ border-collapse: collapse; width: 100%; background: white;
              box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
    th   {{ background: #2C3E50; color: white; padding: 10px 12px;
             text-align: left; font-size: 13px; }}
    td   {{ padding: 9px 12px; border-bottom: 1px solid #eee; font-size: 13px; }}
    tr:hover td {{ background: #EBF5FB; }}
    a    {{ color: #2980B9; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .legend {{ margin: 16px 0; font-size: 13px; }}
    .dot {{ display:inline-block; width:12px; height:12px;
             border-radius:50%; margin-right:6px; }}
  </style>
</head>
<body>
  <h1>🏪 Brokerage URL Test — {location}</h1>
  <div class="legend">
    <span class="dot" style="background:#27AE60"></span> open — plain HTTP request works &nbsp;
    <span class="dot" style="background:#F39C12"></span> semi_open — may work with headers &nbsp;
    <span class="dot" style="background:#E74C3C"></span> js_rendered — headless browser needed
  </div>
  <table>
    <tr>
      <th>Brokerage</th>
      <th>Tier</th>
      <th>Scrape Type</th>
      <th>Owner</th>
      <th>Status Source</th>
      <th>URL Preview</th>
    </tr>
    {rows}
  </table>
  <p style="color:#999;font-size:12px;margin-top:16px">
    Click any brokerage name or URL to open the search in a new tab and verify it lands correctly.
  </p>
</body>
</html>"""
 
    with open(path, "w") as f:
        f.write(html)
 
 
# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    city  = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CITY
    state = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STATE
 
    # Pass --open as third arg to open URLs in browser
    open_browser = "--open" in sys.argv
 
    run_test(city, state, open_browser=open_browser, save_report=True)