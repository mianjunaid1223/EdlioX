from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_cors import CORS
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, generate_csrf
from config import Config
import os
from pymongo import MongoClient
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from markupsafe import Markup
import markdown

# Initialize extensions
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
mail = Mail()
sess = Session()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static')
    app.config.from_object(config_class)
    
    # Ensure secret key is set
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.urandom(24)
    
    # Initialize MongoDB with pure pymongo
    client = MongoClient(app.config['MONGODB_URI'])
    # Extract database name properly, without including query parameters
    uri_parts = app.config['MONGODB_URI'].split('/')
    db_name = uri_parts[-1].split('?')[0]
    app.db = client[db_name]
    
    # Create indexes for discussions
    app.db.discussions.create_index([("title", "text"), ("content", "text")])
    app.db.discussions.create_index("score")
    app.db.discussions.create_index("created_at")
    
    # Initialize extensions
    login_manager.init_app(app)
    mail.init_app(app)
    sess.init_app(app)
    csrf.init_app(app)
    CORS(app)
    
    # Add Markdown filter instead of using the extension
    @app.template_filter('markdown')
    def render_markdown(text):
        return Markup(markdown.markdown(text, extensions=['extra', 'codehilite']))
    
    # Add CSRF token to template context
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=lambda: generate_csrf())
    
    # Add grade levels and subjects to template context
    @app.context_processor
    def inject_constants():
        return dict(
            grade_levels=app.config['GRADE_LEVELS'],
            subjects=app.config['SUBJECTS']
        )
    
    # Register blueprints
    from app.routes import auth, resources, discussion_routes, admin, monetization, main
    from app.api import comments
    from app.api.discussions import api_discussions
    app.register_blueprint(auth.bp)
    app.register_blueprint(resources.bp)
    app.register_blueprint(discussion_routes.discussions_bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(monetization.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(comments.bp, url_prefix='/api')
    app.register_blueprint(api_discussions, url_prefix='/api')
    
    # Create upload folder if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Register custom template filters
    @app.template_filter('timeago')
    def timeago_filter(timestamp):
        """Format a timestamp as a human-readable timeago string"""
        if not timestamp:
            return ''
            
        # Convert to datetime if string
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                try:
                    timestamp = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f')
                except:
                    return timestamp
        
        # Calculate time difference
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
        diff = now - timestamp
        
        # Format as human-readable string
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days} day{"s" if days != 1 else ""} ago'
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f'{weeks} week{"s" if weeks != 1 else ""} ago'
        else:
            return timestamp.strftime('%b %d, %Y')
    
    # Setup logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')
    
    return app