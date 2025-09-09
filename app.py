from flask import Flask, request, render_template
import requests
import polyline
import json

app = Flask(__name__)

GRAPHOPPER_API_KEY = "0429560f-8e31-4924-9cd8-a772c1bc0b0c"
GRAPHOPPER_TIMEOUT = 15
UNSPLASH_ACCESS_KEY = "YOUR_UNSPLASH_ACCESS_KEY"

def geocode_place(place_prompt):
    """
    Geocode a place using GraphHopper Geocoding API with a simple prompt.
    If the first search fails, try appending ', India' to improve results for local places.
    """
    for query in [place_prompt, place_prompt + ", India"]:
        url = "https://graphhopper.com/api/1/geocode"
        params = {
            "q": query,
            "locale": "en",
            "limit": 1,
            "key": GRAPHOPPER_API_KEY
        }
        try:
            resp = requests.get(url, params=params, timeout=GRAPHOPPER_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if "hits" in data and len(data["hits"]) > 0:
                p = data["hits"][0]["point"]
                return float(p["lat"]), float(p["lng"])
        except Exception:
            continue
    return None

def get_routes(start, end, vehicle="car"):
    url = "https://graphhopper.com/api/1/route"
    params = {
        "point": [f"{start[0]},{start[1]}", f"{end[0]},{end[1]}"],
        "vehicle": vehicle,
        "locale": "en",
        "points_encoded": "true",
        "algorithm": "alternative_route",
        "max_paths": 3,
        "key": GRAPHOPPER_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=GRAPHOPPER_TIMEOUT)
    resp.raise_for_status()
    return resp.json()

def get_place_image(place_prompt):
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": place_prompt,
        "client_id": UNSPLASH_ACCESS_KEY,
        "orientation": "landscape",
        "per_page": 1
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            return data["results"][0]["urls"]["regular"]
    except Exception:
        pass
    return None

@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "routes_json": None,
        "start_place": "",
        "end_place": "",
        "vehicle": "car",
        "error": None,
        "start_img": None,
        "end_img": None,
    }

    if request.method == "POST":
        start_place = request.form.get("start", "").strip()
        end_place = request.form.get("end", "").strip()
        vehicle = request.form.get("vehicle", "car")

        context["start_place"] = start_place
        context["end_place"] = end_place
        context["vehicle"] = vehicle

        if not start_place or not end_place:
            context["error"] = "Please enter both start and end locations (city, landmark, address, etc)."
            return render_template("index.html", **context)

        try:
            start_coords = geocode_place(start_place)
            end_coords = geocode_place(end_place)

            context["start_img"] = get_place_image(start_place)
            context["end_img"] = get_place_image(end_place)

            if not start_coords or not end_coords:
                context["error"] = (
                    "Could not geocode start or end place.<br>"
                    "Tip: Use well-known city names, landmarks, or append the city/country. "
                    "Example: 'KITS Institute, Vinjanampadu, Guntur' or just 'Vinjanampadu, India'"
                )
                return render_template("index.html", **context)

            route_data = get_routes(start_coords, end_coords, vehicle)

            if "paths" not in route_data or len(route_data["paths"]) == 0:
                context["error"] = "No route found."
                return render_template("index.html", **context)

            routes = []
            colors = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#d62728"]

            for idx, path in enumerate(route_data["paths"]):
                encoded = path.get("points")
                coords = polyline.decode(encoded)
                coords_latlon = [[lat, lon] for lat, lon in coords]
                distance_km = round(path.get("distance", 0) / 1000.0, 2)
                time_hours = round(path.get("time", 0) / 1000.0 / 3600.0, 2)
                routes.append({
                    "id": idx + 1,
                    "coords": coords_latlon,
                    "distance_km": distance_km,
                    "time_hours": time_hours,
                    "color": colors[idx % len(colors)],
                    "name": f"Route {idx+1}"
                })

            routes_json = json.dumps({
                "routes": routes,
                "start": {"lat": start_coords[0], "lon": start_coords[1]},
                "end": {"lat": end_coords[0], "lon": end_coords[1]},
                "vehicle": vehicle
            })

            context["routes_json"] = routes_json

        except requests.exceptions.RequestException as e:
            context["error"] = f"Network/API error: {e}"
        except Exception as e:
            context["error"] = f"Unexpected error: {e}"

    return render_template("index.html", **context)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)