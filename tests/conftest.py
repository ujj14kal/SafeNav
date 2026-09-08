"""
SafeRoute — Test Configuration & Fixtures
TDD: Tests define what we build before we build it.
"""
import pytest
import json
import os


@pytest.fixture
def client():
    """Flask test client for API testing."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

# ──────────────────────────────────────────────
# FIXTURE: Sample road network graph
# Represents a mini city with 10 nodes and edges
# ──────────────────────────────────────────────
@pytest.fixture
def sample_graph():
    """
    Mini city graph:
    
        [Police]
           |
    [A]---[B]---[C]---[D]
     |     |           |
    [E]---[F]---[G]---[H]
           |         / |
         [Hospital] [I]--[J]
    
    A = Start point (well-lit commercial area)
    D = End point (near police station)
    F-G = Isolated industrial road (dangerous)
    B-C = Main road with shops (safe)
    """
    return {
        "nodes": {
            "A": {"lat": 26.9124, "lng": 75.7873, "type": "intersection"},
            "B": {"lat": 26.9134, "lng": 75.7883, "type": "intersection"},
            "C": {"lat": 26.9144, "lng": 75.7893, "type": "intersection"},
            "D": {"lat": 26.9154, "lng": 75.7903, "type": "intersection"},
            "E": {"lat": 26.9114, "lng": 75.7873, "type": "intersection"},
            "F": {"lat": 26.9124, "lng": 75.7883, "type": "intersection"},
            "G": {"lat": 26.9124, "lng": 75.7893, "type": "intersection"},
            "H": {"lat": 26.9124, "lng": 75.7903, "type": "intersection"},
            "I": {"lat": 26.9114, "lng": 75.7903, "type": "intersection"},
            "J": {"lat": 26.9104, "lng": 75.7903, "type": "intersection"},
        },
        "edges": [
            {"from": "A", "to": "B", "distance": 200, "road_type": "primary", "lit": True, "shops": 15},
            {"from": "B", "to": "C", "distance": 200, "road_type": "primary", "lit": True, "shops": 20},
            {"from": "C", "to": "D", "distance": 200, "road_type": "primary", "lit": True, "shops": 10},
            {"from": "A", "to": "E", "distance": 150, "road_type": "residential", "lit": True, "shops": 5},
            {"from": "E", "to": "F", "distance": 100, "road_type": "service", "lit": False, "shops": 0},
            {"from": "B", "to": "F", "distance": 150, "road_type": "secondary", "lit": True, "shops": 8},
            {"from": "F", "to": "G", "distance": 80, "road_type": "service", "lit": False, "shops": 0},
            {"from": "G", "to": "H", "distance": 80, "road_type": "service", "lit": False, "shops": 0},
            {"from": "H", "to": "D", "distance": 150, "road_type": "secondary", "lit": True, "shops": 5},
            {"from": "H", "to": "I", "distance": 150, "road_type": "residential", "lit": True, "shops": 3},
            {"from": "I", "to": "J", "distance": 200, "road_type": "residential", "lit": True, "shops": 4},
            # Direct shortcut A→D: long but goes through well-lit residential area
            {"from": "A", "to": "D", "distance": 800, "road_type": "residential", "lit": True, "shops": 8},
        ]
    }


@pytest.fixture
def sample_pois():
    """Points of Interest near the sample graph"""
    return {
        "police_stations": [
            {"name": "Ashok Nagar PS", "lat": 26.9160, "lng": 75.7905, "node_near": "D"},
        ],
        "hospitals": [
            {"name": "SMS Hospital", "lat": 26.9120, "lng": 75.7885, "node_near": "F"},
        ],
        "schools": [
            {"name": "DAV School", "lat": 26.9130, "lng": 75.7880, "node_near": "B"},
        ],
        "shops": [
            {"name": "MI Road Market", "lat": 26.9135, "lng": 75.7885, "node_near": "B"},
        ],
        "liquor_shops": [
            {"name": "Wine Shop", "lat": 26.9118, "lng": 75.7890, "node_near": "F"},
        ]
    }


@pytest.fixture
def sample_safety_scores():
    """Expected safety scores for test edges at different times"""
    return {
        "edge_A_B": {"day": 85, "night": 65, "factors": {
            "lighting": 9, "police": 7, "crowd": 9, "road_type": 9,
            "crime": 7, "accessibility": 8, "reports": 9
        }},
        "edge_F_G": {"day": 25, "night": 8, "factors": {
            "lighting": 1, "police": 2, "crowd": 1, "road_type": 3,
            "crime": 2, "accessibility": 2, "reports": 1
        }},
        "edge_B_C": {"day": 90, "night": 70, "factors": {
            "lighting": 10, "police": 8, "crowd": 10, "road_type": 9,
            "crime": 8, "accessibility": 9, "reports": 10
        }},
    }


@pytest.fixture
def sample_community_reports():
    """Sample user-submitted safety reports"""
    return [
        {
            "id": "rpt_001",
            "lat": 26.9125,
            "lng": 75.7884,
            "type": "broken_light",
            "description": "Street light not working for 3 days",
            "timestamp": "2026-09-08T14:30:00",
            "weight": 1.0
        },
        {
            "id": "rpt_002",
            "lat": 26.9120,
            "lng": 75.7892,
            "type": "suspicious",
            "description": "Group of men loitering near abandoned building",
            "timestamp": "2026-09-08T22:15:00",
            "weight": 0.9
        },
        {
            "id": "rpt_003",
            "lat": 26.9115,
            "lng": 75.7870,
            "type": "no_cctv",
            "description": "No CCTV coverage on this stretch",
            "timestamp": "2026-09-07T10:00:00",
            "weight": 0.4  # Older report = lower weight
        }
    ]
