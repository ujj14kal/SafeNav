"""
SafeNav — Real Data Fetcher
Pulls actual road network from OpenStreetMap (via osmnx)
and real POIs from Google Places API.
"""
import os
import json
import time
import hashlib
import math
import requests
import osmnx as ox
import networkx as nx
from datetime import datetime


# ─────────────────────────────────────────────────
# Cache directory (avoids re-fetching on every restart)
# ─────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

GOOGLE_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
PLACES_BASE = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'


def _cache_path(key: str) -> str:
    """Deterministic cache file path for a given key."""
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f'{h}.json')


def _load_cache(key: str, max_age_seconds: int = 86400):
    """Load cached data if fresh enough (default: 24h)."""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            blob = json.load(f)
        if time.time() - blob.get('_cached_at', 0) > max_age_seconds:
            return None
        return blob.get('data')
    except (json.JSONDecodeError, KeyError):
        return None


def _save_cache(key: str, data):
    """Save data to disk cache."""
    path = _cache_path(key)
    with open(path, 'w') as f:
        json.dump({'_cached_at': time.time(), 'data': data}, f)


# ═══════════════════════════════════════════════════
# 1. ROAD NETWORK FROM OPENSTREETMAP
# ═══════════════════════════════════════════════════

# OSM highway tags → our road_type categories
OSM_HIGHWAY_MAP = {
    'motorway': 'motorway',
    'motorway_link': 'motorway',
    'trunk': 'trunk',
    'trunk_link': 'trunk',
    'primary': 'primary',
    'primary_link': 'primary',
    'secondary': 'secondary',
    'secondary_link': 'secondary',
    'tertiary': 'tertiary',
    'tertiary_link': 'tertiary',
    'residential': 'residential',
    'living_street': 'living_street',
    'service': 'service',
    'unclassified': 'unclassified',
    'pedestrian': 'service',
    'footway': 'service',
    'path': 'service',
    'cycleway': 'residential',
    'steps': 'service',
    'track': 'unclassified',
}

# Speed limits by road type (km/h) — Indian defaults
SPEED_LIMITS = {
    'motorway': 100,
    'trunk': 80,
    'primary': 60,
    'secondary': 50,
    'tertiary': 40,
    'residential': 30,
    'service': 20,
    'unclassified': 30,
    'living_street': 20,
}


def fetch_road_network(lat: float, lng: float, radius_m: int = 2000) -> dict:
    """
    Download real road network from OpenStreetMap for a given area.
    Returns graph_data dict with 'nodes' and 'edges' in our format.
    
    Caches results for 7 days (roads don't change often).
    """
    cache_key = f'osm_roads_{lat:.4f}_{lng:.4f}_{radius_m}'
    cached = _load_cache(cache_key, max_age_seconds=7 * 86400)
    if cached:
        print(f'[DataFetcher] Using cached OSM data for ({lat}, {lng})')
        return cached

    print(f'[DataFetcher] Downloading OSM road network for ({lat}, {lng}) r={radius_m}m ...')

    try:
        # Download walkable + drivable road network from OSM
        G = ox.graph_from_point(
            (lat, lng),
            dist=radius_m,
            network_type='drive',  # drivable roads (most relevant for safety routing)
            simplify=True,
        )
    except Exception as e:
        print(f'[DataFetcher] OSM download failed: {e}')
        return None

    print(f'[DataFetcher] Got {G.number_of_nodes()} nodes, {G.number_of_edges()} edges from OSM')

    nodes = {}
    edges = []

    # Extract nodes
    for node_id, data in G.nodes(data=True):
        nodes[str(node_id)] = {
            'lat': data.get('y', data.get('lat', 0)),
            'lng': data.get('x', data.get('lon', 0)),
        }

    # Extract edges with real OSM attributes
    for u, v, key, data in G.edges(keys=True, data=True):
        # Determine road type from OSM highway tag
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0]  # sometimes it's a list
        road_type = OSM_HIGHWAY_MAP.get(highway, 'unclassified')

        # Distance in meters
        length = data.get('length', 100)  # osmnx pre-computes this

        # Lighting: OSM lit tag (yes/no/automatic)
        lit_raw = data.get('lit', '')
        if lit_raw in ('yes', 'automatic'):
            lit = True
        elif lit_raw == 'no':
            lit = False
        else:
            # Infer: main roads in cities are usually lit
            lit = road_type in ('primary', 'secondary', 'trunk', 'motorway')

        # Lanes (infrastructure quality indicator)
        lanes = data.get('lanes', None)
        if isinstance(lanes, str):
            try:
                lanes = int(lanes)
            except ValueError:
                lanes = None

        # One-way
        oneway = data.get('oneway', False)

        # Name
        name = data.get('name', '')

        edges.append({
            'from': str(u),
            'to': str(v),
            'distance': round(length, 1),
            'road_type': road_type,
            'lit': lit,
            'name': name if isinstance(name, str) else '',
            'lanes': lanes,
            'oneway': oneway in ('yes', 'True', True),
            'osm_id': data.get('osmid', ''),
        })

    result = {'nodes': nodes, 'edges': edges}
    _save_cache(cache_key, result)
    print(f'[DataFetcher] Cached {len(nodes)} nodes, {len(edges)} edges')
    return result


# ═══════════════════════════════════════════════════
# 2. REAL POIs FROM GOOGLE PLACES API
# ═══════════════════════════════════════════════════

def _google_nearby(lat: float, lng: float, place_type: str, radius_m: int = 5000) -> list:
    """
    Query Google Places Nearby Search for a given type.
    Returns list of {name, lat, lng, rating, place_id}.
    Handles pagination for up to 60 results.
    """
    if not GOOGLE_API_KEY:
        print('[DataFetcher] No GOOGLE_API_KEY set, skipping Places API')
        return []

    cache_key = f'places_{place_type}_{lat:.3f}_{lng:.3f}_{radius_m}'
    cached = _load_cache(cache_key, max_age_seconds=24 * 3600)
    if cached is not None:
        return cached

    results = []
    params = {
        'location': f'{lat},{lng}',
        'radius': radius_m,
        'type': place_type,
        'key': GOOGLE_API_KEY,
    }

    for _ in range(3):  # max 3 pages (60 results)
        try:
            resp = requests.get(PLACES_BASE, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f'[DataFetcher] Places API error: {e}')
            break

        for place in data.get('results', []):
            loc = place.get('geometry', {}).get('location', {})
            results.append({
                'name': place.get('name', ''),
                'lat': loc.get('lat', 0),
                'lng': loc.get('lng', 0),
                'rating': place.get('rating', 0),
                'place_id': place.get('place_id', ''),
                'address': place.get('vicinity', ''),
                'open_now': place.get('opening_hours', {}).get('open_now', None),
            })

        # Next page token (Google adds a short delay before it works)
        next_token = data.get('next_page_token')
        if not next_token:
            break
        time.sleep(2)
        params = {'pagetoken': next_token, 'key': GOOGLE_API_KEY}

    _save_cache(cache_key, results)
    print(f'[DataFetcher] Found {len(results)} {place_type} places near ({lat}, {lng})')
    return results


def fetch_pois(lat: float, lng: float, radius_m: int = 5000) -> dict:
    """
    Fetch real Points of Interest from Google Places API.
    Returns dict with categories: police_stations, hospitals, schools, etc.
    """
    cache_key = f'all_pois_{lat:.3f}_{lng:.3f}_{radius_m}'
    cached = _load_cache(cache_key, max_age_seconds=12 * 3600)
    if cached is not None:
        print(f'[DataFetcher] Using cached POIs')
        return cached

    print(f'[DataFetcher] Fetching real POIs from Google Places API ...')

    pois = {
        'police_stations': _google_nearby(lat, lng, 'police', radius_m),
        'hospitals': _google_nearby(lat, lng, 'hospital', radius_m),
        'schools': _google_nearby(lat, lng, 'school', radius_m),
        'fire_stations': _google_nearby(lat, lng, 'fire_station', radius_m),
        'liquor_shops': _google_nearby(lat, lng, 'liquor_store', radius_m),
        'atms': _google_nearby(lat, lng, 'atm', radius_m),
        'gas_stations': _google_nearby(lat, lng, 'gas_station', radius_m),
    }

    # Count totals
    total = sum(len(v) for v in pois.values())
    print(f'[DataFetcher] Total POIs fetched: {total}')

    _save_cache(cache_key, pois)
    return pois


# ═══════════════════════════════════════════════════
# 3. CRIME INDEX DERIVATION
# ═══════════════════════════════════════════════════
# India doesn't have a public real-time crime API.
# We derive a crime index from environmental factors:
#   - Proximity to liquor shops (increases risk)
#   - Road type and lighting (poorly lit service roads = riskier)
#   - Isolation (few shops/commercial activity)
#   - Time of day
#   - Community reports (real-time signal)

def compute_crime_index_for_edge(edge: dict, pois: dict) -> float:
    """
    Compute a crime risk index (0.0 = safe, 1.0 = dangerous) for a road edge.
    Uses real environmental data instead of a fake crime_rate.
    """
    lat = edge.get('lat', 0)
    lng = edge.get('lng', 0)
    if not lat or not lng:
        return 0.3  # neutral default

    risk = 0.0

    # Factor 1: Proximity to liquor shops (closer = riskier)
    liquor_shops = pois.get('liquor_shops', [])
    if liquor_shops:
        min_dist = float('inf')
        for shop in liquor_shops:
            d = _haversine(lat, lng, shop['lat'], shop['lng'])
            min_dist = min(min_dist, d)
        if min_dist < 200:
            risk += 0.25
        elif min_dist < 500:
            risk += 0.15
        elif min_dist < 1000:
            risk += 0.05

    # Factor 2: Road type isolation
    road_type = edge.get('road_type', 'residential')
    if road_type == 'service':
        risk += 0.20
    elif road_type == 'unclassified':
        risk += 0.10
    elif road_type == 'residential':
        risk += 0.05

    # Factor 3: Lighting
    if not edge.get('lit', False):
        risk += 0.20

    # Factor 4: Police proximity (closer = safer, reduces risk)
    police = pois.get('police_stations', [])
    if police:
        min_dist = float('inf')
        for p in police:
            d = _haversine(lat, lng, p['lat'], p['lng'])
            min_dist = min(min_dist, d)
        if min_dist < 500:
            risk -= 0.15
        elif min_dist < 1000:
            risk -= 0.08
        elif min_dist < 2000:
            risk -= 0.03

    return max(0.0, min(1.0, risk))


def _haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lng points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ═══════════════════════════════════════════════════
# 4. OVERPASS API FALLBACK (if osmnx is slow/blocked)
# ═══════════════════════════════════════════════════

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'


def fetch_roads_overpass(lat: float, lng: float, radius_m: int = 2000) -> dict:
    """
    Fallback: fetch road data directly from Overpass API.
    Returns same format as fetch_road_network.
    """
    cache_key = f'overpass_roads_{lat:.4f}_{lng:.4f}_{radius_m}'
    cached = _load_cache(cache_key, max_age_seconds=7 * 86400)
    if cached:
        return cached

    query = f"""
    [out:json][timeout:30];
    (
      way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service|unclassified|living_street"]
         (around:{radius_m},{lat},{lng});
    );
    out body geom;
    """

    try:
        resp = requests.post(OVERPASS_URL, data={'data': query}, timeout=35)
        data = resp.json()
    except Exception as e:
        print(f'[DataFetcher] Overpass API error: {e}')
        return None

    nodes = {}
    edges = []
    node_counter = 0

    for way in data.get('elements', []):
        if way.get('type') != 'way':
            continue

        tags = way.get('tags', {})
        highway = tags.get('highway', 'unclassified')
        road_type = OSM_HIGHWAY_MAP.get(highway, 'unclassified')
        name = tags.get('name', '')

        lit_raw = tags.get('lit', '')
        if lit_raw in ('yes', 'automatic'):
            lit = True
        elif lit_raw == 'no':
            lit = False
        else:
            lit = road_type in ('primary', 'secondary', 'trunk', 'motorway')

        geometry = way.get('geometry', [])
        for i in range(len(geometry) - 1):
            n1 = geometry[i]
            n2 = geometry[i + 1]

            node_id_1 = f"N{n1['lat']:.6f}_{n1['lon']:.6f}"
            node_id_2 = f"N{n2['lat']:.6f}_{n2['lon']:.6f}"

            nodes[node_id_1] = {'lat': n1['lat'], 'lng': n1['lon']}
            nodes[node_id_2] = {'lat': n2['lat'], 'lng': n2['lon']}

            dist = _haversine(n1['lat'], n1['lon'], n2['lat'], n2['lon'])
            mid_lat = (n1['lat'] + n2['lat']) / 2
            mid_lng = (n1['lon'] + n2['lon']) / 2

            edges.append({
                'from': node_id_1,
                'to': node_id_2,
                'distance': round(dist, 1),
                'road_type': road_type,
                'lit': lit,
                'name': name,
                'lat': mid_lat,
                'lng': mid_lng,
            })

    result = {'nodes': nodes, 'edges': edges}
    _save_cache(cache_key, result)
    print(f'[DataFetcher] Overpass: {len(nodes)} nodes, {len(edges)} edges')
    return result
