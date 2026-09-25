from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
import google.generativeai as genai
from app import create_app
from app.models.user import User
import os

class Resource:
    def __init__(self, resource_data):
        """Initialize a resource with better debugging"""
        self.id = resource_data.get('_id')
        self.title = resource_data.get('title')
        self.description = resource_data.get('description')
        self.file_path = resource_data.get('file_path')
        self.file_type = resource_data.get('file_type')
        self.google_drive_link = resource_data.get('google_drive_link')
        self.drive_link = resource_data.get('drive_link')  # For compatibility with both field names
        self.user_id = resource_data.get('user_id')
        self.views = resource_data.get('views', 0)
        self.downloads = resource_data.get('downloads', 0)
        self.created_at = resource_data.get('created_at')
        self.updated_at = resource_data.get('updated_at')
        self.country = resource_data.get('country')
        self.board = resource_data.get('board')
        self.grade_level = resource_data.get('grade_level')
        self.tags = resource_data.get('tags', [])
        self.comments = resource_data.get('comments', [])
        
        # Load comment author information
        self._load_comment_authors()
        
        self.thumbnail_url = resource_data.get('thumbnail_url')
        
        # Set the best available Google Drive link
        if not self.google_drive_link and self.drive_link:
            self.google_drive_link = self.drive_link
        
        # Ensure file_type is set if file_path is present
        if self.file_path and not self.file_type:
            file_ext = os.path.splitext(self.file_path)[1].lower()
            if file_ext:
                self.file_type = file_ext[1:]  # Remove the dot
        
        # Cache for author data
        self._author = None
        
        print(f"\n----- Resource Initialization -----")
        print(f"Original _id: {self.id}, type: {type(self.id)}")
        print(f"Converted id: {self.id}, type: {type(self.id)}")
        print(f"------------------------------------\n")
        
        self.subjects = resource_data.get('subjects', [])
        self.chapters = resource_data.get('chapters', [])
        self.is_full_book = resource_data.get('is_full_book', False)
        self.metadata = resource_data.get('metadata', {})

    def _load_comment_authors(self):
        """Load author information for all comments"""
        if not self.comments:
            return
            
        from app.database import get_db
        from bson.objectid import ObjectId
        
        db = get_db()
        
        # Process each comment to add author information
        for comment in self.comments:
            # Initialize author property if it doesn't exist
            if not hasattr(comment, 'author'):
                comment['author'] = None
                
            # Try to find the author
            if 'user_id' in comment:
                try:
                    user_id = comment['user_id']
                    if not isinstance(user_id, ObjectId):
                        try:
                            user_obj_id = ObjectId(user_id)
                        except:
                            user_obj_id = None
                    else:
                        user_obj_id = user_id
                        
                    if user_obj_id:
                        user_data = db.users.find_one({'_id': user_obj_id})
                        if user_data:
                            from app.models.user import User
                            comment['author'] = User(user_data)
                except Exception as e:
                    print(f"Error loading comment author: {str(e)}")
            
            # Create placeholder if no author found
            if not comment.get('author'):
                comment['author'] = type('obj', (object,), {
                    'username': 'Unknown',
                    'id': None,
                    'email': None
                })

    @property
    def author(self):
        """Get the author of this resource"""
        if self._author is None and self.user_id:
            # Try to convert user_id to ObjectId if it's not already
            from app.database import get_db
            from bson import ObjectId
            
            try:
                user_id = self.user_id
                if not isinstance(user_id, ObjectId):
                    user_id = ObjectId(user_id)
                
                db = get_db()
                user_data = db.users.find_one({'_id': user_id})
                if user_data:
                    from app.models.user import User
                    self._author = User(user_data)
                    print(f"Found author: {self._author.username}")
                else:
                    # Create placeholder for missing user
                    self._author = type('obj', (object,), {
                        'username': 'Unknown User',
                        'id': None,
                        'email': None
                    })
            except Exception as e:
                print(f"Error finding author: {str(e)}")
                # Create placeholder for error case
                self._author = type('obj', (object,), {
                    'username': 'Unknown User',
                    'id': None,
                    'email': None
                })
        elif self._author is None:
            # Create placeholder if no user_id
            self._author = type('obj', (object,), {
                'username': 'Unknown User',
                'id': None,
                'email': None
            })
        return self._author

    @staticmethod
    def create_resource(db, title, description, user_id, resource_type, google_drive_link,
                       country, board, grade_level, thumbnail=None, tags=None):
        """
        Create a new resource with Google Drive link
        
        Args:
            db: Database connection
            title: Resource title
            description: Resource description
            user_id: ID of the user uploading the resource
            resource_type: Type of resource (pdf, doc, etc.)
            google_drive_link: Google Drive link to the resource
            country: Country code
            board: Education board
            grade_level: Grade level
            thumbnail: Optional thumbnail image
            tags: List of tags
        """
        # Save thumbnail if provided
        thumbnail_path = None
        if thumbnail:
            from werkzeug.utils import secure_filename
            import os
            from app import create_app
            
            app = create_app()
            filename = secure_filename(thumbnail.filename)
            thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', filename)
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            thumbnail.save(thumbnail_path)
        
        # Prepare subjects and chapters
        # For simplicity, using the resource_type as the subject
        subjects = [resource_type]
        
        resource_data = {
            'user_id': user_id,
            'title': title,
            'description': description,
            'file_type': resource_type,
            'file_path': None,  # No local file path needed
            'google_drive_link': google_drive_link,
            'thumbnail_path': thumbnail_path,
            'country': country,
            'board': board,
            'grade_level': grade_level,
            'subjects': subjects,
            'chapters': [],
            'tags': tags or [],
            'is_full_book': False,
            'views': 0,
            'downloads': 0,
            'comments': [],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'metadata': {}
        }
        
        result = db.resources.insert_one(resource_data)
        resource_data['_id'] = result.inserted_id
        return Resource(resource_data)

    @staticmethod
    def analyze_content(file_path, file_type):
        app = create_app()
        genai.configure(api_key=app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Read file content based on type
        if file_type == 'pdf':
            # Implement PDF reading logic
            content = "PDF content placeholder"
        elif file_type == 'image':
            # Implement image analysis logic
            content = "Image content placeholder"
        else:  # text
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

        # Analyze content with Gemini AI
        prompt = f"""
        Analyze this educational content and extract:
        1. Main subjects
        2. Key chapters/topics
        3. Educational level
        4. Board/curriculum (if mentioned)
        5. Country (if mentioned)
        
        Content: {content[:5000]}  # Limit content length for API
        """
        
        response = model.generate_content(prompt)
        return response.text

    def increment_views(self, db=None):
        """Increment the view count for this resource"""
        from app.database import get_db
        database = db if db is not None else get_db()
        
        # Update the resource views
        database.resources.update_one(
            {'_id': self.id},
            {'$inc': {'views': 1}}
        )
        self.views += 1
        
        # Also update the user's total views for monetization tracking
        if self.user_id:
            database.users.update_one(
                {'_id': self.user_id},
                {'$inc': {'total_views': 1}}
            )
            
        return self.views

    def increment_downloads(self, db=None):
        """Increment the download count for this resource"""
        from app.database import get_db
        database = db if db is not None else get_db()
        
        # Update the resource download count
        database.resources.update_one(
            {'_id': self.id},
            {'$inc': {'downloads': 1}}
        )
        self.downloads += 1
        return self.downloads

    def calculate_earnings(self):
        if self.monetization_status == 'approved':
            return (self.views // 1000) * 0.20  # $0.20 per 1000 views
        return 0.0

    def add_comment(self, db, user_id, content):
        """
        Add a comment to the resource
        
        Args:
            db: Database connection
            user_id: The ID of the user adding the comment
            content: The comment content
            
        Returns:
            The comment ID
        """
        comment = {
            'id': str(ObjectId()),
            'user_id': user_id,
            'content': content,
            'created_at': datetime.utcnow(),
            'likes': 0,
            'liked_by': []
        }
        
        db.resources.update_one(
            {'_id': ObjectId(self.id)},
            {'$push': {'comments': comment}}
        )
        
        return comment['id']

    def like_comment(self, db, comment_id, user_id):
        """
        Like a comment on the resource
        
        Args:
            db: Database connection
            comment_id: The ID of the comment to like
            user_id: The ID of the user liking the comment
            
        Returns:
            The new like count or None if comment not found
        """
        # Find the comment in the comments array
        resource_data = db.resources.find_one(
            {'_id': ObjectId(self.id), 'comments.id': comment_id},
            {'comments.$': 1}
        )
        
        if not resource_data or not resource_data.get('comments'):
            return None
            
        comment = resource_data['comments'][0]
        
        # Check if user already liked the comment
        liked_by = comment.get('liked_by', [])
        if user_id in liked_by:
            # User already liked the comment, do nothing
            return comment.get('likes', 0)
            
        # Add user to liked_by array and increment likes
        result = db.resources.update_one(
            {'_id': ObjectId(self.id), 'comments.id': comment_id},
            {
                '$addToSet': {'comments.$.liked_by': user_id},
                '$inc': {'comments.$.likes': 1}
            }
        )
        
        if result.modified_count:
            return comment.get('likes', 0) + 1
        return None

    @staticmethod
    def get_by_id(db, resource_id):
        """
        Get a resource by ID with proper ObjectId conversion and better error handling
        """
        print(f"\n==== Resource.get_by_id called with resource_id: {resource_id}, type: {type(resource_id)}")
        try:
            # Convert to ObjectId if it's not already one
            if not isinstance(resource_id, ObjectId):
                try:
                    obj_id = ObjectId(resource_id)
                    print(f"Converted to ObjectId: {obj_id}")
                except InvalidId as e:
                    print(f"Invalid ObjectId format: {resource_id}, error: {str(e)}")
                    return None
            else:
                obj_id = resource_id
                print(f"Already an ObjectId: {obj_id}")
            
            # Query the database
            resource_data = db.resources.find_one({'_id': obj_id})
            print(f"Database query result: {resource_data is not None}")
            
            if resource_data:
                resource = Resource(resource_data)
                print(f"Resource found: {resource.title}")
                return resource
            else:
                print(f"Resource not found with ID: {resource_id}")
                return None
                
        except Exception as e:
            print(f"Error in Resource.get_by_id: {str(e)}")
            return None 

    @property
    def unique_viewers_count(self):
        """Returns the count of unique viewers based on IP addresses"""
        from app import create_app
        app = create_app()
        
        return app.db.resource_views.count_documents({
            'resource_id': ObjectId(self.id)
        })
    
    @property
    def returning_viewers_count(self):
        """Returns the count of returning viewers (viewed more than once)"""
        from app import create_app
        app = create_app()
        
        return app.db.resource_views.count_documents({
            'resource_id': ObjectId(self.id),
            'return_count': {'$gt': 0}
        })

    @staticmethod
    def get_resources(db, page=1, per_page=10, sort_by='recent', search_query=None, 
                     subject=None, grade_level=None, tags=None, country=None, board=None):
        """Get resources with pagination, sorting, and filtering"""
        try:
            # Validate and enforce limits on pagination
            page = max(1, page)  # Ensure page is at least 1
            per_page = max(1, min(per_page, 50))  # Ensure per_page is between 1 and 50
            
            # Build pipeline for MongoDB aggregation
            pipeline = [
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
            
            # Add match stage for filters
            match_conditions = {}
            
            # Add search filter if provided
            if search_query:
                # Use text search if indexes are available
                if '$text' in db.resources.index_information():
                    match_conditions['$text'] = {'$search': search_query}
                else:
                    # Fallback to regex if no text index
                    match_conditions['$or'] = [
                        {'title': {'$regex': search_query, '$options': 'i'}},
                        {'description': {'$regex': search_query, '$options': 'i'}}
                    ]
            
            # Add subject filter if provided
            if subject:
                match_conditions['subjects'] = subject
            
            # Add grade level filter if provided
            if grade_level:
                match_conditions['grade_level'] = grade_level
                
            # Add country filter if provided
            if country:
                match_conditions['country'] = country
                
            # Add board filter if provided
            if board:
                match_conditions['board'] = board
                
            # Add tag filter if provided
            if tags:
                if isinstance(tags, str):
                    match_conditions['tags'] = tags
                elif isinstance(tags, list):
                    match_conditions['tags'] = {'$in': tags}
            
            # Add match stage if we have conditions
            if match_conditions:
                pipeline.append({'$match': match_conditions})
            
            # Add sort stage based on user's selection
            if sort_by == 'recent':
                pipeline.append({'$sort': {'created_at': -1}})
            elif sort_by == 'oldest':
                pipeline.append({'$sort': {'created_at': 1}})
            elif sort_by == 'most_views':
                pipeline.append({'$sort': {'views': -1}})
            elif sort_by == 'most_downloads':
                pipeline.append({'$sort': {'downloads': -1}})
            elif sort_by == 'title_asc':
                pipeline.append({'$sort': {'title': 1}})
            elif sort_by == 'title_desc':
                pipeline.append({'$sort': {'title': -1}})
            
            # Create a copy of the pipeline for counting total resources
            count_pipeline = pipeline.copy()
            count_pipeline.append({'$count': 'total'})
            
            # Get total count
            total_count_result = list(db.resources.aggregate(count_pipeline))
            total_count = total_count_result[0]['total'] if total_count_result else 0
            
            # Calculate total pages
            pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            
            # Add pagination to the main pipeline
            pipeline.append({'$skip': (page - 1) * per_page})
            pipeline.append({'$limit': per_page})
            
            # Get paginated resources with author information using aggregation
            resources_data = list(db.resources.aggregate(pipeline))
            
            # Convert results to Resource objects
            resources = []
            for data in resources_data:
                resource = Resource(data)
                if data.get('author'):
                    from app.models.user import User
                    resource._author = User(data['author'])
                resources.append(resource)
            
            # Return result
            return {
                'resources': resources,
                'total': total_count,
                'pages': pages,
                'current_page': page,
                'per_page': per_page,
                'has_prev': page > 1,
                'has_next': page < pages
            }
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error in get_resources: {str(e)}")
            raise