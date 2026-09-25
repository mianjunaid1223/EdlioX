from datetime import datetime
from bson import ObjectId
import google.generativeai as genai
from app import create_app
from slugify import slugify
from flask import current_app
import re
from threading import Lock

# More efficient content moderation patterns with compiled regex
INAPPROPRIATE_PATTERNS = [
    re.compile(r'\b(asshole|bitch|fuck|shit|damn|hell)\b', re.IGNORECASE),
    re.compile(r'\b(nigger|nigga|chink|spic|kike)\b', re.IGNORECASE),
]

# Thread-safe cache implementation
class LRUCache:
    def __init__(self, capacity=100):
        self.capacity = capacity
        self.cache = {}
        self.order = []
        self.lock = Lock()
        
    def get(self, key):
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.order.remove(key)
                self.order.append(key)
                return self.cache[key]
            return None
            
    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.order.remove(key)
            elif len(self.cache) >= self.capacity:
                # Remove least recently used
                oldest = self.order.pop(0)
                del self.cache[oldest]
                
            self.cache[key] = value
            self.order.append(key)

# Initialize global caches
discussion_cache = LRUCache(capacity=50)
user_cache = LRUCache(capacity=100)

def is_inappropriate(content):
    """More efficient content checking using compiled regex patterns"""
    for pattern in INAPPROPRIATE_PATTERNS:
        if pattern.search(content):
            return True
    return False

class Discussion:
    def __init__(self, discussion_data):
        if not discussion_data:
            raise ValueError("Discussion data cannot be None")
            
        self.id = str(discussion_data.get('_id'))
        self.title = discussion_data.get('title', '')
        self.content = discussion_data.get('content', '')
        self.user_id = discussion_data.get('user_id')
        self.resource_id = discussion_data.get('resource_id')
        self.created_at = discussion_data.get('created_at', datetime.utcnow())
        self.updated_at = discussion_data.get('updated_at', datetime.utcnow())
        self.views = discussion_data.get('views', 0)
        self.comments = discussion_data.get('comments', [])
        self.tags = discussion_data.get('tags', [])
        self.status = discussion_data.get('status', 'active')
        self.slug = discussion_data.get('slug', '')
        self.votes = discussion_data.get('votes', {'up': [], 'down': []})
        self.score = discussion_data.get('score', 0)
        self.subject = discussion_data.get('subject', 'General')
        self.grade_level = discussion_data.get('grade_level', 'General')
        self._author = None
        
        # Add username property for convenience
        self.username = 'Anonymous'
        if self.user_id:
            try:
                from app.models.user import User
                user_data = current_app.db.users.find_one({'_id': self.user_id})
                if user_data:
                    user = User(user_data)
                    self.username = user.username
            except:
                pass
        
    @property
    def author(self):
        """Cached property to get the author information"""
        if self._author is None and self.user_id:
            # Check user cache first
            cached_user = user_cache.get(str(self.user_id))
            if cached_user:
                self._author = cached_user
            else:
                from app.models.user import User
                user_data = current_app.db.users.find_one({'_id': self.user_id})
                if user_data:
                    self._author = User(user_data)
                    # Cache the user
                    user_cache.put(str(self.user_id), self._author)
        return self._author
        
    def to_dict(self, include_comments=False):
        """Efficient dictionary conversion with selective comment inclusion"""
        result = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'user_id': str(self.user_id) if self.user_id else None,
            'username': self.author.username if self.author else 'Anonymous',
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
            'views': self.views,
            'comment_count': len(self.comments),
            'score': self.score,
            'votes': self.votes,
            'slug': self.slug,
            'subject': self.subject,
            'grade_level': self.grade_level
        }
        
        if include_comments:
            result['comments'] = self._process_comments_for_output()
            
        return result
    
    def _process_comments_for_output(self):
        """Process comments for optimized output"""
        processed_comments = []
        
        for comment in self.comments:
            # Get username for each comment from cache if possible
            username = 'Anonymous'
            user_id = comment.get('user_id')
            
            if user_id:
                cached_user = user_cache.get(str(user_id))
                if cached_user:
                    username = cached_user.username
                else:
                    from app.models.user import User
                    user_data = current_app.db.users.find_one({'_id': user_id})
                    if user_data:
                        user = User(user_data)
                        username = user.username
                        user_cache.put(str(user_id), user)
            
            processed_comment = {
                'id': comment.get('id'),
                'content': comment.get('content', ''),
                'user_id': str(user_id) if user_id else None,
                'username': username,
                'created_at': comment.get('created_at').isoformat() if isinstance(comment.get('created_at'), datetime) else comment.get('created_at'),
                'parent_id': comment.get('parent_id'),
                'votes': comment.get('votes', {'up': [], 'down': []}),
                'score': comment.get('score', 0)
            }
            
            processed_comments.append(processed_comment)
            
        return processed_comments

    @staticmethod
    def create_discussion(db, user_id, title, content, subject='General', grade_level='General', visibility='public', resource_id=None, tags=None):
        """Create a new discussion with optimized database operations"""
        try:
            # Input validation
            if not title or not content:
                raise ValueError("Title and content cannot be empty")
                
            # Convert user_id to ObjectId if it's a string
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
                
            # Generate a unique slug efficiently
            base_slug = slugify(str(title).strip())
            if not base_slug:
                base_slug = 'untitled'
                
            # Use a more efficient query to check for existing slug
            slug = base_slug
            counter = 1
            while db.discussions.find_one({'slug': slug}, {'_id': 1}):
                slug = f"{base_slug}-{counter}"
                counter += 1
                
            # Prepare discussion data
            discussion_data = {
                'user_id': user_id,
                'title': title,
                'content': content,
                'subject': subject or 'General',
                'grade_level': grade_level or 'General',
                'visibility': visibility,
                'resource_id': ObjectId(resource_id) if resource_id else None,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'views': 0,
                'comments': [],
                'tags': tags or [],
                'status': 'active',
                'slug': slug,
                'votes': {'up': [], 'down': []},
                'score': 0
            }
            
            # Insert discussion with proper error handling
            result = db.discussions.insert_one(discussion_data)
            if not result.inserted_id:
                raise Exception("Failed to insert discussion into database")
                
            discussion_data['_id'] = result.inserted_id
            discussion = Discussion(discussion_data)
            
            # Cache the new discussion
            discussion_cache.put(str(discussion.id), discussion)
            
            return discussion
            
        except Exception as e:
            current_app.logger.error(f"Error creating discussion: {str(e)}")
            raise

    def add_comment(self, db, user_id, content, parent_id=None):
        """Add a comment with optimized database update"""
        if not content:
            raise ValueError("Comment content cannot be empty")
            
        comment_id = str(ObjectId())
        comment = {
            'id': comment_id,
            'user_id': user_id,
            'content': content,
            'created_at': datetime.utcnow(),
            'parent_id': parent_id,
            'votes': {'up': [], 'down': []},
            'score': 0
        }
        
        # More efficient update that only modifies necessary fields
        update_result = db.discussions.update_one(
            {'_id': ObjectId(self.id)},
            {
                '$push': {'comments': comment},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        
        if update_result.modified_count > 0:
            self.comments.append(comment)
            # Invalidate cache entry
            discussion_cache.put(self.id, self)
            
        return comment

    def increment_views(self, db):
        """Increment view count with atomic operation"""
        # Use findAndModify to atomically update and return
        result = db.discussions.find_one_and_update(
            {'_id': ObjectId(self.id)},
            {'$inc': {'views': 1}},
            return_document=True
        )
        
        if result:
            self.views = result.get('views', self.views + 1)
            # Update cache
            discussion_cache.put(self.id, self)
            
        return self.views

    @staticmethod
    def get_by_id(db, discussion_id):
        """Get a discussion by its ID with optimized database access"""
        try:
            # Check if id is a valid ObjectId
            if not ObjectId.is_valid(discussion_id):
                return None

            # Check cache first for optimized performance
            cached_discussion = discussion_cache.get(str(discussion_id))
            if cached_discussion:
                return cached_discussion
            
            # Use pure pymongo query with projection
            discussion_data = db.discussions.find_one(
                {'_id': ObjectId(discussion_id), 'status': 'active'}
            )
            
            if not discussion_data:
                return None
                
            # Create discussion object
            discussion = Discussion(discussion_data)
            
            # Cache the discussion for future access
            discussion_cache.put(str(discussion.id), discussion)
            
            return discussion
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error in get_by_id: {str(e)}")
            return None

    @staticmethod
    def get_by_slug(db, slug):
        """Get discussion by slug with indexing optimization"""
        # First check if we already know the ID from this slug (could be cached)
        discussion_data = db.discussions.find_one({'slug': slug})
        
        if discussion_data:
            discussion_id = str(discussion_data['_id'])
            
            # Check if it's in our cache
            cached_discussion = discussion_cache.get(discussion_id)
            if cached_discussion:
                return cached_discussion
                
            # Create and cache the discussion
            discussion = Discussion(discussion_data)
            discussion_cache.put(discussion_id, discussion)
            return discussion
            
        return None

    @staticmethod
    def get_discussions(db, page=1, per_page=10, sort_by='score', search_query=None, 
                       subject=None, grade_level=None, tag=None):
        """Get discussions with pagination, sorting, and filtering"""
        try:
            # Validate and enforce limits on pagination
            page = max(1, page)  # Ensure page is at least 1
            per_page = max(1, min(per_page, 50))  # Ensure per_page is between 1 and 50
            
            # Build filter
            discussion_filter = {'status': 'active'}
            
            # Add search filter if provided
            if search_query:
                # Use text search if indexes are available
                if db.discussions.index_information().get('title_text_content_text'):
                    discussion_filter['$text'] = {'$search': search_query}
                else:
                    # Fallback to regex if no text index
                    discussion_filter['$or'] = [
                        {'title': {'$regex': search_query, '$options': 'i'}},
                        {'content': {'$regex': search_query, '$options': 'i'}}
                    ]
            
            # Add subject filter if provided
            if subject:
                discussion_filter['subject'] = subject
            
            # Add grade level filter if provided
            if grade_level:
                discussion_filter['grade_level'] = grade_level
                
            # Add tag filter if provided
            if tag:
                discussion_filter['tags'] = tag
            
            # Determine sort order
            sort_order = []
            if sort_by == 'newest':
                sort_order = [('created_at', -1)]
            elif sort_by == 'oldest':
                sort_order = [('created_at', 1)]
            elif sort_by == 'active':
                sort_order = [('updated_at', -1)]
            elif sort_by == 'unanswered':
                # Add filter for discussions with no comments
                discussion_filter['comments'] = {'$size': 0}
                sort_order = [('created_at', -1)]
            else:  # Default to score
                sort_order = [('score', -1), ('views', -1)]
            
            # Calculate skip and limit for pagination
            skip = (page - 1) * per_page
            
            # Get total count - use more efficient countDocuments
            total = db.discussions.count_documents(discussion_filter)
            
            # Calculate total pages
            pages = (total + per_page - 1) // per_page if total > 0 else 1
            
            # Get discussions with projection for efficiency
            # Only get the fields we need for the listing
            projection = {
                'title': 1,
                'content': 1,
                'user_id': 1,
                'created_at': 1,
                'updated_at': 1,
                'views': 1,
                'comments': 1,
                'tags': 1,
                'score': 1,
                'subject': 1,
                'grade_level': 1,
                'votes': 1
            }
            
            discussions_data = list(db.discussions
                .find(discussion_filter, projection)
                .sort(sort_order)
                .skip(skip)
                .limit(per_page))
            
            # Convert to Discussion objects
            discussions = []
            for data in discussions_data:
                discussions.append(Discussion(data))
            
            # Return result
            return {
                'discussions': discussions,
                'total': total,
                'pages': pages,
                'current_page': page
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in get_discussions: {str(e)}")
            raise

    def vote(self, db, user_id, vote_type):
        """Vote on a discussion with optimized atomic updates"""
        try:
            # Validate user_id
            if not user_id:
                raise ValueError("User ID is required")
                
            # Convert to ObjectId if string
            if isinstance(user_id, str) and ObjectId.is_valid(user_id):
                user_id = ObjectId(user_id)
                
            # Validate vote_type
            if vote_type not in ['up', 'down']:
                raise ValueError("Invalid vote type")
                
            # Check if already voted
            has_upvoted = any(str(voter) == str(user_id) for voter in self.votes['up'])
            has_downvoted = any(str(voter) == str(user_id) for voter in self.votes['down'])
            
            # Initialize update operation with atomic updates
            update = {}
            
            # Apply vote logic
            if vote_type == 'up':
                if has_upvoted:
                    # Already upvoted, remove upvote
                    update = {
                        '$pull': {'votes.up': user_id},
                        '$inc': {'score': -1}
                    }
                    # Update local state
                    self.votes['up'] = [voter for voter in self.votes['up'] if str(voter) != str(user_id)]
                    self.score -= 1
                    has_upvoted = False
                else:
                    # New upvote
                    if has_downvoted:
                        # Remove downvote first if exists
                        update = {
                            '$pull': {'votes.down': user_id},
                            '$push': {'votes.up': user_id},
                            '$inc': {'score': 2}  # +1 for removing downvote, +1 for adding upvote
                        }
                        # Update local state
                        self.votes['down'] = [voter for voter in self.votes['down'] if str(voter) != str(user_id)]
                        self.votes['up'].append(user_id)
                        self.score += 2
                        has_upvoted = True
                        has_downvoted = False
                    else:
                        # Simple upvote
                        update = {
                            '$push': {'votes.up': user_id},
                            '$inc': {'score': 1}
                        }
                        # Update local state
                        self.votes['up'].append(user_id)
                        self.score += 1
                        has_upvoted = True
            else:  # vote_type == 'down'
                if has_downvoted:
                    # Already downvoted, remove downvote
                    update = {
                        '$pull': {'votes.down': user_id},
                        '$inc': {'score': 1}
                    }
                    # Update local state
                    self.votes['down'] = [voter for voter in self.votes['down'] if str(voter) != str(user_id)]
                    self.score += 1
                    has_downvoted = False
                else:
                    # New downvote
                    if has_upvoted:
                        # Remove upvote first if exists
                        update = {
                            '$pull': {'votes.up': user_id},
                            '$push': {'votes.down': user_id},
                            '$inc': {'score': -2}  # -1 for removing upvote, -1 for adding downvote
                        }
                        # Update local state
                        self.votes['up'] = [voter for voter in self.votes['up'] if str(voter) != str(user_id)]
                        self.votes['down'].append(user_id)
                        self.score -= 2
                        has_downvoted = True
                        has_upvoted = False
                    else:
                        # Simple downvote
                        update = {
                            '$push': {'votes.down': user_id},
                            '$inc': {'score': -1}
                        }
                        # Update local state
                        self.votes['down'].append(user_id)
                        self.score -= 1
                        has_downvoted = True
            
            # Update the document in one atomic operation
            if update:
                result = db.discussions.update_one(
                    {'_id': ObjectId(self.id)}, 
                    update,
                    upsert=False
                )
                
                # Update timestamp
                db.discussions.update_one(
                    {'_id': ObjectId(self.id)},
                    {'$set': {'updated_at': datetime.utcnow()}}
                )
                
                # Update cache
                discussion_cache.put(self.id, self)
            
            # Return detailed info for frontend
            return {
                'success': True,
                'score': self.score,
                'upvotes': len(self.votes['up']),
                'downvotes': len(self.votes['down']),
                'has_upvoted': has_upvoted,
                'has_downvoted': has_downvoted
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in vote: {str(e)}")
            return {'error': str(e), 'success': False}

    def vote_comment(self, db, comment_id, user_id, vote_type):
        """Vote on a comment with atomic updates"""
        try:
            # Validate parameters
            if not comment_id or not user_id:
                raise ValueError("Comment ID and User ID are required")
            
            # Convert user_id to ObjectId if it's a string
            if isinstance(user_id, str) and ObjectId.is_valid(user_id):
                user_id = ObjectId(user_id)
            
            # Validate vote type
            if vote_type not in ['up', 'down']:
                raise ValueError("Invalid vote type")
            
            # Find the comment
            comment = None
            for i, c in enumerate(self.comments):
                if c.get('id') == comment_id:
                    comment = c
                    comment_index = i
                    break
            
            if not comment:
                raise ValueError("Comment not found")
            
            # Initialize votes if not present
            if 'votes' not in comment:
                comment['votes'] = {'up': [], 'down': []}
            
            # Check current vote status
            has_upvoted = any(str(voter) == str(user_id) for voter in comment['votes'].get('up', []))
            has_downvoted = any(str(voter) == str(user_id) for voter in comment['votes'].get('down', []))
            
            # Initialize update
            update = {}
            
            # Apply vote logic
            if vote_type == 'up':
                if has_upvoted:
                    # Already upvoted, remove upvote
                    update = {
                        '$pull': {f'comments.{comment_index}.votes.up': user_id},
                        '$inc': {f'comments.{comment_index}.score': -1}
                    }
                    # Update local state
                    comment['votes']['up'] = [v for v in comment['votes']['up'] if str(v) != str(user_id)]
                    comment['score'] = comment.get('score', 0) - 1
                    has_upvoted = False
                else:
                    # New upvote
                    if has_downvoted:
                        # Remove downvote first if exists
                        update = {
                            '$pull': {f'comments.{comment_index}.votes.down': user_id},
                            '$push': {f'comments.{comment_index}.votes.up': user_id},
                            '$inc': {f'comments.{comment_index}.score': 2}
                        }
                        # Update local state
                        comment['votes']['down'] = [v for v in comment['votes']['down'] if str(v) != str(user_id)]
                        comment['votes']['up'].append(user_id)
                        comment['score'] = comment.get('score', 0) + 2
                        has_upvoted = True
                        has_downvoted = False
                    else:
                        # Simple upvote
                        update = {
                            '$push': {f'comments.{comment_index}.votes.up': user_id},
                            '$inc': {f'comments.{comment_index}.score': 1}
                        }
                        # Update local state
                        comment['votes']['up'].append(user_id)
                        comment['score'] = comment.get('score', 0) + 1
                        has_upvoted = True
            else: # vote_type == 'down'
                if has_downvoted:
                    # Already downvoted, remove downvote
                    update = {
                        '$pull': {f'comments.{comment_index}.votes.down': user_id},
                        '$inc': {f'comments.{comment_index}.score': 1}
                    }
                    # Update local state
                    comment['votes']['down'] = [v for v in comment['votes']['down'] if str(v) != str(user_id)]
                    comment['score'] = comment.get('score', 0) + 1
                    has_downvoted = False
                else:
                    # New downvote
                    if has_upvoted:
                        # Remove upvote first if exists
                        update = {
                            '$pull': {f'comments.{comment_index}.votes.up': user_id},
                            '$push': {f'comments.{comment_index}.votes.down': user_id},
                            '$inc': {f'comments.{comment_index}.score': -2}
                        }
                        # Update local state
                        comment['votes']['up'] = [v for v in comment['votes']['up'] if str(v) != str(user_id)]
                        comment['votes']['down'].append(user_id)
                        comment['score'] = comment.get('score', 0) - 2
                        has_downvoted = True
                        has_upvoted = False
                    else:
                        # Simple downvote
                        update = {
                            '$push': {f'comments.{comment_index}.votes.down': user_id},
                            '$inc': {f'comments.{comment_index}.score': -1}
                        }
                        # Update local state
                        comment['votes']['down'].append(user_id)
                        comment['score'] = comment.get('score', 0) - 1
                        has_downvoted = True
            
            # Apply update
            if update:
                result = db.discussions.update_one(
                    {'_id': ObjectId(self.id)},
                    update
                )
                
                # Update timestamp
                db.discussions.update_one(
                    {'_id': ObjectId(self.id)},
                    {'$set': {'updated_at': datetime.utcnow()}}
                )
                
                # Update cache
                discussion_cache.put(self.id, self)
            
            # Return updated score, votes count and status
            return {
                'success': True,
                'score': comment.get('score', 0),
                'upvotes': len(comment['votes']['up']),
                'downvotes': len(comment['votes']['down']),
                'has_upvoted': has_upvoted,
                'has_downvoted': has_downvoted
            }
        
        except Exception as e:
            current_app.logger.error(f"Error in vote_comment: {str(e)}")
            return {'error': str(e), 'success': False}

    @classmethod
    def create_indexes(cls, db):
        """Create necessary indexes for performance"""
        db.discussions.create_index('slug', unique=True)
        db.discussions.create_index('user_id')
        db.discussions.create_index('created_at')
        db.discussions.create_index('subject')
        db.discussions.create_index('grade_level')
        db.discussions.create_index('visibility')
        db.discussions.create_index([('title', 'text'), ('content', 'text')])
        
        # Compound indexes for common queries
        db.discussions.create_index([('status', 1), ('score', -1)])
        db.discussions.create_index([('status', 1), ('created_at', -1)])

    def moderate_content(self, db, moderator_id, status, notes=None):
        db.discussions.update_one(
            {'_id': ObjectId(self.id)},
            {
                '$set': {
                    'status': status,
                    'moderated_at': datetime.utcnow(),
                    'moderator_id': moderator_id,
                    'moderator_notes': notes,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        self.status = status
        self.moderated_at = datetime.utcnow()
        self.moderator_id = moderator_id
        self.moderator_notes = notes

    @staticmethod
    def check_content_guidelines(content):
        app = create_app()
        genai.configure(api_key=app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Analyze this discussion content and check if it follows community guidelines:
        1. Is it respectful and professional?
        2. Does it contain inappropriate language?
        3. Is it relevant to education?
        4. Does it promote harmful content?
        
        Content: {content}
        
        Respond with either 'APPROVED' or 'FLAGGED' followed by a brief reason.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()

    @staticmethod
    def rephrase_content(content):
        app = create_app()
        genai.configure(api_key=app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Rephrase this content to be more polite and professional while maintaining its meaning:
        
        Original: {content}
        
        Provide only the rephrased version without any additional text.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
