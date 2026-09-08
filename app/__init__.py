"""
SafeRoute — Flask Application Factory
"""
import os
from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__,
                static_folder='../static',
                template_folder='../templates')
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'saferoute-dev-key')
    app.config['GROQ_API_KEY'] = os.environ.get('GROQ_API_KEY', '')
    
    CORS(app)
    
    from app.routes.api import api_bp
    app.register_blueprint(api_bp)
    
    from app.routes.views import views_bp
    app.register_blueprint(views_bp)
    
    return app
