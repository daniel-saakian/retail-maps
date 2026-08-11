import math
import json
from urllib.parse import quote

def build_cbre_url(lat: float, lng: float, radius_miles: float = 0.5,
                   location_label: str = "", city: str = "", state: str = "") -> str:
    lat_delta = radius_miles / 69.0
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))
    north, south = lat + lat_delta, lat - lat_delta
    east,  west  = lng + lng_delta, lng - lng_delta

    polygon = [
        f"{north},{east}",
        f"{south},{east}",
        f"{south},{west}",
        f"{north},{west}",
    ]
    polygon_enc  = quote(json.dumps([polygon]), safe="")
    location_enc = quote(location_label or (f"{city}, {state}" if city and state else f"{lat:.4f},{lng:.4f}"), safe="")

    base = "https://www.cbre.com/properties/properties-for-lease/commercial-space"
    return (
        f"{base}?Site=us-comm&RadiusType=Miles&transactiontype=allTypes"
        f"&sort=asc(_distance)&Dynamic.UnderOffer=true%2Cfalse"
        f"&Dynamic.LetUnderOffer=true%2Cfalse&lng={lng}&lat={lat}"
        f"&groupType=%21AreaOffice"
        f"&polygons=%5B{polygon_enc}%5D"
        f"&initialPolygons=%5B{polygon_enc}%5D"
        f"&location={location_enc}"
    )

def build_jll_url(lat:float,lng:float,radius_miles:float=0.5, location_label:str="", city:str="",state:str="") -> str:
    state_names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    }
    base = "https://property.jll.com/search"
    if city and state:
        state_full = state_names.get(state.upper(),state)
        return (
            f"{base}?tenureTypes=rent&propertyTypes=retail&orderBy=desc"
            f"&sortBy=dateModified&cities={quote(city)}&regions={quote(state_full)}"
        )
    return f"{base}?tenureTypes=rent&propertyTypes=retail&orderBy=desc&sortBy=dateModified"



def build_cushman_url(lat:float,lng:float,radius_miles:float=0.5, location_label:str="", city:str="",state:str="") -> str:
    state_names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    }
    if city and state:
        state_full = state_names.get(state.upper(), state)
        query = f"{city.lower()}+{state_full.lower()}"
    else:
        query = quote(location_label or f"{lat:.4f},{lng:.4f}", safe = "").replace("%20", "+")
    base = "https://www.cushmanwakefield.com/en/united-states/properties/lease/search/retail"

    return f"{base}?q={query}&sort=relevance"

def build_colliers_url(lat:float,lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    if city and state:
        query = f"{city}, {state}"
    else:
        query = location_label or f"{lat:.4f},{lng:.4f}"

    q_enc = quote(query, safe="")
    listing_enc = quote("[For Lease]", safe="")
    property_enc = quote("[Retail]", safe="")
    base = "https://www.colliers.com/en/properties"

    return (
        f"{base}#q={q_enc}"
        f"&f:listingtype={listing_enc}"
        f"&f:propertytype={property_enc}"
        f"&f:recenttransactions=[0]"
    )

def build_avison_url(lat:float,lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    keyword = quote(city or location_label.split(",")[0].strip(), safe="")
    location = quote(state or "", safe="")

    return (
        "https://www.avisonyoung.us/properties#/"
        "?type=retail.community_center"
        "&type=retail.free_standing_building"
        "&type=retail.lifestyle_center"
        "&type=retail.neighborhood_center"
        "&type=retail.outlet_center"
        "&type=retail.power_center"
        "&type=retail.regional_mall"
        "&type=retail.restaurant"
        "&type=retail.retail_condo"
        "&type=retail.retail_pad"
        "&type=retail.specialty_center"
        "&type=retail.stip_center"
        "&type=retail.vehicle_related"
        "&type=retail.strip_center"
        "&view=sidebar"
        "&status=active"
        "&transaction=lease"
        "&transaction=sublease"
        f"&keyword={keyword}"
    )

def build_kidder_url(lat:float,lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    if city and state:
        term = quote(f"{city}, {state}", safe="")
    else:
        term = quote(location_label or f"{lat:.4f},{lng:.4f}", safe="")
    
    return f"https://www.kidder.com/properties/index.html?listType=For%20Lease&term={term}"

def build_srs_url(lat:float,lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    if city and state:
        term = quote(f"{city}, {state}", safe="")
    else:
        term = quote(location_label or f"{lat:.4f},{lng:.4f}", safe= "")

    return (
        f"https://www.srsre.com/properties/lease/retail"
        f"?price_req=true&cap_req=true&orderby=relevance&order=DESC&s={term}"
    )

def build_regency_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    import json as _json
    search_term = quote(city or state or location_label, safe = "")
    map_center = quote(_json.dumps({"lat":lat, "lng":lng}), safe="")

    filter_panel = quote(
        '{"isPadsPanel":false,"retailSpaceFilter":{"rangeSliderLabel":"Retail space in this range:",'
        '"retailSpaceMin":"0","retailSpaceMax":"70,000","retailSpaceNewDevelopments":false,'
        '"withCheckbox":false,"retailSpaceMaxLabel":"70,000+"},'
        '"padsFilter":{"padsNewDevelopments":false,"retailSpaceMin":"0","retailSpaceMax":"15"},'
        '"retailSpaceFilterAction":null}',
        safe=""
    )
    return (
        f"https://www.regencycenters.com/properties"
        f"?mapSearchTerm={search_term}"
        f"&availableUnitsMobile=false"
        f"&sortClassName=sortAsce"
        f"&sortInnerText=Property"
        f"&lastMapCenter={map_center}"
        f"&lastMapZoom=13"
        f"&filterPanel={filter_panel}"
    )
def build_simon_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    if city and state:
        term = quote(f"{city}, {state}", safe="").replace("%20", "+")
    else:
        term = quote(location_label or f"{lat:.4f},{lng:.4f}",safe="").replace("%20","+")
    
    return f"https://business.simon.com/search?location={term}"

def build_inland_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    state_names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    }
    state_full = state_names.get(state.upper(), state) if state else ""
    location = quote(state_full,safe="")
    return f"https://www.inland-investments.com/properties?location={location}&type=Retail"

def build_phillipsedison_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    state_names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    }
    state_slug = state_names.get(state.upper(), state).lower().replace(" ", "-") if state else ""
    city_slug = city.lower().replace(" ", "-") if city else ""
    state_abbr = state.lower() if state else ""
    if city_slug and state_slug and state_abbr:
        return f"https://www.phillipsedison.com/properties/{state_slug}/{city_slug}"
    elif state_slug:
        return f"https://www.phillipsedison.com/properties/{state_slug}"
    else:
        return "https://www.phillipsedison.com/properties"

def build_namdar_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    keyword = quote(city or location_label.split(",")[0].strip(),safe="")
    st = quote(state.upper() if state else "", safe ="")
    return f"https://namdarrealtygroup.com/?page=search&proptype=&keyword={keyword}&state={st}"

def build_gallelli_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    city_slug = (city or location_label.split(",")[0].strip()).lower().replace(" ","+")
    return (
        f"https://www.gallellire.com/properties/"
        f"?type=retail&status=lease&city={city_slug}"
        f"&min_price=0&max_price=50000000"
        f"&min_size=0&max_size=10000000"
    )

def build_ethanconrad_url(lat:float, lng:float,radius_miles:float=0.5, location_label:str="", city:str="", state:str="") -> str:
    if city and state:
        search = quote(f"{city}, {state}", safe="")
    else:
        search = quote(location_label or f"{lat:.4f},{lng:.4f}", safe="")
    return (
        f"https://www.ethanconradprop.com/properties2/"
        f"?widget_id=2&kind=1&sf_advancedlocationtextsearch={search}"
        f"&sf_select_property_type=6"
        f"&sf_mmunit_field_3047=1"
        f"&sf_select_listing=10"
    )




def build_google_search_url(plaza_name:str,address:str,brokerage_domains:list=None) -> str:
    if brokerage_domains is None:
        brokerage_domains = [
            "cbre.com","property.jll.com","cushmanwakefield.com","colliers.com"
        ]
    site_clause = " OR ".join(f"site:{d}" for d in brokerage_domains[:5])
    query = f'"{plaza_name}" or "{address}" ({site_clause}) retail lease available'
    return f"https://www.google.com/search?q={quote(query)}"



brokerage = {
    "CBRE": {
        "full_name": "CBRE Group, Inc.",
        "tier": 1,
        "hq": "Dallas, TX",
        "website": "https://www.cbre.com/",
        "specialties": ["office", "industrial", "retail", "land"],
        "scrape_type": "js_rendered",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "url_param",
        "status_field": "Dynamic.UnderOffer",
        "url_builder": build_cbre_url,
        "notes": "Bounding box polygon search"
    },
    "JLL": {
        "full_name": "Jones Lang LaSalle Incorporated",
        "tier": 1,
        "hq": "Chicago, IL",
        "website": "https://www.jll.com/en-us/",
        "specialties": ["office", "industrial", "retail"],
        "scrape_type": "semi_open",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "page",
        "status_field": "listingStatus",
        "url_builder": build_jll_url,
        "notes": "Uses JLL subdomain"
    },
    "Cushman & Wakefield": {
        "full_name": "Cushman & Wakefield plc",
        "tier": 1,
        "hq": "Chicago, IL",
        "website": "https://www.cushmanwakefield.com/",
        "specialties": ["office", "industrial", "retail"],
        "scrape_type": "semi_open",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "page",
        "status_field": "listing_status",
        "url_builder": build_cushman_url,
        "notes": "Uses Cushman & Wakefield subdomain"
    },
    "Colliers": {
        "full_name": "Colliers International",
        "tier": 1,
        "hq": "Seattle, WA",
        "website": "https://www.colliers.com/en",
        "specialties": ["office", "industrial", "retail"],
        "scrape_type": "js_rendered",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "js",
        "status_field": "listingtype",
        "url_builder": build_colliers_url,
        "notes": "headless browser required"
    },
    "Newmark": {
        "full_name": "Newmark Group, Inc.",
        "tier": 1,
        "hq": "New York, NY",
        "website": "https://www.nmrk.com",
        "specialties": ["office", "industrial", "retail"],
        "scrape_type": "js_rendered",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "js",
        "status_field": None,
        "url_builder": lambda lat, lng, r, loc, city, state: "https://www.nmrk.com/properties?saleOrLease=lease",
        "notes": "filters are only client-side. INSPECT ELEMENT TO GET HEADLESS SCRAPING"
    },
    "Avison Young": {
        "full_name": "Avison Young",
        "tier": 2,
        "hq": "Atlanta, GA",
        "website": "https://www.avisonyoung.us",
        "specialties": ["retail", "office", "industrial"],
        "scrape_type": "semi_open",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "js",
        "status_field": None,
        "url_builder": build_avison_url,
        "notes": "keyword+loc parameters"        
    },
    "Lee & Associates": {
        "full_name": "Lee and Associates",
        "tier": 2,
        "hq": "Westlake Village, CA",
        "website": "https://www.lee-associates.com",
        "specialties": ["industrial", "retail", "office"],
        "scrape_type": "js_rendered",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "js",
        "status_field": None,
        "url_builder": lambda lat, lng, r, loc, city, state: "https://www.lee-associates.com/properties/",
        "notes": "url never changes, js rendered"
    },
    "NAI Global": {
        "full_name":             "NAI Global",
        "tier":                  2,
        "hq":                    "Princeton, NJ",
        "website":               "https://www.naiglobal.com",
        "specialties":             ["office", "industrial", "retail", "land"],
        "scrape_type":           "js_rendered",
        "owner_type":            "brokerage",
        "owner_known":           False,
        "listing_status_source": "js",
        "status_field":          None,
        "url_builder":          lambda lat, lng, r, loc, city, state: "https://www.naiglobal.com/listings/",
        "notes":                 "Filters are JS-rendered — URL never changes. Base URL only."
    },
    "SVN International": {
        "full_name": "SVN Commercial Real Estate Advisors",
        "tier":                  2,
        "hq":                    "Boston, MA",
        "website":               "https://www.svn.com",
        "specialties":             ["retail", "office", "industrial", "multifamily", "net_lease"],
        "scrape_type":           "js_rendered",
        "owner_type":            "brokerage",
        "owner_known":           False,
        "listing_status_source": "js",
        "status_field":          "None",
        "url_builder":          lambda lat, lng, r, loc, city, state: "https://www.svn.com/properties/",
        "notes":                 "Filters are JS-rendered — URL never changes. Base URL only.",
    },
    "Kidder Matthews": {
        "full_name": "Kidder Matthews",
        "tier": 2,
        "hq": "Seattle, WA",
        "website": "https://kidder.com",
        "specialties": ["office","industrial", "retail"],
        "scrape_type": "semi_open",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "page",
        "status_field": "listType",
        "url_builder": build_kidder_url,
        "notes": "City, ST for format"
    },
    "SRS Real Estate Partners": {
        "full_name": "SRS Real Estate Partners",
        "tier": 2,
        "hq": "Dallas, TX",
        "website": "https://www.srsre.com",
        "specialties": ["retail"],
        "scrape_type": "semi_open",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "page",
        "status_field": "status",
        "url_builder": build_srs_url,
        "notes": "s=City, ST param confirmed. /lease/retail path pre-filters to retail. Spaces encoded as +."
        },
    "Regency Centers": {
        "full_name": "Regency Centers Corporation",
        "tier": 3,
        "hq": "Jacksonville, FL",
        "website": "https://www.regencycenters.com",
        "specialties": ["retail"],
        "scrape_type": "semi_open",
        "owner_type": "reit",
        "owner_known": True,
        "default_owner": "Regency Centers",
        "listing_status_source": "known",
        "status_field": None,
        "url_builder": build_regency_url,
        "notes": "mapsearchterm + lastmapcenter params confirmed"
    },
    "Simon Property Group" : {
        "full_name": "Simon Property Group",
        "tier": 3,
        "hq": "Indianapolis, IN",
        "website": "https://www.business.simon.com",
        "specialties": ["retail"],
        "scrape_type": "open",
        "owner_type": "reit",
        "owner_known": True,
        "default_owner": "Simon Property Group",
        "listing_status_source": "known",
        "status_field": None,
        "url_builder": build_simon_url,
        "notes": "location =city,ST"
    },
    "Brookfield Properties": {
        "full_name": "Brookfield Properties Retail",
        "tier": 3,
        "hq": "New York, NY",
        "website": "https://www.brookfieldproperties.com",
        "specialties": ["retail"],
        "scrape_type": "js_rendered",
        "owner_type": "reit",
        "owner_known": True,
        "default_owner": "Brookfield Properties",
        "listing_status_source": "known",
        "status_field": None,
        "url_builder": lambda lat, lng, r, loc, city, state: "https://www.brookfieldproperties.com/en/our-properties/?PropertyType=Retail",
        "notes": "retail prefiltered but location is js rendered"
    },
    "Inland Real Estate": {
        "full_name": "Inland Real Estate Income Trust",
        "tier": 3,
        "hq": "Chicago, IL",
        "website": "https://www.inland-investments.com",
        "specialties": ["retail"],
        "scrape_type": "open",
        "owner_type": "reit",
        "owner_known": True,
        "default_owner": "Inland Real Estate",
        "listing_status_source": "known",
        "status_field": None,
        "url_builder": build_inland_url,
        "notes": "state-level only no city filtering"
    },
    "Phillips Edison": {
        "full_name": "Phillips Edison & Company",
        "tier": 3,
        "hq": "Cincinnati, OH",
        "website": "https://www.phillipsedison.com",
        "specialties": ["retail"],
        "scrape_type": "open",
        "owner_type": "reit",
        "owner_known": True,
        "default_owner": "Phillips Edison",
        "listing_status_source": "known",
        "status_field": None,
        "url_builder": build_phillipsedison_url,
        "notes": "grocer anchored"
    },
    "Namdar Realty Group": {
        "full_name": "Namdar Realty Group",
        "tier": 3,
        "hq": "Great Neck, NY",
        "website": "https://namdarrealtygroup.com",
        "specialties": ["retail"],
        "scrape_type": "open",
        "owner_type": "private",
        "owner_known": True,
        "default_owner": "Namdar Realty",
        "listing_status_source": "known",
        "status_field": None,
        "url_builder": build_namdar_url,
        "notes": "heavy into malls"
    },
    "TRI Commercial": {
        "full_name": "TRI Commercial Real Estate Services",
        "tier": 3,
        "hq": "Walnut Creek, CA",
        "website": "https://www.tricommercial.com",
        "specialties": ["retail", "office", "industrial"],
        "scrape_type": "js_rendered",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "js",
        "status_field": None,
        "url_builder": lambda lat, lng, r, loc, city, state: "https://www.tricommercial.com/properties",
        "notes": "Norcal Properties"
    },
    "Gallelli Real Estate": {
        "full_name": "Gallelli Real Estate",
        "tier": 3,
        "hq": "Roseville, CA",
        "website": "https://www.gallellire.com",
        "specialties": ["retail", "office", "industrial"],
        "scrape_type": "open",
        "owner_type": "brokerage",
        "owner_known": False,
        "listing_status_source": "page",
        "status_field": "status",
        "url_builder": build_gallelli_url,
        "notes": "parameters all confirmed"
    },
    "Ethan Conrad Properties": {
        "full_name": "Ethan Conrad Properties",
        "tier": 3,
        "hq": "Sacramento, CA",
        "website": "https://www.ethanconradprop.com",
        "specialties": ["retail", "office","industrial"],
        "scrape_type": "open",
        "owner_type": "private",
        "owner_known": True,
        "default_owner": "Ethan Conrad",
        "listing_status_source": "known",
        "url_builder": build_ethanconrad_url,
        "notes": "specialize in sacramento properties" 
    }
}

def find_listings(plaza_name:str, address:str, lat:float,lng:float, radius_miles:float=0.5, location_label:str="", city:str="",state:str="",
                  tiers:list=None, specialties:list=None) -> dict:
    results = {}
    label = location_label or (f"{city}, {state}" if city and state else plaza_name)

    for name, info in brokerage.items():
        if tiers and info["tier"] not in tiers:
            continue
        if specialties:
            covered = [s.lower() for s in info["specialties"]]
            if not any(s.lower() in covered for s in specialties):
                continue
        
        try:
            url = info["url_builder"](lat,lng,radius_miles,label,city,state)
        except Exception:
            url = info.get("website", "")

        status_source = info["listing_status_source"]
        if status_source == "known":
            listing_status = "Check Site - Owner Listed"
        elif status_source == "login":
            listing_status = "Login Required"
        elif status_source == "url_param":
            listing_status = "See Search Results"
        else:
            listing_status = "Search Required"
        
        owner = info.get("default_owner") if info["owner_known"] else None

        results[name] = {
            "url": url,
            "scrape_type": info["scrape_type"],
            "tier": info["tier"],
            "owner_type": info["owner_type"],
            "owner_known": info["owner_known"],
            "owner": owner,
            "status_source": status_source,
            "listing_status": listing_status,
            "website": info["website"]
        }
    js_domains = [
        info["website"].replace("https://www.","").replace("https://","")
        for info in brokerage.values()
        if info["scrape_type"] == "js_rendered"
    ]
    results["Google Search"] = {
        "url":            build_google_search_url(plaza_name, address, js_domains),
        "scrape_type":    "open",
        "tier":           -1,
        "owner_type":     "aggregator",
        "owner_known":    False,
        "owner":          None,
        "status_source":  "page",
        "listing_status": "Search Required",
        "website":        "https://www.google.com",
    }
    return results

def get_by_tier(tier:int) -> dict:
    return {k: v for k, v in brokerage.items() if v["tier"] == tier}
def get_retail_focused() -> dict:
    return {k: v for k, v in brokerage.items()
            if "retail" in v["specialties"] or "all" in v["specialties"]}
def get_scrapeable() -> dict:
    return {k: v for k, v in brokerage.items()
            if v["scrape_type"] in ("open", "semi_open")}
def get_direct_owners() -> dict:
    return {k: v for k, v in brokerage.items()
            if v["owner_type"] in ("reit", "private")}

if __name__ == "__main__":
    results = find_listings(
        plaza_name   = "Westfield Galleria at Roseville",
        address      = "1 Galleria Blvd, Roseville, CA",
        lat          = 38.7521,
        lng          = -121.2874,
        radius_miles = 0.25,
        city         = "Roseville",
        state        = "California",
        specialties  = ["retail"],
    )
 
    print(f"\nGenerated {len(results)} brokerage entries:\n")
    for name, data in results.items():
        owner_str = f"Owner: {data['owner']}" if data['owner'] else "Owner: Unknown"
        print(f"  [{data['scrape_type'].upper():12}] {brokerage}")
        print(f"    Status: {data['listing_status']} | {owner_str}")
        print(f"    {data['url'][:85]}...")
        print()