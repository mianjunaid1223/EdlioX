from flask import Blueprint, jsonify, request, current_app, g
from bson import ObjectId
from datetime import datetime
from app.models.discussion import Discussion
from app.models.user import User
from app.auth.utils import get_current_user

api_discussions = Blueprint('api_discussions', __name__)

@api_discussions.route('/discussions/<discussion_id>/vote', methods=['POST'])
def vote_discussion(discussion_id):
    """Handle voting on discussions"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        vote_type = request.json.get('vote_type')
        if vote_type not in ['up', 'down']:
            return jsonify({'error': 'Invalid vote type'}), 400

        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            return jsonify({'error': 'Discussion not found'}), 404

        result = discussion.vote(current_app.db, user.id, vote_type)
        
        return jsonify({
            'success': True,
            'votes': discussion.votes,
            'score': discussion.score,
            'has_upvoted': user.id in discussion.votes.get('up', []),
            'has_downvoted': user.id in discussion.votes.get('down', [])
        })

    except Exception as e:
        return jsonify({'error': 'Failed to process vote'}), 500

@api_discussions.route('/discussions/<discussion_id>/comments/<comment_id>/vote', methods=['POST'])
def vote_comment(discussion_id, comment_id):
    """Handle voting on comments"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        vote_type = request.json.get('vote_type')
        if vote_type not in ['up', 'down']:
            return jsonify({'error': 'Invalid vote type'}), 400

        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            return jsonify({'error': 'Discussion not found'}), 404

        result = discussion.vote_comment(current_app.db, comment_id, user.id, vote_type)
        
        # Find the updated comment to return its current votes and score
        comment = next((c for c in discussion.comments if c['id'] == comment_id), None)
        if not comment:
            return jsonify({'error': 'Comment not found'}), 404

        return jsonify({
            'success': True,
            'votes': comment['votes'],
            'score': comment['score'],
            'has_upvoted': user.id in comment['votes'].get('up', []),
            'has_downvoted': user.id in comment['votes'].get('down', [])
        })

    except Exception as e:
        return jsonify({'error': 'Failed to process comment vote'}), 500

@api_discussions.route('/discussions/<discussion_id>/comments', methods=['POST'])
def add_comment(discussion_id):
    """Add a new comment to a discussion"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        content = request.json.get('content')
        parent_id = request.json.get('parent_id')

        if not content or not content.strip():
            return jsonify({'error': 'Comment content is required'}), 400

        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            return jsonify({'error': 'Discussion not found'}), 404

        # Add the comment
        comment = discussion.add_comment(current_app.db, user.id, content, parent_id)
        
        # Add author information to the response
        comment['author'] = {
            'username': user.username,
            'id': str(user.id)
        }
        comment['discussion_id'] = discussion_id

        return jsonify({
            'success': True,
            'comment': comment
        })

    except Exception as e:
        return jsonify({'error': 'Failed to create comment'}), 500

@api_discussions.route('/discussions/<discussion_id>/share', methods=['GET'])
def get_share_url(discussion_id):
    """Generate a shareable URL for the discussion"""
    try:
        discussion = Discussion.get_by_id(current_app.db, discussion_id)
        if not discussion:
            return jsonify({'error': 'Discussion not found'}), 404

        share_url = f"{request.host_url.rstrip('/')}/discussions/{discussion.slug}"
        
        return jsonify({
            'success': True,
            'share_url': share_url,
            'title': discussion.title
        })

    except Exception as e:
        return jsonify({'error': 'Failed to generate share URL'}), 500