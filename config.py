import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/edliox')
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    ADMINS = ['mianjunaid2312@gmail.com']
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Google Gemini AI Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Payment Gateway Configuration
    STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
    AWS_REGION = os.getenv('AWS_REGION')
    
    # Monetization config
    MONETIZATION_VIEW_THRESHOLD = 1000
    MONETIZATION_RATE_PER_1000_VIEWS = 0.20  # USD
    MINIMUM_PAYOUT_THRESHOLD = 50.0  # USD
    
    # API settings
    API_PREFIX = '/api'
    
    # Discussion settings
    DISCUSSIONS_PER_PAGE = 10
    COMMENTS_PER_PAGE = 20
    
    # Application-wide constants
    GRADE_LEVELS = [
        "Elementary", 
        "Middle School", 
        "High School", 
        "College", 
        "Graduate", 
        "Professional"
    ]
    
    SUBJECTS = [
        "Mathematics", 
        "Science", 
        "Physics", 
        "Chemistry", 
        "Biology", 
        "English", 
        "History", 
        "Computer Science", 
        "Languages", 
        "Arts", 
        "Other"
    ] 