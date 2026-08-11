import argparse
import os
import smtplib
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from curl_cffi import requests as curl_requests
from dotenv import load_dotenv
from supabase import create_client

from scraper import scrape_one_plaza,headers as scraper_headers

load_dotenv()


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set")
    return create_client(url, key)

def fetch_plazas(sb, city:str | None, state:str | None, skip_newer_than_hours:float | None=None) -> list[dict]:
    q = sb.table("plazas").select("id, name, address, city, state, lat, lng, radius_m, last_scraped_at")
    if city:
        q = q.eq("city", city)
    if state:
        q = q.eq("state", state)
    if skip_newer_than_hours is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=skip_newer_than_hours)).isoformat()
        q = q.or_(f"last_scraped_at.is.null,last_scraped_at.lt.{cutoff}")
    rows = q.execute().data or []
    return [r for r in rows if r.get("address") not in (None, "-") or (r.get("lat") and r.get("lng"))]

def upsert_listing(sb, plaza_id:str, record:dict, touched:set) -> bool:
    dedupe_key = "|".join([
        record.get("brokerage") or "",
        record.get("agent_name") or "",
        record.get("email") or record.get("phone") or record.get("listing_url") or "",
    ])

    existing = (
        sb.table("listings")
          .select("id")
          .eq("plaza_id", plaza_id)
          .eq("dedupe_key", dedupe_key)
          .limit(1)
          .execute()
    ).data

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        row_id = existing[0]["id"]
        sb.table("listings").update({
            "last_seen_at": now,
            "active": True,
            "listing_url": record.get("listing_url"),
        }).eq("id", row_id).execute()
        touched.add(row_id)
        return False
    else:
        inserted = sb.table("listings").insert({
            "plaza_id": plaza_id,
            "brokerage": record.get("brokerage"),
            "agent_name": record.get("agent_name"),
            "phone": record.get("phone"),
            "email": record.get("email"),
            "listing_url": record.get("listing_url"),
            "source": record.get("source"),
            "first_seen_at": now,
            "last_seen_at": now,
            "active": True,
        }).execute()
        if inserted.data:
            touched.add(inserted.data[0]["id"])
        return True
    
def mark_stale_inactive(sb,plaza_id:str, touched: set) -> int:
    rows = (
        sb.table("listings")
          .select("id")
          .eq("plaza_id", plaza_id)
          .eq("active", True)
          .execute()
    ).data or []
    stale_ids = [r["id"] for r in rows if r["id"] not in touched]
    for sid in stale_ids:
        sb.table("listings").update({"active": False}).eq("id", sid).execute()
    return len(stale_ids)

def send_summary_email(new_listings: list[dict]) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", user)
    email_to = os.getenv("EMAIL_TO")

    if not all([host,user,password,email_to]):
        print("  [email] SMTP env vars not fully set - skipping email")
        return
    
    if not new_listings:
        print("  [email] No new listings today - skipping email")
        return
    
    by_city = defaultdict(list)
    for l in new_listings:
        by_city[l["plaza_city"] or "Unknown city"].append(l)

    lines_html = [f"<h2>{len(new_listings)} new retail listing(s) found today</h2>"]
    lines_text = [f"{len(new_listings)} new retail listing(s) found today\n"]

    for city in sorted(by_city):
        lines_html.append(f"<h3>{city}</h3><ul>")
        lines_text.append(f"\n{city}\n{'-' * len(city)}")
        for l in by_city[city]:
            agent = l.get("agent_name") or "Unknown agent"
            contact = l.get("phone") or l.get("email") or "-"
            url = l.get("listing_url") or ""
            plaza = l.get("plaza_name") or "Unnamed Retail Center"
            lines_html.append(
                f"<li><b>{plaza}</b> &mdash; {l['brokerage']} / {agent} ({contact})"
                + (f' &mdash; <a href="{url}">{url}</a>' if url else "")
                + "</li>"
            )
            lines_text.append(f"- {plaza} - {l['brokerage']} / {agent} ({contact}) {url}")
        lines_html.append("</ul>")

    html = "<html><body>" + "\n".join(lines_html) + "</body></html>"
    text = "\n".join(lines_text)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{len(new_listings)} new retail listing(s) - {datetime.now().strftime('%b %d, %Y')}"
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))



def run(city:str | None, state: str | None, sleep_between_plazas: float = 0.0):
    sb = get_supabase()
    plazas = fetch_plazas(sb, city, state)
    print(f"  [loader] {len(plazas)} plaza(s) to scrape"
          + (f" in {city}" if city else "") + (f", {state}" if state else ""))
    
    session = curl_requests.Session()
    session.headers.update(scraper_headers)

    new_listings = []
    total_touched = 0
    total_stale = 0

    for i, plaza in enumerate(plazas):
        plaza_id = plaza["id"]
        plaza_name = plaza.get("name") or "Unnamed Retail Center"
        plaza_city = plaza.get("city") or city or ""
        address = plaza.get("address") or "-"
        plaza_state = plaza.get("state") or state or ""
        lat, lng = plaza.get("lat"), plaza.get("lng")
        radius_m = plaza.get("radius_m")

        print(f"  [loader] [{i+1}/{len(plazas)}] {plaza_name[:50]} ({plaza_city})")

        try:
            records = scrape_one_plaza(plaza_name, plaza_city, address, plaza_state, session, lat=lat, lng=lng, radius_m=radius_m)
        except Exception as e:
            print(f"  [loader] scrape failed for {plaza_name[:50]}: {e}")
            continue

        touched = set()
        for record in records:
            is_new = upsert_listing(sb, plaza_id, record, touched)
            if is_new:
                record["plaza_city"] = plaza_city
                new_listings.append(record)

        stale = mark_stale_inactive(sb, plaza_id, touched)
        total_touched += len(touched)
        total_stale += stale

        if sleep_between_plazas:
            time.sleep(sleep_between_plazas)
    
    print(f"  [loader] Done - {len(new_listings)} new, {total_touched} refreshed, "
          f"{total_stale} newly marked inactive")
    send_summary_email(new_listings)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Scrape all plazas in Supabase and upsert listings")
    parser.add_argument("--city", default=None, help="Only scrape plazas in this city")
    parser.add_argument("--state", default=None, help="Only Scrape plazas in this state")
    parser.add_argument("--sleep", type=float, default = 0.0, help="Seconds to sleep between plazas")
    args = parser.parse_args()
    run(args.city, args.state, args.sleep)



