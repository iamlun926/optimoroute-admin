import os
import json
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests

app = Flask(__name__)
app.secret_key = 'optimoroute-secret-key'

# Load config
API_KEY = os.environ.get("OPTIMOROUTE_API_KEY", "3076b5802ed7da0089dc4306e185913dLYghmIacS1A")
BASE_URL = os.environ.get("OPTIMOROUTE_BASE_URL", "https://api.optimoroute.com/v1")

# Configurable endpoints
ENDPOINTS = {
    "routes": os.environ.get("OPTIMOROUTE_ROUTES_ENDPOINT", "/routes"),
    "drivers": os.environ.get("OPTIMOROUTE_DRIVERS_ENDPOINT", "/drivers"),
    "orders": os.environ.get("OPTIMOROUTE_ORDERS_ENDPOINT", "/orders"),
    "create_order": os.environ.get("OPTIMOROUTE_CREATE_ENDPOINT", "/orders"),
}


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
    except requests.exceptions.ConnectionError:
        return {"error": f"Cannot connect to {url}. Check BASE_URL configuration."}, 500
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/")
def index():
    """Dashboard."""
    routes_res, _ = optimoroute_request("GET", ENDPOINTS["routes"])
    drivers_res, _ = optimoroute_request("GET", ENDPOINTS["drivers"])
    orders_res, _ = optimoroute_request("GET", ENDPOINTS["orders"])
    
    return render_template("index.html",
                         routes=routes_res if isinstance(routes_res, list) else [],
                         drivers=drivers_res if isinstance(drivers_res, list) else [],
                         orders=orders_res if isinstance(orders_res, list) else [],
                         api_key=API_KEY[:20] + "...",
                         base_url=BASE_URL)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Configure API endpoints."""
    config = {
        "base_url": BASE_URL,
        "routes_endpoint": ENDPOINTS["routes"],
        "drivers_endpoint": ENDPOINTS["drivers"],
        "orders_endpoint": ENDPOINTS["orders"],
        "create_endpoint": ENDPOINTS["create_order"],
    }
    
    if request.method == "POST":
        config.update({
            "base_url": request.form.get("base_url"),
            "routes_endpoint": request.form.get("routes_endpoint"),
            "drivers_endpoint": request.form.get("drivers_endpoint"),
            "orders_endpoint": request.form.get("orders_endpoint"),
            "create_endpoint": request.form.get("create_endpoint"),
        })
        flash("Settings updated! Test with the API Status page.", "success")
        return redirect(url_for("settings"))
    
    return render_template("settings.html", config=config)


@app.route("/test-api", methods=["GET", "POST"])
def test_api():
    """Test API connectivity."""
    test_result = None
    if request.method == "POST":
        endpoint = request.form.get("endpoint", "/orders")
        method = request.form.get("method", "GET")
        
        if method == "GET":
            res, status = optimoroute_request("GET", endpoint)
        elif method == "POST":
            try:
                data = json.loads(request.form.get("data", "{}"))
                res, status = optimoroute_request("POST", endpoint, data=data)
            except json.JSONDecodeError:
                res, status = {"error": "Invalid JSON data"}, 400
        else:
            res, status = {"error": "Unsupported method"}, 400
            
        test_result = {"response": res, "status": status, "endpoint": endpoint, "method": method}
    
    return render_template("test_api.html", result=test_result)


@app.route("/routes")
def routes():
    """List all routes."""
    res, status = optimoroute_request("GET", ENDPOINTS["routes"])
    return render_template("routes.html", routes=res if isinstance(res, list) else [], error=res if status != 200 else None)


@app.route("/routes/<route_id>")
def route_detail(route_id):
    """Route details."""
    res, status = optimoroute_request("GET", f"{ENDPOINTS['routes']}/{route_id}")
    if status == 200:
        return render_template("route_detail.html", route=res)
    return render_template("error.html", error=res)


@app.route("/drivers")
def drivers():
    """List all drivers."""
    res, status = optimoroute_request("GET", ENDPOINTS["drivers"])
    return render_template("drivers.html", drivers=res if isinstance(res, list) else [], error=res if status != 200 else None)


@app.route("/orders")
def orders():
    """List all orders."""
    res, status = optimoroute_request("GET", ENDPOINTS["orders"])
    return render_template("orders.html", orders=res if isinstance(res, list) else [], error=res if status != 200 else None)


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
        # Remove empty fields
        order_data = {k: v for k, v in order_data.items() if v}
        
        res, status = optimoroute_request("POST", ENDPOINTS["create_order"], data=order_data)
        if status in [200, 201]:
            flash("Order created successfully!", "success")
            return redirect(url_for("orders"))
        return render_template("error.html", error=res)
    return render_template("create_order.html")


@app.route("/batch-upload", methods=["GET", "POST"])
def batch_upload():
    """Batch upload orders from XLSX file."""
    upload_result = None
    if request.method == "POST":
        if 'file' not in request.files:
            return render_template("error.html", error="No file uploaded")
        
        file = request.files['file']
        if file.filename == '':
            return render_template("error.html", error="No file selected")
        
        if file and file.filename.endswith(('.xlsx', '.xls')):
            try:
                df = pd.read_excel(file)
                orders_data = df.to_dict('records')
                
                # Preview first 5 orders
                preview = orders_data[:5]
                upload_result = {
                    "total": len(orders_data),
                    "preview": preview,
                    "columns": list(df.columns),
                }
                
                # Actually upload if confirmed
                if request.form.get("confirm") == "true":
                    success_count = 0
                    errors = []
                    for i, order in enumerate(orders_data):
                        try:
                            res, status = optimoroute_request("POST", ENDPOINTS["create_order"], data=order)
                            if status in [200, 201]:
                                success_count += 1
                            else:
                                errors.append(f"Row {i+1}: {res}")
                        except Exception as e:
                            errors.append(f"Row {i+1}: {str(e)}")
                    
                    upload_result["success_count"] = success_count
                    upload_result["errors"] = errors[:10]  # Show first 10 errors
                    upload_result["confirmed"] = True
                    
            except Exception as e:
                return render_template("error.html", error=f"Error reading file: {str(e)}")
        else:
            return render_template("error.html", error="Please upload an XLSX file")
    
    return render_template("batch_upload.html", result=upload_result)


@app.route("/api/status")
def api_status():
    """Check API connectivity."""
    res, status = optimoroute_request("GET", ENDPOINTS["routes"])
    return jsonify({
        "status": "connected" if status == 200 else "error",
        "api_key_configured": bool(API_KEY),
        "base_url": BASE_URL,
        "endpoints": ENDPOINTS,
        "response": res,
        "http_status": status
    })


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", error="Server error"), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
