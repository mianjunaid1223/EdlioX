from functools import wraps
from flask import session, redirect, url_for, flash, g, current_app, request
from bson.objectid import ObjectId
import os
from PIL import Image
import io
import base64

# Store current user in g for request lifetime
def get_current_user():
    """Get the current user from the session"""
    # Check if user is already loaded in g
    if hasattr(g, 'user'):
        return g.user
    
    # Check if user ID is in session
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    # Load user from database
    try:
        from app.models.user import User
        user_data = current_app.db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            g.user = User(user_data)
            return g.user
    except Exception as e:
        current_app.logger.error(f"Error loading user: {e}")
    
    return None

def process_profile_image(image_file, max_size=(250, 250), quality=85):
    """
    Process and optimize profile image
    
    Args:
        image_file: The uploaded image file
        max_size: Maximum dimensions (width, height)
        quality: JPEG compression quality (1-100)
        
    Returns:
        Binary image data to store in MongoDB
    """
    try:
        # Open and process the image with Pillow
        img = Image.open(image_file)
        
        # Convert to RGB if image has alpha channel
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img if img.mode == 'RGBA' else None)
            img = background
        
        # Resize image while maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save optimized image to memory buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        
        # Get binary data
        binary_data = buffer.getvalue()
        
        return binary_data
    except Exception as e:
        current_app.logger.error(f"Error processing profile image: {e}")
        return None

def get_profile_image_url(user_id, profile_image=None):
    """
    Get profile image URL - either from database or default avatar
    
    Args:
        user_id: User ID
        profile_image: Profile image binary data (optional)
        
    Returns:
        URL to profile image or default avatar
    """
    if profile_image:
        return f"data:image/jpeg;base64,{base64.b64encode(profile_image).decode('utf-8')}"
    return url_for('static', filename='images/default-avatar.png')

# Login required decorator
def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            flash("Please log in to access this page", "error")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function 