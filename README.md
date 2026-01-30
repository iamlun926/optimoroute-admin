# Optimoroute Admin Portal

Local web interface for managing Optimoroute routes, drivers, and orders.

## Setup

```bash
cd optimoroute_admin
pip install -r requirements.txt
```

## Configuration

Set your API key:
```bash
export OPTIMOROUTE_API_KEY="your_api_key_here"
```

Or create a `.env` file:
```
OPTIMOROUTE_API_KEY=your_api_key_here
```

## Run

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

## Features

- Dashboard with route overview
- Manage routes
- Manage drivers
- Manage orders/deliveries
- API status check
