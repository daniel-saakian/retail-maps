
import requests
 
STATE_AADT_SOURCES = {
    "CA": {
        "label": "Caltrans",
        "url": "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHhighway/Traffic_AADT/MapServer/0/query",
        "aadt_fields": ["AHEAD_AADT", "BACK_AADT"],
        "route_field": "RTE",
        "out_fields": "AHEAD_AADT,BACK_AADT,RTE",
        "verified": True,
        # Caltrans' own State Highway Network (linear-referencing) layer --
        # same org, same route numbering as the AADT layer above, so a
        # route found here matches AADT's RTE field directly with no OSM
        # round trip. It has no lanes/speed fields, so it can only answer
        # "what route is this," not feed the regression model.
        "roadway": {
            "url": "https://geodata.dot.ca.gov/arcgis/rest/services/chhighway/SHN_Lines/MapServer/0/query",
            "route_field": "RouteS",
            "out_fields": "RouteS,Route,RouteType,Direction,County",
            "verified": True,
        },
    },
    "IL": {
        "label": "IDOT",
        "url": "https://gis1.dot.illinois.gov/arcgis/rest/services/AdministrativeData/AADT/MapServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "MARKED_NAM",
        "out_fields": "AADT,MARKED_NAM,ROAD_NAME",
        "verified": True,
    },
    "NY": {
        "label": "NYSDOT",
        "url": "https://gis.dot.ny.gov/hostingny/rest/services/Roadways/Traffic_Monitoring/MapServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteNumber",
        "out_fields": "AADT,RouteNumber,RoadwayName",
        "verified": True
    },
    "TX": {
        "label": "TxDOT",
        "url": "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/ArcGIS/rest/services/TxDOT_AADT/FeatureServer/0/query",
        "aadt_fields": ["AADT_CUR"],
        "route_field": "RTE_NM",
        "out_fields": "AADT_CUR,RTE_NM,RTE_PRFX,RTE_NBR",
        "verified": True,
        # TxDOT's own roadway inventory layer, same route vocabulary
        # (RTE_NM) as the AADT layer above -- route matching without OSM.
        # No lanes/speed fields here either.
        "roadway": {
            "url": "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_Roadways/FeatureServer/0/query",
            "route_field": "RTE_NM",
            "out_fields": "RTE_NM,RTE_PRFX,RTE_NBR,RTE_SFX,COUNTY",
            "verified": True,
        },
    },
    "DE": {
        "label": "DelDOT",
        "url": "https://enterprise.firstmaptest.delaware.gov/arcgis/rest/services/Transportation/DE_Assets/FeatureServer/10/query",
        "aadt_fields": ["CURRENT_AADT"],
        "route_field": "ROAD_NAME",
        "out_fields": "CURRENT_AADT,ROAD_NUMBER,ROAD_NAME",
        "verified": True,
    },
    "IN": {
        "label": "INDOT",
        "url": "https://gis.indot.in.gov/ro/rest/services/DOT/RO_RandH_Organization_Default/FeatureServer/75/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT,ROUTE_ID",
        "verified": True,
    },
    "IA": {
        "label": "Iowa DOT",
        "url": "https://gis.iowadot.gov/rams/rest/services/lrs/FeatureServer/102/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT,AADT_YEAR,ROUTE_ID",
        "verified": True,
    },
    "NH": {
        "label": "NHDOT",
        "url": "https://maps.dot.nh.gov/arcgis_server/rest/services/Highways/NHDOT_HIGHWAYS_Routes/FeatureServer/4/query",
        "aadt_fields": ["AADT"],
        "route_field": "STREET",
        "out_fields": "AADT,AADT_CURR_YEAR,STREET,TOWN_NAME",
        "verified": True,
    },
    "WA": {
        "label": "WSDOT",
        "url": "https://data.wsdot.wa.gov/arcgis/rest/services/Shared/TrafficData/FeatureServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "StateRouteNumber",
        "out_fields": "AADT,ReportingYear,StateRouteNumber,RouteIdentifier",
        "verified": True, 
    },
    "OR": {
        "label": "ODOT",
        "url": "https://gis.odot.state.or.us/arcgis1006/rest/services/transgis/catalog/MapServer/155/query",
        "aadt_fields": ["AADT"],
        "route_field": "HWYNUMB",
        "out_fields": "AADT,HWYNUMB,COUNTYNAME,ATR_NAME",
        "verified": True,
    },
    "LA": {
        "label": "LADOTD",
        "url": "https://maps.dotd.la.gov/road/rest/services/Roads_and_Highways_Realtime/FeatureServer/52/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteID",
        "out_fields": "AADT,DataYear,RouteID",
        "verified": True,
    },
    "ME": {
        "label": "MaineDOT",
        "url": "https://gis.maine.gov/arcgis/rest/services/dot/MaineDOT_OpenData/MapServer/52/query",
        "aadt_fields": ["faadt"],
        "route_field": "prirtecode",
        "out_fields": "faadt,aadt_type,prirtecode",
        "verified": True,
    },
    "MN": {
        "label": "MnDOT",
        "url": "https://dotapp9.dot.state.mn.us/egis12/rest/services/TFA/MNDOT_TRAFFIC_DATA/MapServer/6/query",
        "aadt_fields": ["CURRENT_VOLUME"],
        "route_field": "ROUTE_LABEL",
        "out_fields": "CURRENT_VOLUME,CURRENT_YEAR,ROUTE_LABEL,STREET_NAME",
        "verified": True,
    },
    "MI": {
        "label": "MDOT",
        "url": "https://mdotgis.state.mi.us/arcgis/rest/services/DataAccess/MdotAadtCaadt/FeatureServer/0/query",
        "aadt_fields": ["Aadt"],
        "route_field": "PR",
        "out_fields": "Aadt,PR,Program",
        "verified": True,
    },
    "NC": {
        "label": "NCDOT",
        "url": "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_AADT_Stations/FeatureServer/0/query",
        "aadt_fields": ["AADT_2022","AADT_2021", "AADT_2020"],
        "route_field": "ROUTE",
        "out_fields": "AADT_2022,AADT_2021,AADT_2020,ROUTE,LOCATION",
        "verified": True
    },
    "OH": {
        "label": "ODOT",
        "url": "https://services.arcgis.com/rD2ylXRs80UroD90/ArcGIS/rest/services/WGIS_TRAFFIC_COUNT_SEGMENTS/FeatureServer/8/query",
        "aadt_fields": ["AADT_TOTAL"],
        "route_field": "ROUTE_NBR",
        "out_fields": "AADT_TOTAL,AADT_YEAR,ROUTE_NBR,ROUTE_TYPE",
        "verified": True,
        # ODOT's Road Inventory layer -- unlike CA/TX's roadway layers, this
        # one actually carries lanes, speed limit, and a functional-class
        # code directly, so for Ohio the regression fallback doesn't need
        # OSM/Overpass at all either, not just the measured-station match.
        # FUNCTION_CLASS_CD's coded domain isn't published in the service
        # metadata -- this assumes the standard FHWA 1-7 (rural) / 11-17
        # (urban) scheme every state DOT uses for this field name. Worth a
        # spot-check against a real response the first time it's used.
        "roadway": {
            "url": "https://tims.dot.state.oh.us/ags/rest/services/Roadway_Information/Road_Inventory/MapServer/0/query",
            "route_field": "ROUTE_NBR",
            "name_field": "STREET_NAME",
            "lanes_field": "THROUGH_LANES",
            "speed_field": "SPEED_LIMIT_NBR",
            "class_field": "FUNCTION_CLASS_CD",
            "out_fields": "ROUTE_NBR,ROUTE_TYPE,STREET_NAME,THROUGH_LANES,SPEED_LIMIT_NBR,FUNCTION_CLASS_CD",
            "verified": True,
        },
    },
    "VT": {
        "label": "VTrans",
        "url": "https://maps.vtrans.vermont.gov/arcgis/rest/services/Layers/AADT/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteNum",
        "out_fields": "AADT,YEAR,RouteNum,RouteName",
        "verified": True,
    },
    "AK": {
        "label": "AKDOT&PF",
        "url": "https://services.arcgis.com/r4A0V7UzH9fcLVvv/ArcGIS/rest/services/AADT_TrafficCounts/FeatureServer/9/query",
        "aadt_fields": ["AADT"],
        "route_field": "Route_Name",
        "out_fields": "AADT,AADT_Year,Route_Name",
        "verified": True,
    },
    "ID": {
        "label": "ITD",
        "url": "https://gis.itd.idaho.gov/arcgisprod/rest/services/ArcGISOnline/AADTLayers/MapServer/40/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteID",
        "out_fields": "AADT,AADTYear,RouteID",
        "verified": True,
    },
    "PA": {
        "label": "PennDOT",
        "url": "https://mapservices.pasda.psu.edu/server/rest/services/pasda/PennDOT/MapServer/5/query",
        "aadt_fields": ["CUR_AADT"],
        "route_field": "ST_RT_NO",
        "out_fields": "CUR_AADT,ST_RT_NO,CTY_CODE",
        "verified": True,
    },
    "RI": {
        "label": "RIDOT",
        "url": "https://risegis.ri.gov/hosting/rest/services/RIDOT/AADT_Bridge_Counts/MapServer/0/query",
        "aadt_fields": ["GIS.DBO.Bridges.ADT_Total"],
        "route_field": "GIS.DBO.Bridges.Facility_Carried",
        "out_fields": "GIS.DBO.Bridges.ADT_Total,GIS.DBO.Bridges.ADT_Year,GIS.DBO.Bridges.Facility_Carried",
        "verified": True
    },
    "NV": {
        "label": "NDOT",
        "url": "https://gis.dot.nv.gov/arcgis/rest/services/Applications/TRINA/MapServer/1/query",
        "aadt_fields": ["AADT_2026", "AADT_2025"],
        "route_field": "ROUTE_NAME",
        "out_fields": "AADT_2026,AADT_2025,ROUTE_NAME",
        "verified": True,
    },
    "VA": {
        "label": "VDOT",
        "url": "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Traffic_Volume_2024/FeatureServer/0/query",
        "aadt_fields": ["ADT"],
        "route_field": "ROUTE_COMMON_NAME",
        "out_fields": "ADT,DATA_DATE,ROUTE_COMMON_NAME,RTE_TYPE_CD",
        "verified": True,
    },
    "WV": {
        "label": "WVDOT",
        "url": "https://gis.transportation.wv.gov/arcgis/rest/services/Projects/AADT/FeatureServer/2/query",
        "aadt_fields": ["Value_Nume"],
        "route_field": "Route_ID",
        "out_fields": "Value_Nume,Data_Item,Year_Recor,Route_ID",
        "where": "Data_Item='AADT'",
        "verified": True
    },
    "KS": {
        "label": "KDOT",
        "url": "https://kanplan.ksdot.org/arcgis_web_adaptor/rest/services/Transportation/AADT_Flow_Map/FeatureServer/0/query",
        "aadt_fields": ["AADTCount"],
        "route_field": "ROUTE",
        "out_fields": "AADTCount,ROUTE",
        "verified": True,
    },
    "MT": {
        "label": "MDT",
        "url": "https://gis.mtmdt.us/server/rest/services/MDTGIS/Traffic/MapServer/5/query",
        "aadt_fields": ["TYC_AADT"],
        "route_field": "CORR_ID",
        "out_fields": "TYC_AADT,YEAR,CORR_ID,DEPT_ID",
        "verified": True,
    },
    "NE": {
        "label": "NDOT",
        "url": "https://giscat.ne.gov/dot/rest/services/AADTCountsDOT/MapServer/0/query",
        "aadt_fields": ["ADJ_ADT_TOT_NUM"],
        "route_field": "ROUTE_NO",
        "out_fields": "ADJ_ADT_TOT_NUM,ADT_YEAR,ROUTE_NO,COUNTY",
        "verified": True,
    },
    "MO": {
        "label": "MoDOT",
        "urls": [
            "https://mapping.modot.org/arcgis/rest/services/BusinessInt/TrafficInfoSegAADT/MapServer/1/query",
            "https://mapping.modot.org/arcgis/rest/services/BusinessInt/TrafficInfoSegAADT/MapServer/2/query",
            "https://mapping.modot.org/arcgis/rest/services/BusinessInt/TrafficInfoSegAADT/MapServer/3/query",
            "https://mapping.modot.org/arcgis/rest/services/BusinessInt/TrafficInfoSegAADT/MapServer/4/query",
        ],
        "aadt_fields": ["AADT"],
        "route_field": "TRAVELWAY_NAME",
        "out_fields": "AADT,AADT_YEAR,TRAVELWAY_NAME",
        "verified": True,
    },
    "MD": {
        "label": "MDOT SHA",
        "url": "https://services.arcgis.com/njFNhDsUCentVYJW/ArcGIS/rest/services/MDOT_SHA_Annual_Average_Daily_Traffic/FeatureServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROADNAME",
        "out_fields": "AADT,ROADNAME,ID_PREFIX,ID_RTE_NO",
        "verified": True,
    }
}
 
def inspect_layer(layer_url: str) -> dict:
    r = requests.get(f"{layer_url.rstrip('/')}", params={"f": "json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return {
        "name": data.get("name"),
        "geometry_type": data.get("geometryType"),
        "fields": [f["name"] for f in data.get("fields", [])],
    }
 
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("usage: python state_traffic_sources.py <layer_url>")
    else:
        print(json.dumps(inspect_layer(sys.argv[1]), indent=2))