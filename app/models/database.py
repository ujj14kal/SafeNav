"""
SafeRoute — SQLAlchemy Database Models
All persistent data storage for safety feedback, incidents, journeys, recordings, zones, users.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class SafetyFeedback(db.Model):
    """User feedback (safe/unsafe) tied to exact lat/lng and optional zone."""
    __tablename__ = 'safety_feedback'
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey('location_zone.id'), nullable=True)
    feedback_type = db.Column(db.String(16), nullable=False)  # 'safe' or 'unsafe'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(64), default='anonymous')
    route_info = db.Column(db.Text, nullable=True)  # JSON string of route context

    def to_dict(self):
        return {
            'id': self.id, 'lat': self.lat, 'lng': self.lng,
            'zone_id': self.zone_id, 'feedback_type': self.feedback_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id, 'route_info': self.route_info,
        }


class Incident(db.Model):
    """Reported incidents (from community reports, SOS, etc.)."""
    __tablename__ = 'incident'
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    location_name = db.Column(db.String(256), nullable=True)  # e.g. "Manipal University Jaipur"
    type = db.Column(db.String(64), nullable=False)  # e.g. 'poor_lighting', 'stalker'
    category = db.Column(db.String(32), default='environmental')
    severity = db.Column(db.String(16), default='medium')  # low, medium, high, critical
    description = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(32), default='user_report')  # user_report, sos, admin
    user_id = db.Column(db.String(64), default='anonymous')
    weight = db.Column(db.Float, default=1.0)
    verifications = db.Column(db.Integer, default=0)
    status = db.Column(db.String(16), default='active')  # active, resolved, expired

    def to_dict(self):
        return {
            'id': self.id, 'lat': self.lat, 'lng': self.lng,
            'location_name': self.location_name,
            'type': self.type, 'category': self.category,
            'severity': self.severity, 'description': self.description,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'source': self.source, 'user_id': self.user_id,
            'weight': self.weight, 'verifications': self.verifications,
            'status': self.status,
        }


class Journey(db.Model):
    """Her Way Home journey monitoring."""
    __tablename__ = 'journey'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), nullable=False)
    origin_lat = db.Column(db.Float, nullable=False)
    origin_lng = db.Column(db.Float, nullable=False)
    dest_lat = db.Column(db.Float, nullable=False)
    dest_lng = db.Column(db.Float, nullable=False)
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    eta_minutes = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(16), default='active')  # active, completed, cancelled
    notifications = db.Column(db.Text, nullable=True)  # JSON list of notifications

    def to_dict(self):
        import json
        return {
            'id': self.id, 'user_id': self.user_id,
            'origin': [self.origin_lat, self.origin_lng],
            'destination': [self.dest_lat, self.dest_lng],
            'current': [self.current_lat, self.current_lng] if self.current_lat else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'eta_minutes': self.eta_minutes, 'status': self.status,
            'notifications': json.loads(self.notifications) if self.notifications else [],
        }


class Recording(db.Model):
    """Audio recordings stored during SOS or voluntarily."""
    __tablename__ = 'recording'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), default='anonymous')
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    audio_path = db.Column(db.String(256), nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sos_id = db.Column(db.String(16), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # bytes

    def to_dict(self):
        return {
            'id': self.id, 'user_id': self.user_id,
            'lat': self.lat, 'lng': self.lng,
            'audio_path': self.audio_path,
            'duration_seconds': self.duration_seconds,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'sos_id': self.sos_id, 'file_size': self.file_size,
        }


class LocationZone(db.Model):
    """Pre-defined safety zones with base scores from DB data."""
    __tablename__ = 'location_zone'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    center_lat = db.Column(db.Float, nullable=False)
    center_lng = db.Column(db.Float, nullable=False)
    radius_m = db.Column(db.Float, default=500.0)
    base_safety_score = db.Column(db.Float, nullable=True)  # 0-100
    road_type = db.Column(db.String(32), nullable=True)
    lighting = db.Column(db.Float, nullable=True)  # 0-10
    police_proximity = db.Column(db.Float, nullable=True)  # 0-10
    crowd_density = db.Column(db.Float, nullable=True)  # 0-10
    description = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'center_lat': self.center_lat, 'center_lng': self.center_lng,
            'radius_m': self.radius_m,
            'base_safety_score': self.base_safety_score,
            'road_type': self.road_type, 'lighting': self.lighting,
            'police_proximity': self.police_proximity,
            'crowd_density': self.crowd_density,
            'description': self.description,
        }


class User(db.Model):
    """User accounts with profile info."""
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    full_name = db.Column(db.String(128), nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), default='user')  # 'user' or 'admin'
    home_lat = db.Column(db.Float, nullable=True)
    home_lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username,
            'email': self.email, 'phone': self.phone,
            'full_name': self.full_name, 'role': self.role,
            'home_lat': self.home_lat, 'home_lng': self.home_lng,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class Guardian(db.Model):
    """Emergency guardian contacts — persisted to DB."""
    __tablename__ = 'guardian'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(128), nullable=True)
    relationship = db.Column(db.String(64), default='friend')
    is_primary = db.Column(db.Boolean, default=False)  # Primary guardian gets SMS first
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'relationship': self.relationship,
            'is_primary': self.is_primary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SOSHistory(db.Model):
    """Persistent SOS event log."""
    __tablename__ = 'sos_history'
    id = db.Column(db.Integer, primary_key=True)
    sos_id = db.Column(db.String(16), unique=True, nullable=False)
    user_id = db.Column(db.String(64), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(16), default='panic')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(16), default='active')
    resolved_at = db.Column(db.DateTime, nullable=True)
    audio_path = db.Column(db.String(256), nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'sos_id': self.sos_id, 'user_id': self.user_id,
            'lat': self.lat, 'lng': self.lng, 'type': self.type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'audio_path': self.audio_path,
        }
