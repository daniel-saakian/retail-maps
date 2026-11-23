from __future__ import annotations

sections = [
    ("s1", "1. Franchisee, Site, and Team"),
    ("s2", "2. Premises and Lease Terms"),
    ("s3", "3. Signage, Parking, Access, and Traffic"),
    ("s4", "4. Trade Area, Competition, and Prior Tenant"),
    ("s5", "5. Existing Conditions and Build-out Scope"),
    ("s6", "6. Budget, Economics, and Risk"),
    ("s7", "7. Opening and Marketing Plan"),
    ("s8", "8. Franchisee Opinion of Site"),
    ("s9", "9. Attachments"),
    ("s10", "10. Franchisee Confirmation"),
    ("a1", "A1. Location and Trade Area"),
    ("a2", "A2. Competitor Assessment"),
    ("a3", "A3. Site SWOT"),
    ("a4", "A4. Prioritized Objectives"),
    ("a5", "A5. Marketing Response Plan"),
]

def _f(id, section, label, loc, kind="text", source="manual", hint=None):
    return {"id": id, "section": section, "label": label, "loc": list(loc),
            "kind": kind, "source": source, "hint": hint}

FIELDS = [
    # ---------------------------------------------------------------- 1
    _f("franchisee_entity", "s1", "Franchisee legal entity", (3, 0, 1)),
    _f("primary_contact", "s1", "Primary contact and phone", (3, 0, 3)),
    _f("territory", "s1", "Territory / development area", (3, 1, 1)),
    _f("unit_number", "s1", "Unit number under schedule", (3, 1, 3)),
    _f("tour_date", "s1", "Site tour date", (3, 2, 1)),
    _f("opening_quarter", "s1", "Projected opening quarter and year", (3, 2, 3)),
    _f("tenant_rep", "s1", "Tenant representative and firm", (3, 3, 1)),
    _f("tenant_rep_contact", "s1", "Tenant rep phone and email", (3, 3, 3)),
    _f("landlord_entity", "s1", "Landlord entity", (3, 4, 1), source="listing",
       hint="Listings rarely name the owner entity; confirm from LOI or county records."),
    _f("landlord_rep", "s1", "Landlord representative", (3, 4, 3), source="listing"),
    _f("center_name", "s1", "Shopping center name", (3, 5, 1), source="auto"),
    _f("cross_streets", "s1", "Major cross streets", (3, 5, 3), source="auto"),
    _f("street_suite", "s1", "Street address and suite", (3, 6, 1), source="auto"),
    _f("city_state_zip", "s1", "City, state, ZIP", (3, 6, 3), source="auto"),
    _f("attorney", "s1", "Real estate attorney", (3, 7, 1)),
    _f("architect", "s1", "Architect and license no.", (3, 7, 3)),
    _f("gc", "s1", "General contractor and license no.", (3, 8, 1)),
    _f("equipment_vendor", "s1", "Equipment vendor", (3, 8, 3)),
    _f("penetration_rank", "s1", "Trade area rank in penetration plan (and why pursue it)", (4, 0, 1), "long"),

    # ---------------------------------------------------------------- 2
    _f("total_sf", "s2", "Total square feet", (6, 0, 1), source="listing"),
    _f("dimensions_frontage", "s2", "Length x width, frontage", (6, 0, 3), source="listing"),
    _f("base_rent_psf", "s2", "Base rent annual PSF", (6, 1, 1), source="listing"),
    _f("nnn_psf", "s2", "Annual triple net PSF", (6, 1, 3), source="listing"),
    _f("annual_gross_rent", "s2", "Annual gross rent", (6, 2, 1), source="listing",
       hint="Calculated as (base + NNN) x SF when both are on the listing."),
    _f("rent_escalation", "s2", "Rent escalation", (6, 2, 3)),
    _f("ti_psf", "s2", "TI allowance PSF", (6, 3, 1)),
    _f("ti_conditions", "s2", "TI payment conditions and timing", (6, 3, 3)),
    _f("term_years", "s2", "Lease term in years", (6, 4, 1)),
    _f("options", "s2", "Number and length of options", (6, 4, 3)),
    _f("free_rent", "s2", "Free rent / abatement", (6, 5, 1)),
    _f("fixturing", "s2", "Fixturing period", (6, 5, 3)),
    _f("pct_rent", "s2", "Percentage rent and breakpoint", (6, 6, 1)),
    _f("guaranty", "s2", "Personal guaranty terms", (6, 6, 3)),
    _f("use_clause", "s2", "Use clause, your exclusive, ancillary sales cap", (7, 0, 1), "long"),
    _f("other_exclusives", "s2", "Exclusives / restrictive covenants held by others", (7, 1, 1), "long"),
    _f("hours_cotenancy", "s2", "Required hours, co-tenancy, go-dark, assignment", (7, 2, 1), "long"),

    # ---------------------------------------------------------------- 3
    _f("branded_signage", "s3", "Branded signage above storefront? Y/N", (9, 0, 1), source="listing"),
    _f("proto_signage", "s3", "Prototypical signage allowed? Y/N", (9, 0, 3)),
    _f("sign_area", "s3", "Permitted sign area per ordinance", (9, 1, 1)),
    _f("sign_ordinance", "s3", "Governing sign ordinance and section", (9, 1, 3)),
    _f("parking_ratio", "s3", "Parking ratio for center", (9, 2, 1), source="listing"),
    _f("spaces_nearest", "s3", "Spaces nearest the premises", (9, 2, 3)),
    _f("front_parking", "s3", "Convenient parking in front? Y/N", (9, 3, 1)),
    _f("adt_primary", "s3", "ADT primary street, source and year", (9, 3, 3), source="auto"),
    _f("adt_secondary", "s3", "ADT secondary street, source and year", (9, 4, 1), source="auto"),
    _f("shared_parking", "s3", "Shared or reciprocal parking?", (9, 4, 3)),
    _f("alt_signage", "s3", "Alternative signage, obstructions, landlord criteria", (10, 0, 1), "long", "listing"),
    _f("parking_issues", "s3", "Issues impacting parking", (10, 1, 1), "long", "ai"),
    _f("ingress_egress", "s3", "Ingress and egress", (10, 2, 1), "long", "ai"),
    _f("visibility", "s3", "Storefront visibility from the primary road", (10, 3, 1), "long", "ai"),

    # ---------------------------------------------------------------- 4
    _f("population_135", "s4", "Population 1 / 3 / 5 mile", (12, 0, 1), source="auto"),
    _f("daytime_pop_135", "s4", "Daytime population 1 / 3 / 5 mile", (12, 0, 3), source="auto"),
    _f("median_income_3", "s4", "Median household income, 3 mile", (12, 1, 1), source="auto"),
    _f("median_age_3", "s4", "Median age, 3 mile", (12, 1, 3), source="auto"),
    _f("placer_visits", "s4", "Center annual visits (Placer)", (12, 2, 1)),
    _f("placer_trend", "s4", "Center visit trend YoY", (12, 2, 3)),
    _f("prior_tenant", "s4", "Prior tenant name", (12, 3, 1)),
    _f("prior_tenant_closed", "s4", "Date it ceased operating", (12, 3, 3)),
    _f("cotenant_ranking", "s4", "Ranking of co-tenants vs their own chain", (13, 0, 1), "long", "auto"),
    _f("demand_drivers", "s4", "Demand drivers with distance", (13, 1, 1), "long", "auto"),
    _f("tenant_roster", "s4", "Anchors, tenant roster, vacancy", (13, 2, 1), "long", "auto"),
    _f("competitors_summary", "s4", "Competitors: name, distance, format, visits, price range", (13, 3, 1), "long", "auto"),
    _f("prior_tenant_why", "s4", "Why the prior tenant closed / what you'll do differently", (13, 4, 1), "long"),
    _f("site_swot", "s4", "Site SWOT (2-3 bullets each)", (13, 5, 1), "long", "ai",
       hint="Built from the A3 SWOT table if left blank."),

    # ---------------------------------------------------------------- 5
    _f("gc_inspected", "s5", "GC inspected the space? Y/N and date", (15, 0, 1)),
    _f("architect_inspected", "s5", "Architect inspected? Y/N and date", (15, 0, 3)),
    _f("test_fit", "s5", "HB prototype test fit overlaid? Y/N", (15, 1, 1)),
    _f("delivery_condition", "s5", "Delivery condition per LOI or lease", (15, 1, 3), source="listing"),
    _f("permitting", "s5", "Permitting path, approvals, health dept, who you spoke with", (17, 0, 1), "long", "ai"),

    # ---------------------------------------------------------------- 6
    _f("bud_demo", "s6", "Demolition and general conditions", (19, 0, 1)),
    _f("bud_mep", "s6", "Mechanical, electrical, plumbing", (19, 0, 3)),
    _f("bud_millwork", "s6", "Millwork, cabinets, countertops", (19, 1, 1)),
    _f("bud_finishes", "s6", "Finishes", (19, 1, 3)),
    _f("bud_equipment", "s6", "Equipment and small wares", (19, 2, 1)),
    _f("bud_signage", "s6", "Signage, fabrication and install", (19, 2, 3)),
    _f("bud_ae", "s6", "Architectural, engineering, permits", (19, 3, 1)),
    _f("bud_contingency", "s6", "Contingency, percent of hard cost", (19, 3, 3)),
    _f("bud_total", "s6", "Total project cost", (19, 4, 1)),
    _f("bud_net_cash", "s6", "Less TI allowance, net cash required", (19, 4, 3)),
    _f("bud_fdd", "s6", "Within FDD Item 7 range? Y/N", (19, 5, 1)),
    _f("bud_long_lead", "s6", "Long lead items and lead times", (19, 5, 3)),
    _f("sales_assumption", "s6", "Your sales assumption and its basis", (19, 6, 1)),
    _f("occupancy_cost", "s6", "Total annual occupancy cost", (19, 6, 3)),
    _f("occupancy_pct", "s6", "Occupancy as percent of that assumption", (19, 7, 1)),
    _f("break_even", "s6", "Break-even volume and months to reach it", (19, 7, 3)),
    _f("sources_uses", "s6", "Sources and uses of funds", (20, 0, 1), "long"),
    _f("top_risks", "s6", "Two or three most significant risks and tactics", (20, 1, 1), "long", "ai"),

    # ---------------------------------------------------------------- 7
    _f("possession_date", "s7", "Target possession date", (22, 0, 1)),
    _f("construction_duration", "s7", "Construction duration", (22, 0, 3)),
    _f("opening_date", "s7", "Target opening date", (22, 1, 1)),
    _f("go_budget", "s7", "Grand opening budget", (22, 1, 3)),
    _f("marketing_plan", "s7", "Grand opening and ongoing local marketing plan", (23, 0, 1), "long", "ai"),
    _f("delivery_gbp", "s7", "Delivery platforms, GBP, who operates day to day", (23, 1, 1), "long", "ai"),

    # ---------------------------------------------------------------- 8
    _f("franchisee_opinion", "s8", "Positive and negative factors (be direct)", (25, 0, 1), "long", "ai"),
    _f("tenant_rep_opinion", "s8", "Tenant representative opinion and notes", (25, 1, 1), "long"),

    # ---------------------------------------------------------------- 9 / 10
    _f("attachments_link", "s9", "Link to documents and photos", (27, 0, 1)),
    _f("franchisee_visited", "s10", "I have visited this site. Y/N", (29, 1, 1)),
    _f("franchisee_name", "s10", "Franchisee name", (29, 1, 3)),
    _f("franchisee_sign_date", "s10", "Date (franchisee)", (29, 2, 3)),
    _f("rep_visited", "s10", "Tenant rep has visited. Y/N", (29, 3, 1)),
    _f("rep_name", "s10", "Tenant representative name", (29, 3, 3)),
    _f("rep_sign_date", "s10", "Date (tenant rep)", (29, 4, 3)),

    # ---------------------------------------------------------------- A1
    _f("access_street", "a1", "Access (name of street)", (34, 0, 1), source="auto"),
    _f("exit_street", "a1", "Exit (name of street)", (34, 0, 3), source="auto"),
    _f("other_roads", "a1", "Other main roads or highways", (34, 1, 1), source="auto"),
    _f("store_locator", "a1", "Store locator (i.e. 1st and Main)", (34, 1, 3), source="auto"),

    # ---------------------------------------------------------------- A5 extras
    _f("vis_limitation", "a5", "Visibility or access limitation? Y/N", (47, 0, 1), source="ai"),
    _f("a_opening_date", "a5", "Target opening date (copies Section 7)", (47, 0, 3), hint="Copies Section 7 if blank."),
    _f("wayfinding_plan", "a5", "If yes, discovery and wayfinding plan", (48, 0, 1), "long", "ai"),
    _f("go_plan", "a5", "Grand opening budget and plan", (48, 1, 1), "long", "ai"),
    _f("ongoing_plan", "a5", "Ongoing local marketing plan", (48, 2, 1), "long", "ai"),
    _f("a_delivery_gbp", "a5", "Delivery platforms, GBP, operator (copies Section 7)", (48, 3, 1), "long",
       hint="Copies Section 7 if blank."),
]

MIRRORS = {
    "a_opening_date": "opening_date",
    "a_delivery_gbp": "delivery_gbp",
}

TABLES = [
    {"id": "nearby_business", "section": "a1", "label": "Businesses and institutions",
     "table": 35, "first_row": 1, "columns": [["name", "Name", 0], ["distance", "Distance", 1]],
     "source": "auto", "max_rows": 8},
    {"id": "nearby_community", "section": "a1", "label": "Community groups, schools, organizations",
     "table": 36, "first_row": 1, "columns": [["name", "Name", 0], ["distance", "Distance", 1]],
     "source": "auto", "max_rows": 8},
    {"id": "nearby_residential", "section": "a1", "label": "Local residents and guest base",
     "table": 37, "first_row": 1, "columns": [["name", "Name", 0], ["distance", "Distance", 1]],
     "source": "auto", "max_rows": 8},
    {"id": "comp_direct", "section": "a2", "label": "Direct competitors",
     "table": 39, "first_row": 1,
     "columns": [["name", "Name", 0], ["distance", "Distance", 1], ["price", "Price range", 2],
                 ["strength", "Strength", 3], ["weakness", "Weakness", 4]],
     "source": "auto", "max_rows": 8,
     "hint": "Name and distance are automatic. Fill strength, weakness and price range from your visit and the menu."},
    {"id": "comp_indirect", "section": "a2", "label": "Indirect competitors",
     "table": 40, "first_row": 1,
     "columns": [["name", "Name", 0], ["distance", "Distance", 1], ["price", "Price range", 2],
                 ["strength", "Strength", 3], ["weakness", "Weakness", 4]],
     "source": "auto", "max_rows": 8},
    {"id": "priorities", "section": "a4", "label": "Top five marketing priorities",
     "table": 44, "first_row": 1, "columns": [["objective", "Objective", 1], ["target", "Who this targets", 2]],
     "source": "ai", "max_rows": 5, "fixed_rows": True},
    {"id": "wt_tactics", "section": "a5", "label": "Weakness or threat -> marketing tactic",
     "table": 46, "first_row": 1, "columns": [["item", "Weakness or threat", 0], ["tactic", "Marketing tactic", 1]],
     "source": "ai", "max_rows": 10,
     "hint": "Built from the A3 Weaknesses and Threats if left blank."},
    {"id": "conditions", "section": "s5", "label": "Systems condition (from GC walk)",
     "table": 16, "first_row": 1,
     "columns": [["condition", "Condition as inspected", 1], ["work", "Replace or code work required", 2],
                 ["party", "Landlord or tenant", 3]],
     "row_labels": ["Electrical service and panel", "Plumbing: 3-comp, handwash, mop sink",
                    "Grease interceptor and floor drains", "HVAC, exhaust, make-up air", "Water heater",
                    "Walk-in and reach-in refrigeration", "Flooring, ceiling, finishes",
                    "Restrooms and accessibility"],
     "source": "manual", "max_rows": 8, "fixed_rows": True},
]

SWOT = {"id": "swot","section": "a3", "table": 42, "max_items": 5,
        "quadrants": {"strengths": (0,0), "weaknesses": (0,1), "opportunities": (1,0), "threats": (1,1)}}

FIELD_BY_ID = {f["id"]: f for f in FIELDS}
TABLE_BY_ID = {t["id"]: t for t in TABLES}

def schema() -> dict:
    return {
        "sections": [{"id": s, "label": l} for s, l in sections],
        "fields": [{k: v for k, v in f.items() if k != "loc"} for f in FIELDS],
        "tables": [{k: v for k, v in t.items() if k not in ("table","first_row")} for t in TABLES],
        "swot": {"section": SWOT["section"], "max_items": SWOT["max_items"],
                 "quadrants": list(SWOT["quadrants"].keys())},
    }