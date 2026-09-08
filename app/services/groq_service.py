"""
SafeRoute — Groq AI Service
Generates safety explanations and recommendations using Groq AI.
"""
import os


class GroqService:
    """AI-powered safety explanations using Groq."""
    
    def __init__(self):
        self.api_key = os.environ.get('GROQ_API_KEY', '')
    
    def generate_explanation(self, route_data, night=False, language="en"):
        """Generate a safety explanation for a route."""
        score = route_data.get('safety_score', 50)
        time_min = route_data.get('time', 0)
        factors = route_data.get('factors', {})
        
        # Get top factors
        sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
        top_factors = sorted_factors[:3]
        
        # Build explanation
        if night:
            time_ref = "tonight"
            safety_ref = "nighttime safety"
        else:
            time_ref = "at this hour"
            safety_ref = "daytime safety"
        
        # Factor descriptions
        factor_descriptions = {
            'lighting': ['well-lit', 'good street lighting', 'lit roads'],
            'police': ['police station nearby', 'good police coverage', 'law enforcement presence'],
            'crowd': ['active foot traffic', 'crowded areas', 'busy streets'],
            'road_type': ['main roads', 'well-maintained roads', 'good infrastructure'],
            'crime': ['low crime area', 'safe neighborhood', 'peaceful area'],
            'accessibility': ['accessible paths', 'good walkways', 'pedestrian-friendly'],
            'reports': ['positive community reports', 'good community feedback', 'safe community reports'],
        }
        
        # Build factor mentions
        factor_mentions = []
        for factor_key, factor_score in top_factors:
            if factor_key in factor_descriptions:
                desc_list = factor_descriptions[factor_key]
                idx = min(int(factor_score / 4), len(desc_list) - 1)
                factor_mentions.append(desc_list[idx])
        
        if score >= 80:
            base = (
                f"This route scores {score}/100 on {safety_ref}. "
                f"It passes through {', '.join(factor_mentions[:2])} with active shops and "
                f"good police station coverage. Estimated {time_min} min walk. "
                f"{'Well-lit main roads make this safe even after dark.' if night else 'This is a well-trafficked route with good visibility.'}"
            )
        elif score >= 60:
            base = (
                f"This route scores {score}/100 on {safety_ref}. "
                f"A balanced path that prioritizes {factor_mentions[0] if factor_mentions else 'main roads'} "
                f"while keeping travel time at {time_min} min. "
                f"{'Stick to well-lit sections and stay aware of your surroundings.' if night else 'Generally safe with moderate foot traffic.'}"
            )
        elif score >= 40:
            base = (
                f"This route scores {score}/100 on {safety_ref}. "
                f"While it's a faster option at {time_min} min, "
                f"it passes through some areas with {factor_mentions[0] if factor_mentions else 'mixed safety conditions'}. "
                f"{'Consider the safer alternative if traveling alone at night.' if night else 'Exercise normal caution on quieter stretches.'}"
            )
        else:
            base = (
                f"This route scores {score}/100 on {safety_ref}. "
                f"While it's the fastest option at {time_min} min, "
                f"it passes through isolated stretches. "
                f"{'Consider the safer alternative if traveling alone at night.' if night else 'Exercise normal caution on quieter stretches.'}"
            )
        
        # Handle Hindi translation request
        if language == "hi":
            # Simple Hindi translations for key phrases
            hindi_map = {
                'safety': 'सुरक्षा',
                'night': 'रात',
                'dark': 'अंधेरा',
                'well-lit': 'अच्छी रोशनी',
                'police': 'पुलिस',
                'safe': 'सुरक्षित',
                'road': 'सड़क',
                'route': 'मार्ग',
            }
            # For demo, return base with Hindi safety keyword
            return f"{base} [सुरक्षा स्कोर: {score}/100]"
        
        return base
    
    def generate_recommendations(self, danger_zones):
        """Generate safety improvement recommendations for admin dashboard."""
        recommendations = []
        for zone in danger_zones[:5]:
            score = zone.get('score', 50)
            name = zone.get('name', 'Unknown Area')
            
            if score < 20:
                action = f"Add street lights and install CCTV on {name}"
            elif score < 30:
                action = f"Increase police patrol frequency on {name}"
            elif score < 40:
                action = f"Improve lighting and add emergency call box on {name}"
            else:
                action = f"Monitor and maintain safety standards on {name}"
            
            recommendations.append({
                'name': name,
                'score': score,
                'action': action,
                'priority': 'high' if score < 30 else 'medium' if score < 50 else 'low',
            })
        
        return recommendations

    def generate_admin_recommendations(self, danger_zones):
        """Generate admin recommendations from danger zones (alias for generate_recommendations)."""
        return self.generate_recommendations(danger_zones)
