"""
SafeNav — Page Routes (serve HTML templates)
"""
from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    """Main route planner page."""
    return render_template('index.html')


@views_bp.route('/heatmap')
def heatmap():
    """City-wide safety heatmap page."""
    return render_template('heatmap.html')


@views_bp.route('/school')
def school():
    """School route mode page."""
    return render_template('school.html')


@views_bp.route('/admin')
def admin():
    """City admin dashboard page."""
    return render_template('admin.html')


@views_bp.route('/sos')
def sos():
    """Emergency SOS page with GPS and guardian SMS."""
    return render_template('sos.html')
