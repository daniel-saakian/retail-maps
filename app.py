from flask import Flask, request,jsonify
import majorretail as mr
import time

app = Flask(__name__)
@app.route("/health", methods = ["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/analyze", methods = ["POST"])
def analyze():
    data = request.json or {}
    city = data.get("city", "").strip()
    radius = float(data.get("radius", mr.plaza_radius_mi))
    min_tenants = int(data.get("min_tenants", mr.min_other_tenants))
    search_km = float(data.get("search_km", mr.search_radius_km))

    if not city:
        return jsonify({"status": "error", "message": "city is required"}), 400
    
    try:
        lat, lng, display = mr.geocode_city(city)
        time.sleep(1)

        store_elements = mr.run_overpass(mr.build_store_query(lat,lng,search_km))

        try:
            mall_elements = mr.run_overpass(mr.build_mall_query(lat,lng,search_km))
        except RuntimeError:
            mall_elements = []
        stores = mr.extract_stores(store_elements)
        n_anchors = sum(1 for s in stores if s.is_anchor_store)
        if n_anchors == 0:
            return jsonify({"status": "error", "message": f"No anchor stores found near {city}"}), 404
        
        plazas = mr.build_plazas(stores, radius, min_tenants)
        mr.attach_mall_names(plazas, mall_elements)
        plazas = mr.deduplicate_plaza_stores(plazas)
        plazas = mr.merge_same_name_plazas(plazas)
        mr.attach_counties(plazas)


        slug = display.lower().replace(", ", "-").replace(" ", "-")
        map_path = mr.generate_map(plazas,display, radius, stores, output_path=f"/tmp/{slug}.html")
        map_url = mr.upload_map_to_github(map_path)

        state = city.split(",")[1].strip() if "," in city else "-"
        sorted_plazas = sorted(
            plazas,
            key=lambda p: (
                p.county.lower() if p.county and p.county != "-" else "zzz",
                p.display_city.lower() if p.display_city and p.display_city != "-" else "zzz",
            )
        )


        result = [
            {
                "name": p.label,
                "state": state,
                "county": p.county,
                "city": p.display_city,
                "address": p.display_address,
                "num_anchors": len(p.anchors),
                "anchor_names": p.anchor_names,
                "num_tenants": len(p.tenants), 
                "tenants": p.tenant_names,
            }
            for p in sorted_plazas
        ]
        return jsonify({
            "status": "ok",
            "city": display,
            "map_url": map_url,
            "plazas": result
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port = port)