"""
SafeRoute — Route Optimizer (v2 — Real Data)
Finds 3 routes (fastest, safest, balanced) using NetworkX.
Now uses real OSM road data and Google Places POIs.
"""
import math
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
        """Build NetworkX graph from data (now with real OSM attributes)."""
        for node_id, attrs in data.get('nodes', {}).items():
            self.graph.add_node(node_id, **attrs)
            self.node_positions[node_id] = (attrs.get('lat', 0), attrs.get('lng', 0))

        for edge in data.get('edges', []):
            u, v = edge['from'], edge['to']
            distance = edge.get('distance', 100)
            road_type = edge.get('road_type', 'residential')
            speed = self.SPEED_LIMITS.get(road_type, 30)
            travel_time = (distance / 1000) / (speed / 3600)  # seconds

            # Compute midpoint for spatial lookups
            u_lat = self.graph.nodes[u].get('lat', 0)
            u_lng = self.graph.nodes[u].get('lng', 0)
            v_lat = self.graph.nodes[v].get('lat', 0)
            v_lng = self.graph.nodes[v].get('lng', 0)
            mid_lat = (u_lat + v_lat) / 2
            mid_lng = (u_lng + v_lng) / 2

            # Count nearby shops from POIs (real Google Places data)
            shops = self._count_nearby_shops(mid_lat, mid_lng, radius=300)

            # Compute crime rate from environmental factors
            crime_rate = self._compute_crime_rate(mid_lat, mid_lng, road_type, edge.get('lit', False))

            edge_data = {
                'distance': distance,
                'road_type': road_type,
                'lit': edge.get('lit', False),
                'shops': shops,
                'crime_rate': crime_rate,
                'lat': mid_lat,
                'lng': mid_lng,
                'lanes': edge.get('lanes', None),
                'name': edge.get('name', ''),
                'footpath': edge.get('footpath', road_type in ('primary', 'secondary')),
                'sidewalk': edge.get('sidewalk', False),
            }

            safety_score = self.safety_engine.calculate_edge_score(edge_data, hour=12)
            safety_cost = self.safety_engine.compute_safety_cost(travel_time, safety_score)

            self.graph.add_edge(u, v,
                distance=distance,
                travel_time=travel_time,
                road_type=road_type,
                lit=edge.get('lit', False),
                shops=shops,
                crime_rate=crime_rate,
                safety_score=safety_score,
                safety_cost=safety_cost,
                lat=mid_lat,
                lng=mid_lng,
                lanes=edge.get('lanes', None),
                name=edge.get('name', ''),
            )

    def _count_nearby_shops(self, lat, lng, radius=300):
        """Count Google Places shops/commercial places near a point."""
        count = 0
        # Check multiple POI categories that indicate commercial activity
        for category in ['liquor_shops', 'atms', 'gas_stations', 'schools']:
            for poi in self.pois.get(category, []):
                d = SafetyEngine.haversine(lat, lng, poi['lat'], poi['lng'])
                if d < radius:
                    count += 1
        # Also count hospitals (they indicate developed/commercial areas)
        for poi in self.pois.get('hospitals', []):
            d = SafetyEngine.haversine(lat, lng, poi['lat'], poi['lng'])
            if d < radius:
                count += 2  # hospitals are strong indicators of activity
        return count

    def _compute_crime_rate(self, lat, lng, road_type, lit):
        """
        Derive crime risk from environmental factors.
        0.0 = safe, 1.0 = dangerous.
        """
        risk = 0.0

        # Liquor shops nearby increase risk
        for shop in self.pois.get('liquor_shops', []):
            d = SafetyEngine.haversine(lat, lng, shop['lat'], shop['lng'])
            if d < 200:
                risk += 0.25
            elif d < 500:
                risk += 0.15
            elif d < 1000:
                risk += 0.05

        # Road type isolation
        if road_type == 'service':
            risk += 0.20
        elif road_type == 'unclassified':
            risk += 0.10
        elif road_type == 'residential':
            risk += 0.05

        # Lighting
        if not lit:
            risk += 0.20

        # Police proximity reduces risk
        for p in self.pois.get('police_stations', []):
            d = SafetyEngine.haversine(lat, lng, p['lat'], p['lng'])
            if d < 500:
                risk -= 0.15
            elif d < 1000:
                risk -= 0.08
            elif d < 2000:
                risk -= 0.03

        return max(0.0, min(1.0, risk))

    def _update_costs_for_hour(self, hour, reports=None):
        """Recalculate safety costs for all edges given time of day."""
        for u, v, data in self.graph.edges(data=True):
            edge_info = {
                'distance': data.get('distance', 100),
                'road_type': data.get('road_type', 'residential'),
                'lit': data.get('lit', False),
                'shops': data.get('shops', 0),
                'crime_rate': data.get('crime_rate', 0.3),
                'lat': data.get('lat', 0),
                'lng': data.get('lng', 0),
                'lanes': data.get('lanes', None),
                'name': data.get('name', ''),
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
                    'name': data.get('name', ''),
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
                    'name': data.get('name', '') or f"{u} → {v} ({data.get('road_type', 'road')})",
                    'score': score,
                    'road_type': data.get('road_type', 'unknown'),
                    'lat': data.get('lat', 0),
                    'lng': data.get('lng', 0),
                })

        zones.sort(key=lambda x: x['score'])
        return zones[:limit]
