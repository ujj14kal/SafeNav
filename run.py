"""
SafeNav — Entry Point
Run: python run.py
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("\n🛡️  SafeNav — Safe Route Recommendation System")
    print("=" * 50)
    print("📍 Route Planner:  http://localhost:5000")
    print("🔥 Heatmap:        http://localhost:5000/heatmap")
    print("🏫 School Routes:  http://localhost:5000/school")
    print("📊 Admin Dashboard: http://localhost:5000/admin")
    print("🔌 API:            http://localhost:5000/api/route")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
