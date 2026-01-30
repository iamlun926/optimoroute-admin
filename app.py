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

# Optimoroute API endpoints (from official docs)
ENDPOINTS = {
    "create_order": "/create_order",
    "create_or_update_orders": "/create_or_update_orders",
    "get_orders": "/get_orders",
    "delete_order": "/delete_order",
    "delete_orders": "/delete_orders",
    "delete_all_orders": "/delete_all_orders",
    "get_routes": "/get_routes",
    "get_scheduling_info": "/get_scheduling_info",
}


def optimoroute_request(method, endpoint, data=None, params=None):
    """Make API request to Optimoroute."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}{endpoint}"
    
    # Add API key as query param for GET requests
    if method == "GET" and params:
        params["key"] = API_KEY
    elif method in ["POST", "PUT", "DELETE"]:
        params = {"key": API_KEY}
    
    try:
        response = requests.request(method, url, headers=headers, json=data, params=params, timeout=30)
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        return {"error": f"Cannot connect to {url}"}, 500
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/")
def index():
    """Dashboard."""
    return render_template("index.html",
                         api_key=API_KEY[:20] + "...",
                         base_url=BASE_URL,
                         endpoints=ENDPOINTS)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Configure API settings."""
    config = {
        "api_key_masked": API_KEY[:10] + "...",
        "base_url": BASE_URL,
    }
    
    if request.method == "POST":
        # Update API key
        if request.form.get("api_key"):
            os.environ["OPTIMOROUTE_API_KEY"] = request.form.get("api_key")
            config["api_key_masked"] = "Updated"
            flash("API key updated!", "success")
        
        # Update base URL
        if request.form.get("base_url"):
            os.environ["OPTIMOROUTE_BASE_URL"] = request.form.get("base_url")
            config["base_url"] = request.form.get("base_url")
            flash("Base URL updated!", "success")
        
        return redirect(url_for("settings"))
    
    return render_template("settings.html", config=config)


@app.route("/test-api", methods=["GET", "POST"])
def test_api():
    """Test API connectivity."""
    test_result = None
    if request.method == "POST":
        endpoint = request.form.get("endpoint", "/get_routes")
        method = request.form.get("method", "GET")
        date = request.form.get("date", "")
        
        params = {}
        if date and endpoint == "/get_routes":
            params["date"] = date
        
        if method == "GET":
            res, status = optimoroute_request("GET", endpoint, params=params)
        elif method == "POST":
            try:
                data = json.loads(request.form.get("data", "{}"))
                res, status = optimoroute_request("POST", endpoint, data=data)
            except json.JSONDecodeError:
                res, status = {"error": "Invalid JSON data"}, 400
        else:
            res, status = {"error": "Unsupported method"}, 400
            
        test_result = {"response": res, "status": status, "endpoint": endpoint, "method": method}
    
    return render_template("test_api.html", result=test_result, endpoints=ENDPOINTS)


@app.route("/routes")
def routes():
    """List routes for a date."""
    date = request.args.get("date")
    if not date:
        date = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    res, status = optimoroute_request("GET", ENDPOINTS["get_routes"], params={"date": date})
    
    if isinstance(res, dict) and res.get("success"):
        routes_data = res.get("routes", [])
    else:
        routes_data = []
        flash(f"Error fetching routes: {res.get('message', 'Unknown error')}", "error")
    
    return render_template("routes.html", routes=routes_data, date=date, endpoints=ENDPOINTS)


@app.route("/routes/<order_id>")
def route_detail(order_id):
    """Get scheduling info for an order."""
    res, status = optimoroute_request("GET", ENDPOINTS["get_scheduling_info"], params={"id": order_id})
    
    if status == 200:
        return render_template("route_detail.html", scheduling=res)
    return render_template("error.html", error=res)


@app.route("/orders")
def orders():
    """List orders."""
    # Try get_orders endpoint
    res, status = optimoroute_request("GET", ENDPOINTS["get_orders"], params={"orderNo": ""})
    
    orders_data = []
    if isinstance(res, dict) and res.get("success"):
        for o in res.get("orders", []):
            if o.get("success") and o.get("data"):
                orders_data.append(o["data"])
    
    return render_template("orders.html", orders=orders_data, endpoints=ENDPOINTS)


@app.route("/orders/create", methods=["GET", "POST"])
def create_order():
    """Create or update a single order."""
    if request.method == "POST":
        # Build order data from form
        location_data = {
            "address": request.form.get("address", ""),
            "locationName": request.form.get("location_name", ""),
            "latitude": request.form.get("latitude") or None,
            "longitude": request.form.get("longitude") or None,
        }
        # Remove empty location fields
        location_data = {k: v for k, v in location_data.items() if v}
        
        order_data = {
            "operation": request.form.get("operation", "CREATE"),
            "orderNo": request.form.get("order_no", ""),
            "type": request.form.get("order_type", "D"),
            "date": request.form.get("date", ""),
            "location": location_data,
            "duration": int(request.form.get("duration", 15)),
            "notes": request.form.get("notes", ""),
            "phone": request.form.get("phone", ""),
            "email": request.form.get("email", ""),
        }
        
        # Add time window if provided
        tw_from = request.form.get("tw_from", "")
        tw_to = request.form.get("tw_to", "")
        if tw_from and tw_to:
            order_data["timeWindows"] = [{"twFrom": tw_from, "twTo": tw_to}]
        
        # Add load if provided
        load1 = request.form.get("load1", "")
        if load1:
            order_data["load1"] = float(load1)
        
        # Remove empty fields
        order_data = {k: v for k, v in order_data.items() if v and v != {}}
        
        res, status = optimoroute_request("POST", ENDPOINTS["create_order"], data=order_data)
        
        if isinstance(res, dict) and res.get("success"):
            flash(f"Order created/updated successfully! ID: {res.get('id', 'N/A')}", "success")
            return redirect(url_for("orders"))
        else:
            return render_template("error.html", error=res.get("message", json.dumps(res)))
    
    return render_template("create_order.html")


@app.route("/orders/batch-create", methods=["GET", "POST"])
def batch_create_orders():
    """Create or update multiple orders."""
    if request.method == "POST":
        if 'file' not in request.files:
            return render_template("error.html", error="No file uploaded")
        
        file = request.files['file']
        if file.filename == '':
            return render_template("error.html", error="No file selected")
        
        if file and file.filename.endswith(('.xlsx', '.xls')):
            try:
                df = pd.read_excel(file)
                df = df.fillna('')
                
                orders = []
                for _, row in df.iterrows():
                    order = {"operation": "SYNC"}
                    
                    # Map Excel columns to API fields
                    field_mapping = {
                        'orderNo': 'order_no',
                        'type': 'order_type',
                        'date': 'date',
                        'address': 'address',
                        'locationName': 'location_name',
                        'latitude': 'latitude',
                        'longitude': 'longitude',
                        'duration': 'duration',
                        'notes': 'notes',
                        'phone': 'phone',
                        'email': 'email',
                        'twFrom': 'tw_from',
                        'twTo': 'tw_to',
                        'load1': 'load1',
                        'priority': 'priority',
                    }
                    
                    for api_field, excel_field in field_mapping.items():
                        if excel_field in row and row[excel_field]:
                            if api_field in ['latitude', 'longitude', 'duration', 'load1']:
                                order[api_field] = float(row[excel_field]) if row[excel_field] else None
                            else:
                                order[api_field] = row[excel_field]
                    
                    # Build location object
                    if 'address' in row or 'latitude' in row:
                        location = {}
                        if row.get('address'):
                            location['address'] = row['address']
                        if row.get('location_name'):
                            location['locationName'] = row['location_name']
                        if row.get('latitude'):
                            location['latitude'] = float(row['latitude'])
                        if row.get('longitude'):
                            location['longitude'] = float(row['longitude'])
                        if location:
                            order['location'] = location
                    
                    # Add time window
                    if row.get('tw_from') and row.get('tw_to'):
                        order['timeWindows'] = [{"twFrom": str(row['tw_from']), "twTo": str(row['tw_to'])}]
                    
                    orders.append(order)
                
                # Send batch request
                res, status = optimoroute_request("POST", ENDPOINTS["create_or_update_orders"], data={"orders": orders})
                
                if isinstance(res, dict):
                    success_count = sum(1 for o in res.get("orders", []) if o.get("success"))
                    errors = [o for o in res.get("orders", []) if not o.get("success")]
                    
                    result = {
                        "total": len(orders),
                        "success_count": success_count,
                        "errors": errors[:10],
                    }
                    return render_template("batch_result.html", result=result)
                else:
                    return render_template("error.html", error=str(res))
                    
            except Exception as e:
                return render_template("error.html", error=f"Error processing file: {str(e)}")
        else:
            return render_template("error.html", error="Please upload an XLSX file")
    
    return render_template("batch_create.html")


@app.route("/orders/delete", methods=["GET", "POST"])
def delete_orders():
    """Delete orders."""
    delete_result = None
    if request.method == "POST":
        order_ids = request.form.get("order_ids", "").strip()
        if order_ids:
            order_nos = [o.strip() for o in order_ids.split(",") if o.strip()]
            
            orders = [{"orderNo": no} for no in order_nos]
            res, status = optimoroute_request("POST", ENDPOINTS["delete_orders"], data={"orders": orders})
            
            if isinstance(res, dict):
                success_count = sum(1 for o in res.get("orders", []) if o.get("success"))
                delete_result = {
                    "total": len(orders),
                    "success_count": success_count,
                    "results": res.get("orders", []),
                }
    
    return render_template("delete_orders.html", result=delete_result)


@app.route("/orders/delete-all", methods=["POST"])
def delete_all_orders():
    """Delete all orders for a date."""
    date = request.form.get("date", "")
    
    res, status = optimoroute_request("POST", ENDPOINTS["delete_all_orders"], data={"date": date} if date else {})
    
    if isinstance(res, dict) and res.get("success"):
        flash(f"All orders for {date or 'all dates'} deleted successfully!", "success")
    else:
        flash(f"Error: {res.get('message', 'Unknown error')}", "error")
    
    return redirect(url_for("orders"))


@app.route("/api/status")
def api_status():
    """Check API connectivity."""
    # Test with get_routes
    date = pd.Timestamp.now().strftime("%Y-%m-%d")
    res, status = optimoroute_request("GET", ENDPOINTS["get_routes"], params={"date": date})
    
    return jsonify({
        "status": "connected" if status == 200 else "error",
        "api_key_configured": bool(API_KEY),
        "base_url": BASE_URL,
        "endpoints": ENDPOINTS,
        "test_response": res,
        "http_status": status
    })


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", error="Server error"), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
