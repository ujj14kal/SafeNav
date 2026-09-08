"""
SafeRoute — REST API Endpoints (v3 — DB-Backed, Centralized Scoring)
All safety calculations go through SafetyScoreEngine.
Persistent storage via SQLAlchemy/SQLite.
"""
import os
import json
import math
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load .env before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from app.models.database import (
    db, SafetyFeedback, Incident, Journey, Recording,
    LocationZone, User, SOSHistory, Guardian,
)
from app.services.safety_engine import SafetyEngine
from app.services.safety_score_engine import SafetyScoreEngine
from app.services.route_optimizer import RouteOptimizer
from app.services.data_fetcher import (
    fetch_road_network,
    fetch_roads_overpass,
    fetch_pois,
)
from app.services.sms_service import (
    send_emergency_sms,
    validate_phone_number,
    is_sms_configured,
    format_emergency_sms,
)

api_bp = Blueprint('api', __name__)

# Global state (loaded once at startup)
_optimizer = None
_data_source = None

# In-memory caches for guardians and live locations (lightweight, session-scoped)
_guardians = {}  # user_id -> [guardian dicts]
_live_locations = {}  # share_id -> location dict


def get_optimizer():
    global _optimizer
    if _optimizer is None:
        _optimizer = _load_graph_data()
    return _optimizer


def _load_graph_data():
    """Load real road network and POIs."""
    global _data_source

    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'graph.json')
    pois_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'pois.json')

    # Load POIs
    pois = {}
    if os.path.exists(pois_path):
        with open(pois_path) as f:
            pois = json.load(f)
        total_pois = sum(len(v) for v in pois.values())
        if total_pois > 0:
            print(f'[SafeRoute] Loaded cached POIs: {total_pois} places')
        else:
            pois = {}

    if not pois:
        lat = float(os.environ.get('DEFAULT_LAT', '26.9124'))
        lng = float(os.environ.get('DEFAULT_LNG', '75.7873'))
        try:
            pois = fetch_pois(lat, lng, radius_m=5000)
            total_pois = sum(len(v) for v in pois.values())
            if total_pois > 0:
                print(f'[SafeRoute] Google Places: {total_pois} POIs fetched')
                os.makedirs(os.path.dirname(pois_path), exist_ok=True)
                with open(pois_path, 'w') as f:
                    json.dump(pois, f)
        except Exception as e:
            print(f'[SafeRoute] Google Places failed: {e}')

    # Load road network
    graph_data = None
    if os.path.exists(data_path):
        with open(data_path) as f:
            graph_data = json.load(f)
        _data_source = 'Cached JSON (pre-built)'
        print(f'[SafeRoute] Loaded cached graph: {len(graph_data.get("nodes", {}))} nodes')
        return RouteOptimizer(graph_data=graph_data, pois=pois)

    lat = float(os.environ.get('DEFAULT_LAT', '26.9124'))
    lng = float(os.environ.get('DEFAULT_LNG', '75.7873'))
    radius = 2000

    print(f'[SafeRoute] Fetching road network for ({lat}, {lng}) ...')

    try:
        graph_data = fetch_road_network(lat, lng, radius_m=radius)
        if graph_data:
            _data_source = 'OpenStreetMap (osmnx)'
    except Exception as e:
        print(f'[SafeRoute] osmnx failed: {e}')

    if not graph_data:
        try:
            graph_data = fetch_roads_overpass(lat, lng, radius_m=radius)
            if graph_data:
                _data_source = 'OpenStreetMap (Overpass API)'
        except Exception as e:
            print(f'[SafeRoute] Overpass failed: {e}')

    if not graph_data:
        graph_data = _generate_graph_from_pois(lat, lng, pois)
        _data_source = 'Generated from real POI locations'

    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w') as f:
        json.dump(graph_data, f)

    return RouteOptimizer(graph_data=graph_data, pois=pois)


# ═══════════════════════════════════════════════════════
# FALLBACK DATA GENERATOR
# ═══════════════════════════════════════════════════════

def _generate_graph_from_pois(center_lat, center_lng, pois):
    """Generate a road network based on real POI locations."""
    import random
    random.seed(42)

    nodes = {}
    edges = []
    grid_size = 20
    lat_range = 0.025
    lng_range = 0.025

    for i in range(grid_size):
        for j in range(grid_size):
            node_id = f"N{i}_{j}"
            lat = center_lat + (i - grid_size // 2) * (lat_range / grid_size)
            lng = center_lng + (j - grid_size // 2) * (lng_range / grid_size)
            nodes[node_id] = {'lat': lat, 'lng': lng}

    all_pois = []
    for category, items in pois.items():
        for item in items:
            all_pois.append({
                'lat': item.get('lat', 0), 'lng': item.get('lng', 0), 'category': category,
            })

    def get_road_type(lat, lng):
        nearby_count = sum(1 for p in all_pois
                          if SafetyEngine.haversine(lat, lng, p['lat'], p['lng']) < 300)
        if nearby_count >= 5:
            return random.choices(['primary', 'secondary', 'tertiary'], [0.4, 0.4, 0.2])[0]
        elif nearby_count >= 2:
            return random.choices(['secondary', 'tertiary', 'residential'], [0.3, 0.4, 0.3])[0]
        return random.choices(['tertiary', 'residential', 'service'], [0.2, 0.5, 0.3])[0]

    for i in range(grid_size):
        for j in range(grid_size):
            for di, dj in [(0, 1), (1, 0)]:
                ni, nj = i + di, j + dj
                if ni < grid_size and nj < grid_size:
                    u = f"N{i}_{j}"
                    v = f"N{ni}_{nj}"
                    u_lat, u_lng = nodes[u]['lat'], nodes[u]['lng']
                    v_lat, v_lng = nodes[v]['lat'], nodes[v]['lng']
                    mid_lat = (u_lat + v_lat) / 2
                    mid_lng = (u_lng + v_lng) / 2
                    rt = get_road_type(mid_lat, mid_lng)
                    dist = random.randint(80, 200)
                    lit = rt in ('primary', 'secondary') or random.random() > 0.6
                    edges.append({'from': u, 'to': v, 'distance': dist, 'road_type': rt, 'lit': lit})
                    edges.append({'from': v, 'to': u, 'distance': dist, 'road_type': rt, 'lit': lit})

    print(f'[GraphGen] Generated {len(nodes)} nodes, {len(edges)} edges')
    return {'nodes': nodes, 'edges': edges}


# ═══════════════════════════════════════════════════════
# REPORT CATEGORIES
# ═══════════════════════════════════════════════════════

REPORT_CATEGORIES = {
    'people': {
        'label': 'People Related Concerns', 'icon': '👤',
        'subtypes': ['stalker', 'drunk_person', 'aggressive_behaviour', 'catcalling', 'harassment'],
    },
    'environmental': {
        'label': 'Environmental Hazards', 'icon': '🌿',
        'subtypes': ['poor_lighting', 'broken_road', 'stray_animals', 'flooding', 'construction'],
    },
    'infrastructure': {
        'label': 'Infrastructure Issues', 'icon': '🏗️',
        'subtypes': ['no_streetlight', 'broken_cctv', 'abandoned_building', 'no_footpath', 'blocked_road'],
    },
    'high_risk': {
        'label': 'High Risk Situations', 'icon': '⚠️',
        'subtypes': ['robbery_area', 'assault_zone', 'drug_activity', 'unsafe_at_night', 'isolated_area'],
    },
}


def _get_category_for_type(report_type):
    for cat_key, cat in REPORT_CATEGORIES.items():
        if report_type in cat['subtypes']:
            return cat_key
    return 'environmental'


def _calculate_report_weight(timestamp_str, half_life_hours=48):
    """Exponential decay weight."""
    try:
        ts = datetime.fromisoformat(timestamp_str)
        hours_ago = (datetime.utcnow() - ts).total_seconds() / 3600
        decay_constant = math.log(2) / half_life_hours
        return max(0.05, min(1.0, math.exp(-decay_constant * hours_ago)))
    except (ValueError, TypeError):
        return 0.5


# ═══════════════════════════════════════════════════════
# ROUTE PLANNING API (uses centralized SafetyScoreEngine)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/route', methods=['POST'])
def get_route():
    """Find safe routes between two points."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    start_coords = data.get('start')
    end_coords = data.get('end')
    if not start_coords or not end_coords:
        return jsonify({'error': 'start and end coordinates required'}), 400
    if len(start_coords) != 2 or len(end_coords) != 2:
        return jsonify({'error': 'Coordinates must be [lat, lng]'}), 400

    lat, lng = start_coords
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({'error': 'Invalid coordinates'}), 400

    night = data.get('night', False)
    mode = data.get('mode', 'normal')
    hour = data.get('hour', 22 if night else 12)

    optimizer = get_optimizer()
    start_node = optimizer.find_nearest_node(start_coords[0], start_coords[1])
    end_node = optimizer.find_nearest_node(end_coords[0], end_coords[1])

    if not start_node or not end_node:
        return jsonify({'error': 'Could not find nearby roads'}), 404

    # Get DB-based reports for the optimizer
    db_reports = _get_active_reports_for_optimizer()
    routes = optimizer.find_routes(start_node, end_node, hour=hour, mode=mode, reports=db_reports)

    if not routes:
        return jsonify({'error': 'No route found'}), 404

    # Recompute safety scores using SafetyScoreEngine for each route
    for route in routes:
        coords = route.get('coordinates', [])
        if coords:
            engine_result = SafetyScoreEngine.get_route_breakdown(coords, hour=hour)
            if engine_result.get('breakdown') and any(
                v is not None for v in engine_result['breakdown'].values()
            ):
                # Compute route safety score from breakdown
                breakdown = engine_result['breakdown']
                total = 0
                count = 0
                for factor, weight in SafetyScoreEngine.WEIGHTS.items():
                    val = breakdown.get(factor)
                    if val is not None:
                        total += val * weight * 10
                        count += 1
                if count > 0:
                    night_mult = SafetyScoreEngine.NIGHT_MULTIPLIER.get(hour, 0.7)
                    route['safety_score'] = max(0, min(100, round(total * night_mult, 1)))

    best_route = max(routes, key=lambda r: r.get('safety_score', 0))

    # Get REAL breakdown from SafetyScoreEngine
    best_coords = best_route.get('coordinates', [])
    breakdown_result = SafetyScoreEngine.get_route_breakdown(best_coords, hour=hour)
    safety_breakdown = breakdown_result.get('breakdown', {})

    explanation = _generate_explanation(best_route, night)
    briefing = _generate_safety_briefing(best_route, night=night, hour=hour)

    return jsonify({
        'routes': routes,
        'safety_breakdown': safety_breakdown,
        'breakdown_meta': {
            'data_source': breakdown_result.get('data_source', 'unknown'),
            'report_count': breakdown_result.get('report_count', 0),
            'feedback_count': breakdown_result.get('feedback_count', 0),
        },
        'explanation': explanation,
        'briefing': briefing,
    })


def _get_active_reports_for_optimizer():
    """Get active incidents from DB in the format the optimizer expects."""
    incidents = Incident.query.filter(
        Incident.status == 'active'
    ).order_by(Incident.timestamp.desc()).limit(200).all()

    reports = []
    for inc in incidents:
        reports.append({
            'lat': inc.lat, 'lng': inc.lng,
            'type': inc.type, 'severity': inc.severity,
            'timestamp': inc.timestamp.isoformat() if inc.timestamp else '',
            'weight': inc.weight,
        })
    return reports


# ═══════════════════════════════════════════════════════
# HEATMAP API (data-driven, time-sensitive)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    """Get safety heatmap data — different scores per segment based on DB data."""
    hour = request.args.get('hour', 12, type=int)
    optimizer = get_optimizer()
    heatmap = optimizer.get_heatmap_data(hour=hour)

    # Override heatmap scores with SafetyScoreEngine for DB-based scoring
    for feature in heatmap.get('features', []):
        coords = feature.get('geometry', {}).get('coordinates', [])
        if coords and len(coords) >= 1:
            # GeoJSON is [lng, lat]
            lng_val, lat_val = coords[0][0], coords[0][1]
            engine_result = SafetyScoreEngine.get_location_score(lat_val, lng_val, hour=hour)
            if engine_result.get('score') is not None:
                feature['properties']['safety_score'] = engine_result['score']
                feature['properties']['zone_name'] = engine_result.get('zone_name')
                feature['properties']['data_source'] = engine_result.get('data_source')

    return jsonify(heatmap)


# ═══════════════════════════════════════════════════════
# EMERGENCY API (nearest ON ROUTE)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/emergency', methods=['GET'])
def get_emergency():
    """Find nearest emergency services. If route_coords provided, find nearest ON route."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    route_coords_str = request.args.get('route_coords', None)

    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({'error': 'Invalid coordinates'}), 400

    pois = get_optimizer().pois

    # If route coordinates provided, find nearest along the route
    route_coords = None
    if route_coords_str:
        try:
            route_coords = json.loads(route_coords_str)
        except (json.JSONDecodeError, TypeError):
            pass

    def find_nearest(category):
        items = pois.get(category, [])
        if not items:
            return None

        if route_coords:
            # Find the POI that is nearest to ANY point on the route
            best = None
            best_route_dist = float('inf')
            for poi in items:
                min_dist_to_route = float('inf')
                for coord in route_coords:
                    d = SafetyEngine.haversine(coord[0], coord[1], poi['lat'], poi['lng'])
                    min_dist_to_route = min(min_dist_to_route, d)
                if min_dist_to_route < best_route_dist:
                    best_route_dist = min_dist_to_route
                    best = poi
            dist = best_route_dist
        else:
            best = min(items, key=lambda x: SafetyEngine.haversine(lat, lng, x['lat'], x['lng']))
            dist = SafetyEngine.haversine(lat, lng, best['lat'], best['lng'])

        return {
            'name': best['name'],
            'lat': best['lat'],
            'lng': best['lng'],
            'distance': round(dist),
            'eta_minutes': max(1, round(dist / 80)),
        }

    return jsonify({
        'police': find_nearest('police_stations'),
        'hospital': find_nearest('hospitals'),
        'safe_space': find_nearest('hospitals'),
        'fire_station': find_nearest('fire_stations'),
        'numbers': {
            'police': '100', 'ambulance': '108',
            'emergency': '112', 'women_helpline': '1091',
        },
    })


# ═══════════════════════════════════════════════════════
# COMMUNITY REPORTS (DB-backed)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/report', methods=['POST'])
def submit_report():
    """Submit a community safety report — stored in DB with real location name."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['lat', 'lng', 'type']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} required'}), 400

    report_type = data['type']
    category = data.get('category', _get_category_for_type(report_type))

    # Auto-resolve location name from coordinates
    location_name = data.get('location_name', '')
    if not location_name:
        from app.services.geocoding import reverse_geocode
        location_name = reverse_geocode(data['lat'], data['lng'])

    inc = Incident(
        lat=data['lat'], lng=data['lng'],
        location_name=location_name,
        type=report_type, category=category,
        severity=data.get('severity', 'medium'),
        description=data.get('description', ''),
        source='user_report',
        user_id=data.get('user_id', 'anonymous'),
        weight=1.0,
    )
    db.session.add(inc)
    db.session.commit()

    return jsonify({'id': inc.id, 'status': 'recorded', 'location_name': location_name}), 201


@api_bp.route('/api/reports', methods=['GET'])
def get_reports():
    """Get all active community reports from DB."""
    hours_back = request.args.get('hours', 72, type=int)
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    incidents = Incident.query.filter(
        Incident.status == 'active',
        Incident.timestamp >= cutoff,
    ).order_by(Incident.timestamp.desc()).all()
    return jsonify({
        'reports': [inc.to_dict() for inc in incidents],
        'categories': REPORT_CATEGORIES,
    })


@api_bp.route('/api/reports/categories', methods=['GET'])
def get_report_categories():
    return jsonify({'categories': REPORT_CATEGORIES})


@api_bp.route('/api/reports/<int:report_id>/verify', methods=['POST'])
def verify_report(report_id):
    """Verify a community report."""
    inc = Incident.query.get(report_id)
    if not inc:
        return jsonify({'error': 'Report not found'}), 404
    inc.verifications = (inc.verifications or 0) + 1
    inc.weight = min(1.5, (inc.weight or 1.0) + 0.1)
    db.session.commit()
    return jsonify({'id': report_id, 'verifications': inc.verifications, 'status': 'verified'})


# ═══════════════════════════════════════════════════════
# FEEDBACK SYSTEM (new — Item #3)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Store thumbs up/down feedback with location."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    lat = data.get('lat')
    lng = data.get('lng')
    feedback_type = data.get('feedback_type')  # 'safe' or 'unsafe'

    if lat is None or lng is None or feedback_type not in ('safe', 'unsafe'):
        return jsonify({'error': 'lat, lng, and feedback_type (safe/unsafe) required'}), 400

    # Find matching zone
    zone = SafetyScoreEngine._find_nearest_zone(lat, lng, max_radius_m=1000)

    fb = SafetyFeedback(
        lat=lat, lng=lng,
        zone_id=zone.id if zone else None,
        feedback_type=feedback_type,
        user_id=data.get('user_id', 'anonymous'),
        route_info=json.dumps(data.get('route_info', {})) if data.get('route_info') else None,
    )
    db.session.add(fb)
    db.session.commit()

    return jsonify({'id': fb.id, 'status': 'recorded', 'zone_name': zone.name if zone else None}), 201


@api_bp.route('/api/feedback/stats', methods=['GET'])
def get_feedback_stats():
    """Get feedback statistics for a location."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    nearby = SafetyScoreEngine._get_nearby_feedback(lat, lng, radius_m=500)
    safe_count = sum(1 for f in nearby if f.feedback_type == 'safe')
    unsafe_count = sum(1 for f in nearby if f.feedback_type == 'unsafe')

    # Exponential decay weights
    now = datetime.utcnow()
    safe_weight = 0
    unsafe_weight = 0
    for fb in nearby:
        if fb.timestamp:
            age_h = (now - fb.timestamp).total_seconds() / 3600
            decay = math.exp(-0.015 * age_h)
        else:
            decay = 0.5
        if fb.feedback_type == 'safe':
            safe_weight += decay
        else:
            unsafe_weight += decay

    return jsonify({
        'total': len(nearby),
        'safe_count': safe_count,
        'unsafe_count': unsafe_count,
        'safe_weight': round(safe_weight, 2),
        'unsafe_weight': round(unsafe_weight, 2),
        'net_sentiment': 'safe' if safe_weight > unsafe_weight else 'unsafe' if unsafe_weight > safe_weight else 'neutral',
    })


# ═══════════════════════════════════════════════════════
# HER WAY HOME JOURNEY MONITORING (Item #4)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/journey/start', methods=['POST'])
def start_journey():
    """Start monitoring a journey."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    origin = data.get('origin')
    dest = data.get('destination')
    if not origin or not dest or len(origin) < 2 or len(dest) < 2:
        return jsonify({'error': 'origin and destination [lat, lng] required'}), 400

    journey = Journey(
        user_id=data.get('user_id', 'anonymous'),
        origin_lat=origin[0], origin_lng=origin[1],
        dest_lat=dest[0], dest_lng=dest[1],
        current_lat=origin[0], current_lng=origin[1],
        eta_minutes=data.get('eta_minutes'),
        status='active',
        notifications='[]',
    )
    db.session.add(journey)
    db.session.commit()

    return jsonify({'journey_id': journey.id, 'status': 'active'}), 201


@api_bp.route('/api/journey/<int:journey_id>/status', methods=['GET'])
def get_journey_status(journey_id):
    """Get journey progress and notifications."""
    journey = Journey.query.get(journey_id)
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404

    # Check if entering/leaving zones
    notifications = json.loads(journey.notifications) if journey.notifications else []
    if journey.current_lat and journey.current_lng:
        zone = SafetyScoreEngine._find_nearest_zone(journey.current_lat, journey.current_lng, 1000)
        if zone:
            score_result = SafetyScoreEngine.get_location_score(
                journey.current_lat, journey.current_lng
            )
            if score_result.get('score') is not None and score_result['score'] < 40:
                notifications.append({
                    'type': 'danger_zone',
                    'message': f'Entering low-safety zone: {zone.name}',
                    'score': score_result['score'],
                    'timestamp': datetime.utcnow().isoformat(),
                })
                journey.notifications = json.dumps(notifications)
                db.session.commit()

    return jsonify(journey.to_dict())


@api_bp.route('/api/journey/<int:journey_id>/update', methods=['POST'])
def update_journey(journey_id):
    """Update current position during journey."""
    journey = Journey.query.get(journey_id)
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404

    data = request.get_json()
    journey.current_lat = data.get('lat', journey.current_lat)
    journey.current_lng = data.get('lng', journey.current_lng)
    db.session.commit()

    return jsonify({'status': 'updated', 'current': [journey.current_lat, journey.current_lng]})


@api_bp.route('/api/journey/<int:journey_id>/notifications', methods=['GET'])
def get_journey_notifications(journey_id):
    """Get pending notifications for a journey."""
    journey = Journey.query.get(journey_id)
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404
    notifications = json.loads(journey.notifications) if journey.notifications else []
    return jsonify({'notifications': notifications})


@api_bp.route('/api/journey/<int:journey_id>/complete', methods=['POST'])
def complete_journey(journey_id):
    """Mark journey as completed."""
    journey = Journey.query.get(journey_id)
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404
    journey.status = 'completed'
    db.session.commit()
    return jsonify({'status': 'completed'})


# ═══════════════════════════════════════════════════════
# GUARDIAN NETWORK (DB-backed, SMS-enabled)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/guardians', methods=['POST'])
def add_guardian():
    """Add a guardian contact (persisted to DB)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['user_id', 'name', 'phone']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} required'}), 400

    # Validate phone number
    phone_validation = validate_phone_number(data['phone'])
    if not phone_validation['valid']:
        return jsonify({'error': phone_validation['error']}), 400

    user_id = data['user_id']

    # Check if this is the first guardian (make primary)
    existing_count = Guardian.query.filter_by(user_id=user_id).count()
    is_primary = existing_count == 0 or data.get('is_primary', False)

    # If setting as primary, unset others
    if is_primary:
        Guardian.query.filter_by(user_id=user_id, is_primary=True).update({'is_primary': False})

    guardian = Guardian(
        user_id=user_id,
        name=data['name'],
        phone=phone_validation['cleaned'],
        email=data.get('email', ''),
        relationship=data.get('relationship', 'friend'),
        is_primary=is_primary,
    )
    db.session.add(guardian)
    db.session.commit()

    return jsonify({'guardian': guardian.to_dict(), 'status': 'added'}), 201


@api_bp.route('/api/guardians/<user_id>', methods=['GET'])
def get_guardians(user_id):
    """Get all guardians for a user (from DB)."""
    guardians = Guardian.query.filter_by(user_id=user_id).order_by(Guardian.is_primary.desc()).all()
    return jsonify({
        'guardians': [g.to_dict() for g in guardians],
        'count': len(guardians),
    })


@api_bp.route('/api/guardians/<int:guardian_id>', methods=['PUT'])
def update_guardian(guardian_id):
    """Update a guardian's details."""
    guardian = Guardian.query.get(guardian_id)
    if not guardian:
        return jsonify({'error': 'Guardian not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'name' in data:
        guardian.name = data['name']
    if 'phone' in data:
        phone_validation = validate_phone_number(data['phone'])
        if not phone_validation['valid']:
            return jsonify({'error': phone_validation['error']}), 400
        guardian.phone = phone_validation['cleaned']
    if 'email' in data:
        guardian.email = data['email']
    if 'relationship' in data:
        guardian.relationship = data['relationship']
    if 'is_primary' in data and data['is_primary']:
        Guardian.query.filter_by(user_id=guardian.user_id, is_primary=True).update({'is_primary': False})
        guardian.is_primary = True

    db.session.commit()
    return jsonify({'guardian': guardian.to_dict(), 'status': 'updated'})


@api_bp.route('/api/guardians/<int:guardian_id>', methods=['DELETE'])
def remove_guardian(guardian_id):
    """Remove a guardian."""
    guardian = Guardian.query.get(guardian_id)
    if not guardian:
        return jsonify({'error': 'Guardian not found'}), 404

    user_id = guardian.user_id
    was_primary = guardian.is_primary
    db.session.delete(guardian)
    db.session.commit()

    # If we deleted the primary, promote the next one
    if was_primary:
        next_guardian = Guardian.query.filter_by(user_id=user_id).first()
        if next_guardian:
            next_guardian.is_primary = True
            db.session.commit()

    return jsonify({'status': 'removed'})


@api_bp.route('/api/guardians/<user_id>/primary', methods=['GET'])
def get_primary_guardian(user_id):
    """Get the primary guardian for a user (the one who receives SOS SMS)."""
    guardian = Guardian.query.filter_by(user_id=user_id, is_primary=True).first()
    if not guardian:
        # Fall back to first guardian
        guardian = Guardian.query.filter_by(user_id=user_id).first()
    if not guardian:
        return jsonify({'error': 'No guardian configured', 'has_guardian': False}), 404
    return jsonify({'guardian': guardian.to_dict(), 'has_guardian': True})


# ═══════════════════════════════════════════════════════
# SOS / PANIC MODE (DB-backed + SMS)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/sos', methods=['POST'])
def trigger_sos():
    """
    Trigger SOS alert — stores in DB and sends SMS to guardian.

    Expected payload:
    {
        "user_id": "user123",
        "lat": 26.9124,         ← real GPS latitude (from browser Geolocation API)
        "lng": 75.7873,         ← real GPS longitude
        "user_name": "Khwaab",  ← optional, for SMS message
        "type": "panic"         ← optional
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    lat = data.get('lat')
    lng = data.get('lng')
    user_id = data.get('user_id', 'anonymous')
    user_name = data.get('user_name', user_id)
    sos_type = data.get('type', 'panic')

    # ── Validate coordinates ──
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng are required. Enable GPS/location permissions in your browser.'}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({'error': f'Invalid coordinates: lat={lat}, lng={lng}. GPS may be returning inaccurate data.'}), 400

    # Reject (0, 0) — usually means GPS failed
    if lat == 0.0 and lng == 0.0:
        return jsonify({'error': 'GPS returned (0, 0) — location unavailable. Please check location permissions.'}), 400

    # ── Store SOS in DB ──
    sos_id_val = str(uuid.uuid4())[:8]
    sos = SOSHistory(
        sos_id=sos_id_val, user_id=user_id,
        lat=lat, lng=lng,
        type=sos_type,
        status='active',
    )
    db.session.add(sos)
    db.session.commit()

    # ── Find nearest emergency services ──
    pois = get_optimizer().pois

    def find_nearest(category):
        items = pois.get(category, [])
        if not items:
            return None
        best = min(items, key=lambda x: SafetyEngine.haversine(lat, lng, x['lat'], x['lng']))
        dist = SafetyEngine.haversine(lat, lng, best['lat'], best['lng'])
        return {'name': best['name'], 'lat': best['lat'], 'lng': best['lng'], 'distance': round(dist), 'eta_minutes': max(1, round(dist / 80))}

    # ── Send SMS to guardian ──
    sms_results = []
    guardian = Guardian.query.filter_by(user_id=user_id, is_primary=True).first()
    if not guardian:
        guardian = Guardian.query.filter_by(user_id=user_id).first()

    if guardian:
        sms_result = send_emergency_sms(
            to_phone=guardian.phone,
            user_name=user_name,
            lat=lat,
            lng=lng,
            guardian_name=guardian.name,
        )
        sms_result['guardian_name'] = guardian.name
        sms_result['guardian_phone'] = guardian.phone
        sms_results.append(sms_result)
    else:
        sms_results.append({
            'success': False,
            'error': 'No guardian configured. Add a guardian in Settings first.',
            'method': 'no_guardian',
        })

    # ── Build response ──
    any_sms_sent = any(r.get('success') for r in sms_results)

    return jsonify({
        'sos_id': sos_id_val,
        'status': 'activated',
        'location': {'lat': lat, 'lng': lng},
        'google_maps_link': f'https://maps.google.com/?q={lat},{lng}',
        'nearest_police': find_nearest('police_stations'),
        'nearest_hospital': find_nearest('hospitals'),
        'emergency_numbers': {
            'police': '100',
            'ambulance': '108',
            'emergency': '112',
            'women_helpline': '1091',
        },
        'sms': {
            'sent': any_sms_sent,
            'guardian_notified': any_sms_sent,
            'results': sms_results,
            'sms_configured': is_sms_configured(),
        },
        'timestamp': datetime.utcnow().isoformat(),
    })


@api_bp.route('/api/sos/preview', methods=['POST'])
def preview_sos_sms():
    """
    Preview the SOS SMS without actually sending it.
    Useful for the frontend to show the user what will be sent.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    lat = data.get('lat')
    lng = data.get('lng')
    user_id = data.get('user_id', 'anonymous')
    user_name = data.get('user_name', user_id)

    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    guardian = Guardian.query.filter_by(user_id=user_id, is_primary=True).first()
    if not guardian:
        guardian = Guardian.query.filter_by(user_id=user_id).first()

    if not guardian:
        return jsonify({
            'has_guardian': False,
            'error': 'No guardian configured. Add a guardian first.',
        })

    sms_content = format_emergency_sms(
        user_name=user_name,
        lat=lat, lng=lng,
        guardian_name=guardian.name,
    )

    return jsonify({
        'has_guardian': True,
        'guardian': guardian.to_dict(),
        'sms_content': sms_content,
        'maps_link': f'https://maps.google.com/?q={lat},{lng}',
        'sms_configured': is_sms_configured(),
    })


@api_bp.route('/api/sos/<user_id>/history', methods=['GET'])
def get_sos_history(user_id):
    history = SOSHistory.query.filter_by(user_id=user_id).order_by(SOSHistory.timestamp.desc()).all()
    return jsonify({'history': [s.to_dict() for s in history], 'count': len(history)})


@api_bp.route('/api/sos/<sos_id>/resolve', methods=['POST'])
def resolve_sos(sos_id):
    sos = SOSHistory.query.filter_by(sos_id=sos_id).first()
    if not sos:
        return jsonify({'error': 'SOS not found'}), 404
    sos.status = 'resolved'
    sos.resolved_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'resolved'})


@api_bp.route('/api/sms/status', methods=['GET'])
def get_sms_status():
    """Check if SMS service is configured."""
    return jsonify({
        'configured': is_sms_configured(),
        'provider': 'Twilio' if is_sms_configured() else 'None (manual fallback)',
    })


# ═══════════════════════════════════════════════════════
# LIVE LOCATION SHARING
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/location/share', methods=['POST'])
def share_location():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    share_id = str(uuid.uuid4())[:8]
    _live_locations[share_id] = {
        'user_id': data.get('user_id', 'anonymous'),
        'lat': data.get('lat'), 'lng': data.get('lng'),
        'destination': data.get('destination'),
        'eta_minutes': data.get('eta_minutes'),
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
        'guardians': data.get('guardians', []),
        'status': 'active',
    }
    return jsonify({'share_id': share_id, 'share_url': f'/track/{share_id}', 'expires_in_hours': 2, 'status': 'sharing'}), 201


@api_bp.route('/api/location/<share_id>', methods=['GET'])
def get_shared_location(share_id):
    loc = _live_locations.get(share_id)
    if not loc:
        return jsonify({'error': 'Location share not found'}), 404
    if datetime.utcnow() > datetime.fromisoformat(loc['expires_at']):
        loc['status'] = 'expired'
        return jsonify({'error': 'Location share expired', 'status': 'expired'}), 410
    return jsonify(loc)


@api_bp.route('/api/location/<share_id>/update', methods=['PUT'])
def update_location(share_id):
    data = request.get_json()
    loc = _live_locations.get(share_id)
    if not loc:
        return jsonify({'error': 'Location share not found'}), 404
    loc['lat'] = data.get('lat', loc['lat'])
    loc['lng'] = data.get('lng', loc['lng'])
    loc['last_updated'] = datetime.utcnow().isoformat()
    return jsonify({'status': 'updated'})


@api_bp.route('/api/location/<share_id>/stop', methods=['POST'])
def stop_sharing(share_id):
    loc = _live_locations.get(share_id)
    if not loc:
        return jsonify({'error': 'Location share not found'}), 404
    loc['status'] = 'stopped'
    loc['stopped_at'] = datetime.utcnow().isoformat()
    return jsonify({'status': 'stopped'})


# ═══════════════════════════════════════════════════════
# SAFETY ZONES (Item #16 — area bubbles from DB)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/safety-zones', methods=['GET'])
def get_safety_zones():
    """Get safety zone overlays from DB zones."""
    hour = request.args.get('hour', 12, type=int)

    zones = {'safe': [], 'moderate': [], 'danger': []}

    db_zones = LocationZone.query.all()
    for zone in db_zones:
        # Get real-time score from SafetyScoreEngine
        result = SafetyScoreEngine.get_location_score(
            zone.center_lat, zone.center_lng, hour=hour
        )
        score = result.get('score')
        if score is None:
            score = zone.base_safety_score or 50

        zone_data = {
            'name': zone.name,
            'center_lat': zone.center_lat,
            'center_lng': zone.center_lng,
            'radius': zone.radius_m,
            'score': score,
            'description': zone.description,
            'data_source': result.get('data_source', 'zone'),
            'feedback_count': result.get('feedback_count', 0),
            'incident_count': result.get('incident_count', 0),
        }

        if score >= 70:
            zones['safe'].append(zone_data)
        elif score >= 40:
            zones['moderate'].append(zone_data)
        else:
            zones['danger'].append(zone_data)

    return jsonify({'zones': zones, 'hour': hour, 'total_zones': len(db_zones)})


# ═══════════════════════════════════════════════════════
# RECORDING STORAGE (Item #17)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/recording/upload', methods=['POST'])
def upload_recording():
    """Store audio recording — accepts multipart file upload or JSON metadata."""
    import werkzeug.utils

    user_id = request.form.get('user_id', 'anonymous') if request.form else 'anonymous'
    lat = request.form.get('lat', type=float) if request.form else None
    lng = request.form.get('lng', type=float) if request.form else None
    sos_id = request.form.get('sos_id') if request.form else None
    duration = request.form.get('duration_seconds', type=float) if request.form else None

    audio_path = ''
    file_size = 0

    # Handle actual audio file upload
    if 'audio' in request.files:
        audio_file = request.files['audio']
        if audio_file.filename:
            # Create uploads directory
            upload_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'recordings')
            os.makedirs(upload_dir, exist_ok=True)

            # Generate unique filename
            ext = audio_file.filename.rsplit('.', 1)[-1] if '.' in audio_file.filename else 'webm'
            filename = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
            filepath = os.path.join(upload_dir, filename)

            audio_file.save(filepath)
            audio_path = f"uploads/recordings/{filename}"
            file_size = os.path.getsize(filepath)
    else:
        # JSON metadata only (no file)
        data = request.get_json() if request.is_json else {}
        if data:
            user_id = data.get('user_id', user_id)
            lat = data.get('lat', lat)
            lng = data.get('lng', lng)
            sos_id = data.get('sos_id', sos_id)
            duration = data.get('duration_seconds', duration)
            audio_path = data.get('audio_path', '')
            file_size = data.get('file_size', 0)

    rec = Recording(
        user_id=user_id,
        lat=lat,
        lng=lng,
        audio_path=audio_path,
        duration_seconds=duration,
        sos_id=sos_id,
        file_size=file_size,
    )
    db.session.add(rec)
    db.session.commit()

    return jsonify({'id': rec.id, 'status': 'stored', 'audio_path': audio_path, 'file_size': file_size}), 201


@api_bp.route('/api/recordings', methods=['GET'])
def get_recordings():
    """Get all recordings (admin)."""
    recordings = Recording.query.order_by(Recording.timestamp.desc()).all()
    return jsonify({'recordings': [r.to_dict() for r in recordings]})


@api_bp.route('/api/recording/<int:rec_id>/audio', methods=['GET'])
def get_recording_audio(rec_id):
    """Serve a recording's audio file."""
    rec = Recording.query.get_or_404(rec_id)
    if not rec.audio_path:
        return jsonify({'error': 'No audio file'}), 404
    filepath = os.path.join(os.path.dirname(__file__), '..', '..', rec.audio_path)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Audio file not found on disk'}), 404
    from flask import send_file
    return send_file(filepath, mimetype='audio/webm')


# ═══════════════════════════════════════════════════════
# USER REGISTRATION + LOGIN
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/register', methods=['POST'])
def register_user():
    """Register a new user account."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400

    # Check if username exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    # Check email uniqueness if provided
    email = data.get('email', '').strip() or None
    if email and User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        username=username,
        email=email,
        phone=data.get('phone', '').strip() or None,
        full_name=data.get('full_name', '').strip() or None,
        password_hash=generate_password_hash(password),
        role='user',
        home_lat=data.get('home_lat'),
        home_lng=data.get('home_lng'),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'status': 'registered',
        'user': user.to_dict(),
    }), 201


@api_bp.route('/api/login', methods=['POST'])
def login_user():
    """Login with username/password."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'status': 'authenticated',
        'user': user.to_dict(),
    })


@api_bp.route('/api/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user profile."""
    user = User.query.get_or_404(user_id)
    return jsonify({'user': user.to_dict()})


@api_bp.route('/api/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user profile."""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'email' in data:
        user.email = data['email']
    if 'home_lat' in data:
        user.home_lat = data['home_lat']
    if 'home_lng' in data:
        user.home_lng = data['home_lng']
    if 'password' in data and data['password']:
        user.password_hash = generate_password_hash(data['password'])

    db.session.commit()
    return jsonify({'status': 'updated', 'user': user.to_dict()})


@api_bp.route('/api/users', methods=['GET'])
def get_all_users():
    """Get all users (admin)."""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users], 'count': len(users)})


# ═══════════════════════════════════════════════════════
# ADMIN LOGIN + STATS (DB-backed)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Simple admin authentication."""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')

    user = User.query.filter_by(username=username, role='admin').first()
    if user and check_password_hash(user.password_hash, password):
        return jsonify({'status': 'authenticated', 'role': 'admin', 'username': username})
    return jsonify({'error': 'Invalid credentials'}), 401


@api_bp.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Get city-wide safety statistics from DB."""
    hour = request.args.get('hour', 12, type=int)
    optimizer = get_optimizer()
    danger_zones = optimizer.get_danger_zones(hour=hour)

    # Recompute danger zone scores using SafetyScoreEngine
    for zone in danger_zones:
        result = SafetyScoreEngine.get_location_score(zone['lat'], zone['lng'], hour=hour)
        if result.get('score') is not None:
            zone['score'] = result['score']
            zone['zone_name'] = result.get('zone_name')

    # Compute average from all zones in DB
    db_zones = LocationZone.query.all()
    zone_scores = []
    for z in db_zones:
        result = SafetyScoreEngine.get_location_score(z.center_lat, z.center_lng, hour=hour)
        if result.get('score') is not None:
            zone_scores.append(result['score'])
    avg_score = round(sum(zone_scores) / len(zone_scores), 1) if zone_scores else 0

    # Report statistics
    report_stats = {}
    for cat_key, cat in REPORT_CATEGORIES.items():
        count = Incident.query.filter_by(category=cat_key, status='active').count()
        report_stats[cat_key] = {'count': count, 'label': cat['label'], 'icon': cat['icon']}

    total_reports = Incident.query.filter_by(status='active').count()
    total_feedback = SafetyFeedback.query.count()
    total_recordings = Recording.query.count()
    total_sos = SOSHistory.query.count()

    # AI recommendations using GroqService
    from app.services.groq_service import GroqService
    groq = GroqService()
    recommendations = groq.generate_admin_recommendations(danger_zones[:5])

    return jsonify({
        'avg_score': avg_score,
        'danger_zones': danger_zones,
        'total_reports': total_reports,
        'total_feedback': total_feedback,
        'total_recordings': total_recordings,
        'total_sos': total_sos,
        'report_stats': report_stats,
        'active_sos': SOSHistory.query.filter_by(status='active').count(),
        'active_shares': sum(1 for s in _live_locations.values() if s['status'] == 'active'),
        'recommendations': recommendations,
    })


# ═══════════════════════════════════════════════════════
# ADMIN DATA ACCESS (Item #17)
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/admin/feedback', methods=['GET'])
def admin_get_feedback():
    """Admin: get all feedback."""
    feedback = SafetyFeedback.query.order_by(SafetyFeedback.timestamp.desc()).all()
    return jsonify({'feedback': [f.to_dict() for f in feedback]})


@api_bp.route('/api/admin/incidents', methods=['GET'])
def admin_get_incidents():
    """Admin: get all incidents."""
    incidents = Incident.query.order_by(Incident.timestamp.desc()).all()
    return jsonify({'incidents': [i.to_dict() for i in incidents]})


@api_bp.route('/api/admin/sos', methods=['GET'])
def admin_get_sos():
    """Admin: get all SOS history."""
    sos_list = SOSHistory.query.order_by(SOSHistory.timestamp.desc()).all()
    return jsonify({'sos_history': [s.to_dict() for s in sos_list]})


# ═══════════════════════════════════════════════════════
# DATA STATUS
# ═══════════════════════════════════════════════════════

@api_bp.route('/api/data-status', methods=['GET'])
def get_data_status():
    optimizer = get_optimizer()
    pois = optimizer.pois
    graph = optimizer.graph
    poi_counts = {k: len(v) for k, v in pois.items() if v}
    return jsonify({
        'data_source': _data_source,
        'graph_stats': {'nodes': graph.number_of_nodes(), 'edges': graph.number_of_edges()},
        'poi_counts': poi_counts,
        'total_pois': sum(poi_counts.values()),
        'google_api_configured': bool(os.environ.get('GOOGLE_MAPS_API_KEY')),
        'city': os.environ.get('CITY_NAME', 'Jaipur'),
        'center': {
            'lat': float(os.environ.get('DEFAULT_LAT', '26.9124')),
            'lng': float(os.environ.get('DEFAULT_LNG', '75.7873')),
        },
        'database': {
            'zones': LocationZone.query.count(),
            'incidents': Incident.query.filter_by(status='active').count(),
            'feedback': SafetyFeedback.query.count(),
            'recordings': Recording.query.count(),
            'sos_events': SOSHistory.query.count(),
            'journeys': Journey.query.count(),
        },
    })


# ═══════════════════════════════════════════════════════
# HELPER FUNCTIONS (no more hardcoded values)
# ═══════════════════════════════════════════════════════

def _generate_safety_briefing(route, night=False, hour=12):
    """Generate a detailed AI safety briefing for the route."""
    score = route.get('safety_score', 50)
    time_min = route.get('time', 0)
    dist_km = route.get('distance', 0)
    route_type = route.get('type', 'recommended')

    if 6 <= hour < 12:
        time_context, crowd_expectation = "morning", "moderate foot traffic expected"
    elif 12 <= hour < 17:
        time_context, crowd_expectation = "afternoon", "good pedestrian activity"
    elif 17 <= hour < 21:
        time_context, crowd_expectation = "evening", "declining foot traffic as it gets dark"
    else:
        time_context, crowd_expectation = "night", "minimal foot traffic — stay alert"

    if score >= 80:
        safety_level = "HIGH"
        safety_advice = "This is a well-trafficked, well-lit route."
        tips = [
            "Stick to main roads — they're well-lit and have CCTV coverage",
            "Commercial areas along this route have shops that stay open late",
            "Police stations are within 500m of most points on this route",
        ]
    elif score >= 60:
        safety_level = "MODERATE"
        safety_advice = "This route is generally safe but has some stretches that may feel isolated."
        tips = [
            "Stay on well-lit sections and avoid shortcuts through alleys",
            "Keep your phone charged and share your live location with a trusted contact",
            "If you feel uncomfortable, duck into any open shop or restaurant",
        ]
    elif score >= 40:
        safety_level = "CAUTION"
        safety_advice = "This route passes through areas with mixed safety conditions."
        tips = [
            "Consider traveling with a companion if possible",
            "Share your live location with at least one guardian",
            "Keep emergency numbers (100, 1091) readily accessible",
        ]
    else:
        safety_level = "HIGH ALERT"
        safety_advice = "This route has significant safety concerns. Consider an alternative."
        tips = [
            "STRONGLY recommended to take the safer alternative route",
            "If you must use this route, travel with someone",
            "Share your live location and ETA with multiple contacts",
        ]

    return {
        'safety_level': safety_level, 'safety_score': score,
        'time_context': time_context, 'crowd_expectation': crowd_expectation,
        'advice': safety_advice, 'tips': tips,
        'route_type': route_type, 'distance_km': dist_km, 'time_min': time_min,
        'emergency_numbers': {'police': '100', 'ambulance': '108', 'emergency': '112', 'women_helpline': '1091'},
        'summary': (
            f"Safety Level: {safety_level} ({score}/100)\n"
            f"Time: {time_context.title()} — {crowd_expectation}\n"
            f"Distance: {dist_km} km | Duration: {time_min} min\n\n"
            f"{safety_advice}\n\n"
            f"Key Tips:\n" + "\n".join(f"• {t}" for t in tips)
        ),
    }


def _generate_explanation(route, night=False):
    """Generate AI-style explanation for the recommended route."""
    score = route.get('safety_score', 50)
    time_min = route.get('time', 0)
    dist_km = route.get('distance', 0)
    safety_ref = "nighttime safety" if night else "daytime safety"
    time_ref = "tonight" if night else "at this hour"

    if score >= 80:
        return (
            f"This route scores {score}/100 on {safety_ref}. "
            f"It passes through well-lit commercial roads with active shops and "
            f"good police station coverage. Estimated {time_min} min walk ({dist_km} km). "
            f"{'Well-lit main roads make this safe even after dark.' if night else 'This is a well-trafficked route with good visibility.'}"
        )
    elif score >= 60:
        return (
            f"This route scores {score}/100 on {safety_ref}. "
            f"A balanced path that prioritizes main roads while keeping travel time at "
            f"{time_min} min ({dist_km} km). "
            f"{'Stick to well-lit sections and stay aware of your surroundings.' if night else 'Generally safe with moderate foot traffic.'}"
        )
    else:
        return (
            f"This route scores {score}/100 on {safety_ref}. "
            f"While it's the fastest option at {time_min} min ({dist_km} km), "
            f"it passes through some isolated stretches. "
            f"{'Consider the safer alternative if traveling alone at night.' if night else 'Exercise normal caution on quieter stretches.'}"
        )
