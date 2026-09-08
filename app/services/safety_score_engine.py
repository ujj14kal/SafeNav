"""
SafeRoute — Centralized Safety Score Engine (v3)
Single source of truth for ALL safety calculations across the app.

Formula: base_score + feedback_adjustment + time_of_day_factor + incident_penalty
Produces DIFFERENT scores for different locations and times of day.
Returns {"score": None, "reason": "Insufficient data"} when data is lacking.
"""
import math
from datetime import datetime, timedelta
from app.models.database import (
    db, LocationZone, Incident, SafetyFeedback,
)


class SafetyScoreEngine:
    """
    Centralized safety scoring engine.
    All safety calculations in the app MUST go through this engine
    to ensure data consistency across dashboard, map, heatmap, and routes.
    """

    # Night penalty multipliers by hour (0-23)
    NIGHT_MULTIPLIER = {
        0: 0.55, 1: 0.50, 2: 0.48, 3: 0.45, 4: 0.50, 5: 0.60,
        6: 0.75, 7: 0.85, 8: 0.92, 9: 0.95, 10: 1.0, 11: 1.0,
        12: 1.0, 13: 1.0, 14: 1.0, 15: 1.0, 16: 1.0, 17: 0.98,
        18: 0.92, 19: 0.85, 20: 0.78, 21: 0.70, 22: 0.62, 23: 0.58,
    }

    # Factor weights
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
        'motorway': 9, 'trunk': 8, 'primary': 9,
        'secondary': 7, 'tertiary': 6, 'residential': 5,
        'service': 2, 'unclassified': 3, 'living_street': 4,
    }

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """Distance in meters between two lat/lng points."""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @classmethod
    def get_location_score(cls, lat, lng, hour=12, radius_m=500):
        """
        Get safety score for a specific lat/lng at a specific hour.
        Uses DB data: zones, incidents, feedback.
        Returns dict with 'score', 'breakdown', 'data_source', 'zone_name'.
        Returns {"score": None, "reason": "..."} when insufficient data.
        """
        # Find the closest zone
        zone = cls._find_nearest_zone(lat, lng, radius_m)

        if zone is None:
            # No zone data at all — check if we have any incident data nearby
            nearby_incidents = cls._get_nearby_incidents(lat, lng, radius_m=1000)
            if not nearby_incidents:
                return {
                    'score': None,
                    'reason': 'Insufficient data for this location',
                    'breakdown': {},
                    'data_source': 'none',
                    'zone_name': None,
                }
            # We have incident data but no zone — derive from incidents only
            return cls._score_from_incidents_only(lat, lng, nearby_incidents, hour)

        # We have a zone — compute score from zone + incidents + feedback
        return cls._score_from_zone(lat, lng, zone, hour)

    @classmethod
    def get_route_breakdown(cls, coordinates, hour=12):
        """
        Get safety breakdown for a route (list of [lat, lng] coords).
        Averages the breakdown across sampled points along the route.
        Returns dict of factor scores (0-10 scale) and data_source indicator.
        """
        if not coordinates:
            return {
                'breakdown': {},
                'data_source': 'none',
                'report_count': 0,
                'total_points': 0,
            }

        # Sample up to 10 points along the route
        step = max(1, len(coordinates) // 10)
        sampled = coordinates[::step]
        if coordinates[-1] not in sampled:
            sampled.append(coordinates[-1])

        factor_sums = {
            'lighting': 0, 'police': 0, 'crowd': 0,
            'road_type': 0, 'crime': 0, 'accessibility': 0, 'reports': 0,
        }
        valid_points = 0
        total_feedback = 0
        total_incidents = 0

        for coord in sampled:
            lat, lng = coord[0], coord[1]
            result = cls.get_location_score(lat, lng, hour=hour)
            if result.get('score') is not None and result.get('breakdown'):
                for key in factor_sums:
                    if key in result['breakdown'] and result['breakdown'][key] is not None:
                        factor_sums[key] += result['breakdown'][key]
                valid_points += 1
            # Count nearby data
            total_feedback += len(cls._get_nearby_feedback(lat, lng, radius_m=500))
            total_incidents += len(cls._get_nearby_incidents(lat, lng, radius_m=500))

        if valid_points == 0:
            return {
                'breakdown': {k: None for k in factor_sums},
                'data_source': 'insufficient',
                'report_count': total_incidents,
                'total_points': len(sampled),
            }

        avg_breakdown = {k: round(v / valid_points, 1) for k, v in factor_sums.items()}
        data_source = 'real_data' if (total_feedback > 0 or total_incidents > 0) else 'zone_estimates'

        return {
            'breakdown': avg_breakdown,
            'data_source': data_source,
            'report_count': total_incidents,
            'feedback_count': total_feedback,
            'total_points': len(sampled),
        }

    @classmethod
    def get_segment_score(cls, lat, lng, hour=12):
        """Get safety score for a single segment (used by heatmap and route optimizer)."""
        result = cls.get_location_score(lat, lng, hour=hour)
        return result.get('score', None)

    @classmethod
    def get_heatmap_scores(cls, coordinates_list, hour=12):
        """
        Get safety scores for a list of coordinate pairs.
        Returns list of (lat, lng, score) where score may be None.
        Used by heatmap API to show different values per segment.
        """
        results = []
        for lat, lng in coordinates_list:
            result = cls.get_location_score(lat, lng, hour=hour)
            results.append((lat, lng, result.get('score')))
        return results

    @classmethod
    def get_time_weighted_incident_penalty(cls, lat, lng, hour, radius_m=500):
        """
        Calculate incident penalty specific to the given hour.
        Uses DB incidents that occurred at the same hour.
        Returns penalty value (0.0 to 1.0) and count of matching incidents.
        """
        incidents = cls._get_nearby_incidents(lat, lng, radius_m)
        if not incidents:
            return 0.0, 0

        # Group by severity
        severity_weights = {
            'low': 0.02, 'medium': 0.05, 'high': 0.10, 'critical': 0.20,
        }

        penalty = 0.0
        matching_count = 0
        now = datetime.utcnow()

        for inc in incidents:
            if inc.timestamp is None:
                continue
            # Check if incident occurred at similar hour (±2 hours)
            inc_hour = inc.timestamp.hour
            hour_diff = min(abs(inc_hour - hour), 24 - abs(inc_hour - hour))
            if hour_diff > 2:
                continue  # Skip incidents from different time-of-day

            matching_count += 1
            # Exponential decay based on age
            age_hours = (now - inc.timestamp).total_seconds() / 3600
            decay = math.exp(-0.01 * age_hours)  # Half-life ~70 hours
            penalty += severity_weights.get(inc.severity, 0.05) * decay

        return min(penalty, 0.5), matching_count

    # ── Private helper methods ──

    @classmethod
    def _find_nearest_zone(cls, lat, lng, max_radius_m=500):
        """Find the nearest LocationZone within max_radius_m."""
        zones = LocationZone.query.all()
        best_zone = None
        best_dist = float('inf')

        for zone in zones:
            d = cls.haversine(lat, lng, zone.center_lat, zone.center_lng)
            if d <= zone.radius_m + max_radius_m and d < best_dist:
                best_dist = d
                best_zone = zone

        return best_zone

    @classmethod
    def _get_nearby_incidents(cls, lat, lng, radius_m=500):
        """Get incidents within radius_m of a point."""
        # Query all incidents and filter by distance (SQLite has no spatial index)
        incidents = Incident.query.filter(Incident.status == 'active').all()
        nearby = []
        for inc in incidents:
            d = cls.haversine(lat, lng, inc.lat, inc.lng)
            if d <= radius_m:
                nearby.append(inc)
        return nearby

    @classmethod
    def _get_nearby_feedback(cls, lat, lng, radius_m=500):
        """Get feedback within radius_m of a point."""
        feedback = SafetyFeedback.query.all()
        nearby = []
        for fb in feedback:
            d = cls.haversine(lat, lng, fb.lat, fb.lng)
            if d <= radius_m:
                nearby.append(fb)
        return nearby

    @classmethod
    def _score_from_zone(cls, lat, lng, zone, hour):
        """Compute score from zone base data + incident penalties + feedback adjustment."""
        # Base breakdown from zone data
        breakdown = {
            'lighting': zone.lighting if zone.lighting is not None else 5.0,
            'police': zone.police_proximity if zone.police_proximity is not None else 5.0,
            'crowd': zone.crowd_density if zone.crowd_density is not None else 5.0,
            'road_type': cls.ROAD_TYPE_SCORES.get(zone.road_type, 5.0),
            'crime': 7.0,  # Will be adjusted by incidents
            'accessibility': 6.0 if zone.road_type in ('primary', 'secondary') else 4.0,
            'reports': 7.0,  # Will be adjusted by feedback
        }

        # Incident penalty (time-of-day specific)
        incident_penalty, incident_count = cls.get_time_weighted_incident_penalty(lat, lng, hour)
        breakdown['crime'] = max(1.0, 7.0 - incident_penalty * 20)

        # Feedback adjustment (recent feedback weighted more)
        feedback_adj, feedback_count = cls._compute_feedback_adjustment(lat, lng)
        if feedback_adj is not None:
            breakdown['reports'] = max(1.0, min(10.0, 7.0 + feedback_adj))

        # Compute weighted score
        weighted_sum = sum(
            breakdown[factor] * weight * 10
            for factor, weight in cls.WEIGHTS.items()
        )

        # Apply time-of-day multiplier
        night_mult = cls.NIGHT_MULTIPLIER.get(hour, 0.7)
        # Extra penalty for poorly lit areas at night
        if zone.lighting is not None and zone.lighting < 5:
            night_mult *= 0.75

        adjusted = weighted_sum * night_mult
        score = max(0, min(100, round(adjusted, 1)))

        # Determine data source
        if feedback_count > 0 or incident_count > 0:
            data_source = 'real_data'
        else:
            data_source = 'zone_estimates'

        return {
            'score': score,
            'breakdown': {k: round(v, 1) for k, v in breakdown.items()},
            'data_source': data_source,
            'zone_name': zone.name,
            'feedback_count': feedback_count,
            'incident_count': incident_count,
            'time_hour': hour,
        }

    @classmethod
    def _score_from_incidents_only(cls, lat, lng, incidents, hour):
        """Derive score purely from incident data when no zone exists."""
        severity_weights = {
            'low': 2, 'medium': 5, 'high': 8, 'critical': 10,
        }
        total_penalty = 0
        now = datetime.utcnow()
        matching_count = 0

        for inc in incidents:
            if inc.timestamp:
                age_hours = (now - inc.timestamp).total_seconds() / 3600
                decay = math.exp(-0.01 * age_hours)
                total_penalty += severity_weights.get(inc.severity, 5) * decay
                # Check time match
                inc_hour = inc.timestamp.hour
                hour_diff = min(abs(inc_hour - hour), 24 - abs(inc_hour - hour))
                if hour_diff <= 2:
                    matching_count += 1

        # Convert penalty to score (more incidents = lower score)
        base = 50  # Neutral baseline without zone data
        penalty_reduction = min(total_penalty * 3, 40)
        score = max(10, base - penalty_reduction)

        # Time-of-day multiplier
        night_mult = cls.NIGHT_MULTIPLIER.get(hour, 0.7)
        adjusted = score * night_mult
        score = max(0, min(100, round(adjusted, 1)))

        breakdown = {
            'lighting': None,
            'police': None,
            'crowd': None,
            'road_type': None,
            'crime': max(1.0, round(10 - min(total_penalty, 9), 1)),
            'accessibility': None,
            'reports': max(1.0, round(10 - min(total_penalty * 0.5, 9), 1)),
        }

        return {
            'score': score,
            'breakdown': breakdown,
            'data_source': 'incidents_only',
            'zone_name': None,
            'feedback_count': 0,
            'incident_count': len(incidents),
            'time_hour': hour,
        }

    @classmethod
    def _compute_feedback_adjustment(cls, lat, lng, radius_m=500):
        """
        Compute feedback adjustment using exponential decay.
        Returns (adjustment_value, feedback_count).
        Positive = more safe feedback, negative = more unsafe.
        """
        feedback = cls._get_nearby_feedback(lat, lng, radius_m)
        if not feedback:
            return None, 0

        now = datetime.utcnow()
        safe_weight = 0
        unsafe_weight = 0

        for fb in feedback:
            if fb.timestamp:
                age_hours = (now - fb.timestamp).total_seconds() / 3600
                decay = math.exp(-0.015 * age_hours)  # Half-life ~46 hours
            else:
                decay = 0.5

            if fb.feedback_type == 'safe':
                safe_weight += decay
            else:
                unsafe_weight += decay

        total = safe_weight + unsafe_weight
        if total == 0:
            return 0, len(feedback)

        # Normalized adjustment: +3 if all safe, -3 if all unsafe
        net = (safe_weight - unsafe_weight) / total * 3.0
        return round(net, 2), len(feedback)
