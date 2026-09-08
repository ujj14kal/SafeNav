"""
TDD Test Suite: Safety Scoring Engine
These tests define what the safety engine MUST do.
Write tests FIRST, then implement to pass them.
"""
import pytest


class TestSafetyScoreCalculation:
    """Test that safety scores are computed correctly from 7 factors"""

    def test_well_lit_road_scores_high(self, sample_graph):
        """Road with shops + lighting + main road type should score > 70"""
        edge = [e for e in sample_graph["edges"] if e["from"] == "B" and e["to"] == "C"][0]
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        score = engine.calculate_edge_score(edge, hour=14)
        assert score >= 70, f"Well-lit commercial road scored {score}, expected >= 70"

    def test_isolated_road_scores_low(self, sample_graph):
        """Industrial road with no shops, no lights should score < 30"""
        edge = [e for e in sample_graph["edges"]
                if e["from"] == "F" and e["to"] == "G" and e["road_type"] == "service"][0]
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        score = engine.calculate_edge_score(edge, hour=14)
        assert score < 30, f"Isolated industrial road scored {score}, expected < 30"

    def test_night_reduces_score(self, sample_graph):
        """Same road must score lower at 2AM than at 2PM"""
        edge = [e for e in sample_graph["edges"] if e["from"] == "A" and e["to"] == "B"][0]
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        day_score = engine.calculate_edge_score(edge, hour=14)
        night_score = engine.calculate_edge_score(edge, hour=2)
        assert night_score < day_score, \
            f"Night score ({night_score}) should be less than day score ({day_score})"

    def test_night_penalty_is_meaningful(self, sample_graph):
        """Night penalty should reduce score by at least 15%"""
        edge = [e for e in sample_graph["edges"] if e["from"] == "A" and e["to"] == "B"][0]
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        day_score = engine.calculate_edge_score(edge, hour=14)
        night_score = engine.calculate_edge_score(edge, hour=2)
        reduction = (day_score - night_score) / day_score
        assert reduction >= 0.15, \
            f"Night penalty {reduction:.0%} is too low, expected >= 15%"

    def test_unlit_road_penalized_more_at_night(self, sample_graph):
        """An unlit road should get a BIGGER percentage penalty at night than a lit road"""
        lit_edge = [e for e in sample_graph["edges"] if e["from"] == "A" and e["to"] == "B"][0]
        unlit_edge = [e for e in sample_graph["edges"]
                      if e["from"] == "F" and e["to"] == "G" and e["road_type"] == "service"][0]
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        lit_day = engine.calculate_edge_score(lit_edge, hour=14)
        lit_night = engine.calculate_edge_score(lit_edge, hour=2)
        unlit_day = engine.calculate_edge_score(unlit_edge, hour=14)
        unlit_night = engine.calculate_edge_score(unlit_edge, hour=2)
        lit_pct = (lit_day - lit_night) / lit_day if lit_day > 0 else 0
        unlit_pct = (unlit_day - unlit_night) / unlit_day if unlit_day > 0 else 0
        assert unlit_pct > lit_pct, \
            f"Unlit roads should get bigger night penalty % (unlit: {unlit_pct:.0%} vs lit: {lit_pct:.0%})"

    def test_score_is_between_0_and_100(self, sample_graph):
        """All scores must be clamped to [0, 100]"""
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        for edge in sample_graph["edges"]:
            score = engine.calculate_edge_score(edge, hour=14)
            assert 0 <= score <= 100, f"Score {score} out of bounds for edge {edge['from']}->{edge['to']}"
            score_night = engine.calculate_edge_score(edge, hour=2)
            assert 0 <= score_night <= 100, f"Night score {score_night} out of bounds"

    def test_score_components_sum_correctly(self, sample_graph):
        """7 weighted components should sum to final score (before night adjustment)"""
        edge = [e for e in sample_graph["edges"] if e["from"] == "B" and e["to"] == "C"][0]
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        breakdown = engine.get_score_breakdown(edge, hour=14)
        assert "lighting" in breakdown
        assert "police" in breakdown
        assert "crowd" in breakdown
        assert "road_type" in breakdown
        assert "crime" in breakdown
        assert "accessibility" in breakdown
        assert "reports" in breakdown
        # Breakdown values are 0-10, weighted sum gives 0-100
        weighted_sum = sum(
            breakdown[f] * engine.WEIGHTS[f] * 10
            for f in engine.WEIGHTS
        )
        score = engine.calculate_edge_score(edge, hour=14)
        # Night multiplier at hour=14 should be ~1.0, so scores should be close
        assert abs(weighted_sum - score) < 15, \
            f"Weighted sum ({weighted_sum}) should be close to score ({score})"

    def test_police_proximity_boosts_score(self, sample_graph, sample_pois):
        """Edge near a police station should get a proximity bonus"""
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine(pois=sample_pois)
        # Edge C->D is near the police station (lat 26.9154)
        edge_near_police = [e for e in sample_graph["edges"] if e["from"] == "C" and e["to"] == "D"][0]
        edge_near_police = dict(edge_near_police)  # copy
        edge_near_police['lat'] = 26.9155  # near police station
        edge_near_police['lng'] = 75.7903
        # Edge E->F is far from police
        edge_far_police = [e for e in sample_graph["edges"] if e["from"] == "E" and e["to"] == "F"][0]
        edge_far_police = dict(edge_far_police)
        edge_far_police['lat'] = 26.9114  # far from police
        edge_far_police['lng'] = 75.7883
        breakdown_near = engine.get_score_breakdown(edge_near_police, hour=14)
        breakdown_far = engine.get_score_breakdown(edge_far_police, hour=14)
        assert breakdown_near["police"] > breakdown_far["police"], \
            f"Edge near police station should have higher police score ({breakdown_near['police']} vs {breakdown_far['police']})"


class TestTimeBasedAdjustment:
    """Test that safety changes with time of day"""

    def test_midnight_is_most_dangerous(self, sample_graph):
        """12AM should produce the lowest scores overall"""
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        edge = [e for e in sample_graph["edges"] if e["from"] == "A" and e["to"] == "B"][0]
        scores = {}
        for hour in [6, 12, 18, 21, 0, 3]:
            scores[hour] = engine.calculate_edge_score(edge, hour=hour)
        assert scores[0] <= scores[12], "Midnight should score <= noon"
        assert scores[3] <= scores[18], "3AM should score <= 6PM"

    def test_noon_is_safest(self, sample_graph):
        """12PM should produce the highest scores overall"""
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        edge = [e for e in sample_graph["edges"] if e["from"] == "B" and e["to"] == "C"][0]
        scores = {}
        for hour in [6, 12, 18, 21, 0, 3]:
            scores[hour] = engine.calculate_edge_score(edge, hour=hour)
        assert scores[12] >= max(scores.values()), "Noon should be the highest score"


class TestScoreWithReports:
    """Test that community reports affect safety scores"""

    def test_reports_reduce_safety_score(self, sample_graph, sample_community_reports):
        """Edges with active reports should score lower"""
        from app.services.safety_engine import SafetyEngine
        engine = SafetyEngine()
        edge = [e for e in sample_graph["edges"] if e["from"] == "A" and e["to"] == "B"][0]
        score_without = engine.calculate_edge_score(edge, hour=14)
        score_with = engine.calculate_edge_score(edge, hour=14, reports=sample_community_reports)
        assert score_with <= score_without, \
            "Reports should reduce or maintain safety score"

    def test_expired_reports_have_no_effect(self, sample_graph):
        """Reports older than 24 hours should not affect score"""
        from app.services.safety_engine import SafetyEngine
        from datetime import datetime, timedelta
        engine = SafetyEngine()
        edge = [e for e in sample_graph["edges"] if e["from"] == "A" and e["to"] == "B"][0]
        old_reports = [{
            "lat": 26.9124, "lng": 75.7873,
            "type": "broken_light",
            "timestamp": (datetime.now() - timedelta(hours=25)).isoformat(),
            "weight": 1.0
        }]
        score_without = engine.calculate_edge_score(edge, hour=14)
        score_with_old = engine.calculate_edge_score(edge, hour=14, reports=old_reports)
        assert score_without == score_with_old, "Expired reports should not affect score"
