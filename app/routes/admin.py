from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from app.models.resource import Resource
from app.models.discussion import Discussion
from app.models.user import User
from app import create_app
import os
from datetime import datetime

bp = Blueprint('admin', __name__)

def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    # Copy the original function's attributes to the decorated function
    decorated_function.__name__ = f.__name__
    return decorated_function

@bp.route('/admin/dashboard')
@admin_required
def dashboard():
    app = create_app()
    
    # Get statistics
    stats = {
        'total_users': app.db.users.count_documents({}),
        'total_resources': app.db.resources.count_documents({}),
        'total_discussions': app.db.discussions.count_documents({}),
        'pending_monetization': app.db.users.count_documents({'monetization_status': 'pending'}),
        'flagged_discussions': app.db.discussions.count_documents({'status': 'moderated'}),
        
        # New viewer statistics
        'total_views': sum(r.get('views', 0) for r in app.db.resources.find({}, {'views': 1})),
        'unique_views': sum(r.get('unique_views', 0) for r in app.db.resources.find({}, {'unique_views': 1})),
        'returning_viewers': app.db.resource_views.count_documents({'return_count': {'$gt': 0}}),
        
        # Get today's count as well
        'new_users_today': app.db.users.count_documents({
            'created_at': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        }),
        'new_resources_today': app.db.resources.count_documents({
            'created_at': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        }),
        'new_discussions_today': app.db.discussions.count_documents({
            'created_at': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        }),
        'pending_actions': app.db.users.count_documents({'monetization_status': 'pending'})
    }
    
    # Get recent activity
    recent_activity = []
    
    # Get pending monetization requests from users
    pending_monetization = []
    for user_data in app.db.users.find({'monetization_status': 'pending'}).limit(5):
        user = User(user_data)
        
        pending_monetization.append({
            'user': user,
            'created_at': user_data.get('monetization_applied_at', user_data.get('created_at')),
            'total_views': user_data.get('total_views', 0)
        })
    
    # Get resources with most returning viewers for insights
    top_returning_resources = []
    pipeline = [
        {'$group': {
            '_id': '$resource_id', 
            'returning_count': {'$sum': '$return_count'},
            'unique_viewers': {'$sum': 1}
        }},
        {'$sort': {'returning_count': -1}},
        {'$limit': 5}
    ]
    
    for result in app.db.resource_views.aggregate(pipeline):
        resource_data = app.db.resources.find_one({'_id': result['_id']})
        if resource_data:
            resource = Resource(resource_data)
            top_returning_resources.append({
                'resource': resource,
                'returning_count': result['returning_count'],
                'unique_viewers': result['unique_viewers'],
                'return_rate': result['returning_count'] / result['unique_viewers'] if result['unique_viewers'] > 0 else 0
            })
    
    # Get flagged content
    flagged_content = []
    
    # Get active users
    active_users_count = app.db.users.count_documents({'last_login': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}})
    
    return render_template(
        'admin/dashboard.html', 
        stats=stats, 
        recent_activity=recent_activity,
        pending_monetization=pending_monetization,
        flagged_content=flagged_content,
        top_returning_resources=top_returning_resources,
        active_users_count=active_users_count
    )

@bp.route('/admin/users')
@admin_required
def manage_users():
    app = create_app()
    users = []
    for user_data in app.db.users.find():
        users.append(User(user_data))
    
    return render_template('admin/users.html', users=users)

@bp.route('/admin/resources')
@admin_required
def manage_resources():
    app = create_app()
    resources = []
    for resource_data in app.db.resources.find():
        resources.append(Resource(resource_data))
    
    return render_template('admin/resources.html', resources=resources)

@bp.route('/admin/discussions')
@admin_required
def manage_discussions():
    app = create_app()
    discussions = []
    for discussion_data in app.db.discussions.find():
        discussions.append(Discussion(discussion_data))
    
    return render_template('admin/discussions.html', discussions=discussions)

@bp.route('/admin/monetization')
@admin_required
def manage_monetization():
    app = create_app()
    users = []
    for user_data in app.db.users.find({'monetization_status': 'pending'}):
        users.append(User(user_data))
    
    return render_template('admin/monetization.html', users=users)

@bp.route('/admin/user/<user_id>/approve-monetization', methods=['POST'])
@admin_required
def approve_monetization(user_id):
    app = create_app()
    user_data = app.db.users.find_one({'_id': user_id})
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    user = User(user_data)
    user.approve_monetization(app.db)
    
    return jsonify({'message': 'Monetization approved successfully'})

@bp.route('/admin/user/<user_id>/reject-monetization', methods=['POST'])
@admin_required
def reject_monetization(user_id):
    app = create_app()
    user_data = app.db.users.find_one({'_id': user_id})
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    user = User(user_data)
    user.reject_monetization(app.db)
    
    return jsonify({'message': 'Monetization rejected successfully'})

@bp.route('/admin/user/<user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    app = create_app()
    user_data = app.db.users.find_one({'_id': user_id})
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    user = User(user_data)
    user.update_profile(
        db=app.db,
        is_admin=not user.is_admin
    )
    
    return jsonify({'message': 'Admin status updated successfully'})

@bp.route('/admin/user/<user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    app = create_app()
    
    # Delete user's resources
    app.db.resources.delete_many({'user_id': user_id})
    
    # Delete user's discussions
    app.db.discussions.delete_many({'user_id': user_id})
    
    # Delete user
    app.db.users.delete_one({'_id': user_id})
    
    return jsonify({'message': 'User deleted successfully'})

@bp.route('/admin/resource/<resource_id>/delete', methods=['POST'])
@admin_required
def delete_resource(resource_id):
    app = create_app()
    
    # Check if resource exists
    resource = app.db.resources.find_one({'_id': resource_id})
    if not resource:
        return jsonify({'success': False, 'message': 'Resource not found'}), 404
    
    # Delete the resource
    app.db.resources.delete_one({'_id': resource_id})
    
    # Also delete any associated data like ratings, views, etc.
    if hasattr(app, 'db') and hasattr(app.db, 'resource_views'):
        app.db.resource_views.delete_many({'resource_id': resource_id})
    
    if hasattr(app, 'db') and hasattr(app.db, 'resource_ratings'):
        app.db.resource_ratings.delete_many({'resource_id': resource_id})
    
    return jsonify({'success': True, 'message': 'Resource deleted successfully'})

@bp.route('/admin/discussion/<discussion_id>/delete', methods=['POST'])
@admin_required
def delete_discussion(discussion_id):
    app = create_app()
    app.db.discussions.delete_one({'_id': discussion_id})
    
    return jsonify({'message': 'Discussion deleted successfully'})

@bp.route('/admin/earnings')
@admin_required
def view_earnings():
    app = create_app()
    
    # Get all users with earnings
    users = []
    for user_data in app.db.users.find({'pending_earnings': {'$gt': 0}}):
        users.append(User(user_data))
    
    return render_template('admin/earnings.html', users=users)

@bp.route('/admin/user/<user_id>/approve-payout', methods=['POST'])
@admin_required
def approve_payout(user_id):
    app = create_app()
    user_data = app.db.users.find_one({'_id': user_id})
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    user = User(user_data)
    if user.request_payout(app.db):
        return jsonify({'message': 'Payout approved successfully'})
    else:
        return jsonify({'error': 'User does not meet payout threshold'}), 400

@bp.route('/admin/analytics')
@admin_required
def analytics():
    app = create_app()
    
    # Get currently active users (logged in today)
    active_users_count = app.db.users.count_documents({
        'last_login': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    
    # Get total registered users
    total_users = app.db.users.count_documents({})
    
    # Get daily resource views
    daily_views = {}
    for resource in app.db.resources.find({}, {'views': 1, 'created_at': 1}):
        day = resource.get('created_at', datetime.utcnow()).strftime('%Y-%m-%d')
        daily_views[day] = daily_views.get(day, 0) + resource.get('views', 0)
    
    # Get top resources by views
    top_resources = []
    for resource_data in app.db.resources.find().sort('views', -1).limit(10):
        resource = Resource(resource_data)
        top_resources.append({
            'title': resource.title,
            'views': resource.views,
            'author': resource.author.username if hasattr(resource.author, 'username') else 'Unknown'
        })
    
    # Get most searched keywords
    search_keywords = []
    for search in app.db.search_logs.find().sort('count', -1).limit(10):
        search_keywords.append({
            'keyword': search.get('query', ''),
            'count': search.get('count', 0)
        })
    
    # Get user growth trends
    user_growth = {}
    for user in app.db.users.find({}, {'created_at': 1}):
        month = user.get('created_at', datetime.utcnow()).strftime('%Y-%m')
        user_growth[month] = user_growth.get(month, 0) + 1
    
    # Get traffic sources if tracking enabled
    traffic_sources = {}
    for visit in app.db.visits.find({}, {'referrer': 1}):
        referrer = visit.get('referrer', 'direct')
        traffic_sources[referrer] = traffic_sources.get(referrer, 0) + 1
    
    return render_template(
        'admin/analytics.html',
        active_users=active_users_count,
        total_users=total_users,
        daily_views=daily_views,
        top_resources=top_resources,
        search_keywords=search_keywords,
        user_growth=user_growth,
        traffic_sources=traffic_sources
    )