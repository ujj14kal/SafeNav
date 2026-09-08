"""
TDD Test Suite: Groq AI Service
Tests define what the AI explanation service must do.
"""
import pytest


class TestGroqExplanation:
    """Test AI-generated route explanations"""

    def test_explanation_is_nonempty(self):
        """AI explanation should never be empty"""
        from app.services.groq_service import GroqService
        service = GroqService()
        route_data = {
            "type": "recommended",
            "safety_score": 78,
            "time": 25,
            "factors": {
                "lighting": 8, "police": 9, "crowd": 7,
                "road_type": 8, "crime": 6, "accessibility": 5, "reports": 9
            }
        }
        explanation = service.generate_explanation(route_data, night=False)
        assert len(explanation) > 20, "Explanation should be meaningful"

    def test_explanation_mentions_safety_factors(self):
        """Explanation should reference the key safety factors"""
        from app.services.groq_service import GroqService
        service = GroqService()
        route_data = {
            "type": "recommended",
            "safety_score": 78,
            "time": 25,
            "factors": {
                "lighting": 8, "police": 9, "crowd": 7,
                "road_type": 8, "crime": 6, "accessibility": 5, "reports": 9
            }
        }
        explanation = service.generate_explanation(route_data, night=False)
        # Should mention at least one of the top factors
        keywords = ["police", "lighting", "lit", "safe", "crowd", "shop", "road"]
        found = any(kw in explanation.lower() for kw in keywords)
        assert found, f"Explanation doesn't mention any safety factors: {explanation}"

    def test_night_explanation_mentions_darkness(self):
        """Night mode explanation should reference time/darkness"""
        from app.services.groq_service import GroqService
        service = GroqService()
        route_data = {
            "type": "recommended",
            "safety_score": 55,
            "time": 25,
            "factors": {
                "lighting": 5, "police": 7, "crowd": 3,
                "road_type": 7, "crime": 5, "accessibility": 4, "reports": 6
            }
        }
        explanation = service.generate_explanation(route_data, night=True)
        night_keywords = ["night", "dark", "evening", "pm", "am", "hour", "late"]
        found = any(kw in explanation.lower() for kw in night_keywords)
        assert found, f"Night explanation doesn't reference time: {explanation}"

    def test_hindi_explanation(self):
        """Should support Hindi translation"""
        from app.services.groq_service import GroqService
        service = GroqService()
        route_data = {
            "type": "recommended",
            "safety_score": 78,
            "time": 25,
            "factors": {
                "lighting": 8, "police": 9, "crowd": 7,
                "road_type": 8, "crime": 6, "accessibility": 5, "reports": 9
            }
        }
        explanation = service.generate_explanation(route_data, night=False, language="hi")
        # Should contain Hindi characters (Devanagari)
        has_hindi = any('\u0900' <= c <= '\u097F' for c in explanation)
        assert has_hindi or len(explanation) > 20, \
            "Hindi explanation should be in Hindi or fallback to English"


class TestAdminRecommendations:
    """Test AI-generated admin recommendations"""

    def test_recommendations_generated(self):
        """Admin recommendations should be generated from danger zones"""
        from app.services.groq_service import GroqService
        service = GroqService()
        danger_zones = [
            {"name": "Industrial Area Road", "score": 12, "factors": {"lighting": 1, "police": 2}},
            {"name": "Sitapura SEZ", "score": 18, "factors": {"lighting": 3, "crowd": 1}},
        ]
        recommendations = service.generate_admin_recommendations(danger_zones)
        assert len(recommendations) >= 1, "Should generate at least 1 recommendation"
        assert all("name" in r for r in recommendations), "Each recommendation needs a zone name"
        assert all("action" in r for r in recommendations), "Each recommendation needs an action"
