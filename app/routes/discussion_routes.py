from flask import Blueprint, request, jsonify, render_template, current_app, g, redirect, url_for, flash
from app.models.discussion import Discussion
from app.auth.utils import login_required, get_current_user
from bson.objectid import ObjectId
import json
from datetime import datetime
from markdown import markdown
from markupsafe import Markup
from bson import ObjectId
import math
import re

# Create blueprint
discussions_bp = Blueprint('discussions', __name__, url_prefix='/discussions')

@discussions_bp.route('/')
def index():
    """Render discussions list page with filters and sorting"""
    # Get parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 15)) 
    max_per_page = 20  # Add maximum limit
    per_page = min(per_page, max_per_page)  # Enforce the maximum limit
    sort = request.args.get('sort', 'newest')
    search_query = request.args.get('q', '')
    subject = request.args.get('subject', '')
    grade_level = request.args.get('grade_level', '')
    tag = request.args.get('tag', '')
    
    # Map sort parameter to API sort_by
    sort_mapping = {
        'newest': 'newest',
        'active': 'active',
        'top': 'score',
        'unanswered': 'unanswered'
    }
    sort_by = sort_mapping.get(sort, 'newest')
    
    try:
        # Get discussions
        result = Discussion.get_discussions(
            current_app.db,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            search_query=search_query,
            subject=subject,
            grade_level=grade_level,
            tag=tag
        )
        
        # Get subjects and grade levels for filters from config
        subjects = current_app.config['SUBJECTS']
        grade_levels = current_app.config['GRADE_LEVELS']
        
        # Get popular tags
        popular_tags = []
        try:
            pipeline = [
                {'$unwind': '$tags'},
                {'$group': {'_id': '$tags', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}},
                {'$limit': 20}
            ]
            popular_tags = [{'name': tag['_id'], 'count': tag['count']} 
                           for tag in current_app.db.discussions.aggregate(pipeline)
                           if tag['_id']]  # Filter out None or empty tags
        except Exception as e:
            current_app.logger.error(f"Error getting popular tags: {str(e)}")
        
        # Get hot discussions
        hot_discussions = []
        try:
            hot_discussions = Discussion.get_discussions(
                current_app.db,
                page=1,
                per_page=5,  # Changed from 1 to 5 to show multiple hot discussions
                sort_by='score',
            )['discussions']
        except Exception as e:
            current_app.logger.error(f"Error getting hot discussions: {str(e)}")
        
        # Debug log
        current_app.logger.info(f"Found {len(subjects)} subjects and {len(grade_levels)} grade levels")
        
        # Render template
        return render_template(
            'discussions/index.html',
            discussions=result['discussions'],
            pagination={
                'page': page,
                'per_page': per_page,
                'total': result['total'],
                'pages': result['pages'],
                'has_prev': page > 1,
                'has_next': page < result['pages'],
                'prev_num': page - 1,
                'next_num': page + 1,
                'iter_pages': lambda: range(1, result['pages'] + 1)
            },
            sort=sort,
            subject=subject,
            grade_level=grade_level,
            subjects=subjects,
            grade_levels=grade_levels,
            popular_tags=popular_tags,
            hot_discussions=hot_discussions
        )
    except Exception as e:
        current_app.logger.error(f"Error in discussions index: {str(e)}")
        flash("An error occurred while loading discussions", "error")
        return render_template('discussions/index.html', discussions=[])

@discussions_bp.route('/ask', methods=['GET'])
@login_required
def ask_question():
    """Render the form to ask a new question"""
    # Get subjects and grade levels from config
    subjects = current_app.config['SUBJECTS']
    grade_levels = current_app.config['GRADE_LEVELS']
    
    return render_template(
        'discussions/ask.html',
        subjects=subjects,
        grade_levels=grade_levels
    )

@discussions_bp.route('/<discussion_id>')
def view_discussion(discussion_id):
    """Render single discussion page"""
    try:
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            current_app.logger.error(f"Discussion not found: {discussion_id}")
            flash("Discussion not found", "error")
            return redirect(url_for('discussions.index'))
        
        # Increment view count
        discussion.increment_views(current_app.db)
        
        # Process discussion content with markdown
        if isinstance(discussion.content, str):
            discussion.content = Markup(markdown(discussion.content, extensions=['extra', 'codehilite']))
        
        # Organize comments into threaded structure
        comments = discussion.comments
        
        # Process comments into threaded structure with markdown
        comment_dict = {}
        root_comments = []
        
        # Find the highest voted comment score
        most_voted_score = 0
        for comment in comments:
            comment_score = comment.get('score', 0)
            if comment_score > most_voted_score:
                most_voted_score = comment_score
        
        # Add user info to comments
        user_cache = {}  # Local cache for this request
        for comment in comments:
            comment_id = comment.get('id')
            
            # Apply markdown to comment content
            if isinstance(comment.get('content'), str):
                comment['content'] = Markup(markdown(comment.get('content', ''), extensions=['extra', 'codehilite']))
            
            # Ensure votes structure exists
            if 'votes' not in comment:
                comment['votes'] = {'up': [], 'down': []}
            
            # Add author information
            user_id = comment.get('user_id')
            if user_id:
                if user_id in user_cache:
                    comment['author'] = user_cache[user_id]
                else:
                    from app.models.user import User
                    user_data = current_app.db.users.find_one({'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id})
                    if user_data:
                        user = User(user_data)
                        user_cache[user_id] = user
                        comment['author'] = user
                
            comment['children'] = []
            comment_dict[comment_id] = comment
            
            if comment.get('parent_id'):
                parent = comment_dict.get(comment.get('parent_id'))
                if parent:
                    parent['children'].append(comment)
            else:
                root_comments.append(comment)
        
        # Update discussion with threaded comments
        discussion.comments = root_comments
        
        # Get related discussions
        related_discussions = []
        if discussion.subject:
            try:
                related_pipeline = [
                    {'$match': {
                        '_id': {'$ne': ObjectId(discussion_id)},
                        'subject': discussion.subject
                    }},
                    {'$limit': 5}
                ]
                related_data = list(current_app.db.discussions.aggregate(related_pipeline))
                for data in related_data:
                    related_discussions.append(Discussion(data))
            except Exception as e:
                current_app.logger.error(f"Error getting related discussions: {str(e)}")
        
        return render_template(
            'discussions/view.html',
            discussion=discussion,
            related_discussions=related_discussions,
            most_voted_score=most_voted_score
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viewing discussion: {str(e)}")
        flash("An error occurred while loading the discussion", "error")
        return redirect(url_for('discussions.index'))

@discussions_bp.route('/api/discussions', methods=['GET'])
def get_discussions():
    """API endpoint to get discussions with filters and pagination"""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        sort_by = request.args.get('sort_by', 'score')
        search_query = request.args.get('q', '')
        subject = request.args.get('subject', '')
        grade_level = request.args.get('grade_level', '')
        tag = request.args.get('tag', '')
        
        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 50:
            per_page = 10
        if sort_by not in ['score', 'newest', 'oldest', 'active', 'unanswered']:
            sort_by = 'score'
        
        # Get discussions
        result = Discussion.get_discussions(
            current_app.db,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            search_query=search_query,
            subject=subject,
            grade_level=grade_level,
            tag=tag
        )
        
        # Convert discussions to dicts
        discussions_data = []
        for discussion in result['discussions']:
            discussions_data.append(discussion.to_dict())
        
        # Return results
        return jsonify({
            'discussions': discussions_data,
            'total': result['total'],
            'pages': result['pages'],
            'current_page': result['current_page'],
            'per_page': per_page
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_discussions API: {str(e)}")
        return jsonify({'error': str(e)}), 500

@discussions_bp.route('/api/discussions', methods=['POST'])
@login_required
def create_discussion():
    """Create a new discussion"""
    try:
        # Get user
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Check if request is form or JSON
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = request.form
        
        # Validate required fields
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        subject = data.get('subject', 'General')
        grade_level = data.get('grade_level', 'General')
        
        if not title:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Title is required'}), 400
            flash('Title is required', 'error')
            return redirect(url_for('discussions.ask_question'))
            
        if not content:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Content is required'}), 400
            flash('Content is required', 'error')
            return redirect(url_for('discussions.ask_question'))
        
        # Process tags if provided
        tags = []
        if data.get('tags'):
            if isinstance(data.get('tags'), list):
                tags = data.get('tags')
            else:
                tags = [tag.strip() for tag in data.get('tags').split(',') if tag.strip()]
            
            # Limit to 5 tags
            tags = tags[:5]
        
        # Create discussion
        discussion = Discussion.create_discussion(
            current_app.db,
            user.id,
            title,
            content,
            subject=subject,
            grade_level=grade_level,
            tags=tags
        )
        
        if not discussion:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Failed to create discussion'}), 500
            flash('Failed to create discussion', 'error')
            return redirect(url_for('discussions.ask_question'))
        
        # Return response based on request type
        if request.content_type and 'application/json' in request.content_type:
            return jsonify(discussion.to_dict()), 201
        else:
            flash('Your question has been posted successfully!', 'success')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion.id))
        
    except ValueError as ve:
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({'error': str(ve)}), 400
        flash(str(ve), 'error')
        return redirect(url_for('discussions.ask_question'))
    except Exception as e:
        current_app.logger.error(f"Error in create_discussion: {str(e)}")
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({'error': str(e)}), 500
        flash('An error occurred while posting your question', 'error')
        return redirect(url_for('discussions.ask_question'))

@discussions_bp.route('/api/discussions/<discussion_id>', methods=['GET'])
def get_discussion(discussion_id):
    """Get a single discussion with its comments"""
    try:
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            return jsonify({'error': 'Discussion not found'}), 404
        
        # Increment view count
        discussion.increment_views(current_app.db)
        
        # Return discussion with comments
        return jsonify(discussion.to_dict(include_comments=True))
        
    except Exception as e:
        current_app.logger.error(f"Error in get_discussion: {str(e)}")
        return jsonify({'error': str(e)}), 500

@discussions_bp.route('/api/discussions/<discussion_id>/comments', methods=['POST'])
@login_required
def add_comment(discussion_id):
    """Add a comment to a discussion"""
    try:
        # Get user
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Check if request is form or JSON
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = request.form
        
        # Validate required fields
        content = data.get('content', '').strip()
        parent_id = data.get('parent_id')
        
        if not content:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Content is required'}), 400
            flash('Comment content is required', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Discussion not found'}), 404
            flash('Discussion not found', 'error')
            return redirect(url_for('discussions.index'))
        
        # Add comment
        comment = discussion.add_comment(current_app.db, user.id, content, parent_id)
        
        # Return response based on request type
        if request.content_type and 'application/json' in request.content_type:
            # Get avatar URL for the author
            from app.auth.utils import get_profile_image_url
            avatar_url = None
            if user.profile_image:
                avatar_url = get_profile_image_url(user.id, user.profile_image)
                
            return jsonify({
                'id': comment['id'],
                'content': comment['content'],
                'user_id': str(comment['user_id']),
                'username': user.username,
                'created_at': comment['created_at'].isoformat(),
                'parent_id': comment['parent_id'],
                'score': comment['score'],
                'author': {
                    'id': user.id,
                    'username': user.username,
                    'avatar_url': avatar_url
                }
            }), 201
        else:
            flash('Your answer has been posted', 'success')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in add_comment: {str(e)}")
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({'error': str(e)}), 500
        flash('An error occurred while posting your answer', 'error')
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))

@discussions_bp.route('/api/discussions/<discussion_id>/vote', methods=['POST'])
@login_required
def vote_on_discussion(discussion_id):
    """Handle voting on a discussion"""
    try:
        # Get required data (support both JSON and form data)
        if request.content_type and 'application/json' in request.content_type:
            vote_type = request.json.get('vote_type')
        else:
            vote_type = request.form.get('vote_type')
            
        if vote_type not in ['up', 'down']:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Invalid vote type'}), 400
            flash('Invalid vote type', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
            
        # Get current user
        user = get_current_user()
        if not user:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Authentication required'}), 401
            flash('Authentication required', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
            
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Discussion not found'}), 404
            flash('Discussion not found', 'error')
            return redirect(url_for('discussions.index'))
            
        # Process vote
        result = discussion.vote(current_app.db, user.id, vote_type)
        
        if not result.get('success', False):
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': result.get('error', 'Failed to process vote')}), 500
            flash(result.get('error', 'Failed to process vote'), 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
        # Return response based on request type
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({
                'success': True,
                'score': result['score'],
                'upvotes': result['upvotes'],
                'downvotes': result['downvotes'],
                'has_upvoted': result['has_upvoted'],
                'has_downvoted': result['has_downvoted']
            })
        
        # Redirect back to the discussion
        flash('Vote recorded successfully', 'success')
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in vote_on_discussion: {str(e)}")
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({'error': str(e)}), 500
        flash('An error occurred while processing your vote', 'error')
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))

@discussions_bp.route('/api/discussions/<discussion_id>/comments/<comment_id>/vote', methods=['POST'])
@login_required
def vote_on_comment(discussion_id, comment_id):
    """Handle voting on a comment"""
    try:
        # Get required data (support both JSON and form data)
        if request.content_type and 'application/json' in request.content_type:
            vote_type = request.json.get('vote_type')
        else:
            vote_type = request.form.get('vote_type')
            
        if vote_type not in ['up', 'down']:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Invalid vote type'}), 400
            flash('Invalid vote type', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
            
        # Get current user
        user = get_current_user()
        if not user:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Authentication required'}), 401
            flash('Authentication required', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
            
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': 'Discussion not found'}), 404
            flash('Discussion not found', 'error')
            return redirect(url_for('discussions.index'))
            
        # Process vote
        result = discussion.vote_comment(current_app.db, comment_id, user.id, vote_type)
        
        if not result.get('success', False):
            if request.content_type and 'application/json' in request.content_type:
                return jsonify({'error': result.get('error', 'Failed to process comment vote')}), 500
            flash(result.get('error', 'Failed to process comment vote'), 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
        # Return response based on request type
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({
                'success': True,
                'score': result['score'],
                'upvotes': result['upvotes'],
                'downvotes': result['downvotes'],
                'has_upvoted': result['has_upvoted'],
                'has_downvoted': result['has_downvoted']
            })
        
        # Redirect back to the discussion
        flash('Vote recorded successfully', 'success')
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in vote_on_comment: {str(e)}")
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({'error': str(e)}), 500
        flash('An error occurred while processing your vote', 'error')
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))

@discussions_bp.route('/offline.html')
def offline_page():
    """Render offline page"""
    return render_template('offline.html')

@discussions_bp.route('/<discussion_id>/delete', methods=['POST'])
@login_required
def delete_discussion(discussion_id):
    """Delete a discussion"""
    try:
        # Get user
        user = get_current_user()
        if not user:
            flash('User not authenticated', 'error')
            return redirect(url_for('discussions.index'))
        
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            flash('Discussion not found', 'error')
            return redirect(url_for('discussions.index'))
        
        # Check if user is authorized to delete
        if str(discussion.user_id) != str(user.id) and not user.is_admin:
            flash('You are not authorized to delete this discussion', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
        # Delete discussion
        delete_result = current_app.db.discussions.delete_one({'_id': ObjectId(discussion_id)})
        
        if delete_result.deleted_count > 0:
            flash('Discussion deleted successfully', 'success')
            # Invalidate cache
            from app.models.discussion import discussion_cache
            discussion_cache.put(discussion_id, None)
            return redirect(url_for('discussions.my_discussions'))
        else:
            flash('Failed to delete discussion', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting discussion: {str(e)}")
        flash('An error occurred while deleting the discussion', 'error')
        return redirect(url_for('discussions.index'))

@discussions_bp.route('/create', methods=['GET'])
def create_discussion_form():
    """Render the form to create a new discussion"""
    # Get subjects and grade levels from config
    subjects = current_app.config['SUBJECTS']
    grade_levels = current_app.config['GRADE_LEVELS']
    
    try:
        # Get subjects
        subjects = current_app.db.discussions.distinct('subject')
        subjects = [s for s in subjects if s]
        if not subjects:
            subjects = ["Mathematics", "Science", "English", "History", "Computer Science", "Languages", "Arts", "Other"]
            
        # Get grade levels
        grade_levels = current_app.db.discussions.distinct('grade_level')
        grade_levels = [g for g in grade_levels if g]
        if not grade_levels:
            grade_levels = ["Elementary", "Middle School", "High School", "College", "Graduate", "Professional"]
    except Exception as e:
        current_app.logger.error(f"Error getting subjects or grade levels: {str(e)}")
        subjects = ["Mathematics", "Science", "English", "History", "Computer Science", "Languages", "Arts", "Other"]
        grade_levels = ["Elementary", "Middle School", "High School", "College", "Graduate", "Professional"]
    
    return render_template(
        'discussions/ask.html',
        subjects=subjects,
        grade_levels=grade_levels
    )

@discussions_bp.route('/my-discussions')
@login_required
def my_discussions():
    """Show discussions created by the current user"""
    try:
        # Get current user
        user = get_current_user()
        if not user:
            flash("User not authenticated", "error")
            return redirect(url_for('discussions.index'))
            
        # Get parameters for filtering/sorting
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 15))
        sort = request.args.get('sort', 'newest')
        
        # Convert user ID to string if it's an ObjectId
        user_id = user.id
        if isinstance(user_id, ObjectId):
            user_id = str(user_id)
            
        # Log for debugging
        current_app.logger.info(f"Finding discussions for user: {user_id} (type: {type(user_id)})")
        
        # Try both string and ObjectId versions to be safe
        # This handles both storage formats that might be in the database
        filter_conditions = [
            {'user_id': user_id}
        ]
        
        # If it's a string that could be converted to ObjectId, also try with ObjectId
        if ObjectId.is_valid(user_id):
            filter_conditions.append({'user_id': ObjectId(user_id)})
            
        # Create the final filter with OR condition
        discussion_filter = {'$or': filter_conditions}
        
        # Log the filter we're using
        current_app.logger.info(f"Using filter: {discussion_filter}")
        
        # Determine sort order based on the sort parameter
        if sort == 'newest':
            sort_order = [('created_at', -1)]
        elif sort == 'active':
            sort_order = [('updated_at', -1)]
        else:  # score or default
            sort_order = [('score', -1)]
            
        # Get total count first
        total = current_app.db.discussions.count_documents(discussion_filter)
        current_app.logger.info(f"Found {total} discussions matching the filter")
        
        # Calculate pagination
        skip = (page - 1) * per_page
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        # Fetch discussions with pagination
        discussions_data = list(current_app.db.discussions
            .find(discussion_filter)
            .sort(sort_order)
            .skip(skip)
            .limit(per_page))
            
        current_app.logger.info(f"Retrieved {len(discussions_data)} discussions after pagination")
        
        # Convert to Discussion objects
        discussions = []
        for data in discussions_data:
            try:
                discussions.append(Discussion(data))
            except Exception as e:
                current_app.logger.error(f"Error creating Discussion object: {str(e)}")
        
        # Calculate stats safely
        total_comments = 0
        total_views = 0
        for discussion in discussions:
            if hasattr(discussion, 'comments') and discussion.comments:
                try:
                    total_comments += len(discussion.comments)
                except (TypeError, ValueError) as e:
                    current_app.logger.error(f"Error counting comments: {str(e)}")
                    
            if hasattr(discussion, 'views') and discussion.views:
                try:
                    total_views += int(discussion.views)
                except (TypeError, ValueError) as e:
                    current_app.logger.error(f"Error counting views: {str(e)}")
        
        # Render template
        return render_template(
            'discussions/my_discussions.html',
            discussions=discussions,
            pagination={
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': pages,
                'has_prev': page > 1,
                'has_next': page < pages,
                'prev_num': page - 1,
                'next_num': page + 1,
                'iter_pages': lambda: range(1, pages + 1)
            },
            sort=sort,
            total_comments=total_comments,
            total_views=total_views
        )
    except Exception as e:
        current_app.logger.error(f"Error in my_discussions: {str(e)}")
        flash("An error occurred while loading your discussions", "error")
        return redirect(url_for('discussions.index'))

@discussions_bp.route('/edit/<discussion_id>', methods=['GET', 'POST'])
@login_required
def edit_discussion(discussion_id):
    """Edit an existing discussion"""
    try:
        # Get user
        user = get_current_user()
        if not user:
            flash('User not authenticated', 'error')
            return redirect(url_for('discussions.index'))
        
        # Get discussion
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            flash('Discussion not found', 'error')
            return redirect(url_for('discussions.index'))
        
        # Check if user is authorized to edit
        if str(discussion.user_id) != str(user.id) and not user.is_admin:
            flash('You are not authorized to edit this discussion', 'error')
            return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
        
        # Get subjects and grade levels for dropdowns
        subjects = current_app.db.discussions.distinct('subject')
        grade_levels = current_app.db.discussions.distinct('grade_level')
        
        # If no subjects/grades exist yet, provide defaults
        if not subjects:
            subjects = ["Mathematics", "Science", "English", "History", "Computer Science", "Languages", "Arts", "Other"]
        
        if not grade_levels:
            grade_levels = ["Elementary", "Middle School", "High School", "College", "Graduate", "Professional"]
        
        # Handle form submission
        if request.method == 'POST':
            # Get form data
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            subject = request.form.get('subject', 'General')
            grade_level = request.form.get('grade_level', 'General')
            
            # Validate required fields
            if not title or not content:
                flash('Title and content are required', 'error')
                return render_template(
                    'discussions/edit.html',
                    discussion=discussion,
                    subjects=subjects,
                    grade_levels=grade_levels
                )
            
            # Process tags
            tags = []
            if request.form.get('tags'):
                tags = [tag.strip() for tag in request.form.get('tags').split(',') if tag.strip()]
                tags = tags[:5]  # Limit to 5 tags
            
            # Update discussion in database
            update_result = current_app.db.discussions.update_one(
                {'_id': ObjectId(discussion_id)},
                {
                    '$set': {
                        'title': title,
                        'content': content,
                        'subject': subject,
                        'grade_level': grade_level,
                        'tags': tags,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count > 0:
                flash('Discussion updated successfully', 'success')
                # Invalidate cache
                from app.models.discussion import discussion_cache
                discussion_cache.put(discussion_id, None)
                return redirect(url_for('discussions.view_discussion', discussion_id=discussion_id))
            else:
                flash('No changes were made to the discussion', 'info')
        
        # Render edit form
        return render_template(
            'discussions/edit.html',
            discussion=discussion,
            subjects=subjects,
            grade_levels=grade_levels
        )
        
    except Exception as e:
        current_app.logger.error(f"Error editing discussion: {str(e)}")
        flash('An error occurred while editing the discussion', 'error')
        return redirect(url_for('discussions.index'))

@discussions_bp.route('/comments/<comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    """Edit a comment"""
    try:
        # Get user
        user = get_current_user()
        if not user:
            flash('User not authenticated', 'error')
            return redirect(url_for('discussions.index'))
        
        # Get form data
        content = request.form.get('content', '').strip()
        if not content:
            flash('Comment content cannot be empty', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Find the discussion containing the comment
        discussion_data = current_app.db.discussions.find_one(
            {"comments.id": comment_id}
        )
        if not discussion_data:
            flash('Comment not found', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Get the discussion and comment
        discussion = Discussion(discussion_data)
        comment = None
        comment_index = None
        
        # Find the comment and its index in the array
        for i, c in enumerate(discussion.comments):
            if c.get('id') == comment_id:
                comment = c
                comment_index = i
                break
        
        if not comment or comment_index is None:
            flash('Comment not found', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Check if the user is authorized to edit the comment
        if str(comment.get('user_id')) != str(user.id) and not user.is_admin:
            flash('You are not authorized to edit this comment', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Update the comment using the array index position
        update_result = current_app.db.discussions.update_one(
            {"_id": ObjectId(discussion.id)},
            {"$set": {
                f"comments.{comment_index}.content": content,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if update_result.modified_count > 0:
            # Update cache
            from app.models.discussion import discussion_cache
            discussion_cache.put(discussion.id, None)
            flash('Comment updated successfully', 'success')
        else:
            flash('No changes were made to the comment', 'info')
            
        # Redirect back to the discussion
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion.id))
        
    except Exception as e:
        current_app.logger.error(f"Error editing comment: {str(e)}")
        flash('An error occurred while editing the comment', 'error')
        return redirect(request.referrer or url_for('discussions.index'))

@discussions_bp.route('/comments/<comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """Delete a comment"""
    try:
        # Get user
        user = get_current_user()
        if not user:
            flash('User not authenticated', 'error')
            return redirect(url_for('discussions.index'))
        
        # Find the discussion containing the comment
        discussion_data = current_app.db.discussions.find_one(
            {"comments.id": comment_id}
        )
        if not discussion_data:
            flash('Comment not found', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Get the discussion and comment
        discussion = Discussion(discussion_data)
        comment = None
        for c in discussion.comments:
            if c.get('id') == comment_id:
                comment = c
                break
        
        if not comment:
            flash('Comment not found', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Check if the user is authorized to delete the comment
        if str(comment.get('user_id')) != str(user.id) and not user.is_admin:
            flash('You are not authorized to delete this comment', 'error')
            return redirect(request.referrer or url_for('discussions.index'))
        
        # Delete the comment
        # First, perform a findOneAndUpdate operation to ensure atomic update
        result = current_app.db.discussions.find_one_and_update(
            {"_id": ObjectId(discussion.id)},
            {
                "$pull": {"comments": {"id": comment_id}},
                "$set": {"updated_at": datetime.utcnow()}
            },
            return_document=True
        )
        
        # Clear the discussion cache regardless of result
        from app.models.discussion import discussion_cache
        discussion_cache.put(discussion.id, None)
            
        if result:
            # Log success
            current_app.logger.info(f"Successfully deleted comment {comment_id} from discussion {discussion.id}")
            flash('Comment deleted successfully', 'success')
        else:
            # Log failure
            current_app.logger.error(f"Failed to delete comment {comment_id} from discussion {discussion.id}")
            flash('Failed to delete comment', 'error')
            
        # Redirect back to the discussion
        return redirect(url_for('discussions.view_discussion', discussion_id=discussion.id))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting comment: {str(e)}")
        flash('An error occurred while deleting the comment', 'error')
        return redirect(request.referrer or url_for('discussions.index'))

def init_app(app):
    """Initialize discussion routes"""
    app.register_blueprint(discussions_bp)
    
    # Create indexes during app initialization rather than waiting for first request
    Discussion.create_indexes(app.db) 