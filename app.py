from flask import Flask, request,jsonify
import majorretail as mr

app = Flask(__name__)
@app.route("/health", methods = ["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/analyze", methods = ["POST"])
def analyze():
    data = request.json or {}
    city = data.get("city", "").strip()
    radius = float(data.get("radius", mr.cluster_radius_mi))
    min_anchors = int(data.get("min_anchors", mr.min_anchors_per_cluster))
    search_km = float(data.get("search_km", mr.search_radius_km))

    if not city:
        return jsonify({"status": "error", "message": "city is required"}), 400
    
    try:
        lat, lng, display = mr.geocode_city(city)
        store_elements = mr.run_overpass(mr.build_store_query(lat,lng,search_km))

        try:
            mall_elements = mr.run_overpass(mr.build_store_query(lat,lng,search_km))
        except RuntimeError:
            mall_elements = []
        stores = mr.extract_stores(store_elements)
        clusters = mr.cluster_stores(stores, radius,min_anchors)
        mr.attach_mall_names(clusters, mall_elements)
        clusters = mr.deduplicate_within_clusters(clusters)
        mr.absorb_nearby_stores(clusters, stores, radius)
        clusters = mr.merge_same_name_clusters(clusters)
        mr.attach_counties(clusters)

        map_path = mr.generate_map(clusters,display, radius, stores)
        map_url = mr.upload_map_to_github(map_path)

        state = city.split(",")[1].strip() if "," in city else "-"
        sorted_clusters = sorted(
            clusters,
            key=lambda c: (
                c.county.lower() if c.county and c.county != "-" else "zzz",
                c.display_city.lower() if c.display_city and c.display_city != "-" else "zzz",
            )
        )


        result = [
            {
                "name": c.label,
                "state": state,
                "county": c.county,
                "city": c.display_city,
                "address": c.display_address,
                "anchors": len(c.stores),
                "stores": ", ".join(s.name for s in c.stores),
            }
            for c in sorted_clusters
        ]
        return jsonify({
            "status": "ok",
            "city": display,
            "map_url": map_url,
            "clusters": result
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port = 8080)