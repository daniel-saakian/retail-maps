from flask import Flask, request, jsonify
import majorretail as mr
import threading
import time
import os

app = Flask(__name__)

progress = {}

def run_analysis(city, radius, min_tenants, search_km, slug):
    try:
        # ── Check Supabase cache by city name FIRST — no Overpass needed ──
        progress[slug] = {"step": "1/5", "message": "Checking cache..."}
        sb = mr.get_supabase()
        if sb:
            try:
                from datetime import datetime, timezone, timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

                runs = (sb.table("city_runs")
                          .select("*")
                          .ilike("city", f"%{city.split(',')[0].strip()}%")
                          .gte("ran_at", cutoff)
                          .order("ran_at", desc=True)
                          .limit(1)
                          .execute())

                if runs.data:
                    run = runs.data[0]
                    cached = (sb.table("plazas")
                                .select("*")
                                .eq("city_run_id", run["id"])
                                .execute())
                    if cached.data:
                        print(f"  [cache] HIT — returning early, {len(cached.data)} plazas")
                        progress[slug] = {
                            "step":    "done",
                            "message": f"Found {len(cached.data)} plazas (from cache)",
                            "result": {
                                "status":  "ok",
                                "city":    run["display"],
                                "map_url": run["map_url"],
                                "plazas":  cached.data,
                            }
                        }
                        return
            except Exception as e:
                print(f"  [cache] lookup failed: {e}")

        # ── Cache miss — now do Overpass calls ──────────────────────────────
        progress[slug] = {"step": "1/5", "message": f"Geocoding {city}..."}
        time.sleep(2)
        lat, lng, display = mr.geocode_city(city)
        time.sleep(1)

        progress[slug] = {"step": "2/5", "message": "Querying OpenStreetMap for stores..."}
        store_elements = mr.run_overpass(mr.build_store_query(lat, lng, search_km))

        time.sleep(2)

        progress[slug] = {"step": "3/5", "message": "Querying mall names..."}
        try:
            mall_elements = mr.run_overpass(mr.build_mall_query(lat, lng, search_km))
        except RuntimeError:
            mall_elements = []

        progress[slug] = {"step": "4/5", "message": "Building plazas and looking up counties..."}
        stores = mr.extract_stores(store_elements)
        n_anchors = sum(1 for s in stores if s.is_anchor_store)
        if n_anchors == 0:
            progress[slug] = {"step": "error", "message": f"No anchor stores found near {city}"}
            return

        plazas = mr.build_plazas(stores, radius, min_tenants)
        mr.attach_mall_names(plazas, mall_elements)
        plazas = mr.deduplicate_plaza_stores(plazas)
        plazas = mr.merge_same_name_plazas(plazas)
        mr.attach_counties(plazas)

        progress[slug] = {"step": "5/5", "message": "Generating and uploading map..."}
        map_path = mr.generate_map(plazas, display, radius, stores,
                                   output_path=f"/tmp/{slug}.html")
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
                "name":         p.label,
                "state":        state,
                "county":       p.county,
                "city":         p.display_city,
                "address":      p.display_address,
                "num_anchors":  len(p.anchors),
                "anchor_names": p.anchor_names,
                "num_tenants":  len(p.tenants),
                "tenant_names": p.tenant_names,
            }
            for p in sorted_plazas
        ]

        mr.save_run_to_cache(display, lat, lng, search_km, map_url, plazas, state)

        progress[slug] = {
            "step":    "done",
            "message": f"Found {len(plazas)} plazas",
            "result": {
                "status":  "ok",
                "city":    display,
                "map_url": map_url,
                "plazas":  result,
            }
        }

    except Exception as e:
        progress[slug] = {"step": "error", "message": str(e)}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/analyze", methods=["POST"])
def analyze():
    data       = request.json or {}
    city       = data.get("city", "").strip()
    radius     = float(data.get("radius",      mr.plaza_radius_mi))
    min_ten    = int(data.get("min_tenants",   mr.min_other_tenants))
    search_km  = float(data.get("search_km",   mr.search_radius_km))

    if not city:
        return jsonify({"status": "error", "message": "city is required"}), 400

    slug = city.lower().replace(", ", "-").replace(" ", "-")
    progress[slug] = {"step": "starting", "message": "Starting analysis..."}

    t = threading.Thread(target=run_analysis,
                         args=(city, radius, min_ten, search_km, slug))
    t.daemon = True
    t.start()

    return jsonify({"status": "started", "slug": slug})


@app.route("/status/<slug>", methods=["GET"])
def status(slug):
    return jsonify(progress.get(slug, {"step": "unknown", "message": "Not started"}))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)