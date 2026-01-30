import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
import requests

app = Flask(__name__)

# Load config
API_KEY = os.environ.get("OPTIMOROUTE_API_KEY", "3076b5802ed7da0089dc4306e185913dLYghmIacS1A")
BASE_URL = "https://api.optimoroute.com/v1"

def optimoroute_request(method, endpoint, data=None):
    """Make API request to Optimoroute."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, headers=headers, json=data, timeout=30)
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/")
def index():
    """Dashboard."""
    routes_res, _ = optimoroute_request("GET", "/routes")
    drivers_res, _ = optimoroute_request("GET", "/drivers")
    orders_res, _ = optimoroute_request("GET", "/orders")
    
    return render_template("index.html",
                         routes=routes_res if isinstance(routes_res, list) else [],
                         drivers=drivers_res if isinstance(drivers_res, list) else [],
                         orders=orders_res if isinstance(orders_res, list) else [],
                         api_key=API_KEY[:20] + "...")


@app.route("/routes")
def routes():
    """List all routes."""
    res, _ = optimoroute_request("GET", "/routes")
    return render_template("routes.html", routes=res if isinstance(res, list) else [])


@app.route("/routes/<route_id>")
def route_detail(route_id):
    """Route details."""
    res, status = optimoroute_request("GET", f"/routes/{route_id}")
    if status == 200:
        return render_template("route_detail.html", route=res)
    return render_template("error.html", error=res)


@app.route("/drivers")
def drivers():
    """List all drivers."""
    res, _ = optimoroute_request("GET", "/drivers")
    return render_template("drivers.html", drivers=res if isinstance(res, list) else [])


@app.route("/orders")
def orders():
    """List all orders."""
    res, _ = optimoroute_request("GET", "/orders")
    return render_template("orders.html", orders=res if isinstance(res, list) else [])


@app.route("/orders/create", methods=["GET", "POST"])
def create_order():
    """Create new order."""
    if request.method == "POST":
        order_data = {
            "address": request.form.get("address"),
            "customer_name": request.form.get("customer_name"),
            "customer_phone": request.form.get("customer_phone"),
            "latitude": request.form.get("latitude"),
            "longitude": request.form.get("longitude"),
            "notes": request.form.get("notes"),
            "pickup_time": request.form.get("pickup_time"),
            "delivery_time": request.form.get("delivery_time"),
        }
        res, status = optimoroute_request("POST", "/orders", data=order_data)
        if status in [200, 201]:
            return redirect(url_for("orders"))
        return render_template("error.html", error=res)
    return render_template("create_order.html")


@app.route("/api/status")
def api_status():
    """Check API connectivity."""
    res, status = optimoroute_request("GET", "/routes")
    return jsonify({"status": "connected" if status == 200 else "error", "response": res})


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", error="Server error"), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
