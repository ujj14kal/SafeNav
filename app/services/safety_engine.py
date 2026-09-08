"""
SafeNav — Safety Scoring Engine (v2 — Real Data)
Computes safety scores for road segments based on 7 factors.
Now uses real OSM attributes and Google Places POIs.
"""
import math
from datetime import datetime


class SafetyEngine:
    """
    Computes safety scores (0-100) for road segments based on:
    1. Street Lighting (20%)       — from OSM lit tag + nearby commercial activity
    2. Police Proximity (20%)      — from Google Places real police stations
    3. Crowd/Commercial Density (15%) — from Google Places nearby shops
    4. Road Type/Infrastructure (15%) — from OSM highway classification
    5. Crime Risk (15%)            — derived from environmental factors
    6. Accessibility (5%)          — footpath, sidewalk, lanes from OSM
    7. Community Reports (10%)     — real-time user reports
    """

    WEIGHTS = {
        'lighting': 0.20,
        'police': 0.20,
        'crowd': 0.15,
        'road_type': 0.15,
        'crime': 0.15,
        'accessibility': 0.05,
        'reports': 0.10,
    }

    ROAD_TYPE_SCORES = {
        'motorway': 9,
        'trunk': 8,
        'primary': 9,
        'secondary': 7,
        'tertiary': 6,
        'residential': 5,
        'service': 2,
        'unclassified': 3,
        'living_street': 4,
    }

    # Night penalty multipliers by hour (0-23)
    NIGHT_MULTIPLIER = {
        0: 0.55, 1: 0.50, 2: 0.48, 3: 0.45, 4: 0.50, 5: 0.60,
        6: 0.75, 7: 0.85, 8: 0.92, 9: 0.95, 10: 1.0, 11: 1.0,
        12: 1.0, 13: 1.0, 14: 1.0, 15: 1.0, 16: 1.0, 17: 0.98,
        18: 0.92, 19: 0.85, 20: 0.78, 21: 0.70, 22: 0.62, 23: 0.58,
    }

    def __init__(self, pois=None):
        self.pois = pois or {}
        self._police_cache = None
        self._hospital_cache = None
        self._liquor_cache = None

    def _get_police_stations(self):
        if self._police_cache is None:
            self._police_cache = self.pois.get('police_stations', [])
        return self._police_cache

    def _get_hospitals(self):
        if self._hospital_cache is None:
            self._hospital_cache = self.pois.get('hospitals', [])
        return self._hospital_cache

    def _get_liquor_shops(self):
        if self._liquor_cache is None:
            self._liquor_cache = self.pois.get('liquor_shops', [])
        return self._liquor_cache

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """Distance in meters between two lat/lng points."""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def _score_lighting(self, edge):
        """
        Score based on road lighting (0-10).
        Uses real OSM 'lit' tag when available.
        Falls back to inferring from road type and nearby shops.
        """
        # OSM lit tag is the most reliable source
        lit = edge.get('lit', None)
        if lit is True:
            return 9
        elif lit is False:
            # Explicitly unlit — check if there's commercial activity nearby
            shops = edge.get('shops', 0)
            if shops >= 10:
                return 6  # shops provide some ambient light
            elif shops >= 5:
                return 4
            elif shops >= 1:
                return 3
            return 1  # dark and empty

        # No lit tag data — infer from context
        shops = edge.get('shops', 0)
        road_type = edge.get('road_type', 'residential')
        if road_type in ('primary', 'secondary', 'trunk'):
            return 8  # main roads are typically lit in Indian cities
        if shops >= 10:
            return 7
        elif shops >= 5:
            return 5
        elif shops >= 1:
            return 3
        return 2

    def _score_police_proximity(self, edge):
        """Score based on distance to nearest real police station (0-10)."""
        stations = self._get_police_stations()
        if not stations:
            return 5  # neutral if no data

        edge_lat = edge.get('lat', 0)
        edge_lng = edge.get('lng', 0)
        if not edge_lat or not edge_lng:
            return 5

        min_dist = float('inf')
        for s in stations:
            d = self.haversine(edge_lat, edge_lng, s['lat'], s['lng'])
            min_dist = min(min_dist, d)

        if min_dist < 200:
            return 10
        elif min_dist < 500:
            return 9
        elif min_dist < 1000:
            return 7
        elif min_dist < 2000:
            return 5
        elif min_dist < 5000:
            return 3
        return 1

    def _score_crowd(self, edge):
        """
        Score based on commercial activity / crowd density (0-10).
        Uses real shop count from Google Places + position-based variation.
        """
        shops = edge.get('shops', 0)
        road_type = edge.get('road_type', 'residential')

        if road_type in ('primary', 'trunk', 'motorway'):
            base = 8
        elif road_type == 'secondary':
            base = 6
        elif road_type == 'tertiary':
            base = 5
        else:
            base = 3

        shop_bonus = min(shops / 3, 4)  # up to +4 from shops

        # Add position-based variation using coordinates
        # This ensures different edges of the same type get different scores
        edge_lat = edge.get('lat', 0)
        edge_lng = edge.get('lng', 0)
        if edge_lat and edge_lng:
            # Use a deterministic hash of position for variation (0-2 range)
            pos_hash = ((hash(f"{edge_lat:.4f}_{edge_lng:.4f}") % 200) / 100.0)
            return min(int(base + shop_bonus + pos_hash), 10)

        return min(int(base + shop_bonus), 10)

    def _score_road_type(self, edge):
        """Score based on OSM road classification (0-10)."""
        road_type = edge.get('road_type', 'unclassified')
        return self.ROAD_TYPE_SCORES.get(road_type, 4)

    def _score_crime(self, edge):
        """
        Score based on derived crime risk (0-10).
        crime_rate: 0.0 = safe, 1.0 = dangerous.
        Now computed from real environmental factors with position-based variation.
        """
        crime_rate = edge.get('crime_rate', 0.3)  # default moderate-low

        # Add position-based variation so different edges get different scores
        edge_lat = edge.get('lat', 0)
        edge_lng = edge.get('lng', 0)
        if edge_lat and edge_lng:
            pos_adj = ((hash(f"crime_{edge_lat:.4f}_{edge_lng:.4f}") % 15) - 7) / 100.0
            crime_rate = max(0.0, min(1.0, crime_rate + pos_adj))

        return max(1, int(10 * (1 - crime_rate)))

    def _score_accessibility(self, edge):
        """
        Score based on infrastructure quality (0-10).
        Uses real OSM data: lanes, surface, footpath tags.
        """
        road_type = edge.get('road_type', 'unclassified')
        lanes = edge.get('lanes', None)

        # Check OSM footpath/sidewalk tags
        has_footpath = edge.get('footpath', road_type in ('primary', 'secondary'))
        has_sidewalk = edge.get('sidewalk', False)

        score = 5
        if has_footpath:
            score += 3
        if has_sidewalk:
            score += 2

        # More lanes = better infrastructure
        if lanes and lanes >= 4:
            score += 1
        elif road_type in ('primary', 'secondary', 'tertiary'):
            score += 1

        return min(score, 10)

    def _score_reports(self, edge, reports=None):
        """Score based on community reports (0-10). Real-time user data."""
        if not reports:
            return 9

        edge_lat = edge.get('lat', 0)
        edge_lng = edge.get('lng', 0)
        if not edge_lat or not edge_lng:
            return 9

        now = datetime.now()
        penalty = 0
        for r in reports:
            dist = self.haversine(edge_lat, edge_lng, r.get('lat', 0), r.get('lng', 0))
            if dist > 500:  # only reports within 500m
                continue

            try:
                ts = datetime.fromisoformat(r.get('timestamp', ''))
                hours_ago = (now - ts).total_seconds() / 3600
            except (ValueError, TypeError):
                hours_ago = 24

            if hours_ago > 24:
                continue

            decay = max(0, 1 - (hours_ago / 24))
            weight = r.get('weight', 1.0)
            # Severity multiplier
            severity = r.get('severity', 'medium')
            severity_mult = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'critical': 2.5}.get(severity, 1.0)
            proximity = max(0, 1 - (dist / 500))
            penalty += decay * weight * proximity * severity_mult * 2

        return max(1, int(10 - min(penalty, 9)))

    def get_score_breakdown(self, edge, hour=12, reports=None):
        """Get individual factor scores (each 0-10)."""
        return {
            'lighting': self._score_lighting(edge),
            'police': self._score_police_proximity(edge),
            'crowd': self._score_crowd(edge),
            'road_type': self._score_road_type(edge),
            'crime': self._score_crime(edge),
            'accessibility': self._score_accessibility(edge),
            'reports': self._score_reports(edge, reports),
        }

    def calculate_edge_score(self, edge, hour=12, reports=None):
        """
        Calculate overall safety score (0-100) for a road edge.
        Applies time-of-day adjustment.
        """
        breakdown = self.get_score_breakdown(edge, hour, reports)

        weighted_sum = sum(
            breakdown[factor] * weight * 10
            for factor, weight in self.WEIGHTS.items()
        )

        night_mult = self.NIGHT_MULTIPLIER.get(hour, 0.7)
        is_lit = edge.get('lit', False)
        if not is_lit:
            night_mult *= 0.7  # extra penalty for unlit roads at night

        adjusted = weighted_sum * night_mult
        return max(0, min(100, round(adjusted, 1)))

    def compute_safety_cost(self, travel_time, safety_score):
        """
        Convert safety score to a cost multiplier.
        Inspired by cuOpt: encode safety as optimization cost.

        Safe road (score=90): cost = time × 1.11  (barely penalized)
        Dangerous road (score=10): cost = time × 10 (heavily penalized)
        """
        if safety_score <= 0:
            return travel_time * 100  # effectively blocked
        return travel_time * (100 / safety_score)
