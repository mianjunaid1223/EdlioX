from pymongo import MongoClient
from flask import current_app, g
import os

# Global MongoDB client instance
_mongo_client = None

def get_mongo_client():
    """
    Returns a MongoDB client instance, creating it if necessary.
    This function ensures we maintain a single connection pool throughout the application.
    """
    global _mongo_client
    if _mongo_client is None:
        # Get MongoDB URI from environment or use default
        mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/edliox')
        _mongo_client = MongoClient(mongodb_uri)
    return _mongo_client

def get_db():
    """Get database connection from current app"""
    if not hasattr(current_app, 'db'):
        raise RuntimeError("Database not initialized")
    return current_app.db

def close_db(e=None):
    """
    Closes the database connection at the end of the request.
    This doesn't actually close the connection but returns it to the connection pool.
    """
    db = g.pop('db', None)
    # No need to explicitly close as MongoClient manages the connection pool

def init_app(app):
    """
    Initialize the database connection with the Flask application.
    This registers the close_db function to be called when the application context ends.
    """
    app.teardown_appcontext(close_db)
    
    # Add a convenience property to access the database
    @app.before_request
    def before_request():
        g.db = get_db()
    
    # For backward compatibility, also attach db to app
    # This allows existing code using current_app.db to continue working
    @app.before_request
    def set_app_db():
        if not hasattr(current_app, 'db'):
            current_app.db = get_db()