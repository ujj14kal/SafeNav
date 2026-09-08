"""
TDD Test Suite: REST API Endpoints
Tests define what the API must return.
"""
import pytest
import json


class TestRouteAPI:
    """Test POST /api/route endpoint"""

    def test_valid_coordinates_return_200(self, client):
        """Valid start/end coordinates should return 200 with routes"""
        response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903],
            "night": False,
            "mode": "normal"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "routes" in data
        assert len(data["routes"]) == 3

    def test_missing_coordinates_return_400(self, client):
        """Missing coordinates should return 400 Bad Request"""
        response = client.post('/api/route', json={})
        assert response.status_code == 400

    def test_invalid_coordinates_return_400(self, client):
        """Out-of-range coordinates should return 400"""
        response = client.post('/api/route', json={
            "start": [91.0, 181.0],  # Invalid lat/lng
            "end": [26.9154, 75.7903]
        })
        assert response.status_code == 400

    def test_route_response_has_all_fields(self, client):
        """Response must have routes, safety_breakdown, explanation"""
        response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903]
        })
        data = response.get_json()
        assert "routes" in data
        assert "safety_breakdown" in data
        assert "explanation" in data

    def test_route_types_are_fastest_safest_recommended(self, client):
        """Routes should be labeled as fastest, safest, recommended"""
        response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903]
        })
        data = response.get_json()
        types = [r["type"] for r in data["routes"]]
        assert "fastest" in types
        assert "safest" in types
        assert "recommended" in types

    def test_each_route_has_coordinates(self, client):
        """Each route must have a coordinates array for map rendering"""
        response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903]
        })
        data = response.get_json()
        for route in data["routes"]:
            assert "coordinates" in route
            assert len(route["coordinates"]) >= 2, "Route needs at least 2 coordinate points"
            for coord in route["coordinates"]:
                assert len(coord) == 2, "Each coordinate should be [lat, lng]"

    def test_night_mode_parameter(self, client):
        """Passing night=true should return night-adjusted scores"""
        day_response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903],
            "night": False
        })
        night_response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903],
            "night": True
        })
        day_data = day_response.get_json()
        night_data = night_response.get_json()
        # Safety scores should differ between day and night
        day_rec = [r for r in day_data["routes"] if r["type"] == "recommended"][0]
        night_rec = [r for r in night_data["routes"] if r["type"] == "recommended"][0]
        assert day_rec["safety_score"] != night_rec["safety_score"], \
            "Night mode should change safety scores"

    def test_explanation_is_nonempty_string(self, client):
        """AI explanation should be a non-empty string"""
        response = client.post('/api/route', json={
            "start": [26.9124, 75.7873],
            "end": [26.9154, 75.7903]
        })
        data = response.get_json()
        assert isinstance(data["explanation"], str)
        assert len(data["explanation"]) > 20, "Explanation should be meaningful, not empty"


class TestHeatmapAPI:
    """Test GET /api/heatmap endpoint"""

    def test_heatmap_returns_geojson(self, client):
        """Heatmap endpoint should return valid GeoJSON"""
        response = client.get('/api/heatmap?hour=14')
        assert response.status_code == 200
        data = response.get_json()
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_heatmap_features_have_safety_score(self, client):
        """Each GeoJSON feature must have a safety_score property"""
        response = client.get('/api/heatmap?hour=14')
        data = response.get_json()
        for feature in data["features"][:5]:  # Check first 5
            assert "safety_score" in feature["properties"]

    def test_heatmap_respects_hour_parameter(self, client):
        """Different hours should produce different safety scores"""
        day_response = client.get('/api/heatmap?hour=14')
        night_response = client.get('/api/heatmap?hour=2')
        day_data = day_response.get_json()
        night_data = night_response.get_json()
        # At least some features should have different scores
        day_scores = [f["properties"]["safety_score"] for f in day_data["features"]]
        night_scores = [f["properties"]["safety_score"] for f in night_data["features"]]
        assert day_scores != night_scores, "Night heatmap should differ from day"


class TestEmergencyAPI:
    """Test GET /api/emergency endpoint"""

    def test_returns_nearest_police(self, client):
        """Must return nearest police station with distance"""
        response = client.get('/api/emergency?lat=26.9124&lng=75.7873')
        assert response.status_code == 200
        data = response.get_json()
        assert "police" in data
        assert "name" in data["police"]
        assert "distance" in data["police"]
        assert "eta_minutes" in data["police"]

    def test_returns_nearest_hospital(self, client):
        """Must return nearest hospital with distance"""
        response = client.get('/api/emergency?lat=26.9124&lng=75.7873')
        data = response.get_json()
        assert "hospital" in data
        assert "name" in data["hospital"]
        assert "distance" in data["hospital"]

    def test_returns_emergency_numbers(self, client):
        """Must return Indian emergency numbers"""
        response = client.get('/api/emergency?lat=26.9124&lng=75.7873')
        data = response.get_json()
        assert "numbers" in data
        assert "100" in str(data["numbers"])  # Police
        assert "108" in str(data["numbers"])  # Ambulance
        assert "112" in str(data["numbers"])  # Emergency

    def test_invalid_coordinates_return_400(self, client):
        """Invalid coordinates should return 400"""
        response = client.get('/api/emergency?lat=999&lng=999')
        assert response.status_code == 400


class TestCommunityAPI:
    """Test POST /api/report and GET /api/reports endpoints"""

    def test_submit_report_returns_201(self, client):
        """Valid report submission should return 201"""
        response = client.post('/api/report', json={
            "lat": 26.9124,
            "lng": 75.7873,
            "type": "broken_light",
            "description": "Street light not working"
        })
        assert response.status_code == 201

    def test_submit_report_returns_id(self, client):
        """Response should include report ID"""
        response = client.post('/api/report', json={
            "lat": 26.9124,
            "lng": 75.7873,
            "type": "broken_light",
            "description": "Street light not working"
        })
        data = response.get_json()
        assert "id" in data

    def test_get_reports_returns_list(self, client):
        """GET /api/reports should return a list of reports"""
        # Submit a report first
        client.post('/api/report', json={
            "lat": 26.9124, "lng": 75.7873,
            "type": "broken_light", "description": "Test"
        })
        response = client.get('/api/reports')
        assert response.status_code == 200
        data = response.get_json()
        assert "reports" in data
        assert isinstance(data["reports"], list)

    def test_report_has_required_fields(self, client):
        """Each report must have: id, lat, lng, type, timestamp"""
        client.post('/api/report', json={
            "lat": 26.9124, "lng": 75.7873,
            "type": "suspicious", "description": "Test"
        })
        response = client.get('/api/reports')
        data = response.get_json()
        if data["reports"]:
            report = data["reports"][0]
            for field in ["id", "lat", "lng", "type", "timestamp"]:
                assert field in report, f"Report missing field: {field}"


class TestAdminAPI:
    """Test GET /api/admin/stats endpoint"""

    def test_admin_stats_returns_200(self, client):
        """Admin stats endpoint should return 200"""
        response = client.get('/api/admin/stats')
        assert response.status_code == 200

    def test_admin_stats_has_required_fields(self, client):
        """Stats must have: avg_score, danger_zones, total_reports, recommendations"""
        response = client.get('/api/admin/stats')
        data = response.get_json()
        for field in ["avg_score", "danger_zones", "total_reports", "recommendations"]:
            assert field in data, f"Stats missing field: {field}"

    def test_danger_zones_is_list(self, client):
        """danger_zones should be a list with name and score"""
        response = client.get('/api/admin/stats')
        data = response.get_json()
        assert isinstance(data["danger_zones"], list)
        if data["danger_zones"]:
            zone = data["danger_zones"][0]
            assert "name" in zone
            assert "score" in zone
