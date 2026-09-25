from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from bson import ObjectId
from datetime import datetime
import json

bp = Blueprint('api_comments', __name__, url_prefix='/api')

def serialize_mongo_doc(doc):
    """
    Convert MongoDB document to JSON-serializable format
    by converting ObjectId to string and handling datetime objects
    """
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id' or key.endswith('_id'):
                if isinstance(value, ObjectId):
                    # Keep both _id and id for backwards compatibility
                    result[key] = str(value)
                    if key == '_id':
                        result['id'] = str(value)
                else:
                    result[key] = value
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, (dict, list)):
                result[key] = serialize_mongo_doc(value)
            else:
                result[key] = value
        return result
    elif isinstance(doc, list):
        return [serialize_mongo_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc

@bp.route('/comments/resource/<resource_id>', methods=['GET'])
def get_resource_comments(resource_id):
    """Get comments for a resource (maximum 20)"""
    try:
        # Convert the resource ID to ObjectId
        try:
            obj_id = ObjectId(resource_id)
        except Exception as e:
            print(f"Invalid resource ID format: {resource_id}, error: {str(e)}")
            return jsonify({'success': False, 'message': 'Invalid resource ID format'}), 400
        
        # Find the resource
        resource = current_app.db.resources.find_one({'_id': obj_id})
        if not resource:
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
            
        # Extract comments from the resource
        comments = resource.get('comments', [])
        if comments is None:
            comments = []
        
        # Pre-calculate likes counts for sorting
        for comment in comments:
            comment['likes_count'] = len(comment.get('likes', [])) if isinstance(comment.get('likes'), list) else 0
            
        # Sort comments by likes count in descending order (most likes first)
        comments = sorted(comments, key=lambda x: x.get('likes_count', 0), reverse=True)[:20]
        
        # Format comments for JSON response
        formatted_comments = []
        for comment in comments:
            if not comment:
                continue  # Skip any empty comment entries
            
            # Format each comment
            try:
                comment_obj = {
                    'id': str(comment.get('_id', '')),
                    'content': comment.get('content', ''),
                    'created_at': comment.get('created_at').isoformat() if comment.get('created_at') else None,
                    'author': comment.get('author', {'username': 'Anonymous'}),
                    'likes_count': comment.get('likes_count', 0),
                    'dislikes_count': len(comment.get('dislikes', [])) if isinstance(comment.get('dislikes'), list) else 0,
                    'user_liked': any(like.get('user_id') == current_user.id for like in comment.get('likes', [])) if current_user.is_authenticated and isinstance(comment.get('likes'), list) else False,
                    'user_disliked': any(dislike.get('user_id') == current_user.id for dislike in comment.get('dislikes', [])) if current_user.is_authenticated and isinstance(comment.get('dislikes'), list) else False,
                    'replies': []
                }
                
                # Format replies
                replies = comment.get('replies', [])
                if replies is None:
                    replies = []
                
                # Pre-calculate likes count for replies and sort by likes count
                for reply in replies:
                    if reply:
                        reply['likes_count'] = len(reply.get('likes', [])) if isinstance(reply.get('likes'), list) else 0
                
                # Sort replies by number of likes (most likes first)
                replies = sorted(replies, key=lambda x: x.get('likes_count', 0) if x else 0, reverse=True)
                
                for reply in replies:
                    if not reply:
                        continue  # Skip any empty reply entries
                    
                    try:
                        reply_obj = {
                            'id': str(reply.get('_id', '')),
                            'content': reply.get('content', ''),
                            'created_at': reply.get('created_at').isoformat() if reply.get('created_at') else None,
                            'author': reply.get('author', {'username': 'Anonymous'}),
                            'likes_count': reply.get('likes_count', 0),
                            'dislikes_count': len(reply.get('dislikes', [])) if isinstance(reply.get('dislikes'), list) else 0,
                            'user_liked': any(like.get('user_id') == current_user.id for like in reply.get('likes', [])) if current_user.is_authenticated and isinstance(reply.get('likes'), list) else False,
                            'user_disliked': any(dislike.get('user_id') == current_user.id for dislike in reply.get('dislikes', [])) if current_user.is_authenticated and isinstance(reply.get('dislikes'), list) else False
                        }
                        comment_obj['replies'].append(reply_obj)
                    except Exception as e:
                        print(f"Error formatting reply: {str(e)}")
                        # Continue with other replies
                
                formatted_comments.append(comment_obj)
            except Exception as e:
                print(f"Error formatting comment: {str(e)}")
                # Continue with other comments
            
        return jsonify({
            'success': True,
            'resource_id': resource_id,
            'comments': formatted_comments
        })
        
    except Exception as e:
        print(f"Error in get_resource_comments: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/comments/resource/<resource_id>', methods=['POST'])
@login_required
def add_comment(resource_id):
    """Add a comment to a resource"""
    try:
        # Convert string ID to ObjectId
        if not ObjectId.is_valid(resource_id):
            return jsonify({'success': False, 'message': 'Invalid resource ID format'}), 400
            
        obj_id = ObjectId(resource_id)
        
        # Check if resource exists
        resource = current_app.db.resources.find_one({'_id': obj_id})
        if not resource:
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
            
        # Get comment content
        content = request.form.get('content')
        if not content or len(content.strip()) < 3:
            return jsonify({'success': False, 'message': 'Comment content must be at least 3 characters'}), 400
        
        # Create comment object with unique ID
        comment = {
            '_id': ObjectId(),
            'content': content.strip(),
            'author': {
                'id': current_user.id,
                'username': current_user.username
            },
            'created_at': datetime.utcnow(),
            'likes': [],
            'dislikes': [],
            'likes_count': 0,
            'dislikes_count': 0,
            'replies': []
        }
        
        # Add comment to resource
        current_app.db.resources.update_one(
            {'_id': obj_id},
            {'$push': {'comments': comment}}
        )
        
        # Serialize comment for JSON response
        serialized_comment = serialize_mongo_doc(comment)
        serialized_comment['user_liked'] = False
        serialized_comment['user_disliked'] = False
        
        return jsonify({
            'success': True,
            'message': 'Comment added successfully',
            'comment': serialized_comment
        })
        
    except Exception as e:
        current_app.logger.error(f"Error adding comment: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while adding comment'}), 500

@bp.route('/comments/<comment_id>/like', methods=['POST'])
@login_required
def like_comment(comment_id):
    """Like or unlike a comment"""
    try:
        # Validate the comment_id
        if not comment_id:
            return jsonify({'success': False, 'message': 'Invalid comment ID'}), 400
        
        # Convert the comment ID to ObjectId
        try:
            obj_id = ObjectId(comment_id)
        except Exception as e:
            return jsonify({'success': False, 'message': f'Invalid comment ID format: {str(e)}'}), 400
        
        # Find the resource containing this comment
        resource = current_app.db.resources.find_one({"comments._id": obj_id})
        if not resource:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
            
        # Find the comment
        updated_comment = None
        for c in resource['comments']:
            if c.get('_id') and str(c.get('_id')) == str(obj_id):
                updated_comment = c
                break
                
        if not updated_comment:
            return jsonify({'success': False, 'message': 'Comment not found in resource'}), 404
        
        # Check if the user already liked this comment
        user_already_liked = False
        if 'likes' in updated_comment:
            for like in updated_comment['likes']:
                if like.get('user_id') == current_user.id:
                    user_already_liked = True
                    break
        
        # Toggle like
        if user_already_liked:
            # Remove the like
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$pull': {'comments.$.likes': {'user_id': current_user.id}}}
            )
        else:
            # Check if the user disliked this comment
            if 'dislikes' in updated_comment:
                # Remove the dislike if it exists
                current_app.db.resources.update_one(
                    {'comments._id': obj_id},
                    {'$pull': {'comments.$.dislikes': {'user_id': current_user.id}}}
                )
                
            # Add the like
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$push': {'comments.$.likes': {'user_id': current_user.id, 'created_at': datetime.utcnow()}}}
            )
            
        # Get updated counts
        updated_resource = current_app.db.resources.find_one({'comments._id': obj_id})
        if not updated_resource:
            return jsonify({'success': False, 'message': 'Failed to retrieve updated comment'}), 500
            
        updated_comment = None
        for c in updated_resource['comments']:
            if c.get('_id') and str(c.get('_id')) == str(obj_id):
                updated_comment = c
                break
                
        if not updated_comment:
            return jsonify({'success': False, 'message': 'Failed to find updated comment'}), 500
            
        likes_count = len(updated_comment.get('likes', [])) if updated_comment.get('likes') else 0
        dislikes_count = len(updated_comment.get('dislikes', [])) if updated_comment.get('dislikes') else 0
        
        updated_user_liked = False
        if updated_comment.get('likes'):
            updated_user_liked = any(like.get('user_id') == current_user.id for like in updated_comment.get('likes', []))
        
        updated_user_disliked = False
        if updated_comment.get('dislikes'):
            updated_user_disliked = any(dislike.get('user_id') == current_user.id for dislike in updated_comment.get('dislikes', []))
        
        return jsonify({
            'success': True,
            'message': 'Like toggled successfully',
            'likes_count': likes_count,
            'dislikes_count': dislikes_count,
            'user_liked': updated_user_liked,
            'user_disliked': updated_user_disliked
        })
        
    except Exception as e:
        print(f"Error in like_comment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/comments/<comment_id>/dislike', methods=['POST'])
@login_required
def dislike_comment(comment_id):
    """Dislike or undislike a comment"""
    try:
        # Validate the comment_id
        if not comment_id:
            return jsonify({'success': False, 'message': 'Invalid comment ID'}), 400
        
        # Convert the comment ID to ObjectId
        try:
            obj_id = ObjectId(comment_id)
        except Exception as e:
            return jsonify({'success': False, 'message': f'Invalid comment ID format: {str(e)}'}), 400
        
        # Find the resource containing this comment
        resource = current_app.db.resources.find_one({"comments._id": obj_id})
        if not resource:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
            
        # Find the comment
        updated_comment = None
        for c in resource['comments']:
            if c.get('_id') and str(c.get('_id')) == str(obj_id):
                updated_comment = c
                break
                
        if not updated_comment:
            return jsonify({'success': False, 'message': 'Comment not found in resource'}), 404
        
        # Check if the user already disliked this comment
        user_already_disliked = False
        if 'dislikes' in updated_comment:
            for dislike in updated_comment['dislikes']:
                if dislike.get('user_id') == current_user.id:
                    user_already_disliked = True
                    break
        
        # Toggle dislike
        if user_already_disliked:
            # Remove the dislike
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$pull': {'comments.$.dislikes': {'user_id': current_user.id}}}
            )
        else:
            # Check if the user liked this comment
            if 'likes' in updated_comment:
                # Remove the like if it exists
                current_app.db.resources.update_one(
                    {'comments._id': obj_id},
                    {'$pull': {'comments.$.likes': {'user_id': current_user.id}}}
                )
                
            # Add the dislike
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$push': {'comments.$.dislikes': {'user_id': current_user.id, 'created_at': datetime.utcnow()}}}
            )
            
        # Get updated counts
        updated_resource = current_app.db.resources.find_one({'comments._id': obj_id})
        if not updated_resource:
            return jsonify({'success': False, 'message': 'Failed to retrieve updated comment'}), 500
            
        updated_comment = None
        for c in updated_resource['comments']:
            if c.get('_id') and str(c.get('_id')) == str(obj_id):
                updated_comment = c
                break
                
        if not updated_comment:
            return jsonify({'success': False, 'message': 'Failed to find updated comment'}), 500
            
        likes_count = len(updated_comment.get('likes', [])) if updated_comment.get('likes') else 0
        dislikes_count = len(updated_comment.get('dislikes', [])) if updated_comment.get('dislikes') else 0
        
        updated_user_liked = False
        if updated_comment.get('likes'):
            updated_user_liked = any(like.get('user_id') == current_user.id for like in updated_comment.get('likes', []))
        
        updated_user_disliked = False
        if updated_comment.get('dislikes'):
            updated_user_disliked = any(dislike.get('user_id') == current_user.id for dislike in updated_comment.get('dislikes', []))
        
        return jsonify({
            'success': True,
            'message': 'Dislike toggled successfully',
            'likes_count': likes_count,
            'dislikes_count': dislikes_count,
            'user_liked': updated_user_liked,
            'user_disliked': updated_user_disliked
        })
        
    except Exception as e:
        print(f"Error in dislike_comment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/comments/<comment_id>/reply', methods=['POST'])
@login_required
def reply_to_comment(comment_id):
    """Add a reply to a comment"""
    try:
        # Convert ObjectId
        if not ObjectId.is_valid(comment_id):
            return jsonify({"success": False, "message": "Invalid comment ID format"}), 400
        
        comment_oid = ObjectId(comment_id)
        
        # Verify the comment exists
        comment = current_app.db.resources.find_one({"comments._id": comment_oid})
        if not comment:
            return jsonify({"success": False, "message": "Comment not found"}), 404
        
        # Get the reply content
        content = request.form.get('content')
        if not content or not content.strip():
            return jsonify({"success": False, "message": "Reply content is required"}), 400
        
        # Create reply data
        current_time = datetime.utcnow()
        reply_id = ObjectId()  # Generate a new ObjectId for the reply
        
        reply = {
            "_id": reply_id,
            "content": content.strip(),
            "author": {
                "id": current_user.id,
                "username": current_user.username
            },
            "created_at": current_time,
            "likes": [],
            "dislikes": [],
            "likes_count": 0,
            "dislikes_count": 0
        }
        
        # Update the comment with the new reply
        result = current_app.db.resources.update_one(
            {"comments._id": comment_oid},
            {"$push": {"comments.$.replies": reply}}
        )
        
        if result.modified_count == 0:
            return jsonify({"success": False, "message": "Failed to add reply to comment"}), 500
        
        # Serialize the reply data to make it JSON-safe
        serialized_reply = serialize_mongo_doc(reply)
        serialized_reply["user_liked"] = False
        serialized_reply["user_disliked"] = False
        
        return jsonify({
            "success": True,
            "message": "Reply added successfully",
            "reply": serialized_reply
        })
    
    except Exception as e:
        current_app.logger.error(f"Error adding reply to comment: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred while adding reply"}), 500

@bp.route('/replies/<reply_id>/like', methods=['POST'])
@login_required
def like_reply(reply_id):
    """Like or unlike a reply"""
    try:
        # Convert the reply ID to ObjectId
        obj_id = ObjectId(reply_id)
        
        # Find the resource containing this reply
        resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        if not resource:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
            
        # Find the comment and reply
        comment_index = -1
        reply_index = -1
        for i, comment in enumerate(resource['comments']):
            for j, reply in enumerate(comment.get('replies', [])):
                if reply.get('_id') == obj_id:
                    comment_index = i
                    reply_index = j
                    break
            if comment_index >= 0:
                break
                
        if comment_index < 0 or reply_index < 0:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
            
        # Get the reply
        reply = resource['comments'][comment_index]['replies'][reply_index]
        
        # Check if user already liked this reply
        user_liked = False
        for like in reply.get('likes', []):
            if like.get('user_id') == current_user.id:
                user_liked = True
                break
                
        # Check if user already disliked this reply
        user_disliked = False
        for dislike in reply.get('dislikes', []):
            if dislike.get('user_id') == current_user.id:
                user_disliked = True
                break
                
        # Path to the specific reply's likes/dislikes
        like_path = f"comments.{comment_index}.replies.{reply_index}.likes"
        dislike_path = f"comments.{comment_index}.replies.{reply_index}.dislikes"
        
        # If user already liked, remove the like (toggle)
        if user_liked:
            current_app.db.resources.update_one(
                {'comments.replies._id': obj_id},
                {'$pull': {like_path: {'user_id': current_user.id}}}
            )
            
        # Otherwise, add the like
        else:
            # If disliked, remove the dislike first
            if user_disliked:
                current_app.db.resources.update_one(
                    {'comments.replies._id': obj_id},
                    {'$pull': {dislike_path: {'user_id': current_user.id}}}
                )
                
            # Add the like
            current_app.db.resources.update_one(
                {'comments.replies._id': obj_id},
                {'$push': {like_path: {'user_id': current_user.id, 'created_at': datetime.utcnow()}}}
            )
            
        # Get updated counts
        updated_resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        updated_reply = None
        for comment in updated_resource['comments']:
            for reply in comment.get('replies', []):
                if reply.get('_id') == obj_id:
                    updated_reply = reply
                    break
            if updated_reply:
                break
                
        likes_count = len(updated_reply.get('likes', []))
        dislikes_count = len(updated_reply.get('dislikes', []))
        updated_user_liked = any(like.get('user_id') == current_user.id for like in updated_reply.get('likes', []))
        updated_user_disliked = any(dislike.get('user_id') == current_user.id for dislike in updated_reply.get('dislikes', []))
        
        return jsonify({
            'success': True,
            'message': 'Like toggled successfully',
            'likes_count': likes_count,
            'dislikes_count': dislikes_count,
            'user_liked': updated_user_liked,
            'user_disliked': updated_user_disliked
        })
        
    except Exception as e:
        print(f"Error in like_reply: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/replies/<reply_id>/dislike', methods=['POST'])
@login_required
def dislike_reply(reply_id):
    """Dislike or undislike a reply"""
    try:
        # Convert the reply ID to ObjectId
        obj_id = ObjectId(reply_id)
        
        # Find the resource containing this reply
        resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        if not resource:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
            
        # Find the comment and reply
        comment_index = -1
        reply_index = -1
        for i, comment in enumerate(resource['comments']):
            for j, reply in enumerate(comment.get('replies', [])):
                if reply.get('_id') == obj_id:
                    comment_index = i
                    reply_index = j
                    break
            if comment_index >= 0:
                break
                
        if comment_index < 0 or reply_index < 0:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
            
        # Get the reply
        reply = resource['comments'][comment_index]['replies'][reply_index]
        
        # Check if user already disliked this reply
        user_disliked = False
        for dislike in reply.get('dislikes', []):
            if dislike.get('user_id') == current_user.id:
                user_disliked = True
                break
                
        # Check if user already liked this reply
        user_liked = False
        for like in reply.get('likes', []):
            if like.get('user_id') == current_user.id:
                user_liked = True
                break
                
        # Path to the specific reply's likes/dislikes
        like_path = f"comments.{comment_index}.replies.{reply_index}.likes"
        dislike_path = f"comments.{comment_index}.replies.{reply_index}.dislikes"
        
        # If user already disliked, remove the dislike (toggle)
        if user_disliked:
            current_app.db.resources.update_one(
                {'comments.replies._id': obj_id},
                {'$pull': {dislike_path: {'user_id': current_user.id}}}
            )
            
        # Otherwise, add the dislike
        else:
            # If liked, remove the like first
            if user_liked:
                current_app.db.resources.update_one(
                    {'comments.replies._id': obj_id},
                    {'$pull': {like_path: {'user_id': current_user.id}}}
                )
                
            # Add the dislike
            current_app.db.resources.update_one(
                {'comments.replies._id': obj_id},
                {'$push': {dislike_path: {'user_id': current_user.id, 'created_at': datetime.utcnow()}}}
            )
            
        # Get updated counts
        updated_resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        updated_reply = None
        for comment in updated_resource['comments']:
            for reply in comment.get('replies', []):
                if reply.get('_id') == obj_id:
                    updated_reply = reply
                    break
            if updated_reply:
                break
                
        likes_count = len(updated_reply.get('likes', []))
        dislikes_count = len(updated_reply.get('dislikes', []))
        updated_user_liked = any(like.get('user_id') == current_user.id for like in updated_reply.get('likes', []))
        updated_user_disliked = any(dislike.get('user_id') == current_user.id for dislike in updated_reply.get('dislikes', []))
        
        return jsonify({
            'success': True,
            'message': 'Dislike toggled successfully',
            'likes_count': likes_count,
            'dislikes_count': dislikes_count,
            'user_liked': updated_user_liked,
            'user_disliked': updated_user_disliked
        })
        
    except Exception as e:
        print(f"Error in dislike_reply: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/comments/<comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """Delete a comment (only allowed for comment author or admin)"""
    try:
        if not ObjectId.is_valid(comment_id):
            return jsonify({"success": False, "message": "Invalid comment ID format"}), 400
        
        comment_oid = ObjectId(comment_id)
        
        # Find the comment
        resource = current_app.db.resources.find_one({"comments._id": comment_oid})
        if not resource:
            return jsonify({"success": False, "message": "Comment not found"}), 404
        
        # Find the comment in the array
        comment = None
        for c in resource['comments']:
            if c['_id'] == comment_oid:
                comment = c
                break
        
        if not comment:
            return jsonify({"success": False, "message": "Comment not found"}), 404
        
        # Check if user is the author or an admin
        user_id = str(current_user.id)
        is_author = str(comment['author']['id']) == user_id
        is_admin = current_user.is_admin if hasattr(current_user, 'is_admin') else False
        
        if not (is_author or is_admin):
            return jsonify({"success": False, "message": "You don't have permission to delete this comment"}), 403
        
        # Delete the comment
        result = current_app.db.resources.update_one(
            {"_id": resource['_id']},
            {"$pull": {"comments": {"_id": comment_oid}}}
        )
        
        if result.modified_count == 0:
            return jsonify({"success": False, "message": "Failed to delete comment"}), 500
        
        return jsonify({
            "success": True,
            "message": "Comment deleted successfully"
        })
    
    except Exception as e:
        current_app.logger.error(f"Error deleting comment: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred"}), 500

@bp.route('/comments/<comment_id>/report', methods=['POST'])
@login_required
def report_comment(comment_id):
    """Report a comment as inappropriate"""
    try:
        if not ObjectId.is_valid(comment_id):
            return jsonify({"success": False, "message": "Invalid comment ID format"}), 400
        
        comment_oid = ObjectId(comment_id)
        user_id = str(current_user.id)
        reason = request.form.get('reason', 'inappropriate content')
        details = request.form.get('details', '')
        
        # Find the resource containing the comment
        resource = current_app.db.resources.find_one({"comments._id": comment_oid})
        if not resource:
            return jsonify({"success": False, "message": "Comment not found"}), 404
        
        # Find the comment in the array to check if user already reported
        comment_index = None
        found_comment = None
        
        for i, c in enumerate(resource.get('comments', [])):
            if c.get('_id') == comment_oid:
                found_comment = c
                comment_index = i
                break
        
        if not found_comment:
            return jsonify({"success": False, "message": "Comment not found"}), 404
        
        # Initialize reports array if it doesn't exist
        if 'reports' not in found_comment:
            # First, update the comment to include an empty reports array if it doesn't exist
            current_app.db.resources.update_one(
                {"comments._id": comment_oid},
                {"$set": {"comments.$.reports": []}}
            )
            reports = []
        else:
            reports = found_comment.get('reports', [])
        
        # Check if user already reported this comment
        user_already_reported = False
        for report in reports:
            if str(report.get('user_id')) == user_id:
                user_already_reported = True
                break
        
        if user_already_reported:
            return jsonify({"success": False, "message": "You have already reported this comment"}), 400
        
        # Add the report
        report_data = {
            "user_id": user_id,
            "reason": reason,
            "details": details,
            "reported_at": datetime.utcnow()
        }
        
        # Update the comment with the new report
        result = current_app.db.resources.update_one(
            {"comments._id": comment_oid},
            {"$push": {"comments.$.reports": report_data}}
        )
        
        if result.modified_count == 0:
            return jsonify({"success": False, "message": "Failed to report comment"}), 500
        
        # Log the report for admin review
        current_app.logger.info(f"Comment {comment_id} reported by user {user_id} for '{reason}'")
        
        return jsonify({
            "success": True,
            "message": "Comment reported successfully. Our moderators will review it."
        })
    
    except Exception as e:
        current_app.logger.error(f"Error reporting comment: {str(e)}")
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500
