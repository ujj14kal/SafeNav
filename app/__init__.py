"""
SafeRoute — Flask Application Factory (with SQLAlchemy DB)
"""
import os
from flask import Flask
from flask_cors import CORS
from app.models.database import (
    db, LocationZone, User, Incident, SafetyFeedback,
)
from werkzeug.security import generate_password_hash


def create_app():
    app = Flask(__name__,
                static_folder='../static',
                template_folder='../templates')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'saferoute-dev-key')
    app.config['GROQ_API_KEY'] = os.environ.get('GROQ_API_KEY', '')

    # SQLite database configuration
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'saferoute.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.abspath(db_path)}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    CORS(app)

    # Initialize database
    db.init_app(app)

    with app.app_context():
        # Drop any leftover tables from old schema, then create fresh
        try:
            # Check if old 'guardian' table exists and drop it
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            existing = inspector.get_table_names()
            if 'guardian' in existing:
                with db.engine.connect() as conn:
                    conn.execute(text('DROP TABLE guardian'))
                    conn.commit()
                print('[SafeRoute] Dropped legacy guardian table')
            # Migrate: add missing columns to existing tables
            if 'incident' in existing:
                columns = {col['name'] for col in inspector.get_columns('incident')}
                if 'location_name' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE incident ADD COLUMN location_name VARCHAR(256)'))
                        conn.commit()
                    print('[SafeRoute] Migrated: added location_name to incident')
            if 'user' in existing:
                columns = {col['name'] for col in inspector.get_columns('user')}
                new_cols = {
                    'email': 'VARCHAR(128)',
                    'phone': 'VARCHAR(20)',
                    'full_name': 'VARCHAR(128)',
                    'home_lat': 'FLOAT',
                    'home_lng': 'FLOAT',
                    'last_login': 'DATETIME',
                }
                for col_name, col_type in new_cols.items():
                    if col_name not in columns:
                        with db.engine.connect() as conn:
                            conn.execute(text(f'ALTER TABLE user ADD COLUMN {col_name} {col_type}'))
                            conn.commit()
                        print(f'[SafeRoute] Migrated: added {col_name} to user')
        except Exception as e:
            print(f'[SafeRoute] Table cleanup: {e}')
        db.create_all()
        _seed_database(app)

    from app.routes.api import api_bp
    app.register_blueprint(api_bp)

    from app.routes.views import views_bp
    app.register_blueprint(views_bp)

    return app


def _seed_database(app):
    """Seed the database with sample data for Jaipur if tables are empty."""
    # Only seed if LocationZone table is empty
    if LocationZone.query.count() > 0:
        return

    print('[SafeRoute] Seeding database with Jaipur sample data...')

    # ── Admin user ──
    admin = User(
        username='admin',
        password_hash=generate_password_hash('admin123'),
        role='admin',
    )
    db.session.add(admin)

    # ── Location Zones (covering entire Jaipur area) ──
    zones = [
        LocationZone(
            name='MI Road Commercial District',
            center_lat=26.9180, center_lng=75.7850, radius_m=800,
            base_safety_score=78.0, road_type='primary',
            lighting=8.5, police_proximity=9.0, crowd_density=8.0,
            description='Well-lit commercial area with high foot traffic and nearby police stations.'
        ),
        LocationZone(
            name='Sindhi Camp Transport Hub',
            center_lat=26.9200, center_lng=75.7850, radius_m=600,
            base_safety_score=72.0, road_type='primary',
            lighting=7.5, police_proximity=8.0, crowd_density=7.5,
            description='Busy transport area with moderate safety. Good police presence.'
        ),
        LocationZone(
            name='Mansarovar Residential',
            center_lat=26.8900, center_lng=75.7700, radius_m=1000,
            base_safety_score=65.0, road_type='residential',
            lighting=6.0, police_proximity=5.5, crowd_density=5.0,
            description='Residential area with moderate safety. Some poorly lit stretches.'
        ),
        LocationZone(
            name='Jagatpura Industrial Area',
            center_lat=26.9000, center_lng=75.8000, radius_m=800,
            base_safety_score=42.0, road_type='tertiary',
            lighting=3.5, police_proximity=3.0, crowd_density=2.5,
            description='Industrial area with poor lighting and low foot traffic. Exercise caution.'
        ),
        LocationZone(
            name='MUJ University Campus',
            center_lat=26.9124, center_lng=75.7873, radius_m=500,
            base_safety_score=82.0, road_type='secondary',
            lighting=8.0, police_proximity=7.0, crowd_density=7.0,
            description='University campus with security and good lighting.'
        ),
        LocationZone(
            name='SMS Hospital Area',
            center_lat=26.9180, center_lng=75.7880, radius_m=400,
            base_safety_score=75.0, road_type='secondary',
            lighting=8.0, police_proximity=7.5, crowd_density=7.0,
            description='Hospital area with 24/7 activity and good lighting.'
        ),
        LocationZone(
            name='World Trade Park',
            center_lat=26.8950, center_lng=75.7800, radius_m=500,
            base_safety_score=80.0, road_type='primary',
            lighting=9.0, police_proximity=6.5, crowd_density=8.5,
            description='Modern commercial complex with excellent lighting and CCTV coverage.'
        ),
        LocationZone(
            name='Ashok Nagar Residential',
            center_lat=26.9100, center_lng=75.7920, radius_m=700,
            base_safety_score=58.0, road_type='residential',
            lighting=5.0, police_proximity=6.5, crowd_density=4.5,
            description='Mixed residential area. Some streets poorly lit at night.'
        ),
        LocationZone(
            name='Hawa Mahal Tourist Zone',
            center_lat=26.9239, center_lng=75.8267, radius_m=600,
            base_safety_score=70.0, road_type='tertiary',
            lighting=6.5, police_proximity=7.0, crowd_density=6.0,
            description='Tourist area with moderate safety. Gets quieter at night.'
        ),
        LocationZone(
            name='Malviya Nagar Commercial',
            center_lat=26.8850, center_lng=75.8150, radius_m=800,
            base_safety_score=68.0, road_type='secondary',
            lighting=7.0, police_proximity=5.5, crowd_density=6.5,
            description='Growing commercial area with improving infrastructure.'
        ),
    ]
    for zone in zones:
        db.session.add(zone)

    # ── Sample Incidents (to make heatmap/time-of-day meaningful) ──
    from datetime import datetime, timedelta
    import random
    random.seed(42)

    incident_types = [
        ('poor_lighting', 'environmental', 'medium'),
        ('stalker', 'people', 'high'),
        ('drunk_person', 'people', 'medium'),
        ('no_streetlight', 'infrastructure', 'medium'),
        ('unsafe_at_night', 'high_risk', 'high'),
        ('isolated_area', 'high_risk', 'medium'),
        ('broken_cctv', 'infrastructure', 'low'),
        ('stray_animals', 'environmental', 'low'),
        ('robbery_area', 'high_risk', 'critical'),
        ('catcalling', 'people', 'medium'),
    ]

    now = datetime.utcnow()
    for i in range(40):
        zone = random.choice(zones)
        # Spread incidents across different hours for time-of-day variation
        hour = random.choice([0,1,2,3,20,21,22,23,8,10,14,16,18,19,6,7,5,4])
        inc_type, category, severity = random.choice(incident_types)
        offset_hours = random.randint(0, 168)  # up to 7 days back
        ts = now - timedelta(hours=offset_hours)
        ts = ts.replace(hour=hour)

        # Vary location within zone radius
        lat = zone.center_lat + random.uniform(-0.003, 0.003)
        lng = zone.center_lng + random.uniform(-0.003, 0.003)

        inc = Incident(
            lat=lat, lng=lng, type=inc_type, category=category,
            severity=severity,
            description=f'{inc_type.replace("_", " ")} reported near {zone.name}',
            timestamp=ts, source='user_report',
            weight=max(0.05, 1.0 - (offset_hours / 168) * 0.9),
        )
        db.session.add(inc)

    # ── Sample Feedback ──
    for i in range(25):
        zone = random.choice(zones)
        lat = zone.center_lat + random.uniform(-0.002, 0.002)
        lng = zone.center_lng + random.uniform(-0.002, 0.002)
        fb_type = 'safe' if zone.base_safety_score and zone.base_safety_score > 60 and random.random() > 0.3 else 'unsafe'
        fb = SafetyFeedback(
            lat=lat, lng=lng, zone_id=zone.id,
            feedback_type=fb_type,
            timestamp=now - timedelta(hours=random.randint(0, 72)),
            user_id=f'seed_user_{i}',
        )
        db.session.add(fb)

    db.session.commit()
    print(f'[SafeRoute] Seeded: {LocationZone.query.count()} zones, '
          f'{Incident.query.count()} incidents, {SafetyFeedback.query.count()} feedback, '
          f'{User.query.count()} users')
