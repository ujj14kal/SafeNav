"""
SafeRoute — Route Optimizer
Finds 3 routes (fastest, safest, balanced) using NetworkX.
Algorithm inspired by NVIDIA cuOpt: safety-weighted cost matrix.
"""
import networkx as nx
import numpy as np
from app.services.safety_engine import SafetyEngine


class RouteOptimizer:
    """
    Builds a road network graph and finds optimal routes
    using safety-weighted cost matrices.

    Approach (cuOpt-inspired):
      cost[i][j] = travel_time[i][j] × (100 / safety[i][j])
      - Safe roads: low cost → preferred
      - Dangerous roads: high cost → avoided
    """

    SPEED_LIMITS = {
        'motorway': 100, 'trunk': 80, 'primary': 60,
        'secondary': 50, 'tertiary': 40, 'residential': 30,
        'service': 20, 'unclassified': 30, 'living_street': 20,
    }

    def __init__(self, graph_data=None, graph=None, pois=None):
        self.graph = nx.DiGraph()
        self.safety_engine = SafetyEngine(pois=pois or {})
        self.pois = pois or {}
        self.node_positions = {}

        data = graph_data or graph
        if data:
            self._build_graph(data)

    def _build_graph(self, data):
        """Build NetworkX graph from data."""
        for node_id, attrs in data.get('nodes', {}).items():
            self.graph.add_node(node_id, **attrs)
            self.node_positions[node_id] = (attrs.get('lat', 0), attrs.get('lng', 0))

        for edge in data.get('edges', []):
            u, v = edge['from'], edge['to']
            distance = edge.get('distance', 100)
            road_type = edge.get('road_type', 'residential')
            speed = self.SPEED_LIMITS.get(road_type, 30)
            travel_time = (distance / 1000) / (speed / 3600)  # seconds

            mid_lat = (self.graph.nodes[u].get('lat', 0) + self.graph.nodes[v].get('lat', 0)) / 2
            mid_lng = (self.graph.nodes[u].get('lng', 0) + self.graph.nodes[v].get('lng', 0)) / 2

            edge_data = {
                'distance': distance,
                'road_type': road_type,
                'lit': edge.get('lit', False),
                'shops': edge.get('shops', 0),
                'lat': mid_lat,
                'lng': mid_lng,
                'travel_time': travel_time,
            }

            safety_score = self.safety_engine.calculate_edge_score(edge_data, hour=12)
            safety_cost = self.safety_engine.compute_safety_cost(travel_time, safety_score)

            self.graph.add_edge(u, v,
                distance=distance,
                travel_time=travel_time,
                road_type=road_type,
                lit=edge.get('lit', False),
                shops=edge.get('shops', 0),
                safety_score=safety_score,
                safety_cost=safety_cost,
                lat=mid_lat,
                lng=mid_lng,
            )

    def _update_costs_for_hour(self, hour, reports=None):
        """Recalculate safety costs for all edges given time of day."""
        for u, v, data in self.graph.edges(data=True):
            edge_info = {
                'distance': data.get('distance', 100),
                'road_type': data.get('road_type', 'residential'),
                'lit': data.get('lit', False),
                'shops': data.get('shops', 0),
                'lat': data.get('lat', 0),
                'lng': data.get('lng', 0),
            }
            safety_score = self.safety_engine.calculate_edge_score(edge_info, hour=hour, reports=reports)
            travel_time = data.get('travel_time', 60)
            safety_cost = self.safety_engine.compute_safety_cost(travel_time, safety_score)
            data['safety_score'] = safety_score
            data['safety_cost'] = safety_cost

    def _path_to_coordinates(self, path):
        """Convert node path to lat/lng coordinate list."""
        coords = []
        for node in path:
            lat = self.graph.nodes[node].get('lat', 0)
            lng = self.graph.nodes[node].get('lng', 0)
            coords.append([lat, lng])
        return coords

    def _path_stats(self, path, route_type='fastest'):
        """Calculate stats for a path."""
        total_time = 0
        total_distance = 0
        safety_scores = []

        for i in range(len(path) - 1):
            edge_data = self.graph[path[i]][path[i+1]]
            total_time += edge_data.get('travel_time', 0)
            total_distance += edge_data.get('distance', 0)
            safety_scores.append(edge_data.get('safety_score', 50))

        avg_safety = np.mean(safety_scores) if safety_scores else 50
        min_safety = min(safety_scores) if safety_scores else 50

        return {
            'type': route_type,
            'path': path,
            'coordinates': self._path_to_coordinates(path),
            'time': round(total_time / 60, 1),  # minutes
            'distance': round(total_distance / 1000, 2),  # km
            'safety_score': round(avg_safety, 1),
            'min_safety_score': round(min_safety, 1),
            'segments': len(path) - 1,
        }

    def find_nearest_node(self, lat, lng):
        """Find the nearest graph node to a lat/lng point."""
        min_dist = float('inf')
        nearest = None
        for node_id, (nlat, nlng) in self.node_positions.items():
            d = SafetyEngine.haversine(lat, lng, nlat, nlng)
            if d < min_dist:
                min_dist = d
                nearest = node_id
        return nearest

    def find_routes(self, start, end, hour=12, mode='normal', reports=None):
        """
        Find 3 routes: fastest, safest, and recommended (balanced).

        Returns list of route dicts with path, coordinates, time,
        distance, and safety score.
        """
        if start not in self.graph or end not in self.graph:
            return []

        if start == end:
            return [{
                'type': 'fastest', 'path': [start],
                'coordinates': self._path_to_coordinates([start]),
                'time': 0, 'distance': 0, 'safety_score': 100,
                'min_safety_score': 100, 'segments': 0,
            }]

        self._update_costs_for_hour(hour, reports)

        routes = []

        # Route 1: Fastest (minimize travel_time)
        try:
            fastest_path = nx.shortest_path(self.graph, start, end, weight='travel_time')
            routes.append(self._path_stats(fastest_path, 'fastest'))
        except nx.NetworkXNoPath:
            pass

        # Route 2: Safest (minimize safety_cost = time × 100/safety)
        try:
            safest_path = nx.shortest_path(self.graph, start, end, weight='safety_cost')
            routes.append(self._path_stats(safest_path, 'safest'))
        except nx.NetworkXNoPath:
            pass

        # Route 3: Recommended (blended cost: 40% time + 60% safety)
        try:
            for u, v, data in self.graph.edges(data=True):
                data['blended_cost'] = (
                    0.4 * data.get('travel_time', 60) +
                    0.6 * data.get('safety_cost', 600)
                )
            balanced_path = nx.shortest_path(self.graph, start, end, weight='blended_cost')
            routes.append(self._path_stats(balanced_path, 'recommended'))
        except nx.NetworkXNoPath:
            pass

        # If fastest == safest, try harder to find alternatives
        if len(routes) >= 2 and routes[0]['path'] == routes[1]['path']:
            # Try a different blend ratio for recommended
            try:
                for u, v, data in self.graph.edges(data=True):
                    data['alt_cost'] = (
                        0.2 * data.get('travel_time', 60) +
                        0.8 * data.get('safety_cost', 600)
                    )
                alt_path = nx.shortest_path(self.graph, start, end, weight='alt_cost')
                if alt_path != routes[0]['path']:
                    routes[2] = self._path_stats(alt_path, 'recommended')
            except nx.NetworkXNoPath:
                pass

        # Ensure we always return at least what we have
        return routes[:3]

    def get_heatmap_data(self, hour=12, reports=None):
        """Generate heatmap data for all edges."""
        self._update_costs_for_hour(hour, reports)
        features = []

        for u, v, data in self.graph.edges(data=True):
            lat1 = self.graph.nodes[u].get('lat', 0)
            lng1 = self.graph.nodes[u].get('lng', 0)
            lat2 = self.graph.nodes[v].get('lat', 0)
            lng2 = self.graph.nodes[v].get('lng', 0)

            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [[lng1, lat1], [lng2, lat2]],
                },
                'properties': {
                    'safety_score': data.get('safety_score', 50),
                    'road_type': data.get('road_type', 'unknown'),
                    'lit': data.get('lit', False),
                    'from': u,
                    'to': v,
                }
            })

        return {'type': 'FeatureCollection', 'features': features}

    def get_danger_zones(self, hour=12, limit=10):
        """Get the most dangerous road segments."""
        self._update_costs_for_hour(hour)
        zones = []

        for u, v, data in self.graph.edges(data=True):
            score = data.get('safety_score', 50)
            if score < 40:
                zones.append({
                    'name': f"{u} → {v} ({data.get('road_type', 'road')})",
                    'score': score,
                    'road_type': data.get('road_type', 'unknown'),
                    'lat': data.get('lat', 0),
                    'lng': data.get('lng', 0),
                })

        zones.sort(key=lambda x: x['score'])
        return zones[:limit]
