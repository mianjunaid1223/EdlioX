from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User
from app import create_app, login_manager
from flask_mail import Message
from app import mail
from datetime import datetime, timedelta
from app.forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm, ProfileForm
from urllib.parse import urlparse
from bson.objectid import ObjectId
from app.auth.utils import process_profile_image

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    try:
        # Convert string id to ObjectId for MongoDB
        from app.database import get_db
        object_id = ObjectId(user_id)
        db = get_db()
        user_data = db.users.find_one({'_id': object_id})
        if user_data:
            return User(user_data)
    except Exception as e:
        current_app.logger.error(f"Error loading user: {str(e)}")
    return None

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegisterForm()
    if form.validate_on_submit():
        # Get database connection
        from app.database import get_db
        db = get_db()
        
        # Process profile image if provided
        profile_image = None
        if form.profile_image.data:
            try:
                profile_image = process_profile_image(form.profile_image.data)
                if not profile_image:
                    flash('Error processing profile image. Using default avatar.', 'warning')
            except Exception as e:
                current_app.logger.error(f"Error processing profile image: {str(e)}")
                flash('Error processing profile image. Using default avatar.', 'warning')
        
        # Create new user
        user = User.create_user(
            db=db,
            username=form.username.data.lower(),  # Store username in lowercase
            email=form.email.data.lower(),  # Store email in lowercase
            password=form.password.data,
            country=form.country.data,
            profile_image=profile_image
        )
        
        if user is None:
            # Check which field caused the conflict
            existing_username = User.get_by_username(form.username.data.lower(), db=db)
            existing_email = User.get_by_email(form.email.data.lower(), db=db)
            
            if existing_username:
                form.username.errors.append('Username already exists.')
            if existing_email:
                form.email.errors.append('Email already exists.')
            return render_template('auth/register.html', form=form)
        
        # Log in the user and set remember=True for persistent session
        login_user(user, remember=True)
        
        # Set session values
        session['user_id'] = user.id
        session['username'] = user.username
        session.permanent = True
        
        # Update last login time
        from app.database import get_db
        db = get_db()
        user.update_last_login(db)
        
        flash('Registration successful!', 'success')
        # Force a session save and reload
        session.modified = True
        
        return redirect(url_for('main.index'))
    
    return render_template('auth/register.html', form=form)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        # Try finding user by username first
        user = User.get_by_username(form.username.data.lower(), db=current_app.db)
        
        # If not found by username, try by email
        if user is None:
            user = User.get_by_email(form.username.data.lower(), db=current_app.db)
            
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username/email or password', 'error')
            return redirect(url_for('auth.login'))
        
        # Log in the user
        login_user(user, remember=form.remember_me.data)
        
        # Set session values
        session['user_id'] = user.id
        session['username'] = user.username
        session.permanent = True
        
        # Update last login time
        from app.database import get_db
        db = get_db()
        user.update_last_login(db)
        
        # Get next page or default to index
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        # Force a session save and reload
        session.modified = True
            
        flash('Logged in successfully.', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    # Logout the user from Flask-Login
    logout_user()
    
    # Clear session data explicitly, including all items
    for key in list(session.keys()):
        session.pop(key, None)
        
    # Force session.modified flag
    session.modified = True
    
    # Prepare response
    response = redirect(url_for('main.index'))
    
    # Clear session cookie
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    response.delete_cookie(session_cookie_name, path='/', domain=None)
    
    # Clear the remember-me cookie if it exists
    response.delete_cookie('remember_token', path='/', domain=None)
    
    # Clear any application-specific cookies
    response.delete_cookie('user_session', path='/', domain=None)
    
    # Add cache control headers to prevent caching issues
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    flash('You have been logged out.', 'success')
    return response

@bp.route('/profile', methods=['GET', 'POST'])
def profile():
    # Get username from query parameter
    username = request.args.get('username')
    
    # Get database connection
    from app.database import get_db
    db = get_db()
    
    # If viewing another user's profile
    if username and (not current_user.is_authenticated or username.lower() != current_user.username.lower()):
        # Get the user by username
        user_data = db.users.find_one({'username': username.lower()})
        if not user_data:
            flash('User not found', 'error')
            return redirect(url_for('main.index'))
        
        profile_user = User(user_data)
        
        # Get user's resources
        user_resources = list(db.resources.find({'user_id': profile_user.id}))
        from app.models.resource import Resource
        resources = [Resource(resource_data) for resource_data in user_resources]
        
        # Get user's discussions - UPDATED to handle both string and ObjectId
        user_id = profile_user.id
        
        # Try both string and ObjectId versions to be safe
        filter_conditions = [
            {'user_id': user_id}
        ]
        
        # If it's a string that could be converted to ObjectId, also try with ObjectId
        if ObjectId.is_valid(user_id):
            filter_conditions.append({'user_id': ObjectId(user_id)})
            
        # Create the final filter with OR condition
        discussion_filter = {'$or': filter_conditions}
        
        # Get discussions with the improved filter
        user_discussions = list(db.discussions.find(discussion_filter))
        
        # Format discussions data
        discussions = []
        for discussion in user_discussions:
            # Ensure basic fields exist
            discussion_data = {
                '_id': discussion.get('_id'),
                'title': discussion.get('title', 'Untitled Discussion'),
                'content': discussion.get('content', ''),
                'subject': discussion.get('subject'),
                'grade_level': discussion.get('grade_level'),
                'views': discussion.get('views', 0),
                'comment_count': len(discussion.get('comments', [])),
                'created_at': discussion.get('created_at', datetime.utcnow())
            }
            discussions.append(discussion_data)
        
        # Render public profile template
        return render_template('auth/public_profile.html', 
                             profile_user=profile_user, 
                             resources=resources, 
                             discussions=discussions)
    
    # If viewing own profile and logged in
    if current_user.is_authenticated:
        form = ProfileForm()
        password_form = ChangePasswordForm()
        
        if form.validate_on_submit():
            # Update user profile
            
            # Process profile image if provided
            if form.profile_image.data:
                try:
                    profile_image = process_profile_image(form.profile_image.data)
                    if profile_image:
                        current_user.update_profile(
                            db=db,
                            profile_image=profile_image
                        )
                    else:
                        flash('Error processing profile image.', 'warning')
                except Exception as e:
                    current_app.logger.error(f"Error processing profile image: {str(e)}")
                    flash('Error processing profile image.', 'warning')
            
            # Update other profile fields
            current_user.update_profile(
                db=db,
                country=form.country.data,
                grade_level=form.grade_level.data
            )
            
            flash('Profile updated successfully', 'success')
            return redirect(url_for('auth.profile'))
        
        # Pre-fill form with current values
        if request.method == 'GET':
            form.country.data = current_user.country
            form.grade_level.data = current_user.grade_level
        
        return render_template('auth/profile.html', form=form, password_form=password_form)
    
    # Not logged in and no username specified
    return redirect(url_for('auth.login'))

@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Check current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('auth.profile'))
        
        # Update password
        from app.database import get_db
        db = get_db()
        current_user.update_profile(
            db=db,
            password_hash=generate_password_hash(form.new_password.data)
        )
        
        flash('Password updated successfully', 'success')
        return redirect(url_for('auth.profile'))
    
    return redirect(url_for('auth.profile'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        # Find user by email
        from app.database import get_db
        db = get_db()
        user_data = db.users.find_one({'email': form.email.data})
        if not user_data:
            flash('Email not found', 'error')
            return redirect(url_for('auth.forgot_password'))
        
        # Generate password reset token
        user = User(user_data)
        token = user.generate_reset_token()
        
        # Save the token to the database
        db.users.update_one(
            {'_id': user._id},
            {'$set': {
                'reset_token': user.reset_token,
                'reset_token_expires': user.reset_token_expires
            }}
        )
        
        # Send password reset email
        try:
            msg = Message('Password Reset Request',
                         sender=current_app.config['MAIL_DEFAULT_SENDER'],
                         recipients=[user.email])
            msg.body = f'''To reset your password, visit the following link:
{url_for('auth.reset_password', token=token, _external=True)}

If you did not make this request then simply ignore this email.
'''
            mail.send(msg)
            flash('Password reset instructions sent to your email', 'success')
        except Exception as e:
            current_app.logger.error(f'Failed to send reset email: {str(e)}')
            flash('An error occurred while sending the reset email', 'error')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    from app.database import get_db
    db = get_db()
    user_data = db.users.find_one({
        'reset_token': token,
        'reset_token_expires': {'$gt': datetime.utcnow()}
    })
    
    if not user_data:
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('auth.forgot_password'))
        
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Update password
        user = User(user_data)
        from app.database import get_db
        db = get_db()
        user.update_profile(
            db=db,
            password_hash=generate_password_hash(form.new_password.data),
            reset_token=None
        )
        
        flash('Password reset successfully', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)