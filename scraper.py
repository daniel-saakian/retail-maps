import re
import time
import os
import io
import uuid
import random
from curl_cffi import requests
from urllib.parse import urljoin,urlparse
from brokerages import find_listings, brokerage
import inspect
import json as _json



try:
    from bs4 import BeautifulSoup
    BS4 =True
except ImportError:
    BS4 = False
    print("  [scraper] beautifulsoup not installed")

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

request_timeout = 15
sleep_between = 1.2


def fetch(url:str,session:requests.Session):
    try:
        r=session.get(url,headers=headers,timeout=15)
        if r.status_code == 200:
            return BeautifulSoup(r.text,"html.parser")
    except Exception as e:
        print(f"  [fetch] {url[:80]}: {e}")
    return None

def extract_phones(text:str) -> list[str]:
    pattern = r"""
        (?:\+1[\s\-.]?)? # optional +1 country code
        \(?(\d{3})\)? #area code
        [\s\-.]? #optional dash
        (\d{3}) # next 3 numbers
        [\s\-.]? # optional dash
        (\d{4}) #last 4 digits
        (?:\s?(?:x|ext)\.?\s?\d{1,5})? #optional extension
    """
    matches = re.findall(pattern, text, re.VERBOSE)
    return [f"({m[0]}) {m[1]}-{m[2]}" for m in matches]

def extract_emails(soup) -> list[str]:
    emails = []
    for a in soup.find_all("a",href=True):
        href = a["href"]
        if "mailto:" in href:
            email = href.split("mailto:")[1].split("?")[0].strip()
            if email and "@" in email:
                emails.append(email)
    found = re.findall(f"[a-zA-Z0-9._%+\-]+@-a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", soup.get_text(" "))
    emails.extend(found)
    return list(dict.fromkeys(emails))

generic_address_words = {
    "street", "boulevard", "avenue", "avenu", "road", "drive", "court",
    "circle", "lane", "place", "parkway", "highway", "freeway", "way",
    "plaza", "center", "centre", "shopping", "market", "marketplace",
    "crossing", "commons", "square", "corner", "village", "town", "towne",
    "retail", "mall", "outlets", "outlet", "promenade", "pavilion",
    "gallery", "junction", "station", "landing", "exchange", "district",
    "quarter", "park", "properties", "property", "shops", "shoppe",
    "shoppes", "walk", "row", "terrace", "trail", "path", "loop",
    "grove", "heights", "hills", "ridge", "point", "pointe", "gateway",
}

def normalize(s:str) -> str:
    return re.sub(r"[^a-z0-9\s]","",s.lower()).strip()

_NOISE_NUMBER_PATTERN = re.compile(
    r"\$\s?[\d,]+(\.\d+)?"
    r"|[\d,]+(\.\d+)?\s?(sf|sq\.?s?ft\.?|acres?|ac\b)"
    r"|(suite|ste\.?|unit|#)\s?[\w-]+"
    r"|[\d.]+\s?%",
    re.IGNORECASE,
)

def _presumed_city_words(addr_parts:list) -> set:
    if not addr_parts:
        return set()
    body = addr_parts[1:]
    last_suffix_idx = None
    for i, w in enumerate(body):
        if w in generic_address_words:
            last_suffix_idx = i
    if last_suffix_idx is not None:
        return set(body[last_suffix_idx + 1:])
    return {body[-1]} if body else set()

def plaza_matches(plaza_name:str, address:str,text:str,
                  plaza_lat: float = None, plaza_lng: float = None,
                  candidate_lat: float = None, candidate_lng: float = None,
                  number_tolerance: int = 30) -> bool:
    t_words = set(normalize(text).split())
    addr_parts = normalize(address).split() if address and address != "-" else []
    presumed_city_words = _presumed_city_words(addr_parts) if addr_parts and addr_parts[0].isdigit() else set()

    full_name_norm = normalize(plaza_name) if plaza_name and plaza_name != "Unnamed Retail Center" else ""
    if full_name_norm and len(full_name_norm.split()) >= 3 and full_name_norm in normalize(text):
        return True

    strong_name_signal = False
    name_signal = False
    if plaza_name and plaza_name != "Unnamed Retail Center":
        name_words = set(normalize(plaza_name).split())
        distinctive = name_words - generic_address_words - presumed_city_words
        if distinctive:
            overlap = distinctive & t_words
            containment = len(overlap) / len(distinctive)

            if len(distinctive) >= 2 and containment >= 0.66:
                return True
            elif len(distinctive) == 1:
                word = next(iter(distinctive))
                if containment == 1.0 and len(word) >= 5:
                    name_signal = True

    if strong_name_signal:
        name_signal = True

    street_word = None
    street_word_matches = False
    number_nearby = False
    if addr_parts and addr_parts[0].isdigit():
        num = int(addr_parts[0])
        body = addr_parts[1:]
        street_tokens = [w for w in body if w not in generic_address_words and w not in presumed_city_words]
        street_word = street_tokens[0] if street_tokens else None
        street_word_matches = bool(street_word) and street_word in t_words

        cleaned_for_numbers = _NOISE_NUMBER_PATTERN.sub(" ", text)

        cand_numbers = [int(n) for n in re.findall(r"\d+", cleaned_for_numbers)]
        number_nearby = any(abs(cn-num) <= number_tolerance for cn in cand_numbers)
        if not number_nearby:
            for m in re.finditer(r"\b(\d{2,6})\s*-\s*(\d{2,6})\b",cleaned_for_numbers):
                lo, hi = int(m.group(1)), int(m.group(2))
                if lo > hi:
                    lo, hi = hi, lo
                if hi - lo > 300:
                    continue
                if lo - number_tolerance <= num <= hi + number_tolerance:
                    number_nearby = True
                    break
    
    if street_word is None:
        if number_nearby:
            return True
    elif street_word_matches and number_nearby:
        return True

    if name_signal and None not in (plaza_lat, plaza_lng, candidate_lat, candidate_lng):
        if haversine_m(plaza_lat, plaza_lng, candidate_lat, candidate_lng) <= 150:
            return True
    return False
                    

import math

def haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def make_record(plaza_name, plaza_city, address, agent_name, phone, email, brokerage, listing_url, source):
    return {
        "plaza_name": plaza_name,
        "plaza_city": plaza_city,
        "address": address,
        "agent_name": agent_name,
        "phone": phone,
        "email": email,
        "brokerage": brokerage,
        "listing_url": listing_url,
        "source": source,
    }


SIMON_PHONE = "(916) 985-0313"

SIMON_PROPERTIES = {
    "abq uptown": "ABQ Uptown, Albuquerque, NM", "albertville premium outlets": "Albertville Premium Outlets, Albertville, MN", "allen premium outlets": "Allen Premium Outlets, Allen, TX",
    "anchorage 5th avenue mall": "Anchorage 5th Avenue Mall, Anchorage, AK", "apple blossom mall": "Apple Blossom Mall, Winchester, VA", "arizona mills": "Arizona Mills, Tempe, AZ",
    "arundel mills marketplace": "Arundel Mills Marketplace, Hanover, MD", "arundel mills": "Arundel Mills, Hanover, MD", "auburn mall": "Auburn Mall, Auburn, MA",
    "aurora farms premium outlets": "Aurora Farms Premium Outlets, Aurora, OH", "aventura mall": "Aventura Mall, Miami, FL", "barton creek square": "Barton Creek Square, Austin, TX",
    "battlefield mall": "Battlefield Mall, Springfield, MO", "bay park square": "Bay Park Square, Green Bay, WI", "beverly center": "Beverly Center, Los Angeles, CA",
    "birch run premium outlets": "Birch Run Premium Outlets, Birch Run, MI", "brea mall": "Brea Mall, Brea, CA", "briarwood mall": "Briarwood Mall, Ann Arbor, MI",
    "brickell city centre": "Brickell City Centre, Miami, FL", "broadway square": "Broadway Square, Tyler, TX", "burlington mall": "Burlington Mall, Burlington, MA",
    "calhoun outlet marketplace": "Calhoun Outlet Marketplace, Calhoun, GA", "camarillo premium outlets": "Camarillo Premium Outlets, Camarillo, CA", "cape cod mall": "Cape Cod Mall, Hyannis, MA",
    "carlsbad premium outlets": "Carlsbad Premium Outlets, Carlsbad, CA", "carolina premium outlets": "Carolina Premium Outlets, Smithfield, NC", "castleton square": "Castleton Square, Indianapolis, IN",
    "charlotte premium outlets": "Charlotte Premium Outlets, Charlotte, NC", "cherry creek shopping center": "Cherry Creeek Shopping Center, Denver, CO",
    "chicago premium outlets": "Chicago Premium Outlets, Aurora, IL", "cielo vista mall": "Cielo Vista Mall, El Paso, TX", "cincinnati premium outlets": "Cincinnati Premium Outlets, Monroe, OH",
    "city creek center": "City Creek Center, Salt Lake City, UT", "clarksburg premium outlets": "Clarksburg Premium Outlets, Clarksburg, MD", "clinton premium outlets": "Clinton Premium Outlets, Clinton, CT",
    "coconut point": "Coconut Point, Estero, FL", "college mall": "College Mall, Bloomington, IN", "colorado mills": "Colorado Mills, Lakewood, CO",
    "columbia center": "Columbia Center, Kennewick, WA", "concord mills": "Concord Mills, Concord, NC", "copley place": "Copley Place, Boston, MA",
    "coral square": "Coral Square, Coral Springs, FL", "cordova mall": "Cordova Mall, Pensacola, FL", "dadeland mall": "Dadeland Mall, Miami FL",
    "del amo fashion center": "Del Amo Fashion Center, Torrance, CA", "denver premium outlets": "Denver Premium Outlets, Thornton, CO", "denver west village": "Denver West Village, Lakewood, CO",
    "desert hills premium outlets": "Desert Hills Premium Outlets, Cabazon, CA", "dolphin mall": "Dolphin Mall, Miami, FL", "dover commons": "Dover Commons, Dover, DE",
    "dover mall": "Dover Mall, Dover, DE", "ellenton premium outlets": "Ellenton Premium Outlets, Ellenton, FL", "fashion centre at pentagon city": "Fashion Centre at Pentagon City, Arlington, VA",
    "fashion valley": "Fashion Valley, San Diego, CA", "finger lakes premium outlets": "Finger Lakes Premium Outlets, Waterloo, NY", "firewheel town center": "Firewheel Town Center, Garland, TX",
    "florida keys outlet marketplace": "Florida Keys Outlet Marketplace, Florida City, FL", "folsom premium outlets": "Folsom Premium Outlets, Folsom, CA", "gaffney outlet marketplace": "Gaffney Outlet Marketplace, Gaffney, SC",
    "gilroy premium outlets": "Gilroy Premium Outlets, Gilroy, CA", "gloucester premium outlets": "Gloucester Premium Outlets, Blackwood, NJ", "grand prairie premium outlets": "Grand Prairie Premium Outlets, Grand Prairie, TX",
    "grapevine mills": "Grapevine Mills, Grapevine, TX", "great lakes crossing outlets": "Great Lakes Crossing Outlets, Auburn Hills, MI", "great mall": "Great Mall, Milpitas, CA",
    "greenwood park mall": "Greenwood Park Mall, Greenwood, IN", "grove city premium outlets": "Grove City Premium Outlets, Grove City, PA", "gulfport premium outlets": "Gulfport Premium Outlets, Gulfport, MS",
    "gurnee mills": "Gurnee Mills, Gurnee, IL", "hagerstown premium outlets": "Hagerstown Premium Outlets, Hagerstown, MD", "hamilton town center": "Hamilton Town Center, Noblesville, IN",
    "haywood mall": "Haywood Mall, Greenville, SC", "houston premium outlets": "Houston Premium Outlets, Cypress, TX", "indiana premium outlets": "Indiana Premium Outlets, Edinburgh, IN",
    "international market place": "International Market Place, Honolulu, HI", "international plaza": "International Plaza, Tampa, FL", "jackson premium outlets": "Jackson Premium Outlets, Jackson, NJ",
    "jersey shore premium outlets": "Jersey Shore Premium Outlets, Tinton Falls, NJ", "johnson creek premium outlets": "Johnson Creek Premium Outlets, Johnson Creek, WI",
    "katy mills": "Katy Mills, Katy, TX", "king of prussia": "King of Prussia, King of Prussia, PA", "kittery premium outlets": "Kittery Premium Outlets, Kittery, ME", "la plaza": "La Plaza, McAllen, TX",
    "lakeline mall": "Lakeline Mall, Cedar Park, TX", "las americas premium outlets": "Las Americas Premium Outlets, San Diego, CA", "las vegas north premium outlets": "Las Vegas North Premium Outlets, Las Vegas, NV",
    "las vegas south premium outlets": "Las Vegas South Premium Outlets, Las Vegas, NV", "lee premium outlets": "Lee Premium Outlets, Lee, MA", "leesburg premium outlets": "Leesburg Premium Outlets, Leesburg, VA",
    "lehigh valley mall": "Lehigh Valley Mall, Whitehall, PA", "lenox sqaure": "Lenox Square, Atlanta, GA", "liberty tree mall": "Liberty Tree Mall, Danvers, MA", "liberty tree strip": "Liberty Tree Strip, Danvers, MA",
    "lighthouse place premium outlets": "Lighthouse Place Premium Outlets, Michigan City, IN",  "mall of georgia": "Mall of Georgia, Buford, GA", "mccain mall": "McCain Mall, North Little Rock, AR",
    "meadowood mall": "Meadowood Mall, Reno, NV", "menlo park mall": "Menlo Park Mall, Edison, NJ", "merrimack premium outlets": "Merrimack Premium Outlets, Merrimack, NH",
    "miami international mall": "Miami International Mall, Doral, FL", "midland park mall": "Midland Park Mall, Midland, TX", "miller hill mall": "Miller Hill Mall, Duluth, MN",
    "napa premium outlets": "Napa Premium Outlets, Napa, CA", "newport centre": "Newport Centre, Jersey City, NJ",  "newport crossing": "Newport Crossing, Jersey City, NJ", "newport plaza": "Newport Plaza, Jersey City, NJ",
    "norfolk premium outlets": "Norfolk Premium Outlets, Norfolk, VA", "north bend premium outlets": "North Bend Premium Outlets, North Bend, WA",
    "north east mall": "North East Mall, Hurst, TX", "north georgia premium outlets": "North Georgia Premium Outlets, Dawsonville, GA",
    "northgate station": "Northgate Station, Seattle, WA", "northshore mall": "Northshore Mall, Peabody, MA", "ocean county mall": "Ocean County Mall, Toms River, NJ", "ontario mills": "Ontario Mills, Ontario, CA",
    "opry mills": "Opry Mills, Nashville, TN", "orland square": "Orland Sqaure, Orland Park, IL", "orlando international premium outlets": "Orlando International Premium Outlets, Orlando, FL",
    "orlando outlet marketplace": "Orlando Outlet Marketplace, Orlando, FL", "orlando vineland premium outlets": "Orlando Vineland Premium Outlets, Orlando, FL",
    "oxford valley mall": "Oxford Valley Mall, Langhorne, PA", "penn square mall": "Penn Square Mall, Oklahoma City, OK", "petaluma village premium outlets": "Petaluma Village Premium Outlets, Petaluma, CA",
    "pheasant lane mall": "Pheasant Lane Mall, Nashua, NH", "philadelphia premium outlets": "Philadelphia Premium Outlets, Pottstown, PA",
    "phillips place": "Phillips Place, Charlotte, NC", "phipps plaza": "Phipps Plaza, Atlanta, GA", "phoenix premium outlets": "Phoenix Premium Outlets, Chandler, AZ",
    "pier park": "Pier Park, Panama City Beach, FL", "pismo beach premium outlets": "Pismo Beach Premium Outlets, Pismo Beach, CA",
    "pleasant prairie premium outlets": "Pleasant Prairie Premium Outlets, Pleasant Prairie, WI", "pocono premium outlets": "Pocono Premium Outlets, Tannersville, PA",
    "potomac mills": "Potomac Mills, Woodbridge, VA", "prien lake mall": "Prien Lake Mall, Lake Charles, LA", "quaker bridge mall": "Quaker Bridge Mall, Lawrenceville, NJ",
    "queenstown premium outlets": "Queenstown Premium Outlets, Queenstown, MD", "rio grande valley premium outlets": "Rio Grande Valley Premium Outlets, Mercedes, TX",
    "rockaway townsquare": "Rockaway Townsquare, Rockaway, NJ", "roosevelt field": "Roosevelt Field, Garden City, NY", "ross park mall": "Ross Park Mall, Pittsburgh, PA",
    "round rock premium outlets": "Round Rock Premium Outlets, Round Rock, TX", "san francisco premium outlets": "San Francisco Premium Outlets, Livermore, CA",
    "san marcos premium outlets": "San Marcos Premium Outlets, San Marcos, TX", "santa rosa plaza": "Santa Rosa Plaza, Santa Rosa, CA", "sawgrass mills": "Sawgrass Mills, Sunrise, FL",
    "seattle premium outlets": "Seattle Premium Outlets, Tulalip, WA", "silver sands premium outlets": "Silver Sands Premium Outlets, Destin, FL",
    "smith haven mall": "Smith Haven Mall, Lake Grove, NY", "south hills village": "South Hills Village, Pittsburgh, PA", "south shore plaza": "South Shore Plaza, Braintree, MA",
    "southdale center": "Southdale Center, Edina, MN", "southpark": "SouthPark, Charlottle, NC", "springfield mall": "Springfield Mall, Springfield, PA",
    "square one mall": "Square One Mall, Saugus, MA", "st. augustine premium outlets": "St. Augustine Premium Outlets, St Augustine, FL", "st. charles towne center": "St. Charles Towne Center, Waldorf, MD",
    "st. johns town center": "St. Johns Town Center, Jacksonville, FL", "st. johns community center": "St. Johns Community Center, Jacksonville, FL",
    "st. louis premium outlets": "St. Louis Premium Outlets, Chesterfield, MO", "stanford shopping center": "Stanford Shopping Center, Palo Alto, CA",
    "stoneridge shopping center": "Stoneridge Shopping Center, Pleasanton, CA", "sugarloaf mills": "Sugarloaf Mills, Lawrenceville, GA", "summit mall": "Summit Mall, Fairlawn, OH",
    "sunvalley shopping center": "Sunvalley Shopping Center, Concord, CA", "tacoma mall": "Tacoma Mall, Tacoma, WA", "tampa premium outlets": "Tampa Premium Outlets, Lutz, FL",
    "tanger outlets columbus": "Tanger Outlets Columbus, Sunbury, OH", "tanger outlets houston": "Tanger Outlets Houston, Texas City, TX", "the avenues": "The Avenues, Jacksonville, FL",
    "the colonnade outlets at sawgrass mills": "The Colonnade Outlets at Sawgrass Mills, Sunrise, FL", "the domain": "The Domain, Austin, TX", "the empire mall": "The Empire Mall, Sioux Falls, SD",
    "the falls": "The Falls, Miami, FL", "the fashion mall at keystone": "The Fashion Mall at Keystone, Indianapolis, IN", "the florida mall": "The Florida Mall, Orlando, FL",
    "the forum shops at caesars palace": "The Forum Shops at Caesars Palace, Las Vegas, NV", "the galleria": "The Galleria, Houston, TX", "the gardens mall": "The Gardens Mall, Palm Beach Gardens, FL",
    "the gardens on el paseo": "The Gardens on El Paseo, Palm Desert, CA", "the haven": "The Haven, West Haven, CT", "the mall at green hills": "The Mall at Green Hills, Nashville, TN",
    "the mall at millenia": "The Mall at Millenia, Orlando, FL", "the mall at rockingham park": "The Mall at Rockingham Park, Salem, NH", "the mall at short hills": "The Mall at Short Hills, Short Hills, NJ",
    "the mall at university town center": "The Mall at University Town Center, Sarasota, FL", "the mall of new hampshire": "The Mall of New Hampshire, Manchester, NH", 
    "the mills at jersey gardens": "The Mills at Jersey Gardens, Elizabeth, NJ", "the outlets at orange": "The Outlets at Orange, Orange, CA",
    "the shops at chestnut hill": "The Shops at Chestnut Hill, Chestnut Hill, MA", "the shops at clearfork": "The Shops at Clearfork, Forth Worth, TX",
    "the shops at crystals": "The Shops at Crystals, Las Vegas, NV", "the shops at mission viejo": "The Shops at Mission Viejo, Mission Viejo, CA", "the shops at riverside": "The Shops at Riverside, Hackensack, NJ",
    "the village at southpark": "The Village at SouthPark, Charlotte, NC", "the westchester": "The Westchester, White Plains, NY", "tippecanoe mall": "Tippecanoe Mall, Lafayette, IN",
    "town center at boca raton": "Town Center at Boca Raton, Boca Raton, FL", "towne east square": "Towne East Sqaure, Wichita, KS", "treasure coast square": "Treasure Coast Square, Jensen Beach, FL",
    "tucson premium outlets": "Tucson Premium Outlets, Tucson, AZ", "tulsa premium outlets": "Tulsa Premium Outlets, Jenks, OK", "twelve oaks": "Twelve Oaks, Novi, MI",
    "twin cities premium outlets": "Twin Cities Premium Outlets, Eagan, MN", "tyrone square": "Tyrone Square, St Petersburg, FL", "university park mall": "University Park Mall, Mishiwaka, IN",
    "university park village": "University Park Village, Fort Worth, TX", "vacaville premium outlets": "Vacaville Premium Outlets, Vacaville, CA", "waikele premium outlets": "Waikele Premium Outlets, Waipahu, HI",
    "walt whitman shops": "Walt Whitman Shops, Huntington Station, NY", "waterside shops": "Waterside Shops, Naples, FL", "west town mall": "West Town Mall, Knoxville, TN",
    "westfarms": "Westfarms, West Hartford, CT", "white oaks mall": "White Oaks Mall, Springfield, IL", "williamsburg premium outlets": "Williamsburg Premium Outlets, Williamsburg, VA",
    "wolfchase galleria": "Wolfchase Galleria, Memphis, TN", "woodburn premium outlets": "Woodburn Premium Outlets, Woodburn, OR", "woodbury common premium outlets": "Woodbury Common Premium Outlets, Central Valley, NY",
    "woodfield mall": "Woodfield Mall, Schaumburg, IL", "woodland hills mall": "Woodland Hills Mall, Tulsa, OK", "wrentham village premium outlets": "Wrentham Village Premium Outlets, Wrentham, MA",
}

def _simon_name_matches(plaza_name:str, simon_name:str) -> bool:
    a = set(normalize(plaza_name).split()) - generic_address_words
    b = set(normalize(simon_name).split()) - generic_address_words

    if not a or not b:
        return False
    overlap = a & b
    if not overlap:
        return False
    score = len(overlap) / min(len(a), len(b))
    if score < 0.9:
        return False
    if all(len(w) < 5 for w in overlap):
        return False
    return True

def scrape_simon(plaza_name, plaza_city, address, city, state, session):
    results = []
    state_code = (state or "").strip().upper()
    candidates = {
        key: location for key, location in SIMON_PROPERTIES.items()
        if not state_code or location.strip()[-2:].upper() == state_code
    }
    for key, location in candidates.items():
        if plaza_name and plaza_name != "Unnamed Retail Center" and _simon_name_matches(plaza_name, key.title()):
            results.append(make_record(
                plaza_name,plaza_city, address, "Simon Property Group Leasing team",
                SIMON_PHONE, None, "Simon Property Group",
                f"https://business.simon.com/search?location={city.replace(' ', '+')}%2C+{state}",
                "Simon - fixed company phone"
            ))
            break
    return results

def _gallelli_matches(plaza_name,address,card_text):
    return plaza_matches(plaza_name, address, card_text)


def scrape_gallelli(plaza_name,plaza_city,address,city,state,session):
    results = []
    city_slug = city.lower().replace(" ", "+")
    search_url = (
        f"https://gallellire.com/properties/"
        f"?type=retail&status=lease&city={city_slug}"
        f"&min_price=0&max_price=50000000&min_size=0&max_size=10000000"
    )
    soup = fetch(search_url,session)
    if not soup:
        return results
    time.sleep(sleep_between)

    links = soup.find_all("a", href=re.compile(r"/property/[^/]+/?$"))
    print(f"    [gallelli] {len(links)} property links found on search page")
 
    seen_urls = set()
    for link in links:
        detail_url = urljoin("https://gallellire.com", link["href"])
        if detail_url in seen_urls:
            continue
 
        card_text = link.get_text(" ", strip=True)
        node = link
        for _ in range(4):
            if node.parent is None:
                break
            node = node.parent
            candidate_text = node.get_text(" ", strip=True)
            if len(candidate_text) > 220:
                break
            card_text = candidate_text

        lowered = card_text.lower()
        if "for sale" in lowered or "land parcel" in lowered or "vacant land" in lowered:
            continue
 
        if not _gallelli_matches(plaza_name,address,card_text):
            continue
 
        seen_urls.add(detail_url)
        print(f"    [gallelli] match: {card_text[:100]}")
 
        detail = fetch(detail_url,session)
        if not detail:
            continue
        time.sleep(sleep_between)

        detail_type_match = re.search(
            r"property type\s+(office|industrial|land|multifamily|residential)",
            detail.get_text(" ", strip=True).lower(),
        )
        if detail_type_match:
            print(f"  [gallelli] skipping non-retail listings")
            continue
 
        agent_cards = detail.find_all("div", class_ = re.compile(r"staff-member|js-staff-member"))
        if not agent_cards:
            agent_cards = detail.find_all("div", class_ = re.compile(r"swiper-slide"))
 
        for ac in agent_cards:
            name_el = ac.find(["h3", "h4", "strong"])
            agent_name = name_el.get_text(strip=True) if name_el else None
 
            email = None
            email_link = ac.find("a", class_ = "value", href = re.compile(r"mailto:"))
            if not email_link:
                email_link = ac.find("a", href = re.compile(r"mailto:"))
            if email_link:
                email = email_link["href"].replace("mailto:", "").split("?")[0].strip()
 
            phone = None
            vcard_link = ac.find("a",href = re.compile(r"\.vcf$"))
            if vcard_link:
                vcard_url = urljoin("https://gallellire.com",vcard_link["href"])
                try:
                    vr = session.get(vcard_url,headers = headers, timeout = 10)
                    time.sleep(0.5)
                    if vr.status_code == 200:
                        phone_match = re.search(r"TEL[^:]*:([^\r\n]+)", vr.text)
                        if phone_match:
                            phones = extract_phones(phone_match.group(1))
                            phone = phones[0] if phones else phone_match.group(1).strip()
                except Exception:
                    pass
            
            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name,plaza_city,address,
                    agent_name,phone,email, "Gallelli Real Estate",
                    detail_url, "VCard phone and Gallelli property page"
                ))

    if not results and links:
        print(f"    [gallelli] 0 matches from {len(links)} candidates — sample:")
        for link in links[:5]:
            print(f"    [gallelli]   - {link.get_text(strip=True)} ({link.get('href','')})")
 
    return results


peco_api = "https://peco-ncus-prod-app.azurewebsites.net/api/v1/site-plan/{code}"
peco_metros = {
    "Folsom": "sacramento-ca", "Roseville": "sacramento-ca", "Elk Grove": "sacramento-ca", "Sacramento": "sacramento-ca", "Rancho Cordova": "sacramento-ca", "Davis": "sacramento-ca",
    "Citrus Heights": "sacramento-ca", "Rocklin": "sacramento-ca", "Lincoln": "sacramento-ca",
    "Antioch": "san-francisco-ca", "Clayton": "san-francisco-ca",
    "Tracy": "stockton-ca",
    "Modesto": "modesto-ca", "Ceres": "modesto-ca",
    "Redding": "redding-ca",
    "Salinas": "salinas-ca",
    "Fresno": "fresno-ca", "Clovis": "fresno-ca",
    "Templeton": "templeton-ca",
    "Bakersfield": "bakersfield-ca",
    "Santa Maria": "santa-maria-ca",
    "Lancaster": "los-angeles-ca", "Monrovia": "los-angeles-ca", "West Covina": "los-angeles-ca",
    "Ontario": "riverside-ca", "Murrieta": "riverside-ca",
    "Indian Wells": "ontario",
    "North Las Vegas": "las-vegas-nv", "Henderson": "las-vegas-nv", "Las Vegas": "las-vegas-nv",
    "Glendale": "phoenix-az", "Avondale": "phoenix-az", "Tempe": "phoenix-az", "Phoenix": "phoenix-az",
    "Tucson": "tucson-az", "Oro Valley": "tucson-az",
    "Corvallis": "corvallis-or",
    "Salem": "salem-or",
    "Portland": "portland-or",
    "Everett": "seattle-wa", "Tacoma": "seattle-wa","Renton": "seattle-wa", "Milton": "seattle-wa",
    "Yakima": "yakima-wa",
    "Farmington": "farmington-nm", "Santa Fe": "santa-fe-nm",
    "Colorado Springs": "colorado-springs-co",
    "Littleton": "denver-co", "Centennial": "denver-co", "Greenwood Village": "denver-co", "Golden": "denver-co", "Lakewood": "denver-co", "Wheat Ridge": "denver-co", "Arvada": "denver-co", "Westminster": "denver-co", "Broomfield": "denver-co",
    "Boulder": "boulder-co",
    "Loveland": "loveland-co",
    "Austin": "austin-tx", "Georgetown": "austin-tx",
    "Sugarland": "houston-tx", "Houston": "houston-tx", "Katy": "houston-tx", "Fulshear": "houston-tx", "Cypress": "houston-tx", "The Woodlands": "houston-tx", "Spring": "houston-tx",
    "Crowley": "dallas-tx", "Mansfield": "dallas-tx", "Arlington": "dallas-tx", "Hurst": "dallas-tx", "Southlake": "dallas-tx", "Denton": "dallas-tx", "Coppell": "dallas-tx", "Plano": "dallas-tx", "Prosper": "dallas-tx", "McKinney": "dallas-tx", "Murphy": "dallas-tx", "Rowlett": "dallas-tx",
    "Overland Park": "kansas-city-ks", "Kansas City": "kansas-city-ks",
    "Carroll": "carroll-io", "Des Moines": "des-moines-io",
    "New Prague": "minneapolis-mn", "Albertville": "minneapolis-mn", "Ramsey": "minneapolis-mn", "Chaska": "minneapolis-mn", "Shakopee": "minneapolis-mn", "Chanhassen": "minneapolis-mn", "Eden Prairie": "minneapolis-mn", "Savage": "minneapolis-mn",
    "Hastings": "minneapolis-mn", "Grove Heights": "minneapolis-mn", "Bloomington": "minneapolis-mn", "Edina": "minneapolis-mn", "Plymouth": "minneapolis-mn",
    "Rochester": "rochester-mn", "Onalaska": "onalaska-wi",
    "Petoskey": "petoskey-wi", "Oshkosh": "oshkosk-wi",  "Oconomowok": "milwaukee-wi", "Franklin": "milwaukee-wi", "Racine": "milwaukee-wi", "Kenosha": "milwaukee-wi",
    "Roscoe": "Rockford-wi", "Grayslake": "chicago-il",
    "Hoffman Estates": "chicago-il", "Rolling Meadows": "chicago-il", "Glenview": "chicago-il", "Niles": "chicago-il", "Carol Stream": "chicago-il", "Besenville": "chicago-il", "Batavia": "chicago-il", "Ellyn": "chicago-il", "Naperville": "chicago-il",
    "Burbank": "chicago-il", "Lemont": "chicago-il", "Shorewood": "chicago-il",
    "Dyer": "gary-in", "Normal": "bloomington-il", "Savoy": "champaign-il", "Des Peres": "st-louis-mo", "St. Louis": "st-louis-mo", "Lafayette": "lafayette-in",
    "Noblesville": "indianapolis-in", "Mooresville": "indianapolis-in", "Louisville": "louisville-ky",
    "Nashville": "nashville-tn", "Mt. Juliet": "nashville-tn", "Panama City Beach": "tallahassee-fl", "Tallahassee": "tallahassee-fl", "Chattanooga": "chattanooga-il",
    "Cartersville": "atlanta-ga", "Kennesaw": "atlanta-ga", "Marietta": "atlanta-ga", "Mableton": "atlanta-ga", "Lithia Springs": "atlanta-ga", "Tyrone": "atlanta-ga", "Canton": "atlanta-ga", "Roswell": "atlanta-ga", "Johns Creek": "atlanta-ga",
    "Alpharetta": "atlanta-ga", "Suwanee": "atlanta-ga", "Ellenwood": "atlanta-ga", "Stockbridge": "atlanta-ga", "McDonough": "atlanta-ga", "Dacula": "atlanta-ga", "Buford": "atlanta-ga", "Snellville": "atlanta-ga", "Loganville": "atlanta-ga",
    "Cincinnati": "cincinnati-oh", "Goshen": "cincinnati-oh", "Huber Heights": "dayton-oh", "Beavercreek": "dayton-oh", "Springfield": "dayton-oh", "Findlay": "findlay-oh", "Milan": "ann-arbor-mi",
    "Westland": "detroit-mi", "Livonia": "detroit-mi", "Washington Township": "detroit-mi", 
    "Lewis Center": "columbus-oh", "Dublin": "columbus-oh", "Columbus": "columbus-oh", "Lexington": "lexington-ky",
    "Sheffield Village": "cleveland-oh", "Fairfield Park": "cleveland-oh", "Lakewood": "cleveland-oh", "Willowick": "cleveland-oh", "Parma": "cleveland-oh", "Fairlawn": "cleveland-oh", "Akron": "cleveland-oh", "Hartville": "cleveland-oh",
    "Millcreek Township": "erie-pa", "Amherst": "buffalo-ny", "Indiana": "indiana-pa", "Gibsonia": "pittsburgh-pa", "Edgewood": "pittsburgh-pa", "Salem": "roanoke-va", "Easley": "greenville-sc", "Taylors": "greenville-sc", "Dallas": "charlotte-nc",
    "Fort Mill": "charlotte-nc", "Waxhaw": "charlotte-nc", "Charlott": "charlotte-nc", "Evans": "augusta-ga", "Augusta": "augusta-ga", "Columbia": "columbia-sc", "Irmo": "columbia-sc", "Savannah": "savannah-ga", "Brunswick": "brunswick-ga", 
    "Fernandina Beach": "jacksonville-fl", "Jacksonville": "jacksonville-fl", "Ocala": "ocala-fl", "Ormond Beach": "daytona-beach-fl", "Port Orange": "daytona-beach-fl", "leesburg": "orlando-fl", "Lake Mary": "orlando-fl", "Winter Springs": "orlando-fl",
    "Altamonte Springs": "orlando-fl", "Orlando": "orlando-fl", "Clermont": "orlando-fl", "Davenport": "orlando-fl", "St. Cloud": "orlando-fl", "Winter Haven": "lakeland-fl", "Bartow": "lakeland-fl", "Weeki Wachee": "tampa-fl", "Spring Hill": "tampa-fl",
    "Hudson": "tampa-fl", "Wesley Chapel": "tampa-fl", "Lutz": "tampa-fl", "Palm Harbor": "tampa-fl", "Seminole": "tampa-fl", "Seffner": "tampa-fl", "Valrico": "tampa-fl", "Riverview": "tampa-fl", "Sun City Center": "tampa-fl", "Sarasota": "sarasota-fl",
    "North Port": "sarasota-fl", "North Fort Myers": "fort-myers-fl", "Fort Myers": "fort-myers-fl", "Bonita Springs": "cape-coral-fort-myers-fl", "Miami": "miami-fl", "Miramar": "fort-lauderdale-fl", "Southwest Ranches": "fort-lauderdale-fl",
    "Coconut Creek": "fort-lauderdale-fl", "Boynton Beach": "miami-fl", "Ocean Breeze": "port-st-lucie-fl", "Jensen Beach": "port-st-lucie-fl", "Melbourne": "melbourne-fl", "Rockledge": "melbourne-fl", "Cocoa": "melbourne-fl", "titusville": "melbourne-fl",
    "North Charleston": "charleston-sc", "Summerville": "charleston-sc", "Pawleys Island": "pawleys-island-sc", "Wilmington": "wilmington-nc", "Clinton": "clinton-nc", "Sanford": "sanford-nc", "Asheboro": "greensboro-nc", "Cary": "raleigh-nc", "Raleigh": "raleigh-nc",
    "Chapel Hill": "raleigh-nc", "Hillsborough": "raleigh-nc", "Danville": "danville-va", "Virginia Beach": "virginia-beach-va", "Colonial Heights": "richmond-va", "Midlothian": "richmond-va", "Charlottesville": "charlottesville-va", 
    "Waynesboro": "staunton-va", "Staunton": "staunton-va", "La Plata": "washington-dc-dc", "Bowie": "washington-dc-dc", "Sterling": "washington-dc-dc", "Ashburn": "washington-dc-dc", "Glen Burnie": "baltimore-md", "Winchester": "winchester-va",
    "Bel Air": "baltimore-md", "New Cumberland": "york-pa", "Easton": "easton-pa", "Pompton Plains": "newark-nj", "Bethel": "fairfield-county-ct", "Cheshire": "new-haven-ct", "Montville": "norwich-ct", "Willimantic": "worcester-ct", "Enfield": "hartford-ct",
    "Springfield": "springfield-ma", "Raynham": "boston-ma", "Taunton": "boston-ma", "Easton": "boston-ma", "Hanover": "boston-ma", "Cohasset": "boston-ma", "Sudbury": "boston-ma", "North Reading": "boston-ma", "Amesbury": "boston-ma",

}
state_slugs = {
    "CA": "california", "TX": "texas", "FL": "florida", "IL": "illinois",
    "NY": "new-york", "WA": "washington", "OR": "oregon", "AZ": "arizona",
    "CO": "colorado", "GA": "georgia", "NC": "north-carolina", "OH": "ohio",
    "PA": "pennsylvania", "TN": "tennessee", "VA": "virginia", "NV": "nevada",
    "UT": "utah", "MN": "minnesota", "MO": "missouri", "WI": "wisconsin",
    "IN": "indiana", "MI": "michigan", "KY": "kentucky", "AL": "alabama",
    "SC": "south-carolina", "KS": "kansas", "OK": "oklahoma", "NE": "nebraska",
    "ID": "idaho", "NM": "new-mexico", "AR": "arkansas", "IA": "iowa",
    "MT": "montana", "WY": "wyoming", "ND": "north-dakota", "SD": "south-dakota",
    "MN": "minnesota", "WV": "west-virginia", "DE": "delaware", "MD": "maryland",
    "CT": "connecticut", "RI": "rhode-island", "NH": "new-hampshire",
    "VT": "vermont", "ME": "maine", "AK": "alaska", "HI": "hawaii",
    "MS": "mississippi", "LA": "louisiana", "AR": "arkansas",
    "DC": "district-of-columbia",
}


def build_peco_detail_url(plaza_name: str, city: str, state: str) -> str:
    """
    Build Phillips Edison detail URL directly from plaza name and city.
    Pattern: /property/{state-slug}/{metro-slug}/{city-slug}/{property-slug}
    """
    state_slug = state_slugs.get(state.upper(), state.lower())
    metro      = peco_metros.get(city, f"{city.lower().replace(' ', '-')}-{state.lower()}")
    city_slug  = city.lower().replace(" ", "-")
    prop_slug  = (plaza_name.lower()
                  .replace(" ", "-")
                  .replace("'", "")
                  .replace(",", "")
                  .replace(".", "")
                  .replace("&", "and")
                  .replace("/", "-"))
    return f"https://www.phillipsedison.com/property/{state_slug}/{metro}/{city_slug}/{prop_slug}"

_PECO_PROPERTIES = None

def get_peco_properties(session):
    global _PECO_PROPERTIES
    if _PECO_PROPERTIES is not None:
        return _PECO_PROPERTIES
    try:
        r = session.get(
            "https://www.phillipsedison.com/api/v1/properties?pageSize=500&pageNumber=1&useFallback=true",
            headers=headers, timeout=15
        )
        data = r.json()
        # Build lookup by propertyNameSlug → id
        _PECO_PROPERTIES = {
            p["propertyNameSlug"]: p["id"]
            for p in data.get("results", [])
        }
        print(f"    [peco] Loaded {len(_PECO_PROPERTIES)} properties from API")
    except Exception as e:
        print(f"    [peco] Properties API failed: {e}")
        _PECO_PROPERTIES = {}
    return _PECO_PROPERTIES


def scrape_phillipsedison(plaza_name, plaza_city, address, city, state, session):
    results = []

    # Get property code from slug via the properties API
    all_props = get_peco_properties(session)

    prop_slug = (plaza_name.lower()
                 .replace(" ", "-")
                 .replace("'", "")
                 .replace(",", "")
                 .replace(".", "")
                 .replace("&", "and")
                 .replace("/", "-"))

    code = all_props.get(prop_slug)

    # If exact slug not found, try fuzzy match by city + partial name
    if not code:
        city_clean = city.lower().replace(" ", "-")
        plaza_words = set(normalize(plaza_name).split())
        best_slug,best_pid,best_score = None,None,0.0
        for slug, pid in all_props.items():
            if city_clean not in slug:
                continue
            candidate_words = set(slug.replace("-", " ").split())
            if not plaza_words or not candidate_words:
                continue
            score = len(plaza_words & candidate_words) / len(plaza_words | candidate_words)
            if score > best_score:
                best_score, best_slug, best_pid = score, slug, pid
        
        if best_score >= 0.425:
            code = best_pid
            prop_slug = best_slug
            print(f"  [peco] fuzzy match '{prop_slug}' -> code = {code}")

    if not code:
        print(f"    [peco] no property found for '{prop_slug}' in {city}")
        return results

    detail_url = build_peco_detail_url(plaza_name, city, state)

    try:
        api_url = peco_api.format(code=code)
        r = session.get(api_url, headers=headers, timeout=15)
        time.sleep(sleep_between)

        if r.status_code != 200:
            print(f"    [peco] site-plan API returned {r.status_code}")
            return results

        data = r.json().get("data", {})
        agent_name  = data.get("agent_name")
        agent_email = data.get("agent_email")
        raw_phone   = data.get("agent_phone", "") or ""

        phones = extract_phones(raw_phone)
        phone  = phones[0] if phones else (
            f"({raw_phone[:3]}) {raw_phone[3:6]}-{raw_phone[6:]}"
            if len(raw_phone) == 10 else raw_phone or None
        )

        if agent_name or agent_email or phone:
            results.append(make_record(
                plaza_name, plaza_city, address,
                agent_name, phone, agent_email,
                "Phillips Edison", detail_url,
                f"Phillips Edison API: {api_url}",
            ))

    except Exception as e:
        print(f"    [peco] site-plan API failed: {e}")

    return results


regency_schema_base = "https://schema.milestoneinternet.com/schema/regencycenters.com/property/detail/{id}/{slug}/schema.json"
import xml.etree.ElementTree as ET
_regency_sitemap = None

def get_regency_sitemap(session):
    global _regency_sitemap
    if _regency_sitemap is not None:
        return _regency_sitemap
    try:
        r = session.get(
            "https://www.regencycenters.com/sitemap.xml",
            headers={**headers, "Accept-Encoding": "identity"},
            timeout=15
        )
        root = ET.fromstring(r.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [
            loc.text for loc in root.findall("sm:url/sm:loc", ns)
            if loc.text and "/property/detail/" in loc.text
        ]
        _regency_sitemap = urls
        print(f"    [regency] Loaded {len(urls)} properties from sitemap")
    except Exception as e:
        print(f"    [regency] Sitemap failed: {e}")
        _regency_sitemap = []
    return _regency_sitemap

def scrape_regency(plaza_name,plaza_city,address,city,state,session):
    results = []
    city_clean = city.split(",")[0].strip()
 
    all_props = get_regency_properties(session, state)
 
    for prop in all_props:
        if city_clean.lower() not in prop["city"].lower():
            continue
        if not plaza_matches(plaza_name, address, f"{prop['name']} {prop['street']} {prop['city']}"):
            continue
 
        for person in prop["persons"]:
            agent_name = person["name"] or None
            phone_raw  = person["telephone"]
            email_raw  = person["email"]
 
            phones = extract_phones(phone_raw) if phone_raw else []
            phone  = phones[0] if phones else phone_raw or None
            email  = email_raw or None
 
            if agent_name or phone or email:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email,
                    "Regency Centers", prop["detail_url"],
                    f"Regency sitemap → schema.json: {prop['schema_url']}",
                ))
 
        if results:
            break  
 
    return results
 
_regency_properties_cache = {} 
 
def get_regency_properties(session, state: str):
    key = state.upper()
    if key in _regency_properties_cache:
        return _regency_properties_cache[key]
 
    all_urls = get_regency_sitemap(session)
    resolved = []
 
    print(f"    [regency] resolving property data for {len(all_urls)} properties (state={key}) — one-time cost for this run")
 
    for detail_url in all_urls:
        m = re.search(r"/property/detail/(\d+)/([^/?#]+)", detail_url)
        if not m:
            continue
        prop_id, prop_slug = m.group(1), m.group(2)
        schema_url = (
            f"https://schema.milestoneinternet.com/schema/regencycenters.com"
            f"/property/detail/{prop_id}/{prop_slug}/schema.json"
        )
 
        try:
            r = session.get(schema_url, headers=headers, timeout=15)
            time.sleep(0.3)
            if r.status_code != 200:
                continue
            data = r.json()
        except Exception:
            continue
 
        listing = next((d for d in data if d.get("@type") == "RealEstateListing"), None)
        if not listing:
            continue
 
        def extract_field(obj, key):
            val = obj.get(key)
            if isinstance(val, list):
                return val[0] if val else ""
            return val or ""
 
        loc_val  = listing.get("contentLocation")
        location = loc_val[0] if isinstance(loc_val, list) and loc_val else (loc_val if isinstance(loc_val, dict) else {})
        addr_val = location.get("address")
        addr_obj = addr_val[0] if isinstance(addr_val, list) and addr_val else (addr_val if isinstance(addr_val, dict) else {})
 
        prop_name  = extract_field(listing, "name")
        street     = extract_field(addr_obj, "streetAddress")
        prop_city  = extract_field(addr_obj, "addressLocality")
        prop_state = extract_field(addr_obj, "addressRegion")
 
        if prop_state.upper() != key:
            continue
 
        persons_val = listing.get("accountablePerson")
        if isinstance(persons_val, dict):
            persons_val = [persons_val]
        persons = [
            {
                "name":      extract_field(p, "name"),
                "telephone": extract_field(p, "telephone"),
                "email":     extract_field(p, "email"),
            }
            for p in (persons_val or [])
        ]
 
        resolved.append({
            "name": prop_name, "street": street, "city": prop_city, "state": prop_state,
            "detail_url": detail_url, "schema_url": schema_url,
            "persons": persons,
        })
 
    print(f"    [regency] resolved {len(resolved)} {key} properties (cached for rest of run)")
    _regency_properties_cache[key] = resolved
    return resolved

KIDDER_SEARCH_URL = "https://services.kidder.com/search/public/listing"
KIDDER_HEADERS = {
    "accept":               "application/json, text/javascript, */*; q=0.01",
    "accept-language":      "en-US,en;q=0.9",
    "content-type":         "application/json;charset=UTF-8",
    "origin":               "https://kidder.com",
    "referer":              "https://kidder.com/",
    "sec-fetch-dest":       "empty",
    "sec-fetch-mode":       "cors",
    "sec-fetch-site":       "same-site",
    "user-agent":           "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
}

def build_kidder_payload(city: str, state:str = None) -> dict:
    """Build the minimal POST payload for a Kidder retail for-lease search."""
    city_clean = city.split(",")[0].strip()

    def retail_specialty():
        return {
            "government": False, "mixedUse": False, "bigBox": False,
            "neighborhoodCenter": False, "anchored": False, "stripCenter": False,
            "padSite": False, "restaurant": False, "groceryAnchored": False,
            "misc": False
        }

    return {
        "includeAggregations": True,
        "numResults": 8000,
        "startIndex": 0,
        "requestId": 2172.8,
        "searchCriteria": {
            "buildingClassCriteria": {
                "trophy": False, "a": False, "b": False, "c": False, "d": False
            },
            "priceCriteria": {
                "minPrice": None, "maxPrice": None,
                "minLeaseRate": None, "maxLeaseRate": None,
                "minCapRate": None, "maxCapRate": None
            },
            "listingTypeCriteria": {
                "forSale": False, "forLease": True,
                "investmentSaleFlg": False, "nnnInvestmentFlg": False,
                "forSublease": False
            },
            "searchTerm": city_clean,
            "locationCriteria": {
                "states": [state] if state else None, "city": city_clean, "address": None, "cities": [city_clean]
            },
            "brokerName": None, "brokers": None, "buildingName": None,
            "statusCriteria": {
                "existing": False, "proposed": False,
                "underConstruction": False, "kmManagedOnly": False
            },
            "tenancyCriteria": {"single": False, "multi": False},
            "sizeCriteria": {
                "min": "", "max": "",
                "availableSf": False, "totalSf": False, "acreage": False
            },
            "propertyTypes": {
                "Office":     {"propertyType": "Office",     "selected": False, "specialtyTypeCriteria": retail_specialty()},
                "Retail":     {"propertyType": "Retail",     "selected": True, "specialtyTypeCriteria": retail_specialty()},
                "Industrial": {"propertyType": "Industrial", "selected": False, "specialtyTypeCriteria": {"government": False, "mixedUse": False, "misc": False}},
                "Land":       {"propertyType": "Land",       "selected": False, "specialtyTypeCriteria": {"vacantLand": False, "farmlandRanch": False, "misc": False}},
                "Multifamily":{"propertyType": "Multifamily","selected": False, "specialtyTypeCriteria": {"garden": False, "midrise": False, "hirise": False, "misc": False}},
                "Hospitality":{"propertyType": "Hospitality","selected": False, "specialtyTypeCriteria": {"hotel": False, "motel": False, "resort": False, "misc": False}},
                "Healthcare": {"propertyType": "Healthcare", "selected": False, "specialtyTypeCriteria": {"medicalDental": False, "veterinary": False, "misc": False}},
                "Other":      {"propertyType": "Other",      "selected": False, "specialtyTypeCriteria": {"misc": False}},
            }
        }
    }

def scrape_kidder(plaza_name,plaza_city,address,city,state,session, lat = None, lng=None):
    results = []

    session.get("https://kidder.com/", headers = KIDDER_HEADERS, timeout = 10)
    time.sleep(1)

    try:
        r = session.post(
            KIDDER_SEARCH_URL,
            json = build_kidder_payload(city),
            headers = KIDDER_HEADERS,
            timeout = 15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"  [kidder] search returned {r.status_code}")
            return results
        data = r.json()
    except Exception as e:
        print(f"  [kidder] search failed: {e}")
        return results
    
    listings = data.get("results", [])
    print(f"  [kidder] {len(listings)} listings returned for '{city}'")

    for listing in listings:
        prop_addr = listing.get("property_address", "") or ""
        prop_name = listing.get("property_name") or listing.get("building_name") or ""
        match_text = f"{prop_name} {prop_addr}"

        cand_lat = listing.get("latitude") or listing.get("lat")
        cand_lng = listing.get("longitude") or listing.get("lng") or listing.get("lon")

        if not prop_addr:
            print(f"  [kidder] candidate has no address field: {prop_name!r} - address-based verifications isn't possible for this one")

        if not plaza_matches(plaza_name, address, match_text, plaza_lat=lat,
                             plaza_lng=lng, candidate_lat = cand_lat, candidate_lng = cand_lng):
            continue
        
        listing_id = listing.get("listing_key")
        prop_key = listing.get("property_key")
        brokers = listing.get("brokers",[])
        detail_url = f"https://kidder.com/properties/single.html?listing={listing_id}&property={prop_key}"

        print(f"  [kidder] match: {prop_name} | brokers: {brokers}")

        broker_contacts = {}
        detail_api_url = f"https://services.kidder.com/properties/public/listings/{prop_key}"
        try:
            detail_r = session.get(detail_api_url, headers = KIDDER_HEADERS, timeout = 15)
            time.sleep(sleep_between)
            if detail_r.status_code == 200:
                detail_data = detail_r.json()
                for l in detail_data.get("listings", []) or []:
                    if l.get("listingKey") != listing_id:
                        continue
                    for lb in l.get("listingBrokers", []) or []:
                        person = ((lb.get("brokerAgentKey") or {}).get("person")) or {}
                        first = person.get("firstName") or ""
                        last = person.get("lastName") or ""
                        full_name = f"{first} {last}".strip()
                        if not full_name:
                            continue

                        contact = person.get("personContactInfo") or {}
                        phone_raw = (contact.get("phoneNumber") or {}).get("phoneNumber")
                        phones = extract_phones(phone_raw) if phone_raw else []
                        phone = phones[0] if phones else phone_raw
                        email = contact.get("emailAddress")
                        company = ((person.get("company") or {}).get("displayName")) or "Kidder Mathews"

                        broker_contacts[full_name.strip().lower()] = {
                            "phone": phone, "email": email, "company": company,
                        }
            else:
                print(f"  [kidder] detail fetch returned {detail_r.status_code}")
        except Exception as e:
            print(f"  [kidder] detail fetch failed: {e}")

        for broker_name in brokers:
            if not broker_name:
                continue

            info = broker_contacts.get(broker_name.strip().lower(), {})
            phone = info.get("phone")
            email = info.get("email")
            brokerage_name = info.get("company") or "Kidder Mathews"
            source = f"Kidder listing detail API: {detail_api_url}"

            if not phone and not email:
                parts = broker_name.strip().lower().split()
                if len(parts) >= 2:
                    prof_slug = f"{parts[-1]}-{parts[0]}"
                    prof_url = f"https://kidder.com/professionals/{prof_slug}/"
                    print(f"  [kidder] no contact info in detail API, trying profile: {prof_url}")

                    prof_soup = fetch(prof_url,session)
                    time.sleep(sleep_between)

                    if prof_soup:
                        tel = prof_soup.find("a", href = re.compile(r"^tel:"))
                        if tel:
                            raw = tel.get_text(strip=True) or tel["href"].replace("tel:", "")
                            phones = extract_phones(raw)
                            phone = phones[0] if phones else raw

                        email_link = prof_soup.find("a",href = re.compile(r"^mailto:"))
                        if email_link:
                            email = email_link["href"].replace("mailto:", "").split("?")[0].strip()

                        if not phone:
                            tel2 = prof_soup.find("a", class_ = "card-pro__tel")
                            if tel2:
                                phones = extract_phones(tel2.get_text())
                                phone = phones[0] if phones else None
                        if not email:
                            em2 = prof_soup.find("a", class_ = "card-pro__email")
                            if em2:
                                email = em2["href"].replace("mailto:", "").split("?")[0].strip()
                    source = f"Kidder API and profile page"
            results.append(make_record(
                plaza_name,plaza_city,address,
                broker_name,phone,email,
                brokerage_name, detail_url, source
            ))
    return results



ETHAN_PHONE = "(916) 779-1000"

ETHAN_PROPERTIES = {
    "2491 Boatman Ave": "2491 Boatman Ave, West Sacramento, California 95691",
    "5601 Florin Rd": "5601 Florin Road, Sacramento, California 95823", "Glenbrook Shopping Center": "8700 La Riveiera Dr, Sacramento, CA 95826",
    "Ardendale Shopping Center": "2901 Arden Way, Sacramento, CA 95825", "Summer Hills Plaza": "7867 Lichen Dr, Citrus Heights, CA",
    "Elkhorn Plaza": "5309-5447 Elkhorn Blvd, Sacramento, CA", "Florin Towne Centre": "Florin Rd & Stockton Blvd, Sacramento, CA 95823",
    "Northridge Plaza": "11100 Fair Oaks Blvd, Fair Oaks, CA 95628", "Mills Center": "10355 Folsom Blvd, Rancho Cordova, CA 95670",
    "Crestview Village Shopping Center": "4708 Manzanita Avenue, Carmichael, California 95608", "Rocklin Pointe": "4780 Granite Dr, Rocklin, CA 95677",
    "Zinfandel Crossings": "2800 Zinfandel Dr, Rancho Cordova, California 95670", "Eureka Ridge Plaza": "1470 Eureka Rd, Roseville, CA 95661",
    "7471 Watt Avenue": "7471 Watt Ave, North Highlands, CA 95660", "Rancho Cordova Town Center": "10801 Olson Dr, Rancho Cordova, CA 95670",
    "Plaza de Oro": "2941 Sunrise Blvd, Rancho Cordova, CA 95742", "Placer Center Plaza Shopping Center": "1811 Douglas Blvd, Roseville, CA 95661",
    "4040 Manzanita Ave": "4040 Manzanita Ave, Carmichael, CA 95608", "Granite Village Shopping Center": "8701 Auburn Folsom Rd, Granite Bay, CA 95746",
    "Folsom Village": "9580 Oak Ave Pkwy, Folsom, CA 95630", "Florin Towne Cenre": "8275 Florin Rd, Sacramento, CA 95828",
    "Elk Hills Plaza": "1251 Baseline Rd, Roseville, CA 95747", "11070 Coloma Rd": "11070 Coloma Rd, Rancho Cordova, CA",
    "Bradville Square Shopping Center": "3615 Bradshaw Rd, Sacramento, CA 95827", "Auburn Plaza Shopping Center": "5948 Auburn Blvd, Citrus Heights, CA 95621",
    "Arcade Square": "3321 Watt Ave, Sacramento, CA 95821", "American River Plaza": "9500 Greenback Ln, Folsom, CA 95630",
    "Fair Oaks Pointe": "8552 Madison Ave, Fair Oaks, CA 95628", "Ancil Hoffman Shopping Center": "7700 Sunrise Blvd, Citrus Heights, CA 95610",
}
def scrape_ethanconrad(plaza_name, plaza_city, address, city, state, session):
    if state.upper() != "CA":
        return []

    listings_url = "https://ethanconradprop.com/properties/listings/"

    try:
        soup = fetch(listings_url, session)
        time.sleep(sleep_between)
        if not soup:
            print(f"  [ethanconrad] could not fetch listings page")
            return []

        links = soup.find_all("a", href = re.compile(r"/properties/listings/\d+-"))
        print(f"  [ethanconrad] {len(links)} listing links found")

        seen_urls = set()
        for link in links:
            detail_url = urljoin("https://ethanconradprop.com", link["href"])
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            img = link.find("img")
            candidate_text = (img.get("alt", "") if img else "") or link.get_text(" ", strip=True)

            candidate_text = candidate_text.replace(","," ")
            if not plaza_matches(plaza_name,address,candidate_text):
                continue

            print(f"  [ethanconrad] match: {candidate_text[:100]}")
            return [make_record(
                plaza_name, plaza_city, address,
                "Ethan Conrad Properties", ETHAN_PHONE, None,
                "Ethan Conrad Properties", detail_url,
                "Fixed Company Phone"
            )]
        
        if links:
            print(f"  [ethanconrad] 0 matches from {len(links)} candidates - sample:")
            for link in links[:5]:
                img = link.find("img")
                sample = img.get("alt", "") if img else link.get_text(strip=True)
                print(f"  [ethanconrad]  - {sample}")
        
        return []
    except Exception as e:
        print(f"  [ethanconrad] unexpected: {e}")
        import traceback
        traceback.print_exc()
        return []



NAMDAR_PHONE = "(516) 773-0010"

NAMDAR_PROPERTIES = {
    # California
    "sunrise mall": "Sunrise Mall, Citrus Heights, CA", "2300 broadway": "2300 Broadway, New York, NY",
    "fort gratiot plaza": "Fort Gratiot Plaza, Fort Gratiot, MI", "sierra vista mall": "Sierra Vista Mall, Clovis, CA",
    "florence mall": "Florence Mall, Florence, KY", "green tree mall": "Green Tree Mall, Clarksville, IN",
    "chapel hills mall": "Chapel Hills Mall, Colorado Springs, CO", "country club mall": "Country Club Mall, Cumberland, MD",
    "dumbo retail": "Dumbo Retail, Brooklyn, NY", "south town plaza": "South Town Plaza, Rochester, NY",
    "matteson town center": "Matteson Town Center, Matteson, IL", "central mall": "Central Mall, Fort Smith, AR",
    "acadiana mall": "Acadiana Mall, Lafayette, LA", "176 mulberry street": "176 Mulberry Street, New York, NY",
    "west valley mall": "West Valley Mall, Tracy, CA", "fallen timbers": "Fallen Timbers, Maumee, OH",
    "outlets at tuscola": "Outlets at Tuscola, Tuscola, IL", "salem plaza": "Salem Plaza, Trotwood, OH",
    "140 essex street": "140 Essex Street, New York, NY", "284 fifth avenue": "284 Fifth Avenue, New York, NY",
    "stonecrest marketplace": "Stonecrest Marketplace, Lithonia, GA", "enfield square mall": "Enfield Square Mall, Enfield, CT",
    "westfield mall": "Westfield Mall, Westland, MI", "mesilla valley mall": "Mesilla Valley Mall, Las Cruces, NM",
    "patchogue sunrise": "Patchogue Sunrise, Patchogue, NY", "trumbull mall": "Trumbull Mall, Trumbull, CT",
    "river oaks center": "River Oaks Center, Calumet City, IL", "southland mall": "Southland Mall, Hayward, CA",
    "crossroads mall (wv)": "Crossroads Mall, Mount Hope, WV", "marketplace of brown deer": "Marketplace of Brown Deer, Brown Deer, WI",
    "tuttle crossing mall": "Tuttle Crossing Mall, Dublin, OH", "berkshire mall": "Berkshire Mall, Wyomissing, PA",
    "the shops at ithaca mall": "The Shops at Ithaca Mall, Ithaca, NY", "fairview heights plaza": "Fairview Heights Plaza, Fairview Heights, IL",
    "fountain place": "Fountain Place, Logan, WV", "the citadel mall": "The Citadel Mall, Colorado Springs, CO",
    "the gallery at south dekalb": "The Gallery at South Dekalb, Decatur, GA", "peppertree commons": "Peppertree Commons, Commack, NY",
    "wenatchee valley mall": "Wenatchee Valley Mall, East Wenatchee, WA", "river valley mall": "River Valley Mall, Lancaster, OH",
    "conway towne center": "Conway Towne Center, Conway, AR", "times square mall": "Times Square Mall, Mount Vernon, IL",
    "the shoppes at buckland hills": "The Shoppes at Buckland Hills, Manchester, CT", "beaver valley mall": "Beaver Valley Mall, Monaca, PA",
    "mall de las aguilas": "Mall de las Aguilas, Eagle Pass, TX", "merrit square mall": "Merrit Square Mall, Merritt Island, FL",
    "mt. shasta mall": "Mt. Shasta Mall, Redding, CA", "centereach commons": "Centereach Commons, Centereach, NY",
    "concord mall": "Concord Mall, Wilmington, DE", "severance town center": "Severance Town Center, Cleveland, OH",
    "pullman park": "Pullman Park, Chicago, IL", "the lakes mall": "The Lakes Mall, Muskegon, MI",
    "bangor mall": "Bangor Mall, Bangor, ME", "northwest arkansas mall": "Northwest Arkansas Mall, Fayetteville, AR",
    "south park mall": "South Park Mall, San Antonio, TX", "midway mall": "Midway Mall, Elyria, OH",
    "ford city mall": "Ford City Mall, Chicago, IL", "west palm shopping center": "West Palm Shopping Center, West Palm Beach, FL",
    "nittany mall": "Nittany Mall, State College, PA", "southland mall": "Southland Mall, Memphis, TN",
    "uniontown mall": "Uniontown Mall, Uniontown, PA", "village at bay park": "Village at Bay Park, Ashwaubenon, WI",
    "hamilton mall": "Hamilton Mall, Mays Landing, NJ", "south shore mall": "South Shore Mall, Bay Shore, NY",
    "marketplace of matteson": "Marketplace of Matteson, Matteson, IL", "meriden mall": "Meriden Mall, Meriden, CT",
    "voorhees town center": "Voorhees Town Center, Voorhees, NJ", "valley hills mall": "Valley Hills Mall, Hickory, NC",
    "westgate mall": "Westgate Mall, Amarillo, TX", "gulf view square mall": "Gulf View Square Mall, Port Richey, FL",
    "cache valley mall": "Cache Valley Mall, Logan, UT", "genesee valley mall": "Genesee Valley Mall, Flint, MI",
    "centerpointe of woodridge": "Centerpoint of Woodridge, Woodridge, IL", "tierpoint": "Tierpoint, Bellevue, NE",
    "westgate mall": "Westgate Mall, Spartanburg, SC", "crossroads mall": "Crossroads Mall, Waterloo, IA",
    "winchendon retail": "Winchendon Retail, Winchendon, MA", "galleria at pittsburgh mills": "Galleria at Pittsburgh Mills, Tarentum, PA",
    "heritage mall": "Heritage Mall, Albany, OR", "marketplace college avenue": "Marketplace College Avenue, Appleton, WI",
    "university mall": "University Mall, Carbondale, IL", "outlets at west branch": "Outlets at West Branch, West Branch, MI",
    "wiregrass commons mall": "Wiregrass Commons Mall, Dothan, AL", "louis joliet mall": "Louis Joliet Mall, Joliet, IL", 
    "logan valley mall": "Logan Valley Mall, Altoona, PA", "jackson crossing": "Jackson Crossing, Jackson, MI",
    "hickory point mall": "Hickory Point Mall, Forsyth, IL", "grand traverse mall": "Grand Traverse Mall, Grand Traverse, MI",
    "eastdale mall": "Eastdale Mall, Montgomery, AL", "north hanover mall": "North Hanover Mall, Hanover, PA",
    "marley station mall": "Marley Station Mall, Glen Burnie, MD", "canton centere": "Canton Centere, West Canton, OH",
}

def scrape_namdar(plaza_name, plaza_city, address, city, state, session):
    results = []
    name_norm = normalize(plaza_name)

    for key in NAMDAR_PROPERTIES:
        if plaza_matches(key.title(), None,name_norm):
            results.append(make_record(
                plaza_name, plaza_city, address,
                "Namdar Realty Group",
                NAMDAR_PHONE, None,
                "Namdar Realty Group",
                f"https://namdarrealtygroup.com/?page=search&proptype=&keyword={city.replace(' ', '+')}&state={state.upper()}",
                "Namdar — fixed company phone, matched by property name",
            ))
            return results

    search_url = (
        f"https://namdarrealtygroup.com/"
        f"?page=search&proptype=&keyword={city.replace(' ', '+')}&state={state.upper()}"
    )
    soup = fetch(search_url, session)
    if not soup:
        return results
    time.sleep(sleep_between)

    cards = soup.find_all(["div", "li", "article"],
                          class_=re.compile(r"property|result|listing|card", re.I))
    for card in cards:
        if not plaza_matches(plaza_name, address, card.get_text(" ", strip=True)):
            continue
        link = card.find("a", href=re.compile(r"page=detail"))
        detail_url = urljoin("https://namdarrealtygroup.com", link["href"]) if link else search_url
        results.append(make_record(
            plaza_name, plaza_city, address,
            "Namdar Realty Group",
            NAMDAR_PHONE, None,
            "Namdar Realty Group",
            detail_url,
            "Namdar — fixed company phone (516) 773-0010",
        ))
        break

    return results

SRS_API = "https://srsre-next-412955565034.us-central1.run.app/api/property-search"
SRS_HEADERS = {
    "accept":           "*/*",
    "accept-language":  "en-US,en;q=0.9",
    "content-type":     "application/json",
    "origin":           "https://srsre.com",
    "referer":          "https://srsre.com/",
    "user-agent":       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
}

def build_srs_payload(city: str, state: str, plaza_name: str = "",
                       address: str = "", lat: float = None, lng: float = None) -> dict:
    # Bounding box around plaza center (0.5 degree ≈ 35 miles)
    if lat and lng:
        delta = 0.5
        bb_top_left     = [lat + delta, lng - delta]
        bb_bottom_right = [lat - delta, lng + delta]
    else:
        # Fallback — wide US box
        bb_top_left     = [56.650590464543484, -115.1905735625]
        bb_bottom_right = [11.599150095394833, -78.8917454375]

    # Search term — plaza name is most specific, fall back to city
    if plaza_name and plaza_name != "Unnamed Retail Center":
        search_term = plaza_name.lower()
    elif address and address != "-":
        search_term = address.split(",")[0].strip().lower()
    else:
        search_term = city.lower()

    return {
        "query": {
            "offset":          0,
            "pageSize":        20,
            "availability":    "lease",
            "broker":          "",
            "cap_req":         "true",
            "mb_top_left":     bb_top_left,
            "mb_bottom_right": bb_bottom_right,
            "office":          "",
            "order":           "DESC",
            "orderby":         "relevance",
            "portfolio":       "",
            "price_req":       "true",
            "s":               search_term,
            "type":            "retail",
        },
        "client_ip": ""
    }
def decode_cf_email(protected:str):
    if not protected:
        return None
    frag = protected.split("#")[-1].strip()
    try:
        r = int(frag[:2], 16)
        email = "".join(
            chr(int(frag[i:i + 2],16) ^ r) for i in range(2, len(frag),2)
        )
        return email if "@" in email else None
    except Exception:
        return None

def fetch_impersonated(url: str):
    try:
        r = requests.get(url, headers = headers, timeout = request_timeout, impersonate="chrome120")
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        else:
            print(f"  [fetch_impersonated] {url[:80]}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  [fetch_impersonated] {url[:80]}: {e}")
    return None

def scrape_srs(plaza_name,plaza_city,address,city,state,session,lat=None, lng=None):
    results = []
 
    try:
        r = session.post(
            SRS_API,
            json=build_srs_payload(city, state, plaza_name, address, lat, lng),
            headers=SRS_HEADERS,
            timeout=15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"    [srs] API returned {r.status_code}")
            return results
        data = r.json()
    except Exception as e:
        print(f"    [srs] API failed: {e}")
        return results
 
    print(f"    [srs] response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    listings = []
    if isinstance(data, list):
        listings = data
    elif isinstance(data, dict):
        listings = (data.get("properties") or data.get("results") or
                    data.get("listings") or data.get("data") or [])
 
    print(f"    [srs] {len(listings)} listings returned")
    if listings:
        print(f"    [srs] first listing top-level keys: {list(listings[0].keys())}")
        sans_apto = {k: v for k, v in listings[0].items() if k != "apto_data"}
        print(f"    [srs] first listing (excl. apto_data): {_json.dumps(sans_apto, indent=2, default=str)[:3000]}")
 
    for listing in listings:
        apto   = listing.get("apto_data", {})
        loc    = listing.get("location", {}) or {}
        office = listing.get("office", "")
        tags   = listing.get("tags", []) or []
 
        prop_name = apto.get("Name") or ""
        prop_addr = (apto.get("Property_Address__c") or
                    apto.get("Property_Address_for_Marketing_Materials__c") or
                    loc.get("address") or "")
 
        match_text = f"{prop_name} {prop_addr}"
        if not plaza_matches(plaza_name, address, match_text,
                             plaza_lat=lat, plaza_lng=lng,
                             candidate_lat=loc.get("lat"), candidate_lng=loc.get("lon")):
            continue
 

        permalink = listing.get("permalink")
        if permalink:
            detail_url = urljoin("https://srsre.com", permalink)
        else:
            listing_id = listing.get("id", "")
            slug       = prop_name.lower().replace(" ", "-").replace("|", "").replace(",", "").strip("-")
            city_slug  = (loc.get("city") or city).lower().replace(" ", "-")
            state_slug = state.lower()
            detail_url = f"https://srsre.com/properties/lease/retail/{state_slug}/{city_slug}/{slug}/l{listing_id}"
 
        broker_tags = [t for t in tags if "-" in t and not any(
            x in t for x in ["retail", "lease", "sale", "office", "industrial"]
        )]

        page_contacts = []
        detail_soup = fetch_impersonated(detail_url)
        time.sleep(sleep_between)
 
        if detail_soup:
            for tel in detail_soup.find_all("a", href=re.compile(r"^tel:")):
                phones = extract_phones(tel.get_text(strip=True) or tel["href"])
                phone  = phones[0] if phones else tel["href"].replace("tel:", "")
 
                name, email = None, None
                container = tel
                for _ in range(6):
                    container = container.parent
                    if container is None:
                        break
                    cf_link = container.find("a", href=re.compile(r"email-protection"))
                    if cf_link and not email:
                        email = decode_cf_email(cf_link.get("href", ""))
                    if not name:
                        heading = container.find(re.compile(r"^h[1-6]$"))
                        if heading:
                            name = heading.get_text(strip=True)
                    if name and email:
                        break
 
                if name or phone or email:
                    page_contacts.append({"name": name, "phone": phone, "email": email})
 
            print(f"    [srs] contact block found {len(page_contacts)} agent(s) on detail page")
        else:
            print(f"    [srs] could not fetch detail page: {detail_url}")
 
        if page_contacts:
            for c in page_contacts:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    c.get("name"), c.get("phone"), c.get("email"),
                    "SRS Real Estate Partners", detail_url,
                    f"SRS API → detail page contact block: {detail_url}",
                ))
        elif broker_tags:
            for slug_name in broker_tags:
                parts      = slug_name.split("-")
                agent_name = " ".join(w.capitalize() for w in parts)
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, None, None,
                    "SRS Real Estate Partners", detail_url,
                    "SRS API — tags only, detail page contact block not found",
                ))
        else:
            results.append(make_record(
                plaza_name, plaza_city, address,
                None, None, None,
                "SRS Real Estate Partners", detail_url,
                "SRS API — no broker tags found",
            ))
 
    return results


def scrape_cushman(plaza_name,plaza_city,address,city,state,session):
    results = []
    query = city.lower().replace(" ", "+")
    search_url = (
        f"https://www.cushmanwakefield.com/en/united-states/properties"
        f"/lease/search/retail?q={query}&sort=relevance"
    )
    soup = fetch(search_url, session)
    if not soup:
        return results
    time.sleep(sleep_between)

    cards = soup.find_all("a",class_ = "js-property-card")
    seen_urls = set()
    for card in cards:
        title_el = card.find("p", class_ = re.compile(r"cw-search-card__title"))
        addr_el = card.find("p", class_ = re.compile(r"cw-search-card__address"))
        card_text = " ".join([
            title_el.get_text(strip=True) if title_el else "",
            addr_el.get_text(strip=True) if addr_el else "",
        ])
        if not plaza_matches(plaza_name,address, card_text):
            continue

        href = card.get("href", "")
        if not href:
            continue
        detail_url = urljoin("https://www.cushmanwakefield.com", href)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)

        detail = fetch(detail_url,session)
        if not detail:
            continue
        time.sleep(sleep_between)

        contact_headings = detail.find_all("h6")
        for h6 in contact_headings:
            name_link = h6.find("a")
            if not name_link:
                continue
            agent_name = name_link.get_text(strip=True)

            container = h6.find_parent("div", class_ = "card-body")
            if not container:
                continue
            phone = None
            email = None

            if container:
                tel = container.find("a", href = re.compile(r"^tel:"))
                if tel:
                    raw = tel.get_text(strip=True)
                    phones = extract_phones(raw)
                    phone = phones[0] if phones else raw

                vcard_link = container.find("a",href =re.compile(r"GetVCard"))
                if vcard_link:
                    vcard_url = urljoin("https://www.cushmanwakefield.com", vcard_link["href"])
                    try:
                        vr = session.get(vcard_url, headers = headers, timeout = 10)
                        time.sleep(0.5)
                        if vr.status_code == 200:
                            email_match = re.search(r"EMAIL[^:]*:([^\r\n]+)", vr.text)
                            if email_match:
                                email = email_match.group(1).strip()
                    except Exception:
                        pass
            
            if agent_name or phone or email:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email, "Cushman & Wakefield",
                    detail_url, "Cushman contact page + vcard email"
                ))

    seen_agents = set()
    unique_results = []
    for r in results:
        key = (r.get("agent_name"), r.get("phone"), r.get("email"))
        if key not in seen_agents:
            seen_agents.add(key)
            unique_results.append(r)
    return unique_results

def scrape_kimco(plaza_name, plaza_city,address,city,state,session):
    results = []
    search_url = (
        f"https://www.kimcorealty.com/leasing/available-spaces"
        f"?location={city.replace(' ', '+')}%2C+{state}"
    )
    soup = fetch(search_url,session)
    if not soup:
        return results
    time.sleep(sleep_between)

    for card in soup.find_all(["div", "article"], class_=re.compile(r"property|listing|card|result", re.I)):
        if not plaza_matches(plaza_name,address,card.get_text(" ", strip=True)):
            continue
        link = card.find("a", href=re.compile(r"/property/|/leasing/"))
        if not link:
            continue
        detail_url = urljoin("https://www.kimcorealty.com",link["href"])
        detail = fetch(detail_url,session)
        if not detail:
            continue
        time.sleep(sleep_between)

        agent_name = None
        phone = None
        email = None

        for el in detail.find_all(["div", "section"], class_=re.compile(r"contact|leasing|agent|broker",re.I)):
            name_el = el.find(["h3", "h4", "strong", "p"])
            if name_el:
                txt = name_el.get_text(strip=True)
                if re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+",txt):
                    agent_name = txt
            tel = el.find("a", href = re.compile(r"^tel:"))
            if tel:
                phones = extract_phones(tel.get_text(strip=True) or tel["href"])
                phone = phones[0] if phones else None
            em = el.find("a",href = re.compile(r"^mailto:"))
            if em:
                email = em["href"].replace("mailto:", "").split("?")[0].strip()
        
        results.append(make_record(
            plaza_name,plaza_city,address,
            agent_name,phone,email,
            "Kimco Realty", detail_url,
            "kimco realty -> property detail -> leasing contact"
        ))
    return results

def scrape_inland(plaza_name,plaza_city,address,city,state,session):
    results = []
    state_names = {
        "CA": "California", "TX": "Texas", "FL": "Florida", "IL": "Illinois", "NY": "New York",
        "WA": "Washington", "OR": "Oregon", "AZ": "Arizona", "CO": "Colorado", "GA": "Georgia",
        "NC": "North Carolina", "OH": "Ohio", "PA": "Pennsylvania", "TN": "Tennessee", "VA": "Virginia",
        "NV": "Nevada", "UT": "Utah", "MN": "Minnesota", "MO": "Missouri", "WI": "Wisconsin", "IN": "Indiana",
        "MI": "Michigan", "KY": "Kentucky", "AL": "Alabama"
    }
    state_full = state_names.get(state.upper(),state)
    search_url = f"https://inland-investments.com/properties?location={state_full}&type=Retail"

    soup = fetch(search_url,session)
    if not soup:
        return results
    time.sleep(sleep_between)

    for card in soup.find_all(["div","article"],class_ = re.compile(r"property|listing|card", re.I)):
        if not plaza_matches(plaza_name,address,card.get_text(" ",strip=True)):
            continue
        link = card.find("a",href=True)
        if not link:
            continue
        detail_url = urljoin("https://inland-investments.com",link["href"])
        detail = fetch(detail_url,session)
        if not detail:
            continue
        time.sleep(sleep_between)

        phone = None
        email = None
        agent_name = None

        tel = detail.find("a",href=re.compile(r"^tel:"))
        if tel:
            phones = extract_phones(tel.get_text(strip=True) or tel["href"])
            phone = phones[0] if phones else None
        em = detail.find("a",href=re.compile(r"^mailto:"))
        if em:
            email = em["href"].replace("mailto:","").split("?")[0].strip()

        results.append(make_record(
            plaza_name,plaza_city,address,agent_name,phone,email,"Inland Real Estate", detail_url,"state search -> property detail"
        ))
    return results
import json as _json

CBRE_API = "https://www.cbre.com/listings-api/propertylistings/query"
def build_cbre_polygon(lat:float,lng:float,delta:float = 0.1) -> str:
    north = lat+delta
    south = lat-delta
    east = lng+delta
    west = lng-delta

    points = [
        f"{south},{west}",
        f"{north},{west}",
        f"{north},{east}",
        f"{south},{east}",
        f"{south},{west}", 
    ]
    import json as _json
    return _json.dumps([points])

def scrape_cbre(plaza_name, plaza_city, address, city, state, session,
                lat=None, lng=None):
    results = []

    if not lat or not lng:
        print(f"    [cbre] no coords for {city} — skipping")
        return results

    # Build polygon as URL string directly — don't let requests encode it
    delta = 0.1
    north = lat + delta
    south = lat - delta
    east  = lng + delta
    west  = lng - delta

    # Exact format confirmed from Network tab
    polygon = (
        f'[["{south}","{west}",'
        f'"{north}","{west}",'
        f'"{north}","{east}",'
        f'"{south}","{east}",'
        f'"{south}","{west}"]]'
    )

    from urllib.parse import urlencode, quote
    polygon_str = build_cbre_polygon(lat, lng)
    query = urlencode({
        "Site":             "us-comm",
        "CurrencyCode":     "USD",
        "Unit":             "sqft",
        "Common.Aspects":   "isLetting",
        "Common.UsageType": "Retail",
        "PageSize":         500,
        "Page":             1,
    }) + "&PolygonFilters=" + quote(polygon_str, safe="")

    full_url = f"{CBRE_API}?{query}"
    print(f"    [cbre] requesting: {full_url[:120]}...")

    try:
        r = requests.get(
            full_url,
            headers={**headers, "Referer": "https://www.cbre.com/"},
            timeout=15,
            impersonate="chrome120"
        )
        time.sleep(sleep_between)
        print(f"    [cbre] status={r.status_code} length={len(r.text)}")

        if r.status_code != 200:
            print(f"    [cbre] response: {r.text[:200]}")
            return results

        data = r.json()
    except Exception as e:
        print(f"    [cbre] API failed: {e}")
        return results

    documents = data.get("Documents", [])
    listings = []
    for doc in documents:
        if isinstance(doc, list):
            listings.extend(doc)
        elif isinstance(doc, dict):
            listings.append(doc)

    print(f"    [cbre] {len(listings)} retail listings in bbox")

    for listing in listings:
        addr_obj   = listing.get("Common.ActualAddress", {})
        prop_name  = addr_obj.get("Common.Line1", "")
        prop_addr  = addr_obj.get("Common.Line2", "")
        prop_city  = addr_obj.get("Common.Locallity", "")
        prop_state = addr_obj.get("Common.Region", "")

        if state.upper() != prop_state.upper():
            continue

        cand_lat = addr_obj.get("Common.Latitude") or listing.get("Common.Latitude")
        cand_lng = addr_obj.get("Common.Longitude") or listing.get("Common.Longitude")

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name, address, match_text,
                             plaza_lat = lat, plaza_lng = lng,
                             candidate_lat=cand_lat, candidate_lng = cand_lng):
            continue

        print(f"  [cbre] match: {prop_name} | {prop_addr}")

        prop_url = listing.get("Common.PropertyUrl") or listing.get("Common.Url") or ""
        prop_id  = listing.get("Common.PrimaryKey") or listing.get("Common.PropertyId") or ""
        if not prop_url and prop_id:
            prop_url = f"https://www.cbre.com/properties/properties-for-lease/commercial-space/details/{prop_id}"
        if prop_url and not prop_url.startswith("http"):
            prop_url = f"https://www.cbre.com{prop_url}"

        for agent in listing.get("Common.Agents", []):
            agent_name = agent.get("Common.AgentName")
            email      = agent.get("Common.EmailAddress")
            phone_raw  = agent.get("Common.TelephoneNumber", "") or ""
            phones     = extract_phones(phone_raw)
            phone      = phones[0] if phones else phone_raw or None

            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email,
                    "CBRE", prop_url,
                    "CBRE listings API → Common.Agents",
                ))
    seen = set()
    unique = []
    for r in results:
        key = (r.get("agent_name"), r.get("email"),r.get("plaza_name"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    if not unique and listings:
        print(f"  [cbre] 0 matches from {len(listings)} candidates - sample:")
        for listing in listings[:5]:
            a = listing.get("Common.ActualAddress", {})
            print(f"  [cbre]  - {a.get('Common.Line1','')} | {a.get('Common.Line2','')} | {a.get('Common.Locallity','')}, {a.get('Common.Region','')}")
            
    return unique

avison_api = "https://pse-api.sharplaunch.com/data"
avison_api_key = "b9fda00f3d4d7f623665270841e32176"

_avison_properties = None
_avison_team = None

def get_avison_data(session):
    global _avison_properties, _avison_team
    avison_headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.avisonyoung.us",
        "Referer": "https://www.avisonyoung.us/properties",
        "X-Api-Key": avison_api_key,
        "User-Agent": headers.get("User-Agent"),
    }
    if _avison_properties is None:
        try:
            r = session.get(
                f"{avison_api}?entity=website&status=active,escrow,closed",
                headers = avison_headers, timeout=20
            )
            data = r.json()
            _avison_properties = data.get("items", [])
            print(f"  [avison] Loaded {len(_avison_properties)} properties")
        except Exception as e:
            print(f"  [avison] Properties fetch failed: {e}")
            _avison_properties = []
    if _avison_team is None:
        try:
            r = session.get(
                f"{avison_api}?entity=team_member",
                headers=avison_headers,timeout=20
            )
            data = r.json()
            team_list = data.get("items", [])
            _avison_team = {t["id"]: t for t in team_list}
            print(f"  [avison] Loaded {len(_avison_team)} team members")
        except Exception as e:
            print(f"  [avison] Team fetch failed: {e}")
            _avison_team = {}
    return _avison_properties,_avison_team

def scrape_avison(plaza_name,plaza_city,address,city,state,session):
    results = []
    properties, team = get_avison_data(session)
    if not properties:
        return results
    for prop in properties:
        prop_city = prop.get("city", "")
        prop_state = prop.get("state", "")
        prop_addr = prop.get("address", "")
        prop_name = prop.get("name", "")

        if state.upper() != prop_state.upper():
            continue
        if city.lower() != prop_city.lower():
            continue
        types = prop.get("type",[]) or []
        if not any("retail" in t.lower() for t in types):
            continue

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name,address,match_text):
            continue

        print(f"  [avison] match: {prop_name} | {prop_addr}")

        detail_url = prop.get("external_url", "")
        team_ids = prop.get("team_member_ids", []) or []

        for tid in team_ids:
            member = team.get(tid)
            if not member:
                continue

            first = member.get("first_name", "")
            last = member.get("last_name", "")
            agent_name = f"{first} {last}".strip()
            email = member.get("email")
            phone_raw = member.get("phone","") or ""
            phones = extract_phones(phone_raw)
            phone = phones[0] if phones else phone_raw or None

            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name,plaza_city,address,
                    agent_name,phone,email,
                    "Avison Young", detail_url,
                    "website + team_member"
                ))
    return results

colliers_api = "https://www.colliers.com/coveo/rest/search/v2"
def _colliers_search(session,q,aq="",cq='(@z95xlanguage==en) (@z95xlatestversion==1)', num_results = 10):
    payload = {
        "aq": aq,
        "cq": cq,
        "q": q,
        "searchHub": "Properties",
        "locale": "en",
        "firstResult": 0,
        "numberOfResults": num_results,
        "sortCriteria": "relevancy",
    }
    r = session.post(colliers_api,json=payload,
                     headers = {"Content-Type": "application/json"}, timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

def scrape_colliers(plaza_name,plaza_city,address,city,state,session):
    results = []
    query = plaza_name if plaza_name != "Unnamed Retail Center" else city
    props = _colliers_search(
        session,query,
        aq='(@propertyforsaleorleasecomputed=="For Lease")',
        num_results=10
    )
    time.sleep(sleep_between)

    print(f"  [colliers] {len(props)} property results for '{query}'")

    for prop in props:
        raw = prop.get("raw", {})
        prop_name = raw.get("title","")
        prop_addr = raw.get("propertyz32xfullz32xaddress","")

        match_text = f"{prop_name} {prop_addr}"
        if not plaza_matches(plaza_name,address,match_text):
            continue

        print(f"  [colliers] match: {prop_name} | {prop_addr}")
        detail_url = raw.get("sysprintableuri","")
        expert_names = raw.get("relatedz32xez120xpertsz32xvar",[]) or []
        expert_ids = raw.get("relatedz32xez120xperts",[]) or []

        for i, expert_id in enumerate(expert_ids):
            expert_results = _colliers_search(
                session,"",
                aq=f'@permanentid=="{expert_id}"',
                num_results=1
            )
            time.sleep(sleep_between)

            if not expert_results:
                continue
            expert_raw = expert_results[0].get("raw",{})
            agent_name = expert_raw.get("displayname") or (
                expert_names[i] if i < len(expert_names) else None
            )
            office_phone = expert_raw.get("officez32xphone", "")
            mobile_phone = expert_raw.get("mobilez32xphone", "")
            phone_raw = mobile_phone or office_phone
            phones = extracts = extract_phones(phone_raw)
            phone = phones[0] if phones else phone_raw or None

            email = None
            if agent_name:
                parts = agent_name.lower().split()
                if len(parts) >= 2:
                    email = f"{parts[0]}.{parts[-1]}@colliers.com"
            if agent_name or phone or email:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email,
                    "Colliers", detail_url,
                    "colliers api"
                ))
    seen = set()
    unique = []
    for r in results:
        key = (r.get("agent_name"), r.get("email"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique

newmark_api = "https://api-public.nim.nmrk.com/api/properties/search"
newmark_state_codes = {
    "AL": 1, "AK": 2, "AZ": 3, "AR": 4, "CA": 5, "CO": 6, "CT": 7, "DE": 8,
    "FL": 9, "GA": 10, "HI": 11, "ID": 12, "IL": 13, "IN": 14, "IA": 15,
    "KS": 16, "KY": 17, "LA": 18, "ME": 19, "MD": 20, "MA": 21, "MI": 22,
    "MN": 23, "MS": 24, "MO": 25, "MT": 26, "NE": 27, "NV": 28, "NH": 29,
    "NJ": 30, "NM": 31, "NY": 32, "NC": 33, "ND": 34, "OH": 35, "OK": 36,
    "OR": 37, "PA": 38, "RI": 39, "SC": 40, "SD": 41, "TN": 42, "TX": 43,
    "UT": 44, "VT": 45, "VA": 46, "WA": 47, "WV": 48, "WI": 49, "WY": 50,
}
def build_newmark_payload(city:str, state:str) -> dict:
    state_code = newmark_state_codes.get(state.upper(),5)
    return {
        "type": 1,
        "listingIds": [],
        "propertyTypes": [],
        "brokers": [],
        "statuses": [],
        "states": [],
        "propertySubtypes": [],
        "spaceTypes": [],
        "buildingClasses": [],
        "leaseTypes": [],
        "locationOption": {
            "name": city,
            "city": city,
            "state": state_code,
            "country": "United States",
            "additionalField": f"{state} United States",
            "additionalHighlights": [city],
            "scope": 44,
            "locationType": 3,
            "type": "location"
        },
        "locationOptions": [
            {
                "name": city,
                "city": city,
                "state": state_code,
                "country": "United States",
                "additionalField": f"{state} United States",
                "additionalHighlights": [city],
                "scope": 44,
                "locationType": 3,
                "type": "location",
            }
        ],
        "excludeUnpriced": False,
        "page": 0,
        "take": 20,
        "sortBy": "createdOn",
        "isAscending": False
    }

newmark_search_api = "https://api-public.nim.nmrk.com/api/properties/search"
newmark_detail_api = "https://api-public.nim.nmrk.com/api/properties/{id}"
newmark_buildout_token = "58e0b0dd25f4956b52239a56e5d54865c8af0008"

def scrape_newmark(plaza_name,plaza_city,address,city,state,session):
    results = []

    try:
        r = session.post(
            newmark_search_api,
            json=build_newmark_payload(city, state),
            headers={
                "accept":       "application/json",
                "content-type": "application/json",
                "referer":      "https://nim.nmrk.com/",
            },
            timeout=15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"    [newmark] search returned {r.status_code}")
            return results
        data = r.json()
    except Exception as e:
        print(f"    [newmark] search failed: {e}")
        return results

    listings = data.get("data", [])
    print(f"    [newmark] {len(listings)} listings for '{city}, {state}'")

    for listing in listings:
        props = listing.get("properties", [])
        if not props:
            continue
        prop = props[0]

        prop_addr = prop.get("address", "")
        prop_city = prop.get("city", "")
        prop_name = listing.get("name", "") or prop_addr

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name, address, match_text):
            continue

        slug = listing.get("slug", "")
        detail_url = listing.get("externalWebsiteUrl", "")
        print(f"    [newmark] match: {prop_addr} — fetching detail for brokers")

        buildout_url = (
            f"https://buildout.nmrk.com/plugins/{newmark_buildout_token}"
            f"/www.nmrk.com/inventory/{slug}"
            f"?pluginId=0&iframe=true&embedded=true&cacheSearch=true"
        )

        detail_soup = fetch(buildout_url, session)
        time.sleep(sleep_between)
        if not detail_soup:
            continue

        tel_links = detail_soup.find_all("a", href=re.compile(r"^tel:"))
        for tel in tel_links:
            phone_text = tel.get_text(strip=True)
            phones = extract_phones(phone_text) or extract_phones(tel["href"])
            phone  = phones[0] if phones else None

            phone_div = tel.find_parent("div", class_="pdt-broker-phone")
            broker_card = phone_div.find_parent("div") if phone_div else None
            email = None
            agent_name = None
            search_container = phone_div
            for _ in range(4): 
                if not search_container:
                    break
                text = search_container.get_text()
                email_match = re.search(r"[a-zA-Z0-9._%+\-]+@nmrk\.com", text)
                if email_match:
                    email = email_match.group(0)
                    break
                search_container = search_container.find_parent("div")

            name_link = tel.find_previous("a", href="#")
            if name_link:
                agent_name = name_link.get_text(strip=True)

            print(f"    [newmark debug] agent={agent_name}, phone={phone}, email={email}")

            if agent_name or phone or email:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email,
                    "Newmark", detail_url,
                    f"Newmark Buildout page",
                ))
    return results


lee_buildout_token = "9a64a93980aeae8db347e72cdfa8ca6107acc9a"
lee_search_url = f"https://buildout.com/plugins/{lee_buildout_token}/inventory"

def scrape_lee(plaza_name,plaza_city, address, city, state, session, lat = None, lng=None):
    results = []
    if not lat or not lng:
        print(f"  [lee] no coords for {city} - skipping")
        return results

    delta = 0.3
    exact_url = (
        "https://buildout.com/plugins/9a64a93980aeae8db347e72cdfa8ca61017acc9a/inventory"
        f"?lat_min={lat-delta}&lat_max={lat+delta}&lng_min={lng-delta}&lng_max={lng+delta}"
        "&page=0&light_view=true&placesAutoComplete="
        "&q%5Btype_use_offset_eq_any%5D%5B%5D="
        "&q%5Bsale_or_lease_eq%5D=lease"
        "&q%5Bwith_space_type_ids%5D%5B%5D="
        "&q%5Bbuilding_size_sf_gteq%5D=&q%5Bbuilding_size_sf_lteq%5D="
        "&q%5Blot_size_acres_gteq%5D=&q%5Blot_size_acres_lteq%5D="
        "&q%5Bproperty_research_property_year_built_gteq%5D=&q%5Bproperty_research_property_year_built_lteq%5D="
        "&q%5Blistings_data_max_space_available_on_market_gteq%5D=&q%5Blistings_data_min_space_available_on_market_lteq%5D="
        "&q%5Bmax_lease_rate_gteq%5D=&q%5Bmin_lease_rate_lteq%5D="
        "&q%5Bmax_lease_rate_monthly_gteq%5D=&q%5Bmin_lease_rate_monthly_lteq%5D="
        "&q%5Bproperty_research_property_number_of_units_gteq%5D=&q%5Bproperty_research_property_number_of_units_lteq%5D="
        f"&q%5Bstate_eq_any%5D%5B%5D={state}"
        "&q%5Bs%5D%5B%5D=last_edited_at+desc"
    )

    try:
        r = session.get(
            exact_url,
            headers={"Accept": "application/json", "Referer": "https://www.lee-associates.com/"},
            timeout=15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"    [lee] search returned {r.status_code}")
            return results
        data = r.json()
    except Exception as e:
        print(f"    [lee] search failed: {e}")
        return results

    listings = data.get("inventory") or []
    print(f"    [lee] {len(listings)} listings for '{city}, {state}'")

    for listing in listings:
        prop_name = listing.get("name", "") or listing.get("display_name", "")
        prop_addr = listing.get("address", "")
        prop_city = listing.get("city", "")

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name, address, match_text):
            continue

        print(f"    [lee] match: {prop_name} | {prop_addr}")

        detail_url = listing.get("show_link", "")

        for contact in listing.get("broker_contacts", []):
            raw_name = contact.get("name", "")
            agent_name = re.sub(r",\s*CalDRE.*$", "", raw_name).strip()
            email      = contact.get("email")
            phone_raw  = contact.get("phone", "") or ""
            phones     = extract_phones(phone_raw)
            phone      = phones[0] if phones else phone_raw or None

            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email,
                    "Lee & Associates", detail_url,
                    "Lee & Associates Buildout API → broker_contacts",
                ))

    return results

def scrape_nai(plaza_name,plaza_city,address,city,state,session,lat=None,lng=None):
    results = []
    if not lat or not lng:
        print(f"  [nai] no coords for {city} - skipping")
        return results
    delta = 0.3
    exact_url = (
        "https://buildout.com/plugins/4fc4c741a2b49384c474ebc81ede3d108d02ca1c/inventory"
        f"?lat_min={lat-delta}&lat_max={lat+delta}&lng_min={lng-delta}&lng_max={lng+delta}"
        "&page=0&light_view=true&placesAutoComplete="
        "&q%5Btype_use_offset_eq_any%5D%5B%5D="
        "&q%5Bsale_or_lease_eq%5D=lease"
        "&q%5Bwith_space_type_ids%5D%5B%5D="
        "&q%5Bbuilding_size_sf_gteq%5D=&q%5Bbuilding_size_sf_lteq%5D="
        "&q%5Blot_size_acres_gteq%5D=&q%5Blot_size_acres_lteq%5D="
        "&q%5Bproperty_research_property_year_built_gteq%5D=&q%5Bproperty_research_property_year_built_lteq%5D="
        "&q%5Blistings_data_max_space_available_on_market_gteq%5D=&q%5Blistings_data_min_space_available_on_market_lteq%5D="
        "&q%5Bmax_lease_rate_gteq%5D=&q%5Bmin_lease_rate_lteq%5D="
        "&q%5Bmax_lease_rate_monthly_gteq%5D=&q%5Bmin_lease_rate_monthly_lteq%5D="
        "&q%5Bproperty_research_property_number_of_units_gteq%5D=&q%5Bproperty_research_property_number_of_units_lteq%5D="
        f"&q%5Bstate_eq_any%5D%5B%5D={state}"
        "&q%5Bs%5D%5B%5D=last_edited_at+desc"
    )

    try: 
        r = session.get(
            exact_url,
            headers = {"Accept": "application/json", "Referer": "https://www.naiglobal.com/"},
            timeout = 15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"  [nai] search returned {r.status_code}")
            return results
        data = r.json()
    except Exception as e:
        print(f"  [nai] search failed: {e}")
        return results
    
    listings = data.get("inventory") or []
    print(f"  [nai] {len(listings)} listings for '{city}, {state}'")
    for l in listings:
        print(f"    [nai]   - {l.get('name') or l.get('display_name')} | {l.get('address')}")

    for listing in listings:
        prop_name = listing.get("name", "") or listing.get("display_name", "")
        prop_addr = listing.get("address", "")
        prop_city = listing.get("city", "")

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name,address,match_text):
            continue

        print(f"  [nai] match: {prop_name} | {prop_addr}")
        detail_url = listing.get("show_link", "")

        for contact in listing.get("broker_contacts", []):
            raw_name = contact.get("name", "")
            agent_name = re.sub(r",\s*(CalDRE|DRE|License).*$", "", raw_name, flags=re.IGNORECASE).strip()
            email = contact.get("email")
            phone_raw = contact.get("phone", "") or ""
            phones = extract_phones(phone_raw)
            phone = phones[0] if phones else phone_raw or None

            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name,plaza_city,address,agent_name,phone,email,"NAI Global", detail_url, "Buildout API"
                ))
    return results

def scrape_svn(plaza_name,plaza_city,address,city,state,session,lat=None,lng=None):
    results = []
    if not lat or not lng:
        print(f"  [svn] no coords for {city} - skipping")
        return results
    
    delta = 0.3
    exact_url = (
        "https://buildout.com/plugins/b933480474026c41d248b77156c84aef37dcac68/inventory"
        f"?lat_min={lat-delta}&lat_max={lat+delta}&lng_min={lng-delta}&lng_max={lng+delta}"
        "&page=0&light_view=true&placesAutoComplete="
        "&q%5Btype_use_offset_eq_any%5D%5B%5D="
        "&q%5Bsale_or_lease_eq%5D=lease"
        "&q%5Bwith_space_type_ids%5D%5B%5D="
        "&q%5Bbuilding_size_sf_gteq%5D=&q%5Bbuilding_size_sf_lteq%5D="
        "&q%5Blot_size_acres_gteq%5D=&q%5Blot_size_acres_lteq%5D="
        "&q%5Bproperty_research_property_year_built_gteq%5D=&q%5Bproperty_research_property_year_built_lteq%5D="
        "&q%5Blistings_data_max_space_available_on_market_gteq%5D=&q%5Blistings_data_min_space_available_on_market_lteq%5D="
        "&q%5Bmax_lease_rate_gteq%5D=&q%5Bmin_lease_rate_lteq%5D="
        "&q%5Bmax_lease_rate_monthly_gteq%5D=&q%5Bmin_lease_rate_monthly_lteq%5D="
        "&q%5Bproperty_research_property_number_of_units_gteq%5D=&q%5Bproperty_research_property_number_of_units_lteq%5D="
        f"&q%5Bstate_eq_any%5D%5B%5D={state}"
        "&q%5Bs%5D%5B%5D=last_edited_at+desc"
    )

    try:
        r = session.get(
            exact_url,
            headers={"Accept": "application/json", "Referer": "https://www.svn.com/"},
            timeout=15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"  [svn] search returned {r.status_code}")
            return results
        data = r.json()
    except Exception as e:
        print(f"  [svn] search failed: {e}")
        return results
    
    listings = data.get("inventory") or []
    print(f"  [svn] {len(listings)} listings for '{city}, {state}'")
    for l in listings:
        print(f"  [svn]  -{l.get('name') or l.get('display_name')} | {l.get('address')}")

    for listing in listings:
        prop_name = listing.get("name", "") or listing.get("display_name","")
        prop_addr = listing.get("address", "")
        prop_city = listing.get("city", "")

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name,address,match_text):
            continue

        print(f"  [svn] match: {prop_name} | {prop_addr}")

        detail_url = listing.get("show_link","")

        for contact in listing.get("broker_contacts", []):
            raw_name = contact.get("name", "")
            agent_name = re.sub(r",\s*(CalDRE|DRE|License).*$", "", raw_name, flags=re.IGNORECASE).strip()
            email = contact.get("email")
            phone_raw = contact.get("phone", "") or ""
            phones = extract_phones(phone_raw)
            phone = phones[0] if phones else phone_raw or None

            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name,plaza_city,address,agent_name,phone,email,"SVN International",detail_url, "Buildout API"
                ))
    return results

def scrape_tricommercial(plaza_name,plaza_city,address,city,state,session,lat=None,lng=None):
    results=[]
    if not lat or not lng:
        print(f"  [tri] no coords for {city} - skipping")
        return results
    
    delta = 0.3
    exact_url = (
        "https://buildout.com/plugins/4d24ff217c26907aaaa12bb0837e451e568a61e4/inventory"
        f"?lat_min={lat-delta}&lat_max={lat+delta}&lng_min={lng-delta}&lng_max={lng+delta}"
        "&page=0&light_view=true&placesAutoComplete="
        "&q%5Btype_use_offset_eq_any%5D%5B%5D="
        "&q%5Bsale_or_lease_eq%5D=lease"
        "&q%5Bwith_space_type_ids%5D%5B%5D="
        "&q%5Bbuilding_size_sf_gteq%5D=&q%5Bbuilding_size_sf_lteq%5D="
        "&q%5Blot_size_acres_gteq%5D=&q%5Blot_size_acres_lteq%5D="
        "&q%5Bproperty_research_property_year_built_gteq%5D=&q%5Bproperty_research_property_year_built_lteq%5D="
        "&q%5Blistings_data_max_space_available_on_market_gteq%5D=&q%5Blistings_data_min_space_available_on_market_lteq%5D="
        "&q%5Bmax_lease_rate_gteq%5D=&q%5Bmin_lease_rate_lteq%5D="
        "&q%5Bmax_lease_rate_monthly_gteq%5D=&q%5Bmin_lease_rate_monthly_lteq%5D="
        "&q%5Bproperty_research_property_number_of_units_gteq%5D=&q%5Bproperty_research_property_number_of_units_lteq%5D="
        f"&q%5Bstate_eq_any%5D%5B%5D={state}"
        "&q%5Bs%5D%5B%5D=last_edited_at+desc"
    )

    try:
        r = session.get(
            exact_url, headers = {"Accept": "application/json", "Referer": "https://www.tricommercial.com/"},
            timeout = 15
        )
        time.sleep(sleep_between)
        if r.status_code != 200:
            print(f"  [tri] search returned {r.status_code}")
            return results

        data = r.json()
    except Exception as e:
        print(f"  [tri] search failed: {e}")
        return results
    
    listings = data.get("inventory") or []
    print(f"  [tri] {len(listings)} listings for '{city}, {state}'")
    for l in listings:
        print(f"  [tri] - {l.get('name') or l.get('display_name')} | {l.get('address')}")
    
    for listing in listings:
        prop_name = listing.get("name", "") or listing.get("display_name", "")
        prop_addr = listing.get("address", "")
        prop_city = listing.get("city", "")

        match_text = f"{prop_name} {prop_addr} {prop_city}"
        if not plaza_matches(plaza_name,address,match_text):
            continue

        print(f"  [tri] match: {prop_name} | {prop_addr}")

        detail_url = listing.get("show_link", "")

        for contact in listing.get("broker_contacts", []):
            raw_name = contact.get("name", "")
            agent_name = re.sub(r",\s*(CalDRE|DRE|License).*$", "", raw_name, flags=re.IGNORECASE).strip()
            email = contact.get("email")
            phone_raw = contact.get("phone", "") or ""
            phones = extract_phones(phone_raw)
            phone = phones[0] if phones else phone_raw or None

            if agent_name or email or phone:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    agent_name, phone, email, 
                    "TRI Commercial", detail_url,
                    "Buildout API"
                ))
    return results

def save_agents(agents:list) -> None:
    try:
        from majorretail import get_supabase
        sb = get_supabase()
        if not sb:
            return
        saved = skipped = 0
        for a in agents:
            existing = (sb.table("agents")
                           .select("id")
                           .eq("plaza_name",a.get("plaza_name") or "")
                           .eq("plaza_city", a.get("plaza_city") or "")
                           .eq("agent_name", a.get("agent_name") or "")
                           .limit(1).execute())
            if existing.data:
                skipped += 1
                continue
            sb.table("agents").insert({
                "plaza.name": a.get("plaza_name"),
                "plaza_city": a.get("plaza_city"),
                "address": a.get("address"),
                "agent_name": a.get("agent_name"),
                "phone": a.get("phone"),
                "email": a.get("email"),
                "brokerage": a.get("brokerage"),
                "listing_url": a.get("listing_url"),
                "source": a.get("source"),
            }).execute()
            saved += 1
        if saved or skipped:
            print(f"  [agents] {saved} saved, {skipped} already exist")
    except Exception as e:
        print(f"  [agents] Supabase save failed: {e}")

CREXI_BOUNDING_BOX = {
    "latitudeMax": 61.24034074463999,
    "latitudeMin": 9.953904742151717,
    "longitudeMax": -64.8734481248038,
    "longitudeMin": -132.2855518719615,
}

def _local_bounding_box(lat,lng,miles=7.0):
    if lat is None or lng is None:
        return None
    lat_delta = miles / 69.0
    lng_delta = miles / (69.0 * max(math.cos(math.radians(lat)),0.1))
    return {
        "latitudeMax": lat + lat_delta,
        "latitudeMin": lat - lat_delta,
        "longitudeMax": lng + lng_delta,
        "longitudeMin": lng - lng_delta
    }

_DEFAULT_SEARCH_MILES = 7.0

def _crexi_search_miles(radius_m) -> float:
    if not radius_m:
        return _DEFAULT_SEARCH_MILES
    miles = (radius_m / 1609.34) * 2.0
    return max(miles, 0.5) # can change to 0.2 if found that it is too large the range

def scrape_crexi(plaza_name,plaza_city,address,city,state,session, lat=None, lng=None, radius_m=None):
    results = []
    url = "https://api.crexi.com/universal-search/v2/search"

    search_miles = _crexi_search_miles(radius_m)
    bbox = _local_bounding_box(lat,lng, miles=search_miles) or CREXI_BOUNDING_BOX
    if bbox is CREXI_BOUNDING_BOX:
        print(f"  [crexi] no lat/lng for {plaza_name[:50]!r} - falling back to the continent-wide box")
    else:
        print(f"  [crexi] searching within {search_miles:.2f}mi of {plaza_name[:50]!r}"
              + (f" (plaza footprint: {radius_m:.0f}m)" if radius_m else " (no footprint data - using flat default)"))

    payload = {
        "boundingBox": bbox,
        "excludeFilters": [],
        "excludeSort": [],
        "filters": {
            "address": {
                "mode": "Include",
                "structuredValues": [f"{city}, {state}"],
                "type": "Plain",
                "values": [],
            }
        },
        "from": 0,
        "ids": [],
        "searchTypes": ["Lease"],
        "size": 60,
        "sorting": {"searchAttributes.crexiSearchRank": "Descending"},
    }

    crexi_headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "client-timezone-offset": "-7",
        "content-type": "application/json",
        "mixpanel-distinct-id": f"$device:{uuid.uuid4()}",
        "ml-scenario": "Recombee-Recommendations-Challenger",
        "origin": "https://www.crexi.com",
        "referer": "https://www.crexi.com/",
        "schema-mode": "Searchable",
        "sec-ch-us": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": headers["User-Agent"],
        "x-session-id": str(random.randint(10**18, 10**19 - 1)),
        "x-skip-interceptor": "true",
    }

    try:
        all_items = []
        from_offset = 0
        page = 0
        max_pages = 5
        while page < max_pages:
            payload["from"] = from_offset
            r = requests.post(url, headers = crexi_headers, json=payload, timeout=15, impersonate="chrome120")
            time.sleep(sleep_between)

            if page == 0:
                print(f"  [crexi] status={r.status_code} length={len(r.text)}")
            if r.status_code != 200:
                print(f"  [crexi] response: {r.text[:200]}")
                break

            data = r.json()
            if page == 0:
                print(f"  [crexi] response top-level keys: {list(data.keys()) if isinstance(data,dict) else type(data)}")

            items = data.get("items") if isinstance(data,dict) else None
            if not isinstance(items,list):
                print(f"  [crexi] could not find 'items' in response - raw sample: {str(data)[:500]}")
                break

            all_items.extend(items)
            total = data.get("totalCount", len(all_items))
            from_offset += len(items)
            page += 1

            if from_offset >= total or not items:
                break
        
        if not all_items:
            return results
        
        print(f"  [crexi] {len(all_items)} items collected across {page} page(s)")

        for listing in all_items:
            if not isinstance(listing, dict):
                continue

            addr_list = listing.get("address") or []
            addr_obj = addr_list[0] if addr_list and isinstance(addr_list[0], dict) else {}

            prop_name = listing.get("propertyName") or ""
            prop_addr = addr_obj.get("fullAddress") or ""
            prop_city = addr_obj.get("city") or ""
            cand_loc = addr_obj.get("location") or {}
            cand_lat = cand_loc.get("lat")
            cand_lng = cand_loc.get("lon")

            raw_id = listing.get("id") or ""
            id_num = raw_id.split("-")[-1] if "-" in raw_id else raw_id
            url_slug = listing.get("urlSlug") or ""
            listing_url = (
                f"https://www.crexi.com/lease/properties/{id_num}/{url_slug}"
                if id_num and url_slug else "https://www.crexi.com/"
            )
            
            match_text = f"{prop_name} {prop_addr} {prop_city}"
            if not plaza_matches(plaza_name, address, match_text,
                                 plaza_lat=lat, plaza_lng=lng,
                                 candidate_lat=cand_lat, candidate_lng=cand_lng):
                continue

            print(f"  [crexi] match: {prop_name} | {prop_addr}")

            brokers = listing.get("brokers") or []
            if isinstance(brokers,list) and brokers:
                for b in brokers:
                    if not isinstance(b,dict):
                        continue
                    agent_name = b.get("name") or b.get("fullName")
                    brokerage_name = b.get("brokerage") or "Crexi Listing"
                    phone = b.get("phone") or b.get("phoneNumber")
                    email = b.get("email")
                    results.append(make_record(
                        plaza_name,plaza_city,address,
                        agent_name, phone, email, brokerage_name, listing_url,
                        "matched listing crexi search"
                    ))
            else:
                results.append(make_record(
                    plaza_name, plaza_city, address,
                    None,None,None,
                    brokerage_name or "Crexi listing", listing_url,
                    "matched listing crexi search, broker field unmapped"
                ))
        return results
    except Exception as e:
        print(f"  [crexi] error: {e}")
        import traceback
        traceback.print_exc()
        return results

scrapers = {
    "Kidder Matthews": scrape_kidder,
    "SRS Real Estate": scrape_srs,
    "Gallelli Real Estate": scrape_gallelli,
    "CBRE": scrape_cbre,
    "Cushman & Wakefield": scrape_cushman,
    "Phillips Edison": scrape_phillipsedison,
    "Ethan Conrad Properties": scrape_ethanconrad,
    "Colliers": scrape_colliers,
    "Newmark": scrape_newmark,
    "Lee & Associates": scrape_lee,
    "NAI Global": scrape_nai,
    "SVN International": scrape_svn,
    "TRI Commercial": scrape_tricommercial,
    "Avison Young": scrape_avison,
    "Regency Centers": scrape_regency,
    "Simon Property Group": scrape_simon,
    "Namdar Realty Group": scrape_namdar,
    "Crexi": scrape_crexi
}

def _brokerage_key(brokerage:str) -> str:
    if not brokerage:
        return ""
    base = brokerage.split(" - ")[0]
    return " ".join(normalize(base).split()[:2])

def _dedupe_key(a: dict, include_plaza:bool = False):
    brokerage_key = _brokerage_key(a.get("brokerage"))
    agent_name = normalize(a.get("agent_name") or "")
    tail = agent_name or (a.get("email") or a.get("phone") or a.get("listing_url"))
    key = (brokerage_key, tail)
    return (a.get("plaza_name"), *key) if include_plaza else key
def _more_complete(a: dict, b: dict) -> dict:
    score = lambda r: sum(1 for k in ("phone", "email") if r.get(k))
    return a if score(a) >= score(b) else b
def _dedupe_agents(agents:list, include_plaza: bool=False) -> list:
    seen ={}
    for a in agents:
        key = _dedupe_key(a, include_plaza = include_plaza)
        seen[key] = _more_complete(seen[key], a) if key in seen else a
    return list(seen.values())


def scrape_one_plaza(plaza_name, plaza_city, address, state, session, lat = None, lng = None, radius_m=None):
    plaza_agents = []
    for brokerage_name,fn in scrapers.items():
        if brokerage_name == "Crexi":
            continue
        try:
            if "lat" in inspect.signature(fn).parameters:
                agents = fn(plaza_name, plaza_city, address, plaza_city, state, session, lat=lat, lng=lng)
            else:
                agents = fn(plaza_name, plaza_city, address, plaza_city, state, session)
            plaza_agents.extend(agents)
        except Exception as e:
            print(f"\n  [{brokerage_name}] error: {e}")
        if plaza_agents:
            print(f"\n  [scraper] matched via {brokerage_name}")
            break
    try:
        crexi_agents = scrape_crexi(plaza_name,plaza_city,address,plaza_city,state,session, lat=lat,lng=lng, radius_m=radius_m)
        if crexi_agents:
            print(f"\n. [scraper] +{len(crexi_agents)} candidate(s) from Crexi for {plaza_name[:50]}")
        plaza_agents.extend(crexi_agents)
    except Exception as e:
        print(f"\n. [Crexi] error: {e}")

    return _dedupe_agents(plaza_agents)

def scrape_listings(plazas:list,city:str,state:str) -> list:
    if not BS4:
        print("  [scraper] Skipping - run: pip install beautifulsoup4")
        return []
    
    session = requests.Session()
    session.headers.update(headers)

    all_agents = []
    total = len(plazas)
    print(f"\n  [scraper] Searching {len(scrapers)} brokerages for {total} plazas...")

    for i, plaza in enumerate(plazas):
        plaza_name = plaza.label if hasattr(plaza,"label") else plaza.get("name", "")
        address = plaza.display_address if hasattr(plaza, "display_address") else plaza.get("address", "-")
        plaza_city = plaza.display_city if hasattr(plaza, "display_city") else plaza.get("city", city)

        if hasattr(plaza, "center"):
            clat,clng = plaza.center
        else:
            clat = plaza.get("lat")
            clng = plaza.get("lng")

        cradius = plaza.radius_m if hasattr(plaza, "radius_m") else plaza.get("radius_m") if isinstance(plaza, dict) else None

        print(f"  [scraper] [{i+1}/{total}] {plaza_name[:50]}", end="\r")

        unique_plaza_agents = scrape_one_plaza(plaza_name, plaza_city, address, state, session, lat=clat, lng=clng, radius_m=cradius)

        if hasattr(plaza, "agents"):
            plaza.agents = unique_plaza_agents
        elif isinstance(plaza,dict):
            plaza["agents"] = unique_plaza_agents

        all_agents.extend(unique_plaza_agents)
    print(f" \n  [scraper] Done - {len(all_agents)} contacts found")

    unique = _dedupe_agents(all_agents, include_plaza=True)

    save_agents(unique)
    return unique



if __name__ == "__main__":
    import sys

    class FakePlaza:
        def __init__(self,name,address,city):
            self.label = name
            self.display_address = address
            self.display_city = city
    city = sys.argv[1] if len(sys.argv) > 1 else "Roseville"
    state = sys.argv[2] if len(sys.argv) >2 else "CA"

    test = [
        FakePlaza("Renaissance Creek",   "SWC Douglas Blvd & Sierra College Blvd, Roseville, CA", "Roseville"),
        FakePlaza("The Marketplace",     "1411 W. Covell Blvd, Davis, CA 95616",                  "Davis"),
        FakePlaza("Sunrise Mall",        "6041 Sunrise Mall Rd, Citrus Heights, CA",               "Citrus Heights"),
        FakePlaza("Baseline Marketplace","NWC Baseline Rd & Fiddyment Rd, Roseville, CA",          "Roseville"),
    ]

    agents = scrape_listings(test,city=city, state=state)
    print(f"\n{len(agents)} contacts:\n")
    for a in agents:
        print(f"  [{a['brokerage']}] {a['agent_name']}")
        print(f"    Phone: {a['phone'] or '-'}")
        print(f"    Email: {a['email'] or '-'}")
        print(f"    Plaza: {a['plaza_name']}")
        print(f"    URL:   {a['listing_url']}")
        print()