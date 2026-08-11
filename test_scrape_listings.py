import sys
import time

from scraper import scrape_listings

known_plazas = [
    {
        "name": "Creekside Ridge",
        "address": "1025 Creekside Ridge Dr, Roseville, CA 95678",
        "city": "Roseville",
        "lat": 38.767356,
        "lng": -121.261355,
    },
    {
        "name": "211 Jefferson Street",
        "address": "211 Jefferson Street, San Francisco, CA",
        "city": "San Francisco",
        "lat": 37.8085,
        "lng": -122.4156,
    },
    {
        "name": "2530 Douglas Boulevard", 
        "address": "2530 Douglas Blvd, Roseville, CA",
        "city": "Roseville",
        "lat": 38.749,
        "lng": -121.245,
    },
    {
        "name": "Commonwealth Square",
        "address": "713-817 E. Bidwell Street, Folsom, CA 95630",
        "city": "Folsom",
        "lat": 38.6668,
        "lng": -121.1544,
    },
]

def summarize(plaza:dict):
    agents = plaza.get("agents",[])
    print(f"\n{'-'*60}")
    print(f"  Plaza:  {plaza['name']}")
    print(f"  Address: {plaza['address']}")
    print(f"{'-'*60}")

    if not agents:
        print("No agents attached")
        print("property or something in the pipeline did not link back")
        return
    
    print(f" {len(agents)} agent record(s) attached to plaza['agents']:")
    for a in agents:
        print(f"\n  Agent:  {a.get('agent_name') or 'n'}")
        print(f"    Brokerage: {a.get('brokerage') or '-'}")
        print(f"    Phone:  {a.get('phone') or '-'}")
        print(f"    Email:  {a.get('email') or '-'}")
        print(f"    URL:  {(a.get('listing_url') or '')[:80]}")

def main():
    run_all = len(sys.argv) > 1 and sys.argv[1].lower() == "all"
    plazas = known_plazas if run_all else known_plazas[:2]

    print(f"\n{'='*60}")
    print(f"  scrape listing test - {len(plazas)} plaza(s)")
    print(f"  (17 brokerages checked per plaza - might take a while)")
    print(f"{'='*60}")

    start = time.time()

    all_agents = scrape_listings(plazas, city="Roseville", state="CA")
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"\n{'='*60}")

    for plaza in plazas:
        summarize(plaza)

    print(f"\n{'='*60}")
    print(f" SANITY CHECKS")
    print(f"{'='*60}")
    print(f"  Total time:  {elapsed:.1f}s")
    print(f"  scrape_listings() return count: {len(all_agents)}")
    attached_count = sum(len(p.get("agents",[])) for p in plazas)
    print(f"  Sum of plazas['agents'] counts: {attached_count}")
    if attached_count != len(all_agents):
        print(" Mismatch - return value and per plaza attachment disagreements")
        print("  dedup key collision")
    else:
        print(" return value and per plaza attachment agee.")

    no_agents = [p["name"] for p in plazas if not p.get("agents")]
    if no_agents:
        print(f"\n Plazas with zero agents found: {no_agents}")
        print("if you expected a match right here, check over")

if __name__ == "__main__":
    main()