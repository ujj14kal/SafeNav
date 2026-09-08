"""
Fetch real data from OSM + Google Places and save to app/data/.
Run this ONCE before starting the server.
"""
import os
import sys
import json

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app.services.data_fetcher import (
    fetch_road_network,
    fetch_roads_overpass,
    fetch_pois,
)

LAT = float(os.environ.get('DEFAULT_LAT', '26.9124'))
LNG = float(os.environ.get('DEFAULT_LNG', '75.7873'))
RADIUS = 2000

DATA_DIR = os.path.join(os.path.dirname(__file__), 'app', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

print(f"=" * 50)
print(f"SafeRoute — Real Data Fetcher")
print(f"Location: ({LAT}, {LNG}) | Radius: {RADIUS}m")
print(f"=" * 50)

# 1. Fetch road network from OSM
print(f"\n[1/2] Fetching road network from OpenStreetMap ...")
graph_data = None

try:
    graph_data = fetch_road_network(LAT, LNG, radius_m=RADIUS)
    if graph_data:
        print(f"  ✓ osmnx: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")
except Exception as e:
    print(f"  ✗ osmnx failed: {e}")

if not graph_data:
    print("  Trying Overpass API fallback ...")
    try:
        graph_data = fetch_roads_overpass(LAT, LNG, radius_m=RADIUS)
        if graph_data:
            print(f"  ✓ Overpass: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")
    except Exception as e:
        print(f"  ✗ Overpass failed: {e}")

if graph_data:
    graph_path = os.path.join(DATA_DIR, 'graph.json')
    with open(graph_path, 'w') as f:
        json.dump(graph_data, f)
    print(f"  Saved to {graph_path}")
else:
    print("  ✗ Could not fetch road network!")

# 2. Fetch POIs from Google Places
print(f"\n[2/2] Fetching POIs from Google Places API ...")
pois = {}
try:
    pois = fetch_pois(LAT, LNG, radius_m=5000)
    total = sum(len(v) for v in pois.values())
    for k, v in pois.items():
        if v:
            print(f"  ✓ {k}: {len(v)} found")
    print(f"  Total: {total} POIs")
except Exception as e:
    print(f"  ✗ Google Places failed: {e}")

pois_path = os.path.join(DATA_DIR, 'pois.json')
with open(pois_path, 'w') as f:
    json.dump(pois, f)
print(f"  Saved to {pois_path}")

print(f"\n{'=' * 50}")
print(f"Done! Data saved to app/data/")
print(f"Start the server: python run.py")
print(f"{'=' * 50}")
