from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models.discussion import Discussion, Comment
from app import db
from sqlalchemy import or_
import re

discussion_bp = Blueprint('discussion', __name__)

# Content moderation patterns
INAPPROPRIATE_PATTERNS = [
    r'\b(asshole|bitch|fuck|shit|damn|hell)\b',
    r'\b(nigger|nigga|chink|spic|kike)\b',
    # Add more patterns as needed
]

def is_inappropriate(content):
    for pattern in INAPPROPRIATE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False

@discussion_bp.route('/discussions', methods=['GET'])
def get_discussions():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    sort_by = request.args.get('sort_by', 'score')
    search_query = request.args.get('q', '')
    
    query = Discussion.query.filter_by(is_archived=False)
    
    if search_query:
        query = query.filter(
            or_(
                Discussion.title.ilike(f'%{search_query}%'),
                Discussion.content.ilike(f'%{search_query}%')
            )
        )
    
    if sort_by == 'score':
        query = query.order_by((Discussion.upvotes - Discussion.downvotes).desc())
    elif sort_by == 'newest':
        query = query.order_by(Discussion.created_at.desc())
    elif sort_by == 'oldest':
        query = query.order_by(Discussion.created_at.asc())
    
    paginated_discussions = query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'discussions': [discussion.to_dict() for discussion in paginated_discussions.items],
        'total': paginated_discussions.total,
        'pages': paginated_discussions.pages,
        'current_page': page
    })

@discussion_bp.route('/discussions', methods=['POST'])
@login_required
def create_discussion():
    data = request.get_json()
    
    if not data or not data.get('title') or not data.get('content'):
        return jsonify({'error': 'Title and content are required'}), 400
    
    if is_inappropriate(data['title']) or is_inappropriate(data['content']):
        return jsonify({'error': 'Content contains inappropriate language'}), 400
    
    discussion = Discussion(
        title=data['title'],
        content=data['content'],
        user_id=current_user.id
    )
    
    db.session.add(discussion)
    db.session.commit()
    
    return jsonify(discussion.to_dict()), 201

@discussion_bp.route('/discussions/<int:discussion_id>', methods=['GET'])
def get_discussion(discussion_id):
    discussion = Discussion.query.get_or_404(discussion_id)
    return jsonify(discussion.to_dict())

@discussion_bp.route('/discussions/<int:discussion_id>/comments', methods=['GET'])
def get_comments(discussion_id):
    discussion = Discussion.query.get_or_404(discussion_id)
    comments = Comment.query.filter_by(
        discussion_id=discussion_id,
        parent_id=None,
        is_archived=False
    ).order_by((Comment.upvotes - Comment.downvotes).desc()).all()
    
    return jsonify([comment.to_dict() for comment in comments])

@discussion_bp.route('/discussions/<int:discussion_id>/comments', methods=['POST'])
@login_required
def create_comment(discussion_id):
    data = request.get_json()
    
    if not data or not data.get('content'):
        return jsonify({'error': 'Content is required'}), 400
    
    if is_inappropriate(data['content']):
        return jsonify({'error': 'Content contains inappropriate language'}), 400
    
    discussion = Discussion.query.get_or_404(discussion_id)
    
    comment = Comment(
        content=data['content'],
        user_id=current_user.id,
        discussion_id=discussion_id,
        parent_id=data.get('parent_id')
    )
    
    db.session.add(comment)
    db.session.commit()
    
    return jsonify(comment.to_dict()), 201

@discussion_bp.route('/discussions/<int:discussion_id>/vote', methods=['POST'])
@login_required
def vote_discussion(discussion_id):
    data = request.get_json()
    vote_type = data.get('vote_type')
    
    if vote_type not in ['up', 'down']:
        return jsonify({'error': 'Invalid vote type'}), 400
    
    discussion = Discussion.query.get_or_404(discussion_id)
    
    if vote_type == 'up':
        discussion.upvotes += 1
    else:
        discussion.downvotes += 1
    
    db.session.commit()
    return jsonify(discussion.to_dict())

@discussion_bp.route('/comments/<int:comment_id>/vote', methods=['POST'])
@login_required
def vote_comment(comment_id):
    data = request.get_json()
    vote_type = data.get('vote_type')
    
    if vote_type not in ['up', 'down']:
        return jsonify({'error': 'Invalid vote type'}), 400
    
    comment = Comment.query.get_or_404(comment_id)
    
    if vote_type == 'up':
        comment.upvotes += 1
    else:
        comment.downvotes += 1
    
    db.session.commit()
    return jsonify(comment.to_dict()) 