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
        "roadway": {
            "url": "https://gis1.dot.illinois.gov/arcgis/rest/services/AdministrativeData/FunctionalClass/MapServer/0/query",
            "route_field": "KEY_RT_NBR",
            "name_field": "LABEL_1",
            "class_field": "FC",
            "out_fields": "KEY_RT_NBR,LABEL_1,FC,KEY_RT_TYP",
            "verified": True,
        },
    },
    "NY": {
        "label": "NYSDOT",
        "url": "https://gis.dot.ny.gov/hostingny/rest/services/Roadways/Traffic_Monitoring/MapServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteNumber",
        "out_fields": "AADT,RouteNumber,RoadwayName",
        "verified": True,
        "roadway": {
            "url": "https://gis.dot.ny.gov/hostingny/rest/services/FunctionalClass/MapServer/1/query",
            "route_field": "ROUTE_NO",
            "name_field": "SEGMENT_NAME",
            "class_field": "FUNC_CLASS",
            "out_fields": "ROUTE_NO,SEGMENT_NAME,FUNC_CLASS,ROADWAY_TYPE",
            "verified": True,
        },
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
        "roadway": {
            "url": "https://enterprise.firstmaptest.delaware.gov/arcgis/rest/services/Transportation/DE_Roadways_Main/FeatureServer/2/query",
            "route_field": "ROUTE_NO",
            "name_field": "RDWAY_NAME",
            "lanes_field": "LANES_QTY",
            "speed_field": "SPEED_LIMIT",
            "class_field": "FNCTNL_CLASS_CODE",
            "out_fields": "ROUTE_NO,RDWAY_NAME,LANES_QTY,SPEED_LIMIT,FNCTNL_CLASS_CODE",
            "verified": True,
        },
    },
    "IN": {
        "label": "INDOT",
        "url": "https://gis.indot.in.gov/ro/rest/services/DOT/RO_RandH_Organization_Default/FeatureServer/75/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT,ROUTE_ID",
        "verified": True,
        "roadway": {
            "url": "https://gisdata.in.gov/server/rest/services/Hosted/LRSE_Functional_Class/FeatureServer/22/query",
            "route_field": "route_id",
            "class_field": "functional_class",
            "out_fields": "route_id,functional_class",
            "verified": True,
        },
    },
    "IA": {
        "label": "Iowa DOT",
        "url": "https://gis.iowadot.gov/rams/rest/services/lrs/FeatureServer/102/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT,AADT_YEAR,ROUTE_ID",
        "verified": True,
        "roadway": {
            "url": "https://gis.iowadot.gov/agshost/rest/services/RAMS/Road_Network/FeatureServer/0/query",
            "route_field": "ROUTEID",
            "name_field": "ROUTEID_NAME",
            "lanes_field": "NUMBER_LANES",
            "speed_field": "SPEED_LIMIT",
            "class_field": "FED_FUNCTIONAL_CLASS",
            "out_fields": "ROUTEID,ROUTEID_NAME,ROUTETYPE,NUMBER_LANES,SPEED_LIMIT,FED_FUNCTIONAL_CLASS",
            "verified": True,
        },
    },
    "NH": {
        "label": "NHDOT",
        "url": "https://maps.dot.nh.gov/arcgis_server/rest/services/Highways/NHDOT_HIGHWAYS_Routes/FeatureServer/4/query",
        "aadt_fields": ["AADT"],
        "route_field": "STREET",
        "out_fields": "AADT,AADT_CURR_YEAR,STREET,TOWN_NAME",
        "verified": True,
        # Same service as the AADT entry, layer 4 also carries roadway
        # characteristics -- no dedicated posted-speed field on this layer.
        "roadway": {
            "url": "https://maps.dot.nh.gov/arcgis_server/rest/services/Highways/NHDOT_HIGHWAYS_Routes/FeatureServer/4/query",
            "route_field": "ROUTE_ID",
            "name_field": "STREET",
            "lanes_field": "NUM_LANES",
            "class_field": "FUNCT_SYSTEM",
            "out_fields": "ROUTE_ID,STREET,ROUTE_TYPE,NUM_LANES,HPMS_THRU_LANES,FUNCT_SYSTEM,FUNCT_SYSTEM_DESCR",
            "verified": True,
        },
    },
    "WA": {
        "label": "WSDOT",
        "url": "https://data.wsdot.wa.gov/arcgis/rest/services/Shared/TrafficData/FeatureServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "StateRouteNumber",
        "out_fields": "AADT,ReportingYear,StateRouteNumber,RouteIdentifier",
        "verified": True,
        # WSDOT splits roadway characteristics into separate per-attribute
        # layers rather than one combined layer -- this is "Lane
        # Information," route + lanes only, no speed/functional-class.
        "roadway": {
            "url": "https://data.wsdot.wa.gov/arcgis/rest/services/Shared/RoadwayCharacteristicData/MapServer/3/query",
            "route_field": "RouteIdentifier",
            "lanes_field": "NumberOfLanes",
            "out_fields": "RouteIdentifier,NumberOfLanes,BeginStateRouteMilepost,EndStateRouteMilepost",
            "verified": True,
        },
    },
    "OR": {
        "label": "ODOT",
        "url": "https://gis.odot.state.or.us/arcgis1006/rest/services/transgis/catalog/MapServer/155/query",
        "aadt_fields": ["AADT"],
        "route_field": "HWYNUMB",
        "out_fields": "AADT,HWYNUMB,COUNTYNAME,ATR_NAME",
        "verified": True,
        # Route/name only -- no lanes, speed, or functional-class fields
        # exist on ODOT's public Highway Network layer.
        "roadway": {
            "url": "https://gis.odot.state.or.us/arcgis1006/rest/services/transgis/catalog/MapServer/169/query",
            "route_field": "HWYNUMB",
            "name_field": "HWYNAME",
            "out_fields": "HWYNUMB,HWYNAME,RDWY_TYP,BEGMP,ENDMP",
            "verified": True,
        },
    },
    "LA": {
        "label": "LADOTD",
        "url": "https://maps.dotd.la.gov/road/rest/services/Roads_and_Highways_Realtime/FeatureServer/52/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteID",
        "out_fields": "AADT,DataYear,RouteID",
        "verified": True,
        "roadway": {
            "url": "https://maps.dotd.la.gov/road/rest/services/Roads_and_Highways_Realtime/FeatureServer/49/query",
            "route_field": "RouteID",
            "name_field": "FullName",
            "lanes_field": "FromLanes",
            "speed_field": "FromSpeedLimit",
            "class_field": "FeatureClassCode",
            "out_fields": "RouteID,StateRoute,FullName,FromLanes,ToLanes,FromSpeedLimit,ToSpeedLimit,FeatureClassCode,RouteClassCode",
            "verified": True,
        },
    },
    "ME": {
        # Host moved from gis.maine.gov/arcgis (now 404s) to
        # gis.maine.gov/mapservices -- confirmed live 2026-09-23.
        "label": "MaineDOT",
        "url": "https://gis.maine.gov/mapservices/rest/services/dot/MaineDOT_OpenData/MapServer/52/query",
        "aadt_fields": ["faadt"],
        "route_field": "prirtecode",
        "where": "faadt IS NOT NULL",
        "out_fields": "faadt,aadt_type,prirtecode",
        "verified": True,
        # Same layer as the AADT entry above -- MaineDOT's public-roads
        # inventory layer also carries lanes/speed/functional class.
        "roadway": {
            "url": "https://gis.maine.gov/mapservices/rest/services/dot/MaineDOT_OpenData/MapServer/52/query",
            "route_field": "prirtecode",
            "name_field": "prirtename",
            "lanes_field": "num_lanes",
            "speed_field": "speed_lim",
            "class_field": "fedfunccls",
            "out_fields": "prirtecode,prirtename,strtname,num_lanes,speed_lim,fedfunccls",
            "verified": True,
        },
    },
    "MN": {
        # dotapp9.dot.state.mn.us/.../TFA/MNDOT_TRAFFIC_DATA is genuinely
        # down (HTTP 500 "service not started" on a live query, not just a
        # stale layer id) -- switched to MnDOT's own ArcGIS Online-hosted
        # "AADT traffic counts" layer, confirmed live 2026-09-23. The
        # roadway sub-dict below is a different dotapp9 service group
        # (BASEMAP, not TFA) and wasn't independently re-checked -- worth
        # a spot-check given its sibling group's outage.
        "label": "MnDOT",
        "url": "https://services2.arcgis.com/tJVbdHdHy8Vhg5kh/arcgis/rest/services/AADT_traffic_counts/FeatureServer/0/query",
        "aadt_fields": ["CURRENT_VO"],
        "route_field": "ROUTE_LABE",
        "where": "CURRENT_VO IS NOT NULL",
        "out_fields": "CURRENT_VO,CURRENT_YE,ROUTE_LABE,STREET_NAM,AADT_COMME",
        "verified": True,
        # Route/name only -- ROUTE_SYSTEM is a coarse route-system category
        # (Interstate/US/MN/Other), not lanes/speed/a numeric func-class code.
        "roadway": {
            "url": "https://dotapp9.dot.state.mn.us/egis12/rest/services/BASEMAP/mndot_commonlayers2/FeatureServer/0/query",
            "route_field": "ROUTE_LABEL",
            "name_field": "ROUTE_NAME",
            "class_field": "ROUTE_SYSTEM",
            "out_fields": "ROUTE_ID,ROUTE_NAME,ROUTE_LABEL,ROUTE_NUMBER,ROUTE_SYSTEM,TRAFFIC_DIRECTION",
            "verified": True,
        },
    },
    "MI": {
        "label": "MDOT",
        "url": "https://mdotgis.state.mi.us/arcgis/rest/services/DataAccess/MdotAadtCaadt/FeatureServer/0/query",
        "aadt_fields": ["Aadt"],
        "route_field": "PR",
        "out_fields": "Aadt,PR,Program",
        "verified": True,
        # Route + speed only -- MDOT's fuller Road Asset Inventory layer is
        # token-gated and not publicly queryable; this standalone speed-
        # limit layer was the best verified, open alternative.
        "roadway": {
            "url": "https://services2.arcgis.com/67lKNkQ2TO1I3lhR/arcgis/rest/services/SpeedLimitRAI/FeatureServer/0/query",
            "route_field": "PR",
            "speed_field": "SpeedLimit",
            "out_fields": "PR,PRBmp,PREmp,SpeedLimit",
            "verified": True,
        },
    },
    "NC": {
        "label": "NCDOT",
        "url": "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_AADT_Stations/FeatureServer/0/query",
        "aadt_fields": ["AADT_2022","AADT_2021", "AADT_2020"],
        "route_field": "ROUTE",
        "out_fields": "AADT_2022,AADT_2021,AADT_2020,ROUTE,LOCATION",
        "verified": True,
        "roadway": {
            "url": "https://gis11.services.ncdot.gov/arcgis/rest/services/NCDOT_RoadCharacteristicsQtr/MapServer/0/query",
            "route_field": "RouteNumber",
            "name_field": "RouteName",
            "lanes_field": "ThruLaneCount",
            "speed_field": "SpeedLimit",
            "class_field": "FuncClass",
            "out_fields": "RouteNumber,RouteName,RouteClass,ThruLaneCount,SpeedLimit,FuncClass",
            "verified": True,
        },
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
        # No lanes/functional-class field on this layer (VT's lane data is
        # keyed by internal town/state linear-reference IDs, not a route
        # field, so it was less suitable as the primary roadway pick).
        "roadway": {
            "url": "https://maps.vtrans.vermont.gov/arcgis/rest/services/Master/VTrans2/FeatureServer/32/query",
            "route_field": "ROUTE",
            "name_field": "LOCATION",
            "speed_field": "SPEED_LIMIT",
            "out_fields": "ROUTE,LOCATION,SPEED_LIMIT,TOWN_NAME,DIRECTION,JURISDICTION",
            "verified": True,
        },
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
        # Route/name only -- ITD's functional-class layers key by an
        # internal SegCode rather than a human route number.
        "roadway": {
            "url": "https://gis.itd.idaho.gov/arcgisprod/rest/services/ArcGISOnline/TransportationLayers/MapServer/12/query",
            "route_field": "PREFIX",
            "name_field": "RD_NAME",
            "out_fields": "PREFIX,RD_NAME,RD_TYPE,HWY_TYPE,ITD_DIST,Direction",
            "verified": True,
        },
    },
    "PA": {
        "label": "PennDOT",
        "url": "https://mapservices.pasda.psu.edu/server/rest/services/pasda/PennDOT/MapServer/5/query",
        "aadt_fields": ["CUR_AADT"],
        "route_field": "ST_RT_NO",
        "out_fields": "CUR_AADT,ST_RT_NO,CTY_CODE",
        "verified": True,
        # No speed-limit or functional-class field present on this layer.
        "roadway": {
            "url": "https://mapservices.pasda.psu.edu/server/rest/services/pasda/PennDOT/MapServer/4/query",
            "route_field": "TRAF_RT_NO",
            "name_field": "STREET_NAM",
            "lanes_field": "LANE_CNT",
            "out_fields": "TRAF_RT_NO,T_RT_NO,STREET_NAM,LANE_CNT,SURF_TYPE,DIVSR_TYPE",
            "verified": True,
        },
    },
    "RI": {
        "label": "RIDOT",
        "url": "https://risegis.ri.gov/hosting/rest/services/RIDOT/AADT_Bridge_Counts/MapServer/0/query",
        "aadt_fields": ["GIS.DBO.Bridges.ADT_Total"],
        "route_field": "GIS.DBO.Bridges.Facility_Carried",
        "out_fields": "GIS.DBO.Bridges.ADT_Total,GIS.DBO.Bridges.ADT_Year,GIS.DBO.Bridges.Facility_Carried",
        "verified": True,
        # No speed-limit field found on this layer.
        "roadway": {
            "url": "https://risegis.ri.gov/hosting/rest/services/RIDOT/Road_Centerlines/MapServer/0/query",
            "route_field": "RTNO",
            "name_field": "NAME",
            "lanes_field": "LANES",
            "class_field": "F_SYSTEM",
            "out_fields": "RTNO,NAME,LANES,ROADCLASS,FUNC,F_SYSTEM,NHS",
            "verified": True,
        },
    },
    "NV": {
        "label": "NDOT",
        "url": "https://gis.dot.nv.gov/arcgis/rest/services/Applications/TRINA/MapServer/1/query",
        "aadt_fields": ["AADT_2026", "AADT_2025"],
        "route_field": "ROUTE_NAME",
        "out_fields": "AADT_2026,AADT_2025,ROUTE_NAME",
        "verified": True,
        # Route/name only -- no lanes/speed/functional-class field present.
        "roadway": {
            "url": "https://gis.dot.nv.gov/rhgis/rest/services/GeoHub/StatewideRoutes/FeatureServer/0/query",
            "route_field": "RouteID",
            "name_field": "RouteNameFull",
            "out_fields": "RouteID,RouteNameFull,SystemType,SystemSubtype,JurisdictionCode,CountyCode",
            "verified": True,
        },
    },
    "VA": {
        "label": "VDOT",
        "url": "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Traffic_Volume_2024/FeatureServer/0/query",
        "aadt_fields": ["ADT"],
        "route_field": "ROUTE_COMMON_NAME",
        "out_fields": "ADT,DATA_DATE,ROUTE_COMMON_NAME,RTE_TYPE_CD",
        "verified": True,
        # No lanes/speed field on this layer (VDOT publishes speed limits
        # separately with no stable direct-REST endpoint confirmed).
        "roadway": {
            "url": "https://vdotgisuportal.vdot.virginia.gov/env/rest/services/VDOT_Map/Virginia_Tech_LRS_Routes/FeatureServer/4/query",
            "route_field": "RTE_COMMON_NM",
            "name_field": "RTE_NM",
            "class_field": "TMPD_FUNCTIONAL_CLASS_CD",
            "out_fields": "RTE_COMMON_NM,RTE_NM,RTE_TYPE_NM,TMPD_FUNCTIONAL_CLASS_CD,TMPD_FUNCTIONAL_CLASS_NM",
            "verified": True,
        },
    },
    "WV": {
        "label": "WVDOT",
        "url": "https://gis.transportation.wv.gov/arcgis/rest/services/Projects/AADT/FeatureServer/2/query",
        "aadt_fields": ["Value_Nume"],
        "route_field": "Route_ID",
        "out_fields": "Value_Nume,Data_Item,Year_Recor,Route_ID",
        "where": "Data_Item='AADT'",
        "verified": True,
        # No name/lanes/speed field on this layer.
        "roadway": {
            "url": "https://gis.transportation.wv.gov/arcgis/rest/services/Routes/FeatureServer/3/query",
            "route_field": "ROUTE_ID",
            "class_field": "STATE_FUNCTIONAL_CLASS",
            "out_fields": "ROUTE_ID,STATE_FUNCTIONAL_CLASS,FROM_MEASURE,TO_MEASURE",
            "verified": True,
        },
    },
    "KS": {
        # kanplan.ksdot.org doesn't resolve at all (DNS failure on a live
        # query, not just a blocked host) -- switched to KDOT's own ArcGIS
        # Online-hosted "AADT2021" layer, confirmed live 2026-09-23. The
        # roadway sub-dict below still points at kanplan.ksdot.gov (a
        # different TLD from the dead .org host, so not necessarily also
        # down, but unverified here) -- worth a spot-check.
        "label": "KDOT",
        "url": "https://services6.arcgis.com/Xj5oQOHmqKlB1HVs/ArcGIS/rest/services/AADT2021/FeatureServer/0/query",
        "aadt_fields": ["AADTCount"],
        "route_field": "RouteID",
        "where": "AADTCount IS NOT NULL",
        "out_fields": "AADTCount,AADTCountYear,RouteID,SingleUnitTruck,CombinationTruck",
        "verified": True,
        # Covers one route-classification category (stubs/local-service
        # routes) on this specific layer id; sibling layers 0-3 on the
        # same MapServer likely share the schema for other categories.
        "roadway": {
            "url": "https://kanplan.ksdot.gov/arcgis_web_adaptor/rest/services/Transportation/KDOT_Route_Classification/MapServer/4/query",
            "route_field": "RouteID",
            "class_field": "KDOTRouteClass",
            "out_fields": "RouteID,KDOTRouteClass,FromMeasure,ToMeasure",
            "verified": True,
        },
    },
    "MT": {
        "label": "MDT",
        "url": "https://gis.mtmdt.us/server/rest/services/MDTGIS/Traffic/MapServer/5/query",
        "aadt_fields": ["TYC_AADT"],
        "route_field": "CORR_ID",
        "out_fields": "TYC_AADT,YEAR,CORR_ID,DEPT_ID",
        "verified": True,
        # No verified roadway layer -- MDT's candidate route/speed-limit
        # services (app.mdt.mt.gov) were returning HTTP 500 "service not
        # started" at verification time. Worth retrying later rather than
        # guessing field names for a service that couldn't be queried.
    },
    "NE": {
        "label": "NDOT",
        "url": "https://giscat.ne.gov/dot/rest/services/AADTCountsDOT/MapServer/0/query",
        "aadt_fields": ["ADJ_ADT_TOT_NUM"],
        "route_field": "ROUTE_NO",
        "out_fields": "ADJ_ADT_TOT_NUM,ADT_YEAR,ROUTE_NO,COUNTY",
        "verified": True,
        # No lanes/speed/functional-class field on this layer.
        "roadway": {
            "url": "https://giscat.ne.gov/enterprise/rest/services/Highways_DOT_NE/MapServer/5/query",
            "route_field": "RouteID",
            "name_field": "HwyLabel",
            "out_fields": "RouteID,HwyType,HwyLabel,BegRefPost,EndRefPost,BegLogMile,EndLogMile",
            "verified": True,
        },
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
        # No dedicated lanes or speed-limit field; DIVIDED_UNDIVIDED gives
        # a rough lane-configuration hint but isn't a lane count.
        "roadway": {
            "url": "https://mapping.modot.org/arcgis/rest/services/BusinessInt/FedAidRoutes/MapServer/1/query",
            "route_field": "TRAVELWAY_NAME",
            "class_field": "FUNC_CLASS_NAME",
            "out_fields": "TRAVELWAY_NAME,TRAVELWAY_DESG,TRAVELWAY_DIR,FUNC_CLASS_NAME,FED_SYS_CLS_NAME,STATE_SYSTEM_CLASS,DIVIDED_UNDIVIDED,COUNTY_NAME",
            "verified": True,
        },
    },
    "MD": {
        "label": "MDOT SHA",
        "url": "https://services.arcgis.com/njFNhDsUCentVYJW/ArcGIS/rest/services/MDOT_SHA_Annual_Average_Daily_Traffic/FeatureServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROADNAME",
        "out_fields": "AADT,ROADNAME,ID_PREFIX,ID_RTE_NO",
        "verified": True,
        # No lanes/speed field on this layer (published as separate
        # point-feature datasets, not on this route layer).
        "roadway": {
            "url": "https://maps.roads.maryland.gov/arcgis/rest/services/CMAPS/CMAPS_Maryland_MDOTSHA/MapServer/0/query",
            "route_field": "ID_RTE_NO",
            "name_field": "ROAD_NAME",
            "class_field": "FUNCTIONAL_CLASS",
            "out_fields": "ROAD_NAME,ID_PREFIX,ID_RTE_NO,MP_SUFFIX,FUNCTIONAL_CLASS,FUNCTIONAL_CLASS_ID,OWNERSHIP,NHS_STATUS",
            "verified": True,
        },
    },
 
    # ---- Newly added states (verified 2026-09-23) ----
 
    "AL": {
        "label": "ALDOT",
        "url": "https://aldotgis.dot.state.al.us/pubgis2/rest/services/EGISATDServices/TDMPublic/MapServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteID",
        "out_fields": "AADT,YearAADT,RouteID,Station",
        "verified": True,
        # No lanes/speed/functional-class fields present on this layer.
        "roadway": {
            "url": "https://aldotgis.dot.state.al.us/pubgis2/rest/services/Roads/EGISRoutes/MapServer/2/query",
            "route_field": "RouteNumber",
            "out_fields": "RouteNumber,RouteType,RouteDirection,CountyFIPSCode",
            "verified": True,
        },
    },
    "AZ": {
        "label": "ADOT",
        "url": "https://services6.arcgis.com/clPWQMwZfdWn4MQZ/arcgis/rest/services/ADOT_2024_Average_Annual_Daily_Traffic_(AADT)/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "RouteId",
        "out_fields": "AADT,SubmittalYear,RouteId,SourceDataset",
        "verified": True,
        # No lanes/speed/functional-class fields present on this layer, but
        # ISDIVIDED (already in out_fields, previously unused) is a real
        # signal worth using: a divided road is essentially always at
        # least a secondary arterial regardless of what TIGER's coarse
        # bucket guesses -- see _is_divided in adjacent_estimation.py.
        "roadway": {
            "url": "https://azgeo.az.gov/arcgis/rest/services/adot/ATIS_Roads/MapServer/0/query",
            "route_field": "ROUTE",
            "divided_field": "ISDIVIDED",
            "out_fields": "ROUTE,RTE_TYPE,RTE_ID,ISDIVIDED,SUBTYPEFIELD",
            "verified": True,
        },
    },
    "AR": {
        # Road_Inventory_OnSystem (still used below for roadway/lanes/speed/
        # class) turned out to have zero non-null ADT values live -- it's
        # not a live traffic-count layer despite having an ADT field in its
        # schema. The actual live counts are on a sibling layer, ADTLinear.
        # Confirmed live 2026-09-23.
        "label": "ARDOT",
        "url": "https://gis.ardot.gov/referenced/rest/services/SIR_TIS/ADTLinear/FeatureServer/0/query",
        "aadt_fields": ["MostRecentADT"],
        "route_field": "Route",
        "where": "MostRecentADT IS NOT NULL",
        "out_fields": "MostRecentADT,Route,AH_RoadID,Year_ADT,TruckPercent",
        "verified": True,
        "roadway": {
            "url": "https://gis.ardot.gov/referenced/rest/services/SIR_TIS/Road_Inventory_OnSystem/FeatureServer/0/query",
            "route_field": "AH_Route",
            "lanes_field": "Total_Lanes",
            "speed_field": "Speedlimit",
            "class_field": "FunctionalClass",
            "out_fields": "AH_Route,Total_Lanes,Speedlimit,FunctionalClass,AH_RoadID",
            "verified": True,
        },
    },
    "CO": {
        "label": "CDOT",
        "url": "https://dtdapps.codot.gov/server/rest/services/Webapps/open_data_sde/FeatureServer/13/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE",
        "out_fields": "AADT,AADTYR,ROUTE,COUNTSTATIONID",
        "verified": True,
        # This "Geometrics" layer has lanes but no speed limit or
        # functional class; functional class is on a separate CDOT layer
        # (FeatureServer/11, field FUNCCLASS) if you want a second lookup.
        "roadway": {
            "url": "https://dtdapps.codot.gov/server/rest/services/Webapps/open_data_sde/FeatureServer/12/query",
            "route_field": "ROUTE",
            "lanes_field": "THRULNQTY",
            "out_fields": "ROUTE,THRULNQTY,THRULNWD,REFPT,ENDREFPT",
            "verified": True,
        },
    },
    "CT": {
        "label": "CTDOT",
        "url": "https://services1.arcgis.com/FCaUeJ5SOVtImake/arcgis/rest/services/CTDOT_Traffic_Monitoring_Data/FeatureServer/1/query",
        "aadt_fields": ["AADT_AADT_VALUE"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT_AADT_VALUE,AADT_AADT_YEAR,ROUTE_ID,AADT_STATION_ID",
        "verified": True,
        # Lanes are on a separate sublayer as width/type, not a lane count,
        # and there's no dedicated speed-limit sublayer in this service.
        "roadway": {
            "url": "https://services1.arcgis.com/FCaUeJ5SOVtImake/arcgis/rest/services/CTDOT_Roadway_Classification_and_Characteristic_Data/FeatureServer/3/query",
            "route_field": "ROUTE_ID",
            "class_field": "FC_FC_CODE",
            "out_fields": "ROUTE_ID,FC_FC_CODE,FC_CODE_DESC,TOWN_NAME",
            "verified": True,
        },
    },
    "FL": {
        "label": "FDOT",
        "url": "https://gis.fdot.gov/arcgis/rest/services/RCI_Layers/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROADWAY",
        "out_fields": "AADT,YEAR_,ROADWAY,COUNTY,DISTRICT",
        "verified": True,
        # Speed limit and functional class are separate FDOT layers, not
        # combined here (Maximum_Speed_Limit_TDA field SPEED; RCI_Layers/3
        # field FUNCLASS) -- all three share ROADWAY + BEGIN_POST/END_POST
        # keys if you want to join them later.
        "roadway": {
            "url": "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/Number_Of_Lanes_TDA/FeatureServer/0/query",
            "route_field": "ROADWAY",
            "lanes_field": "LANE_CNT",
            "out_fields": "ROADWAY,LANE_CNT,COUNTY,DISTRICT",
            "verified": True,
        },
    },
    "GA": {
        # Single GDOT layer serves as both AADT source and roadway inventory.
        "label": "GDOT",
        "url": "https://maps.itos.uga.edu/arcgis/rest/services/GDOT/GDOT_FunctionalClass/MapServer/21/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT,ROUTE_ID,Road,Lanes,Speed_Limit,Milepoint",
        "verified": True,
        # No functional-class attribute on this layer -- GDOT expresses
        # func-class as separate MapServer sublayers by class instead.
        "roadway": {
            "url": "https://maps.itos.uga.edu/arcgis/rest/services/GDOT/GDOT_FunctionalClass/MapServer/21/query",
            "route_field": "ROUTE_ID",
            "name_field": "Road",
            "lanes_field": "Lanes",
            "speed_field": "Speed_Limit",
            "out_fields": "ROUTE_ID,Road,Lanes,Speed_Limit,AADT,Milepoint",
            "verified": True,
        },
    },
    "KY": {
        # Single KYTC layer serves as both AADT source and roadway inventory.
        "label": "KYTC",
        "url": "https://kygisserver.ky.gov/arcgis/rest/services/WGS84WM_Services/Ky_AllRoad_Assets_Flattened_WGS84WM/MapServer/0/query",
        "aadt_fields": ["Traffic_Last_Count"],
        "route_field": "Route",
        "out_fields": "Traffic_Last_Count,Traffic_Last_Count_Year,Route,Route_Number,Lanes_Total_Number_Driving,Speed_Limit_Posted_MPH,Functional_Class",
        "verified": True,
        "roadway": {
            "url": "https://kygisserver.ky.gov/arcgis/rest/services/WGS84WM_Services/Ky_AllRoad_Assets_Flattened_WGS84WM/MapServer/0/query",
            "route_field": "Route",
            "lanes_field": "Lanes_Total_Number_Driving",
            "speed_field": "Speed_Limit_Posted_MPH",
            "class_field": "Functional_Class",
            "out_fields": "Route,Route_Number,Lanes_Total_Number_Driving,Speed_Limit_Posted_MPH,Functional_Class",
            "verified": True,
        },
    },
    "MA": {
        "label": "MassDOT",
        "url": "https://gis.massdot.state.ma.us/arcgis/rest/services/Roads/TrafficInventoryYearEnd/FeatureServer/1/query",
        "aadt_fields": ["AADT"],
        "route_field": "route_id",
        "out_fields": "AADT,AADT_Year,route_id,Route_Number,Route_System,St_Name,F_F_Class,Num_Lanes",
        "verified": True,
        # Paired with the year-end Road Inventory layer for speed limit,
        # which the traffic layer itself lacks.
        "roadway": {
            "url": "https://gis.massdot.state.ma.us/arcgis/rest/services/Roads/RoadInventoryYearEndFiles/FeatureServer/10/query",
            "route_field": "route_id",
            "name_field": "St_Name",
            "lanes_field": "Num_Lanes",
            "speed_field": "Speed_Lim",
            "class_field": "F_F_Class",
            "out_fields": "route_id,Route_Number,St_Name,Num_Lanes,Speed_Lim,F_F_Class",
            "verified": True,
        },
    },
    "MS": {
        "label": "MDOT",
        "url": "https://services.arcgis.com/04HiymDgLlsbhaV4/arcgis/rest/services/Mississippi_RCI/FeatureServer/3/query",
        "aadt_fields": ["ADT_21", "ADT_20", "ADT_19"],
        "route_field": "ROUTEID",
        "out_fields": "ADT_21,ADT_20,ADT_19,ROUTEID,SRI",
        "verified": True,
        # Same Roadway Characteristics Inventory service, a different
        # sublayer, keyed on the same ROUTEID/SRI.
        "roadway": {
            "url": "https://services.arcgis.com/04HiymDgLlsbhaV4/arcgis/rest/services/Mississippi_RCI/FeatureServer/2/query",
            "route_field": "ROUTEID",
            "lanes_field": "TOTAL_LANES",
            "speed_field": "SPEEDLIMIT",
            "class_field": "FUNCCLASSNMBR",
            "out_fields": "ROUTEID,SRI,TOTAL_LANES,SPEEDLIMIT,FUNCCLASSNMBR",
            "verified": True,
        },
    },
    "NJ": {
        "label": "NJDOT",
        "url": "https://services.arcgis.com/HggmsDF7UJsNN1FK/arcgis/rest/services/New_jersey_Annual_Average_Daily_Traffic_2017/FeatureServer/0/query",
        "aadt_fields": ["AADT_2024", "AADT_2023", "CURRENT_AA"],
        "route_field": "SRI",
        "out_fields": "AADT_2024,AADT_2023,CURRENT_AA,CURRENT_YE,SRI,ROAD_TYPE,STATION,MP_START,MP_END",
        "verified": True,
        # No lanes/speed/functional-class field found on NJDOT's roadway
        # network layer -- route/name identifiers only.
        "roadway": {
            "url": "https://services.arcgis.com/HggmsDF7UJsNN1FK/arcgis/rest/services/New_Jersey_DOT_Roadway_Network/FeatureServer/0/query",
            "route_field": "SRI",
            "name_field": "SLD_NAME",
            "out_fields": "SRI,ROAD_NUM,SLD_NAME,ROUTE_SUBTYPE,DIRECTION",
            "verified": True,
        },
    },
    "NM": {
        # Single NMDOT layer (HPMS) serves as both AADT source and roadway
        # inventory. No speed-limit field present. AADT was never a wrong
        # field name -- it's a real, valid field confirmed live -- but a
        # plain query hits a lot of ramp/auxiliary segments HPMS doesn't
        # sample for traffic, so most records come back null. The where
        # clause below filters those out at the source instead of relying
        # on downstream code to skip a mostly-null result set.
        "label": "NMDOT",
        "url": "https://services.arcgis.com/hOpd7wfnKm16p9D9/arcgis/rest/services/HPMS2026/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "route_id",
        "where": "AADT IS NOT NULL",
        "out_fields": "AADT,AADTYear,route_id,RoadLabel,ThroughLaneCount,FSystem",
        "verified": True,
        "roadway": {
            "url": "https://services.arcgis.com/hOpd7wfnKm16p9D9/arcgis/rest/services/HPMS2026/FeatureServer/0/query",
            "route_field": "route_id",
            "name_field": "RoadLabel",
            "lanes_field": "ThroughLaneCount",
            "class_field": "FSystem",
            "out_fields": "route_id,RoadLabel,ThroughLaneCount,FSystem",
            "verified": True,
        },
    },
    "ND": {
        # Single NDGISHUB layer serves as both AADT source and roadway
        # inventory. NDDOT's own gis.dot.nd.gov blocks fetching, so this is
        # an ArcGIS-Online-hosted layer under the NDGISHDP-DOT org instead.
        # No street-name field present.
        "label": "NDDOT",
        "url": "https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/NDGISHUB_County_Roads/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTEID",
        "out_fields": "AADT,AADT_YR,ROUTEID,RTE_ID,FUNCTIONAL_CLASS,HPMS_THROUGH_LANES",
        "verified": True,
        "roadway": {
            "url": "https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/NDGISHUB_County_Roads/FeatureServer/0/query",
            "route_field": "ROUTEID",
            "lanes_field": "HPMS_THROUGH_LANES",
            "class_field": "FUNCTIONAL_CLASS",
            "out_fields": "ROUTEID,RTE_ID,HPMS_THROUGH_LANES,FUNCTIONAL_CLASS",
            "verified": True,
        },
    },
    "OK": {
        # Single ODOT layer serves as both AADT source and roadway
        # inventory. No speed-limit field present. ROUTENAME and LANECOUNT
        # were never real field names on this layer -- confirmed live
        # 2026-09-23 the actual fields are STREETNAME and NOOFLANES.
        "label": "ODOT",
        "url": "https://services6.arcgis.com/RBtoEUQ2lmN0K3GY/arcgis/rest/services/Roadways/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "where": "AADT IS NOT NULL",
        "out_fields": "AADT,AADTYEAR,ROUTE_ID,STREETNAME,NOOFLANES,FUNCTIONALCLASS",
        "verified": True,
        "roadway": {
            "url": "https://services6.arcgis.com/RBtoEUQ2lmN0K3GY/arcgis/rest/services/Roadways/FeatureServer/0/query",
            "route_field": "ROUTE_ID",
            "name_field": "STREETNAME",
            "lanes_field": "NOOFLANES",
            "class_field": "FUNCTIONALCLASS",
            "out_fields": "ROUTE_ID,STREETNAME,NOOFLANES,FUNCTIONALCLASS",
            "verified": True,
        },
    },
    "SC": {
        "label": "SCDOT",
        "url": "https://services1.arcgis.com/VaY7cY9pvUYUP1Lf/arcgis/rest/services/2021_Statewide_Traffic_Lines/FeatureServer/0/query",
        "aadt_fields": ["Factored_A"],
        "route_field": "RouteLRS",
        "out_fields": "Factored_A,Factored_1,RouteLRS,Route_Type,Route_Numb,County",
        "verified": True,
        # No speed-limit or functional-classification layer found for SC.
        "roadway": {
            "url": "https://services1.arcgis.com/VaY7cY9pvUYUP1Lf/arcgis/rest/services/All_Roads_Lanes/FeatureServer/0/query",
            "route_field": "RouteLRS",
            "lanes_field": "Total_Lane",
            "out_fields": "RouteLRS,Route_Type,Route_Num,Total_Lane,Right_Lane,Left_Lanes",
            "verified": True,
        },
    },
    "SD": {
        "label": "SDDOT",
        "url": "https://sdgis.sd.gov/dot/rest/services/TIM/HR49_GisADT/FeatureServer/0/query",
        "aadt_fields": ["Adt01Nbr"],
        "route_field": "HighwayNbr",
        "out_fields": "Adt01Nbr,Adt02Nbr,HighwayNbr,BeginMrmNbr,EndMrmNbr,TruckPercentNbr",
        "verified": True,
        # No speed-limit field on the state-highway display layer; a
        # local-roads layer has lanes/class but only for non-state roads.
        "roadway": {
            "url": "https://sdgis.sd.gov/dot/rest/services/TIM/DOT_StateHighways_display/MapServer/0/query",
            "route_field": "HighwayNbr",
            "name_field": "HwyName",
            "class_field": "HighwayClass",
            "out_fields": "HighwayNbr,HwyName,HighwayClass,Direction",
            "verified": True,
        },
    },
    "TN": {
        "label": "TDOT",
        "url": "https://services2.arcgis.com/nf3p7v7Zy4fTOh6M/arcgis/rest/services/Traffic_Lines/FeatureServer/0/query",
        "aadt_fields": ["AADT"],
        "route_field": "ROUTE_ID",
        "out_fields": "AADT,AADTYEAR,ROUTE_ID,FUNCTIONAL_CLASS",
        "verified": True,
        # Road_Geometrics has no functional-class field.
        "roadway": {
            "url": "https://services2.arcgis.com/nf3p7v7Zy4fTOh6M/arcgis/rest/services/Road_Geometrics/FeatureServer/0/query",
            "route_field": "NBR_RTE",
            "lanes_field": "THRU_LANES",
            "speed_field": "SPD_LMT",
            "out_fields": "NBR_RTE,NBR_TENN_CNTY,SPD_LMT,NBR_LANES,THRU_LANES",
            "verified": True,
        },
    },
    "UT": {
        "label": "UDOT",
        "url": "https://services.arcgis.com/pA2nEVnB6tquxgOW/arcgis/rest/services/AADT2024_Unrounded/FeatureServer/3/query",
        "aadt_fields": ["AADT2024"],
        "route_field": "RouteID",
        "out_fields": "RouteID,Station,BeginPoint,EndPoint,DESC_,AADT2024",
        "verified": True,
        # UDOT's Statewide Speed Limit layer conveniently bundles route,
        # name and speed in one layer.
        "roadway": {
            "url": "https://services.arcgis.com/pA2nEVnB6tquxgOW/arcgis/rest/services/Statewide_Speed_Limit/FeatureServer/0/query",
            "route_field": "Route",
            "name_field": "Name",
            "speed_field": "Speed_Limit",
            "out_fields": "Route,Name,Direction,Type,Speed_Limit",
            "verified": True,
        },
    },
    "WI": {
        # dotmaps.wi.gov is confirmed genuinely dead on a live query (this
        # was the entry flagged before as "only verified via metadata.xml,
        # never a live query" -- that caution turned out to be warranted).
        # Switched to WisDOT's own ArcGIS Online-hosted TCMap Traffic Count
        # Sites layer, confirmed live 2026-09-23. No dedicated route-number
        # field on this layer -- LOC_DESC embeds the route in free text
        # (e.g. "STH 13 SOUTH OF..."), which is what route_field points at.
        "label": "WisDOT",
        "url": "https://services5.arcgis.com/0pgGLzT0Nh7FVjon/arcgis/rest/services/TCMap_Traffic_Count_Sites/FeatureServer/0/query",
        "aadt_fields": ["CURR_AADT"],
        "route_field": "LOC_DESC",
        "where": "CURR_AADT IS NOT NULL",
        "out_fields": "CURR_AADT,CURR_AADT_YR,SITE_ID,LOC_DESC,CNTY_NM,FNCT_CLS_DESC",
        "verified": True,
        "roadway": {
            "url": "https://services5.arcgis.com/0pgGLzT0Nh7FVjon/arcgis/rest/services/FFCL_gdb/FeatureServer/3/query",
            "route_field": "HWYNUM",
            "class_field": "FC_CD",
            "out_fields": "HWYNUM,HWYTYPE,HWYDIR,FC_CD,FC_DESC",
            "verified": True,
        },
    },
    "WY": {
        "label": "WYDOT",
        # WYDOT's "Traffic Counts" is a group layer split into 5 sibling
        # sublayers by AADT range (ids 33-37), each with identical schema
        # but a hidden range filter. This uses layer 33 (AADT > 20,000)
        # only -- for full statewide coverage, query ids 33-37 together;
        # no unfiltered merged endpoint exists publicly.
        "url": "https://gisservices.wyoroad.info/arcgis/rest/services/ITSM/ITSM_Data_Layers/MapServer/33/query",
        "aadt_fields": ["aadt", "truck_aadt"],
        "route_field": "route",
        "out_fields": "route,common_route_name,aadt,truck_aadt,eff_year,from_rm,to_rm",
        "verified": True,
        "roadway": {
            "url": "https://services2.arcgis.com/WI04Bd6haCzitbuQ/arcgis/rest/services/FClass2025_gdb/FeatureServer/0/query",
            "route_field": "RouteId",
            "class_field": "FunctionalClass",
            "out_fields": "RouteId,BeginPoint,EndPoint,FunctionalClassCode,FunctionalClass",
            "verified": True,
        },
    },
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