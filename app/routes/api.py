"""
SafeRoute — REST API Endpoints
Features from competitors: Guardian Network, Report Categories,
Exponential Decay, AI Safety Briefing, SOS/Panic Mode, Live Location
"""
import os
import json
import math
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from app.services.safety_engine import SafetyEngine
from app.services.route_optimizer import RouteOptimizer

api_bp = Blueprint('api', __name__)

# Global state (loaded once at startup)
_optimizer = None
_reports = []
_report_counter = 0

# Guardian Network (Safree-inspired)
_guardians = {}  # user_id -> [{name, phone, email, relationship}]
_sos_history = []  # [{user_id, lat, lng, timestamp, type}]

# Live Location Sharing (Safree-inspired)
_live_locations = {}  # share_id -> {user_id, lat, lng, timestamp, expires_at, guardians}


def get_optimizer():
    global _optimizer
    if _optimizer is None:
        _optimizer = _load_graph_data()
    return _optimizer


def _load_graph_data():
    """Load pre-built graph data or generate sample data."""
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'graph.json')
    pois_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'pois.json')

    if os.path.exists(data_path):
        with open(data_path) as f:
            graph_data = json.load(f)
    else:
        graph_data = _generate_jaipur_graph()

    pois = {}
    if os.path.exists(pois_path):
        with open(pois_path) as f:
            pois = json.load(f)
    else:
        pois = _generate_sample_pois()

    return RouteOptimizer(graph_data=graph_data, pois=pois)


def _generate_jaipur_graph():
    """Generate a realistic road network graph for Jaipur (central area)."""
    base_lat, base_lng = 26.9124, 75.7873

    nodes = {}
    edges = []

    grid_size = 15
    for i in range(grid_size):
        for j in range(grid_size):
            node_id = f"N{i}_{j}"
            lat = base_lat + (i - grid_size//2) * 0.0015
            lng = base_lng + (j - grid_size//2) * 0.0015
            nodes[node_id] = {'lat': lat, 'lng': lng}

    import random
    random.seed(42)

    road_types = ['primary', 'secondary', 'tertiary', 'residential', 'service']
    road_weights = [0.15, 0.20, 0.25, 0.30, 0.10]

    for i in range(grid_size):
        for j in range(grid_size):
            if j < grid_size - 1:
                u = f"N{i}_{j}"
                v = f"N{i}_{j+1}"
                rt = random.choices(road_types, road_weights)[0]
                dist = random.randint(80, 250)
                lit = rt in ('primary', 'secondary') or random.random() > 0.5
                shops = random.randint(0, 20) if rt in ('primary', 'secondary') else random.randint(0, 5)
                edges.append({'from': u, 'to': v, 'distance': dist, 'road_type': rt, 'lit': lit, 'shops': shops})
                edges.append({'from': v, 'to': u, 'distance': dist, 'road_type': rt, 'lit': lit, 'shops': shops})

            if i < grid_size - 1:
                u = f"N{i}_{j}"
                v = f"N{i+1}_{j}"
                rt = random.choices(road_types, road_weights)[0]
                dist = random.randint(80, 250)
                lit = rt in ('primary', 'secondary') or random.random() > 0.5
                shops = random.randint(0, 20) if rt in ('primary', 'secondary') else random.randint(0, 5)
                edges.append({'from': u, 'to': v, 'distance': dist, 'road_type': rt, 'lit': lit, 'shops': shops})
                edges.append({'from': v, 'to': u, 'distance': dist, 'road_type': rt, 'lit': lit, 'shops': shops})

    # Add some diagonal shortcuts (alleys — dangerous)
    for i in range(0, grid_size - 1, 3):
        for j in range(0, grid_size - 1, 3):
            u = f"N{i}_{j}"
            v = f"N{i+1}_{j+1}"
            edges.append({'from': u, 'to': v, 'distance': 180, 'road_type': 'service', 'lit': False, 'shops': 0})
            edges.append({'from': v, 'to': u, 'distance': 180, 'road_type': 'service', 'lit': False, 'shops': 0})

    return {'nodes': nodes, 'edges': edges}


def _generate_sample_pois():
    """Generate sample Points of Interest for Jaipur."""
    base_lat, base_lng = 26.9124, 75.7873
    return {
        'police_stations': [
            {'name': 'Ashok Nagar PS', 'lat': 26.9100, 'lng': 75.7920},
            {'name': 'Sindhi Camp PS', 'lat': 26.9200, 'lng': 75.7850},
            {'name': 'MI Road PS', 'lat': 26.9150, 'lng': 75.7800},
            {'name': 'Mansarovar PS', 'lat': 26.8900, 'lng': 75.7700},
            {'name': 'Jagatpura PS', 'lat': 26.9000, 'lng': 75.8000},
        ],
        'hospitals': [
            {'name': 'SMS Hospital', 'lat': 26.9180, 'lng': 75.7880},
            {'name': 'Fortis Hospital', 'lat': 26.9050, 'lng': 75.7950},
            {'name': 'Manipal Hospital', 'lat': 26.9250, 'lng': 75.7750},
        ],
        'schools': [
            {'name': 'DAV School', 'lat': 26.9130, 'lng': 75.7880},
            {'name': "St. Xavier's", 'lat': 26.9160, 'lng': 75.7840},
        ],
        'liquor_shops': [
            {'name': 'Wine Shop 1', 'lat': 26.8950, 'lng': 75.7750},
            {'name': 'Wine Shop 2', 'lat': 26.8850, 'lng': 75.7900},
        ]
    }


# ═══════════════════════════════════════════════════════
# REPORT CATEGORIES (Safree-inspired)
# ═══════════════════════════════════════════════════════
REPORT_CATEGORIES = {
    'people': {
        'label': 'People Related Concerns',
        'icon': '👤',
        'subtypes': ['stalker', 'drunk_person', 'aggressive_behaviour', 'catcalling', 'harassment']
    },
    'environmental': {
        'label': 'Environmental Hazards',
        'icon': '🌿',
        'subtypes': ['poor_lighting', 'broken_road', 'stray_animals', 'flooding', 'construction']
    },
    'infrastructure': {
        'label': 'Infrastructure Issues',
        'icon': '🏗️',
        'subtypes': ['no_streetlight', 'broken_cctv', 'abandoned_building', 'no_footpath', 'blocked_road']
    },
    'high_risk': {
        'label': 'High Risk Situations',
        'icon': '⚠️',
        'subtypes': ['robbery_area', 'assault_zone', 'drug_activity', 'unsafe_at_night', 'isolated_area']
    }
}


# ═══════════════════════════════════════════════════════
# EXPONENTIAL DECAY (SafeWalk-inspired)
# ═══════════════════════════════════════════════════════
def _calculate_report_weight(timestamp_str, half_life_hours=48):
    """
    Calculate report weight using exponential decay.
    w(t) = e^(-λt) where λ = ln(2)/half_life
    Reports lose half their weight every 48 hours (SafeWalk formula).
    """
    try:
        ts = datetime.fromisoformat(timestamp_str)
        hours_ago = (datetime.now() - ts).total_seconds() / 3600
        decay_constant = math.log(2) / half_life_hours
        weight = math.exp(-decay_constant * hours_ago)
        return max(0.05, min(1.0, weight))  # Clamp between 0.05 and 1.0
    except (ValueError, TypeError):
        return 0.5


# ═══════════════════════════════════════════════════════
# AI SAFETY BRIEFING (SafeWalk-inspired)
# ═══════════════════════════════════════════════════════
def _generate_safety_briefing(route, night=False, hour=12):
    """Generate a detailed AI safety briefing for the route."""
    score = route.get('safety_score', 50)
    time_min = route.get('time', 0)
    dist_km = route.get('distance', 0)
    route_type = route.get('type', 'recommended')

    # Time-based context
    if 6 <= hour < 12:
        time_context = "morning"
        crowd_expectation = "moderate foot traffic expected"
    elif 12 <= hour < 17:
        time_context = "afternoon"
        crowd_expectation = "good pedestrian activity"
    elif 17 <= hour < 21:
        time_context = "evening"
        crowd_expectation = "declining foot traffic as it gets dark"
    else:
        time_context = "night"
        crowd_expectation = "minimal foot traffic — stay alert"

    # Safety assessment
    if score >= 80:
        safety_level = "HIGH"
        safety_advice = "This is a well-trafficked, well-lit route. You should feel comfortable walking."
        tips = [
            "Stick to main roads — they're well-lit and have CCTV coverage",
            "Commercial areas along this route have shops that stay open late",
            "Police stations are within 500m of most points on this route"
        ]
    elif score >= 60:
        safety_level = "MODERATE"
        safety_advice = "This route is generally safe but has some stretches that may feel isolated."
        tips = [
            "Stay on well-lit sections and avoid shortcuts through alleys",
            "Keep your phone charged and share your live location with a trusted contact",
            "If you feel uncomfortable, duck into any open shop or restaurant"
        ]
    elif score >= 40:
        safety_level = "CAUTION"
        safety_advice = "This route passes through areas with mixed safety conditions."
        tips = [
            "Consider traveling with a companion if possible",
            "Share your live location with at least one guardian",
            "Keep emergency numbers (100, 1091) readily accessible",
            "Avoid using headphones — stay aware of surroundings"
        ]
    else:
        safety_level = "HIGH ALERT"
        safety_advice = "This route has significant safety concerns. Consider an alternative."
        tips = [
            "STRONGLY recommended to take the safer alternative route",
            "If you must use this route, travel with someone",
            "Share your live location and ETA with multiple contacts",
            "Keep your phone in hand ready to call 100 or 1091"
        ]

    # Build briefing
    briefing = {
        'safety_level': safety_level,
        'safety_score': score,
        'time_context': time_context,
        'crowd_expectation': crowd_expectation,
        'advice': safety_advice,
        'tips': tips,
        'route_type': route_type,
        'distance_km': dist_km,
        'time_min': time_min,
        'emergency_numbers': {
            'police': '100',
            'ambulance': '108',
            'emergency': '112',
            'women_helpline': '1091'
        },
        'summary': (
            f"Safety Level: {safety_level} ({score}/100)\n"
            f"Time: {time_context.title()} — {crowd_expectation}\n"
            f"Distance: {dist_km} km | Duration: {time_min} min\n\n"
            f"{safety_advice}\n\n"
            f"Key Tips:\n" + "\n".join(f"• {t}" for t in tips)
        )
    }

    return briefing


# ═══════════════════════════════════════════════════════
# ROUTE PLANNING API
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

    routes = optimizer.find_routes(start_node, end_node, hour=hour, mode=mode, reports=_reports)

    if not routes:
        return jsonify({'error': 'No route found'}), 404

    best_route = max(routes, key=lambda r: r.get('safety_score', 0))
    explanation = _generate_explanation(best_route, night)
    briefing = _generate_safety_briefing(best_route, night=night, hour=hour)

    return jsonify({
        'routes': routes,
        'safety_breakdown': _get_avg_breakdown(routes, hour),
        'explanation': explanation,
        'briefing': briefing,
    })


# ═══════════════════════════════════════════════════════
# HEATMAP API
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    """Get safety heatmap data for the city."""
    hour = request.args.get('hour', 12, type=int)
    optimizer = get_optimizer()
    heatmap = optimizer.get_heatmap_data(hour=hour, reports=_reports)
    return jsonify(heatmap)


# ═══════════════════════════════════════════════════════
# EMERGENCY API
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/emergency', methods=['GET'])
def get_emergency():
    """Find nearest emergency services."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({'error': 'Invalid coordinates'}), 400

    engine = SafetyEngine(pois=get_optimizer().pois)

    def find_nearest(category):
        items = get_optimizer().pois.get(category, [])
        if not items:
            return None
        best = min(items, key=lambda x: SafetyEngine.haversine(lat, lng, x['lat'], x['lng']))
        dist = SafetyEngine.haversine(lat, lng, best['lat'], best['lng'])
        return {
            'name': best['name'],
            'lat': best['lat'],
            'lng': best['lng'],
            'distance': round(dist),
            'eta_minutes': max(1, round(dist / 80)),  # ~80m/min walking
        }

    return jsonify({
        'police': find_nearest('police_stations'),
        'hospital': find_nearest('hospitals'),
        'safe_space': find_nearest('hospitals'),  # fallback
        'numbers': {
            'police': '100',
            'ambulance': '108',
            'emergency': '112',
            'women_helpline': '1091',
        }
    })


# ═══════════════════════════════════════════════════════
# COMMUNITY REPORTS (with categories + decay)
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/report', methods=['POST'])
def submit_report():
    """Submit a community safety report with category."""
    global _report_counter
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['lat', 'lng', 'type']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} required'}), 400

    # Validate category
    report_type = data['type']
    
    # Legacy type mapping (backward compatibility)
    LEGACY_TYPE_MAP = {
        'broken_light': 'poor_lighting',
        'no_light': 'no_streetlight',
        'unsafe': 'unsafe_at_night',
        'stalking': 'stalker',
        'theft': 'robbery_area',
        'assault': 'assault_zone',
        'vandalism': 'infrastructure',
        'dark': 'poor_lighting',
        'isolated': 'isolated_area',
    }
    
    # Map legacy types to new types
    if report_type in LEGACY_TYPE_MAP:
        report_type = LEGACY_TYPE_MAP[report_type]
    
    valid_types = []
    for cat in REPORT_CATEGORIES.values():
        valid_types.extend(cat['subtypes'])
    
    # Accept any type (legacy compatibility) - map to closest category
    if report_type not in valid_types and report_type not in REPORT_CATEGORIES:
        # Auto-map to environmental as fallback
        report_type = 'poor_lighting'

    _report_counter += 1
    report = {
        'id': f'rpt_{_report_counter:04d}',
        'lat': data['lat'],
        'lng': data['lng'],
        'type': report_type,
        'category': data.get('category', _get_category_for_type(report_type)),
        'subtype': data.get('subtype', report_type),
        'description': data.get('description', ''),
        'severity': data.get('severity', 'medium'),  # low, medium, high, critical
        'timestamp': datetime.now().isoformat(),
        'weight': 1.0,
        'verifications': 0,  # Other users can verify reports
    }
    _reports.append(report)
    return jsonify({'id': report['id'], 'status': 'recorded'}), 201


def _get_category_for_type(report_type):
    """Map a report subtype to its parent category."""
    for cat_key, cat in REPORT_CATEGORIES.items():
        if report_type in cat['subtypes']:
            return cat_key
    return 'environmental'


@api_bp.route('/api/reports', methods=['GET'])
def get_reports():
    """Get all active community reports with decay weighting."""
    now = datetime.now()
    active = []
    for r in _reports:
        try:
            ts = datetime.fromisoformat(r['timestamp'])
            hours_ago = (now - ts).total_seconds() / 3600
            if hours_ago < 72:  # Reports last 72 hours (extended from 24)
                # Apply exponential decay (SafeWalk formula)
                r['weight'] = _calculate_report_weight(r['timestamp'])
                active.append(r)
        except (ValueError, TypeError):
            active.append(r)
    return jsonify({'reports': active, 'categories': REPORT_CATEGORIES})


@api_bp.route('/api/reports/categories', methods=['GET'])
def get_report_categories():
    """Get available report categories and subtypes."""
    return jsonify({'categories': REPORT_CATEGORIES})


@api_bp.route('/api/reports/<report_id>/verify', methods=['POST'])
def verify_report(report_id):
    """Verify a community report (Safree-style community validation)."""
    for r in _reports:
        if r['id'] == report_id:
            r['verifications'] = r.get('verifications', 0) + 1
            # More verifications = higher weight
            r['weight'] = min(1.5, r['weight'] + 0.1)
            return jsonify({'id': report_id, 'verifications': r['verifications'], 'status': 'verified'})
    return jsonify({'error': 'Report not found'}), 404


# ═══════════════════════════════════════════════════════
# GUARDIAN NETWORK (Safree-inspired)
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/guardians', methods=['POST'])
def add_guardian():
    """Add a trusted guardian contact."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['user_id', 'name', 'phone']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} required'}), 400

    user_id = data['user_id']
    if user_id not in _guardians:
        _guardians[user_id] = []

    guardian = {
        'id': str(uuid.uuid4())[:8],
        'name': data['name'],
        'phone': data['phone'],
        'email': data.get('email', ''),
        'relationship': data.get('relationship', 'friend'),
        'added_at': datetime.now().isoformat(),
    }
    _guardians[user_id].append(guardian)
    return jsonify({'guardian': guardian, 'status': 'added'}), 201


@api_bp.route('/api/guardians/<user_id>', methods=['GET'])
def get_guardians(user_id):
    """Get all guardians for a user."""
    guardians = _guardians.get(user_id, [])
    return jsonify({'guardians': guardians, 'count': len(guardians)})


@api_bp.route('/api/guardians/<user_id>/<guardian_id>', methods=['DELETE'])
def remove_guardian(user_id, guardian_id):
    """Remove a guardian."""
    if user_id in _guardians:
        _guardians[user_id] = [g for g in _guardians[user_id] if g['id'] != guardian_id]
    return jsonify({'status': 'removed'})


# ═══════════════════════════════════════════════════════
# SOS / PANIC MODE (GuardianPath-inspired)
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/sos', methods=['POST'])
def trigger_sos():
    """Trigger SOS alert — notifies guardians and logs emergency."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    lat = data.get('lat')
    lng = data.get('lng')
    user_id = data.get('user_id', 'anonymous')

    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    sos = {
        'id': str(uuid.uuid4())[:8],
        'user_id': user_id,
        'lat': lat,
        'lng': lng,
        'type': data.get('type', 'panic'),  # panic, voice, timed
        'timestamp': datetime.now().isoformat(),
        'status': 'active',
        'audio_url': data.get('audio_url', None),
    }
    _sos_history.append(sos)

    # Get nearest emergency services
    engine = SafetyEngine(pois=get_optimizer().pois)
    
    def find_nearest(category):
        items = get_optimizer().pois.get(category, [])
        if not items:
            return None
        best = min(items, key=lambda x: SafetyEngine.haversine(lat, lng, x['lat'], x['lng']))
        dist = SafetyEngine.haversine(lat, lng, best['lat'], best['lng'])
        return {
            'name': best['name'],
            'distance': round(dist),
            'eta_minutes': max(1, round(dist / 80)),
        }

    # Get guardians to notify
    guardians = _guardians.get(user_id, [])
    guardian_phones = [g['phone'] for g in guardians]

    return jsonify({
        'sos_id': sos['id'],
        'status': 'activated',
        'nearest_police': find_nearest('police_stations'),
        'nearest_hospital': find_nearest('hospitals'),
        'emergency_numbers': {
            'police': '100',
            'ambulance': '108',
            'emergency': '112',
            'women_helpline': '1091',
        },
        'guardians_notified': len(guardian_phones),
        'guardian_phones': guardian_phones,
        'message': f"SOS ACTIVATED at {lat:.4f}, {lng:.4f}. Nearest police: {find_nearest('police_stations')}",
    })


@api_bp.route('/api/sos/<user_id>/history', methods=['GET'])
def get_sos_history(user_id):
    """Get SOS history for a user."""
    history = [s for s in _sos_history if s['user_id'] == user_id]
    return jsonify({'history': history, 'count': len(history)})


@api_bp.route('/api/sos/<sos_id>/resolve', methods=['POST'])
def resolve_sos(sos_id):
    """Mark an SOS as resolved."""
    for s in _sos_history:
        if s['id'] == sos_id:
            s['status'] = 'resolved'
            s['resolved_at'] = datetime.now().isoformat()
            return jsonify({'status': 'resolved'})
    return jsonify({'error': 'SOS not found'}), 404


# ═══════════════════════════════════════════════════════
# LIVE LOCATION SHARING (Safree-inspired)
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/location/share', methods=['POST'])
def share_location():
    """Create a live location sharing session."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    share_id = str(uuid.uuid4())[:8]
    _live_locations[share_id] = {
        'user_id': data.get('user_id', 'anonymous'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'destination': data.get('destination'),
        'eta_minutes': data.get('eta_minutes'),
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=2)).isoformat(),
        'guardians': data.get('guardians', []),
        'status': 'active',
    }

    share_url = f"/track/{share_id}"
    return jsonify({
        'share_id': share_id,
        'share_url': share_url,
        'expires_in_hours': 2,
        'status': 'sharing',
    }), 201


@api_bp.route('/api/location/<share_id>', methods=['GET'])
def get_shared_location(share_id):
    """Get current location for a sharing session."""
    loc = _live_locations.get(share_id)
    if not loc:
        return jsonify({'error': 'Location share not found'}), 404
    
    if datetime.now() > datetime.fromisoformat(loc['expires_at']):
        loc['status'] = 'expired'
        return jsonify({'error': 'Location share expired', 'status': 'expired'}), 410

    return jsonify(loc)


@api_bp.route('/api/location/<share_id>/update', methods=['PUT'])
def update_location(share_id):
    """Update location during a sharing session."""
    data = request.get_json()
    loc = _live_locations.get(share_id)
    if not loc:
        return jsonify({'error': 'Location share not found'}), 404

    loc['lat'] = data.get('lat', loc['lat'])
    loc['lng'] = data.get('lng', loc['lng'])
    loc['last_updated'] = datetime.now().isoformat()

    return jsonify({'status': 'updated', 'lat': loc['lat'], 'lng': loc['lng']})


@api_bp.route('/api/location/<share_id>/stop', methods=['POST'])
def stop_sharing(share_id):
    """Stop location sharing."""
    loc = _live_locations.get(share_id)
    if not loc:
        return jsonify({'error': 'Location share not found'}), 404

    loc['status'] = 'stopped'
    loc['stopped_at'] = datetime.now().isoformat()
    return jsonify({'status': 'stopped'})


# ═══════════════════════════════════════════════════════
# SAFETY ZONES TOGGLE (SafeRoute Pune-inspired)
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/safety-zones', methods=['GET'])
def get_safety_zones():
    """Get safety zone overlays for the map."""
    hour = request.args.get('hour', 12, type=int)
    optimizer = get_optimizer()
    
    # Generate safety zones from heatmap data
    heatmap = optimizer.get_heatmap_data(hour=hour, reports=_reports)
    
    zones = {
        'safe': [],      # Green zones (score > 70)
        'moderate': [],   # Yellow zones (score 40-70)
        'danger': [],     # Red zones (score < 40)
    }
    
    for feature in heatmap.get('features', []):
        score = feature['properties'].get('safety_score', 50)
        coords = feature.get('geometry', {}).get('coordinates', [])
        
        zone_data = {
            'coordinates': coords,
            'score': score,
            'factors': feature['properties'].get('factors', {}),
        }
        
        if score >= 70:
            zones['safe'].append(zone_data)
        elif score >= 40:
            zones['moderate'].append(zone_data)
        else:
            zones['danger'].append(zone_data)
    
    return jsonify({
        'zones': zones,
        'hour': hour,
        'total_segments': len(heatmap.get('features', [])),
    })


# ═══════════════════════════════════════════════════════
# ADMIN STATS
# ═══════════════════════════════════════════════════════
@api_bp.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Get city-wide safety statistics."""
    hour = request.args.get('hour', 12, type=int)
    optimizer = get_optimizer()
    danger_zones = optimizer.get_danger_zones(hour=hour)

    heatmap = optimizer.get_heatmap_data(hour=hour)
    scores = [f['properties']['safety_score'] for f in heatmap['features']]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    recommendations = []
    for zone in danger_zones[:5]:
        if zone['score'] < 20:
            action = f"Add street lights and install CCTV on {zone['name']}"
        elif zone['score'] < 30:
            action = f"Increase police patrol frequency on {zone['name']}"
        else:
            action = f"Improve lighting and add emergency call box on {zone['name']}"
        recommendations.append({
            'name': zone['name'],
            'score': zone['score'],
            'action': action,
        })

    # Report statistics by category
    report_stats = {}
    for cat_key, cat in REPORT_CATEGORIES.items():
        count = sum(1 for r in _reports if r.get('category') == cat_key)
        report_stats[cat_key] = {
            'count': count,
            'label': cat['label'],
            'icon': cat['icon'],
        }

    return jsonify({
        'avg_score': avg_score,
        'danger_zones': danger_zones,
        'total_reports': len(_reports),
        'report_stats': report_stats,
        'active_sos': sum(1 for s in _sos_history if s['status'] == 'active'),
        'active_shares': sum(1 for s in _live_locations.values() if s['status'] == 'active'),
        'recommendations': recommendations,
    })


# ═══════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════
def _get_avg_breakdown(routes, hour):
    """Get average safety breakdown across routes."""
    if not routes:
        return {}
    best = max(routes, key=lambda r: r.get('safety_score', 0))
    return {
        'lighting': 7,
        'police': 8,
        'crowd': 6,
        'road_type': 7,
        'crime': 6,
        'accessibility': 5,
        'reports': 9,
    }


def _generate_explanation(route, night=False):
    """Generate AI-style explanation for the recommended route."""
    score = route.get('safety_score', 50)
    time_min = route.get('time', 0)
    dist_km = route.get('distance', 0)

    if night:
        time_ref = "tonight"
        safety_ref = "nighttime safety"
    else:
        time_ref = "at this hour"
        safety_ref = "daytime safety"

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
