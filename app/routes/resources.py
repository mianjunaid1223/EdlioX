import os
from flask import Blueprint, request, jsonify, render_template, current_app, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models.resource import Resource
from app.forms import ResourceForm, CommentForm
from app import create_app
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
import logging

bp = Blueprint('resources', __name__, url_prefix='/resources')

@bp.route('/')
def list_resources():
    """List all resources"""
    try:
        # Get sort option from query parameters (default to 'recent')
        sort_option = request.args.get('sort', 'recent')
        # Get page number from query parameters (default to 1)
        page = int(request.args.get('page', 1))
        # Set resources per page limit and get from query parameters if provided
        per_page = int(request.args.get('per_page', 10))
        max_per_page = 20  # Add maximum limit
        per_page = min(per_page, max_per_page)  # Enforce the maximum limit
        
        # Get search query if provided
        search_query = request.args.get('q', '')
        subject = request.args.get('subject', '')
        grade_level = request.args.get('grade_level', '')
        
        # Use the new get_resources method from Resource model
        result = Resource.get_resources(
            current_app.db,
            page=page,
            per_page=per_page,
            sort_by=sort_option,
            search_query=search_query,
            subject=subject,
            grade_level=grade_level
        )
        
        resources = result['resources']
        
        # If this is an AJAX request for loading more resources
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from flask import render_template_string
            # Render only the resource cards for AJAX responses
            html = render_template('resources/resource_cards.html', resources=resources)
            return jsonify({
                'html': html,
                'has_more': result['has_next'],
                'next_page': page + 1 if result['has_next'] else None
            })
            
        return render_template('resources/list.html', 
                              resources=resources, 
                              current_sort=sort_option,
                              pagination={
                                'page': page,
                                'per_page': per_page,
                                'total': result['total'],
                                'pages': result['pages'],
                                'has_prev': result['has_prev'],
                                'has_next': result['has_next'],
                                'prev_num': page - 1,
                                'next_num': page + 1,
                                'iter_pages': lambda: range(1, result['pages'] + 1)
                              })
    except Exception as e:
        current_app.logger.error(f"Error in list_resources: {str(e)}")
        flash('An error occurred while fetching resources', 'error')
        return render_template('resources/list.html', resources=[], current_sort='recent')

@bp.route('/load-more')
def load_more_resources():
    """AJAX endpoint to load more resources"""
    return list_resources()

@bp.route('/resource/<resource_id>/download')
def download_resource(resource_id):
    download_param = request.args.get('download', 'false').lower()
    as_attachment = download_param == 'true'
    
    try:
        # Try to convert the ID to ObjectId
        if not isinstance(resource_id, ObjectId):
            obj_id = ObjectId(resource_id)
        else:
            obj_id = resource_id
            
        # Query the database
        resource_data = current_app.db.resources.find_one({'_id': obj_id})
        if not resource_data:
            current_app.logger.warning(f"Resource not found with ID: {resource_id}")
            if as_attachment:
                return jsonify({'error': 'Resource not found'}), 404
            else:
                return render_template('errors/generic.html', 
                                      error_title="Resource Not Found",
                                      error_message="The requested resource could not be found."), 404
        
        resource = Resource(resource_data)
        
        # Always increment download count when download=true parameter is provided
        if as_attachment:
            # Only increment downloads count if user is logged in
            if current_user.is_authenticated:
                resource.increment_downloads(current_app.db)
        
        # First check if Google Drive link exists - use it as the primary source
        if resource.google_drive_link:
            # For direct downloads, modify the link to get the file directly
            if as_attachment and 'drive.google.com/file/d/' in resource.google_drive_link:
                # Extract file ID and create a direct download link
                file_id = resource.google_drive_link.split('/file/d/')[1].split('/')[0]
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                
                return redirect(download_url)
            else:
                # For preview, use the original Google Drive link
                return redirect(resource.google_drive_link)
        
        # Fallback to local file if it exists (less preferred)
        if resource.file_path and os.path.exists(resource.file_path):
            # Determine content type
            content_type = None
            if resource.file_type == 'pdf':
                content_type = 'application/pdf'
            elif resource.file_type in ['jpg', 'jpeg']:
                content_type = 'image/jpeg'
            elif resource.file_type == 'png':
                content_type = 'image/png'
            
            return send_file(
                resource.file_path,
                as_attachment=as_attachment,
                download_name=os.path.basename(resource.file_path),
                mimetype=content_type
            )
        
        # If we reach here, no file is available
        current_app.logger.warning(f"No file available for resource: {resource.title}")
        return render_template('errors/generic.html', 
                             error_title="File Not Available",
                             error_message="This resource doesn't have an associated file or Google Drive link."), 404
        
    except InvalidId as e:
        current_app.logger.error(f"Invalid ObjectId format: {resource_id}, error: {str(e)}")
        return jsonify({'error': 'Invalid resource ID format'}), 400
    except Exception as e:
        current_app.logger.error(f"Error in download_resource: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/resource/<resource_id>')
def view_resource(resource_id):
    """View a resource details"""
    try:
        # Convert string ID to ObjectId for MongoDB
        obj_id = ObjectId(resource_id)
        
        # Get resource from database
        resource_data = current_app.db.resources.find_one({'_id': obj_id})
        if not resource_data:
            flash('Resource not found', 'error')
            return redirect(url_for('resources.list_resources'))
        
        # Convert to Resource object
        resource = Resource(resource_data)
        
        # Increment view count
        resource.increment_views(current_app.db)
        
        # Get comments for this resource
        comment_form = CommentForm()
        
        # Get client IP address
        if request.headers.getlist("X-Forwarded-For"):
            # If behind a proxy
            ip_address = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip_address = request.remote_addr
        
        return render_template('resources/view.html', resource=resource, comment_form=comment_form)
        
    except InvalidId as e:
        flash('Invalid resource ID format', 'error')
        return redirect(url_for('resources.list_resources'))
    except Exception as e:
        current_app.logger.error(f"Error in view_resource: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('resources.list_resources'))

@bp.route('/comment/<comment_id>/like', methods=['POST'])
@bp.route('/resources/comment/<comment_id>/like', methods=['POST'])
@bp.route('/resources/resources/comment/<comment_id>/like', methods=['POST'])
@login_required
def like_comment(comment_id):
    """Like a comment"""
    try:
        # Convert the comment ID to ObjectId
        obj_id = ObjectId(comment_id)
        
        # Find the resource containing this comment
        resource_data = current_app.db.resources.find_one({"comments._id": obj_id})
        if not resource_data:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
        
        # Find the comment in the resource
        comment = None
        for c in resource_data['comments']:
            if c['_id'] == obj_id:
                comment = c
                break
                
        if not comment:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
        
        # Check if user already liked this comment
        user_liked = False
        for like in comment.get('likes', []):
            if like.get('user_id') == current_user.id:
                user_liked = True
                break
        
        # Check if user already disliked this comment
        user_disliked = False
        for dislike in comment.get('dislikes', []):
            if dislike.get('user_id') == current_user.id:
                user_disliked = True
                break
        
        # If user already liked, remove the like (toggle)
        if user_liked:
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$pull': {'comments.$.likes': {'user_id': current_user.id}}}
            )
            
            # Get updated likes count
            resource = current_app.db.resources.find_one({'comments._id': obj_id})
            comment = next((c for c in resource['comments'] if c['_id'] == obj_id), None)
            likes_count = len(comment.get('likes', []))
            dislikes_count = len(comment.get('dislikes', []))
            
            return jsonify({
                'success': True, 
                'message': 'Like removed',
                'likes': likes_count,
                'dislikes': dislikes_count
            })
            
        # If disliked, remove the dislike first
        if user_disliked:
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$pull': {'comments.$.dislikes': {'user_id': current_user.id}}}
            )
        
        # Add the like
        current_app.db.resources.update_one(
            {'comments._id': obj_id},
            {'$push': {'comments.$.likes': {'user_id': current_user.id, 'created_at': datetime.utcnow()}}}
        )
        
        # Get updated likes count
        resource = current_app.db.resources.find_one({'comments._id': obj_id})
        comment = next((c for c in resource['comments'] if c['_id'] == obj_id), None)
        likes_count = len(comment.get('likes', []))
        dislikes_count = len(comment.get('dislikes', []))
        
        return jsonify({
            'success': True, 
            'message': 'Comment liked',
            'likes': likes_count,
            'dislikes': dislikes_count
        })
    except Exception as e:
        print(f"Error in like_comment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/comment/<comment_id>/dislike', methods=['POST'])
@bp.route('/resources/comment/<comment_id>/dislike', methods=['POST'])
@bp.route('/resources/resources/comment/<comment_id>/dislike', methods=['POST'])
@login_required
def dislike_comment(comment_id):
    """Dislike a comment"""
    try:
        # Convert the comment ID to ObjectId
        obj_id = ObjectId(comment_id)
        
        # Find the resource containing this comment
        resource_data = current_app.db.resources.find_one({"comments._id": obj_id})
        if not resource_data:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
            
        # Find the comment in the resource
        comment = None
        for c in resource_data['comments']:
            if c['_id'] == obj_id:
                comment = c
                break
                
        if not comment:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
        
        # Check if user already disliked this comment
        user_disliked = False
        for dislike in comment.get('dislikes', []):
            if dislike.get('user_id') == current_user.id:
                user_disliked = True
                break
        
        # Check if user already liked this comment
        user_liked = False
        for like in comment.get('likes', []):
            if like.get('user_id') == current_user.id:
                user_liked = True
                break
        
        # If user already disliked, remove the dislike (toggle)
        if user_disliked:
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$pull': {'comments.$.dislikes': {'user_id': current_user.id}}}
            )
            
            # Get updated dislikes count
            resource = current_app.db.resources.find_one({'comments._id': obj_id})
            comment = next((c for c in resource['comments'] if c['_id'] == obj_id), None)
            likes_count = len(comment.get('likes', []))
            dislikes_count = len(comment.get('dislikes', []))
            
            return jsonify({
                'success': True, 
                'message': 'Dislike removed',
                'likes': likes_count,
                'dislikes': dislikes_count
            })
            
        # If liked, remove the like first
        if user_liked:
            current_app.db.resources.update_one(
                {'comments._id': obj_id},
                {'$pull': {'comments.$.likes': {'user_id': current_user.id}}}
            )
        
        # Add the dislike
        current_app.db.resources.update_one(
            {'comments._id': obj_id},
            {'$push': {'comments.$.dislikes': {'user_id': current_user.id, 'created_at': datetime.utcnow()}}}
        )
        
        # Get updated dislikes count
        resource = current_app.db.resources.find_one({'comments._id': obj_id})
        comment = next((c for c in resource['comments'] if c['_id'] == obj_id), None)
        likes_count = len(comment.get('likes', []))
        dislikes_count = len(comment.get('dislikes', []))
        
        return jsonify({
            'success': True, 
            'message': 'Comment disliked',
            'likes': likes_count,
            'dislikes': dislikes_count
        })
    except Exception as e:
        print(f"Error in dislike_comment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/comment/<comment_id>/reply', methods=['POST'])
@bp.route('/resources/comment/<comment_id>/reply', methods=['POST'])
@bp.route('/resources/resources/comment/<comment_id>/reply', methods=['POST'])
@login_required
def add_reply(comment_id):
    """Add a reply to a comment"""
    try:
        # Convert the comment ID to ObjectId
        obj_id = ObjectId(comment_id)
        
        # Find the resource containing this comment
        resource_data = current_app.db.resources.find_one({"comments._id": obj_id})
        if not resource_data:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
            
        # Find the comment in the resource
        comment = None
        for c in resource_data['comments']:
            if c['_id'] == obj_id:
                comment = c
                break
                
        if not comment:
            return jsonify({'success': False, 'message': 'Comment not found'}), 404
        
        # Get the reply content from the form
        reply_content = request.form.get('reply_content')
        if not reply_content or not reply_content.strip():
            return jsonify({'success': False, 'message': 'Reply content cannot be empty'}), 400
            
        # Create a new reply object
        reply = {
            '_id': ObjectId(),
            'content': reply_content.strip(),
            'user_id': current_user.id,
            'author': {
                'username': current_user.username,
                'id': current_user.id
            },
            'created_at': datetime.utcnow(),
            'likes': [],
            'dislikes': []
        }
        
        # Add the reply to the comment
        current_app.db.resources.update_one(
            {'comments._id': obj_id},
            {'$push': {'comments.$.replies': reply}}
        )
        
        return jsonify({
            'success': True,
            'message': 'Reply added successfully'
        })
    except Exception as e:
        print(f"Error in add_reply: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/reply/<reply_id>/like', methods=['POST'])
@bp.route('/resources/reply/<reply_id>/like', methods=['POST'])
@bp.route('/resources/resources/reply/<reply_id>/like', methods=['POST'])
@login_required
def like_reply(reply_id):
    """Like a reply"""
    try:
        # Convert the reply ID to ObjectId
        obj_id = ObjectId(reply_id)
        
        # Find the resource containing this reply
        resource_data = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        if not resource_data:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
        
        # Find the comment and reply
        comment = None
        reply = None
        comment_index = 0
        reply_index = 0
        
        for i, c in enumerate(resource_data['comments']):
            for j, r in enumerate(c.get('replies', [])):
                if r.get('_id') == obj_id:
                    comment = c
                    reply = r
                    comment_index = i
                    reply_index = j
                    break
            if comment:
                break
                
        if not comment or not reply:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
            
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
        
        # The path to the specific reply's likes/dislikes
        like_path = f"comments.{comment_index}.replies.{reply_index}.likes"
        dislike_path = f"comments.{comment_index}.replies.{reply_index}.dislikes"
        
        # If user already liked, remove the like (toggle)
        if user_liked:
            current_app.db.resources.update_one(
                {'comments.replies._id': obj_id},
                {'$pull': {like_path: {'user_id': current_user.id}}}
            )
            
            # Get updated likes count after change
            updated_resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
            updated_reply = None
            for c in updated_resource['comments']:
                for r in c.get('replies', []):
                    if r.get('_id') == obj_id:
                        updated_reply = r
                        break
                if updated_reply:
                    break
                    
            likes_count = len(updated_reply.get('likes', []))
            dislikes_count = len(updated_reply.get('dislikes', []))
            
            return jsonify({
                'success': True, 
                'message': 'Like removed',
                'likes': likes_count,
                'dislikes': dislikes_count
            })
            
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
        
        # Get updated counts after change
        updated_resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        updated_reply = None
        for c in updated_resource['comments']:
            for r in c.get('replies', []):
                if r.get('_id') == obj_id:
                    updated_reply = r
                    break
            if updated_reply:
                break
                
        likes_count = len(updated_reply.get('likes', []))
        dislikes_count = len(updated_reply.get('dislikes', []))
        
        return jsonify({
            'success': True, 
            'message': 'Reply liked',
            'likes': likes_count,
            'dislikes': dislikes_count
        })
    except Exception as e:
        print(f"Error in like_reply: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/reply/<reply_id>/dislike', methods=['POST'])
@bp.route('/resources/reply/<reply_id>/dislike', methods=['POST'])
@bp.route('/resources/resources/reply/<reply_id>/dislike', methods=['POST'])
@login_required
def dislike_reply(reply_id):
    """Dislike a reply"""
    try:
        # Convert the reply ID to ObjectId
        obj_id = ObjectId(reply_id)
        
        # Find the resource containing this reply
        resource_data = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        if not resource_data:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
        
        # Find the comment and reply
        comment = None
        reply = None
        comment_index = 0
        reply_index = 0
        
        for i, c in enumerate(resource_data['comments']):
            for j, r in enumerate(c.get('replies', [])):
                if r.get('_id') == obj_id:
                    comment = c
                    reply = r
                    comment_index = i
                    reply_index = j
                    break
            if comment:
                break
                
        if not comment or not reply:
            return jsonify({'success': False, 'message': 'Reply not found'}), 404
            
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
        
        # The path to the specific reply's likes/dislikes
        like_path = f"comments.{comment_index}.replies.{reply_index}.likes"
        dislike_path = f"comments.{comment_index}.replies.{reply_index}.dislikes"
        
        # If user already disliked, remove the dislike (toggle)
        if user_disliked:
            current_app.db.resources.update_one(
                {'comments.replies._id': obj_id},
                {'$pull': {dislike_path: {'user_id': current_user.id}}}
            )
            
            # Get updated dislikes count after change
            updated_resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
            updated_reply = None
            for c in updated_resource['comments']:
                for r in c.get('replies', []):
                    if r.get('_id') == obj_id:
                        updated_reply = r
                        break
                if updated_reply:
                    break
                    
            likes_count = len(updated_reply.get('likes', []))
            dislikes_count = len(updated_reply.get('dislikes', []))
            
            return jsonify({
                'success': True, 
                'message': 'Dislike removed',
                'likes': likes_count,
                'dislikes': dislikes_count
            })
            
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
        
        # Get updated counts after change
        updated_resource = current_app.db.resources.find_one({'comments.replies._id': obj_id})
        updated_reply = None
        for c in updated_resource['comments']:
            for r in c.get('replies', []):
                if r.get('_id') == obj_id:
                    updated_reply = r
                    break
            if updated_reply:
                break
                
        likes_count = len(updated_reply.get('likes', []))
        dislikes_count = len(updated_reply.get('dislikes', []))
        
        return jsonify({
            'success': True, 
            'message': 'Reply disliked',
            'likes': likes_count,
            'dislikes': dislikes_count
        })
    except Exception as e:
        print(f"Error in dislike_reply: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_resource():
    """Create a new resource"""
    form = ResourceForm()
    
    if form.validate_on_submit():
        try:
            print(f"[DEBUG] Form validated. Processing resource upload...")
            
            # Get file info
            file_path = None
            google_drive_link = form.drive_link.data if hasattr(form, 'drive_link') else None
            print(f"[DEBUG] Google Drive Link: {google_drive_link}")
            
            # Use the resource_type from the form
            file_type = form.resource_type.data if hasattr(form, 'resource_type') else None
            print(f"[DEBUG] Resource Type: {file_type}")
            
            # Handle file upload (only if Google Drive link is not provided)
            if not google_drive_link and hasattr(form, 'file') and form.file.data:
                file = form.file.data
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                # Don't override the file_type from the form
                if not file_type:
                    file_type = os.path.splitext(filename)[1][1:] if file_path else None
            elif google_drive_link:
                # Try to determine file type from Google Drive link
                if 'drive.google.com' in google_drive_link:
                    # Default to PDF for Google Drive links if not specified
                    if not file_type:
                        file_type = 'pdf'
            
            print(f"[DEBUG] Creating resource document with title: {form.title.data}")
            
            # Create resource document
            resource_data = {
                'title': form.title.data,
                'description': form.description.data,
                'file_path': file_path,
                'file_type': file_type,
                'google_drive_link': google_drive_link,
                'user_id': current_user.id,
                'created_at': datetime.utcnow(),
                'views': 0,
                'downloads': 0
            }
            
            # Add optional fields if present in the form
            if hasattr(form, 'country') and form.country.data:
                resource_data['country'] = form.country.data
            if hasattr(form, 'grade_level') and form.grade_level.data:
                resource_data['grade_level'] = form.grade_level.data
            if hasattr(form, 'subject') and form.subject.data:
                resource_data['subject'] = form.subject.data
            if hasattr(form, 'tags') and form.tags.data:
                resource_data['tags'] = [tag.strip() for tag in form.tags.data.split(',')] if form.tags.data else []
            
            print(f"[DEBUG] Inserting resource into database...")
            print(f"[DEBUG] Database instance: {current_app.db}")
            
            # Insert into database
            try:
                result = current_app.db.resources.insert_one(resource_data)
                print(f"[DEBUG] Insert result: {result.inserted_id}")
                
                if result.inserted_id:
                    print(f"[DEBUG] Resource created successfully with ID: {result.inserted_id}")
                    flash('Resource created successfully!', 'success')
                    return redirect(url_for('resources.view_resource', resource_id=result.inserted_id))
                else:
                    print(f"[DEBUG] Failed to create resource. No inserted_id returned.")
                    flash('Failed to create resource', 'error')
            except Exception as db_error:
                print(f"[DEBUG] Database error: {str(db_error)}")
                current_app.logger.error(f"Database error in create_resource: {str(db_error)}")
                flash(f'Database error: {str(db_error)}', 'error')
                
        except Exception as e:
            print(f"[DEBUG] Error in create_resource: {str(e)}")
            current_app.logger.error(f"Error in create_resource: {str(e)}")
            flash('An error occurred while creating the resource', 'error')
    else:
        # Print form validation errors if any
        if form.errors:
            print(f"[DEBUG] Form validation errors: {form.errors}")
    
    return render_template('resources/create.html', form=form)

@bp.route('/search')
def search():
    """Search for resources"""
    try:
        # Get search query
        query = request.args.get('q', '')
        if not query:
            return redirect(url_for('resources.list_resources'))
            
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        max_per_page = 20
        per_page = min(per_page, max_per_page)
        
        # Get sort option (default to relevance for search)
        sort_option = request.args.get('sort', 'recent')
        
        # Get filter parameters
        subject = request.args.get('subject', '')
        grade_level = request.args.get('grade_level', '')
        country = request.args.get('country', '')
        board = request.args.get('board', '')
        
        # Use the get_resources method with search query
        result = Resource.get_resources(
            current_app.db,
            page=page,
            per_page=per_page,
            sort_by=sort_option,
            search_query=query,
            subject=subject,
            grade_level=grade_level,
            country=country,
            board=board
        )
        
        # Get the resources
        resources = result['resources']
        
        # If this is an AJAX request for infinite scroll/pagination
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_template('resources/resource_cards.html', resources=resources)
            return jsonify({
                'html': html,
                'has_more': result['has_next'],
                'next_page': page + 1 if result['has_next'] else None
            })
        
        # Render the same template as list_resources for consistent UI
        return render_template(
            'resources/list.html',
            resources=resources,
            query=query,
            current_sort=sort_option,
            pagination={
                'page': page,
                'per_page': per_page,
                'total': result['total'],
                'pages': result['pages'],
                'has_prev': result['has_prev'],
                'has_next': result['has_next'],
                'prev_num': page - 1,
                'next_num': page + 1,
                'iter_pages': lambda: range(1, result['pages'] + 1)
            }
        )
        
    except Exception as e:
        print(f"Error in search: {str(e)}")
        flash('An error occurred while searching resources', 'error')
        return render_template('resources/list.html', resources=[], query=request.args.get('q', ''))

@bp.route('/search_resources')
def search_resources():
    """Advanced search for resources with filters"""
    try:
        # Get search parameters
        query = request.args.get('q', '')
        country = request.args.get('country', '')
        subject = request.args.get('subject', '')
        grade_level = request.args.get('grade_level', '')
        min_price = request.args.get('min_price', '')
        max_price = request.args.get('max_price', '')
        sort = request.args.get('sort', 'relevance')
        tag = request.args.get('tag', '')
        page = int(request.args.get('page', '1'))
        
        # Build match criteria
        match_criteria = {}
        
        if query:
            match_criteria["$or"] = [
                {"title": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}}
            ]
        
        if country:
            match_criteria["country"] = country
            
        if subject:
            match_criteria["subject"] = subject
            
        if grade_level:
            match_criteria["grade_level"] = grade_level
            
        if tag:
            match_criteria["tags"] = tag
            
        # Add price range filter if specified
        if min_price or max_price:
            price_filter = {}
            if min_price:
                try:
                    price_filter["$gte"] = float(min_price)
                except ValueError:
                    pass
            if max_price:
                try:
                    price_filter["$lte"] = float(max_price)
                except ValueError:
                    pass
            if price_filter:
                match_criteria["price"] = price_filter
        
        # Build the aggregation pipeline
        pipeline = []
        
        # Only add match stage if we have criteria
        if match_criteria:
            pipeline.append({'$match': match_criteria})
        
        # Add author lookup
        pipeline.extend([
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'user_id',
                    'foreignField': '_id',
                    'as': 'author'
                }
            },
            {
                '$addFields': {
                    'author': { '$arrayElemAt': ['$author', 0] }
                }
            }
        ])
        
        # Add sort stage
        if sort == 'newest':
            pipeline.append({'$sort': {'created_at': -1}})
        elif sort == 'popular':
            pipeline.append({'$sort': {'views': -1}})
        elif sort == 'rating':
            pipeline.append({'$sort': {'rating': -1}})
        else:  # relevance or default
            if query:
                # Relevance sort with text match score
                pipeline.append({'$sort': {'score': {'$meta': 'textScore'}}})
            else:
                # Default to newest if no query
                pipeline.append({'$sort': {'created_at': -1}})
        
        # Get popular tags
        popular_tags = []
        try:
            # Aggregate to get tag counts
            tag_pipeline = [
                {'$unwind': '$tags'},
                {'$group': {'_id': '$tags', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}},
                {'$limit': 15}
            ]
            
            tag_results = list(current_app.db.resources.aggregate(tag_pipeline))
            popular_tags = [{'name': tag['_id'], 'count': tag['count']} for tag in tag_results]
        except Exception as e:
            print(f"Error getting popular tags: {str(e)}")
        
        # Get distinct countries
        countries = []
        try:
            countries = current_app.db.resources.distinct('country')
            countries = [c for c in countries if c]  # Filter out empty values
        except Exception as e:
            print(f"Error getting countries: {str(e)}")
        
        # Get resources with pagination
        per_page = 12
        skip = (page - 1) * per_page
        
        # Create a copy of the pipeline for counting
        count_pipeline = pipeline.copy()
        count_pipeline.append({'$count': 'total'})
        
        # Add pagination
        pipeline.append({'$skip': skip})
        pipeline.append({'$limit': per_page})
        
        # Execute the pipeline
        resources_data = list(current_app.db.resources.aggregate(pipeline))
        
        # Get total count
        count_result = list(current_app.db.resources.aggregate(count_pipeline))
        total = count_result[0]['total'] if count_result else 0
        
        # Convert results to Resource objects
        resources = []
        for data in resources_data:
            resource = Resource(data)
            if data.get('author'):
                from app.models.user import User
                resource._author = User(data['author'])
            resources.append(resource)
        
        # Create pagination object
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': page < ((total + per_page - 1) // per_page),
            'prev_num': page - 1,
            'next_num': page + 1,
            'iter_pages': lambda: range(1, result['pages'] + 1)
        }
        
        # Get grade levels and subjects from config
        grade_levels = current_app.config['GRADE_LEVELS']
        subjects = current_app.config['SUBJECTS']
        
        return render_template('resources/search.html',
                              resources=resources,
                              query=query,
                              countries=countries,
                              subjects=subjects,
                              grade_levels=grade_levels,
                              popular_tags=popular_tags,
                              pagination=pagination)
                              
    except Exception as e:
        print(f"Error in search_resources: {str(e)}")
        flash('An error occurred while searching resources', 'error')
        return redirect(url_for('resources.list_resources'))

@bp.route('/my-resources')
@login_required
def my_resources():
    """Show resources created by the current user"""
    try:
        # Get parameters for filtering/sorting
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        max_per_page = 20  # Add maximum limit
        per_page = min(per_page, max_per_page)  # Enforce the maximum limit
        sort_option = request.args.get('sort', 'recent')
        
        # Add match stage for current user's resources
        match_conditions = {}
        match_conditions['user_id'] = current_user.id
        
        # Use the new get_resources method with user filter
        pipeline = [
            {'$match': match_conditions},
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'user_id',
                    'foreignField': '_id',
                    'as': 'author'
                }
            },
            {
                '$addFields': {
                    'author': { '$arrayElemAt': ['$author', 0] }
                }
            }
        ]
        
        # Add sort stage based on user's selection
        if sort_option == 'recent':
            pipeline.append({'$sort': {'created_at': -1}})
        elif sort_option == 'oldest':
            pipeline.append({'$sort': {'created_at': 1}})
        elif sort_option == 'most_views':
            pipeline.append({'$sort': {'views': -1}})
        elif sort_option == 'most_downloads':
            pipeline.append({'$sort': {'downloads': -1}})
        elif sort_option == 'title_asc':
            pipeline.append({'$sort': {'title': 1}})
        elif sort_option == 'title_desc':
            pipeline.append({'$sort': {'title': -1}})
        
        # Create a copy of the pipeline for counting total resources
        count_pipeline = pipeline.copy()
        count_pipeline.append({'$count': 'total'})
        
        # Get total count
        total_count_result = list(current_app.db.resources.aggregate(count_pipeline))
        total_count = total_count_result[0]['total'] if total_count_result else 0
        
        # Calculate total pages
        pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        # Add pagination to the main pipeline
        pipeline.append({'$skip': (page - 1) * per_page})
        pipeline.append({'$limit': per_page})
        
        # Get paginated resources with author information using aggregation
        resources_data = list(current_app.db.resources.aggregate(pipeline))
        
        # Convert results to Resource objects
        resources = []
        for data in resources_data:
            resource = Resource(data)
            if data.get('author'):
                from app.models.user import User
                resource._author = User(data['author'])
            resources.append(resource)
        
        return render_template(
            'resources/my_resources.html',
            resources=resources,
            current_sort=sort_option,
            pagination={
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': pages,
                'has_prev': page > 1,
                'has_next': page < pages,
                'prev_num': page - 1,
                'next_num': page + 1,
                'iter_pages': lambda: range(1, pages + 1)
            }
        )
        
    except Exception as e:
        print(f"Error in my_resources: {str(e)}")
        flash('An error occurred while fetching your resources', 'error')
        return render_template('resources/my_resources.html', resources=[])

@bp.route('/<resource_id>/comment', methods=['POST'])
@login_required
def add_comment(resource_id):
    """Add a comment to a resource"""
    form = CommentForm()
    
    if form.validate_on_submit():
        try:
            # Convert string ID to ObjectId
            if not isinstance(resource_id, ObjectId):
                obj_id = ObjectId(resource_id)
            else:
                obj_id = resource_id
                
            # Get the resource
            resource_data = current_app.db.resources.find_one({'_id': obj_id})
            if not resource_data:
                flash('Resource not found', 'error')
                return redirect(url_for('resources.list_resources'))
            
            resource = Resource(resource_data)
            
            # Get current user data for author info
            user_data = current_app.db.users.find_one({'_id': current_user.id})
            if not user_data:
                flash('User data not found', 'error')
                return redirect(url_for('resources.view_resource', resource_id=resource_id))
            
            # Add the comment with user data
            comment = {
                'id': str(ObjectId()),
                'user_id': current_user.id,
                'content': form.content.data,
                'created_at': datetime.utcnow(),
                'likes': 0,
                'liked_by': []
            }
            
            # Insert the comment
            current_app.db.resources.update_one(
                {'_id': obj_id},
                {'$push': {'comments': comment}}
            )
            
            flash('Comment added successfully', 'success')
        except InvalidId as e:
            flash('Invalid resource ID format', 'error')
        except Exception as e:
            print(f"Error adding comment: {str(e)}")
            flash('An error occurred while adding your comment', 'error')
    
    return redirect(url_for('resources.view_resource', resource_id=resource_id))

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_resource():
    """Upload a new resource (alias for create_resource for backwards compatibility)"""
    return create_resource()

@bp.route('/resource/<resource_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_resource(resource_id):
    """Edit a resource"""
    try:
        # Convert string ID to ObjectId for MongoDB
        obj_id = ObjectId(resource_id)
        
        # Get resource from database
        resource_data = current_app.db.resources.find_one({'_id': obj_id})
        if not resource_data:
            flash('Resource not found', 'error')
            return redirect(url_for('resources.my_resources'))
        
        # Check if user owns this resource
        resource = Resource(resource_data)
        if str(resource.user_id) != str(current_user.id):
            flash('You do not have permission to edit this resource', 'error')
            return redirect(url_for('resources.my_resources'))
        
        # Initialize form
        form = ResourceForm(obj=resource)
        
        if request.method == 'POST' and form.validate_on_submit():
            # Update resource fields
            updates = {
                'title': form.title.data,
                'description': form.description.data,
                'country': form.country.data,
                'grade_level': form.grade_level.data,
                'subject': form.subject.data,
                'tags': [tag.strip() for tag in form.tags.data.split(',')] if form.tags.data else [],
                'updated_at': datetime.now(),
            }
            
            # Update Google Drive link if provided
            if form.drive_link.data:
                updates['google_drive_link'] = form.drive_link.data
            
            # Update resource type if provided
            if hasattr(form, 'resource_type') and form.resource_type.data:
                updates['file_type'] = form.resource_type.data
            
            # Update thumbnail if provided
            if request.files.get('thumbnail') and request.files['thumbnail'].filename:
                from werkzeug.utils import secure_filename
                import os
                
                # Save new thumbnail
                file = request.files['thumbnail']
                filename = secure_filename(file.filename)
                thumbnail_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'thumbnails', filename)
                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                file.save(thumbnail_path)
                updates['thumbnail_url'] = url_for('static', filename=f'uploads/thumbnails/{filename}', _external=True)
            
            # Update in database
            current_app.db.resources.update_one(
                {'_id': obj_id},
                {'$set': updates}
            )
            
            flash('Resource updated successfully', 'success')
            return redirect(url_for('resources.view_resource', resource_id=resource_id))
        
        # For GET request, populate form with resource data
        return render_template('resources/edit.html', form=form, resource=resource)
        
    except InvalidId as e:
        flash('Invalid resource ID format', 'error')
        return redirect(url_for('resources.my_resources'))
    except Exception as e:
        current_app.logger.error(f"Error in edit_resource: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('resources.my_resources'))

@bp.route('/resource/<resource_id>/delete', methods=['POST'])
@login_required
def delete_resource(resource_id):
    """Delete a resource"""
    try:
        # Convert string ID to ObjectId for MongoDB
        obj_id = ObjectId(resource_id)
        
        # Get resource from database
        resource_data = current_app.db.resources.find_one({'_id': obj_id})
        if not resource_data:
            flash('Resource not found', 'error')
            return redirect(url_for('resources.my_resources'))
        
        # Check if user owns this resource
        resource = Resource(resource_data)
        if str(resource.user_id) != str(current_user.id):
            flash('You do not have permission to delete this resource', 'error')
            return redirect(url_for('resources.my_resources'))
        
        # Delete the resource
        current_app.db.resources.delete_one({'_id': obj_id})
        
        flash('Resource deleted successfully', 'success')
        return redirect(url_for('resources.my_resources'))
        
    except InvalidId as e:
        flash('Invalid resource ID format', 'error')
        return redirect(url_for('resources.my_resources'))
    except Exception as e:
        current_app.logger.error(f"Error in delete_resource: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('resources.my_resources'))

@bp.route('/analytics')
@login_required
def resource_analytics():
    """Show analytics for user's resources"""
    try:
        user_id = current_user.id
        
        # Try to convert user_id to ObjectId if it's a string
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except InvalidId:
                current_app.logger.warning(f"Could not convert user_id to ObjectId, using as is: {user_id}")
        
        # Get resources for the current user, try both ObjectId and string formats
        resource_query = {'$or': [
            {'user_id': user_id},
            {'user_id': str(user_id)}
        ]}
        
        resources_data = list(current_app.db.resources.find(resource_query))
        
        if not resources_data:
            flash('No resources found for your account', 'info')
            return render_template('resources/analytics.html', 
                                  resources=[],
                                  total_views=0,
                                  total_downloads=0,
                                  total_resources=0,
                                  avg_views=0,
                                  avg_downloads=0,
                                  most_viewed=None,
                                  most_downloaded=None)
        
        # Convert results to Resource objects
        resources = [Resource(data) for data in resources_data]
        
        # Calculate aggregate stats
        total_views = sum(resource.views or 0 for resource in resources)
        total_downloads = sum(resource.downloads or 0 for resource in resources)
        total_resources = len(resources)
        
        # Calculate average views and downloads per resource
        avg_views = total_views / total_resources if total_resources > 0 else 0
        avg_downloads = total_downloads / total_resources if total_resources > 0 else 0
        
        # Get most viewed and most downloaded resources
        most_viewed = max(resources, key=lambda r: r.views or 0) if resources else None
        most_downloaded = max(resources, key=lambda r: r.downloads or 0) if resources else None
        
        return render_template('resources/analytics.html', 
                              resources=resources,
                              total_views=total_views,
                              total_downloads=total_downloads,
                              total_resources=total_resources,
                              avg_views=avg_views,
                              avg_downloads=avg_downloads,
                              most_viewed=most_viewed,
                              most_downloaded=most_downloaded)
                              
    except Exception as e:
        current_app.logger.error(f"Error in resource_analytics: {str(e)}")
        flash('An error occurred while generating analytics', 'error')
        return redirect(url_for('resources.my_resources'))

@bp.route('/user/<username>')
def user_profile(username):
    """Display a user's profile and all resources they have uploaded"""
    try:
        from app.models.user import User
        
        # Find the user by username
        user = User.get_by_username(username, db=current_app.db)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('resources.list_resources'))
        
        # Build the aggregation pipeline to find all resources by this user
        # Use both possible ID formats to ensure we find all resources
        user_id_obj = ObjectId(user.id) if isinstance(user.id, str) else user.id
        
        pipeline = [
            {
                '$match': {
                    '$or': [
                        {'user_id': user_id_obj},
                        {'user_id': user.id}
                    ]
                }
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'user_id',
                    'foreignField': '_id',
                    'as': 'author'
                }
            },
            {
                '$addFields': {
                    'author': { '$arrayElemAt': ['$author', 0] }
                }
            },
            {'$sort': {'created_at': -1}}
        ]
        
        # Get resources with author information using aggregation
        resources_data = list(current_app.db.resources.aggregate(pipeline))
        current_app.logger.info(f"Found {len(resources_data)} resources for user {user.username}")
        
        # Convert results to Resource objects and calculate total views and downloads
        resources = []
        total_views = 0
        total_downloads = 0
        
        for data in resources_data:
            resource = Resource(data)
            if data.get('author'):
                resource._author = User(data['author'])
            resources.append(resource)
            
            # Add to totals
            total_views += data.get('views', 0)
            total_downloads += data.get('downloads', 0)
        
        return render_template(
            'resources/user_profile.html', 
            user=user, 
            resources=resources,
            total_resources=len(resources),
            total_views=total_views,
            total_downloads=total_downloads
        )
    except Exception as e:
        current_app.logger.error(f"Error in user_profile: {str(e)}")
        flash('An error occurred while fetching user profile', 'error')
        return redirect(url_for('resources.list_resources'))