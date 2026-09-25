from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
from bson import ObjectId

class User(UserMixin):
    def __init__(self, user_data):
        self._id = user_data.get('_id')
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.password_hash = user_data.get('password_hash')
        self.country = user_data.get('country')
        self.grade_level = user_data.get('grade_level')
        self.reset_token = user_data.get('reset_token')
        self.reset_token_expires = user_data.get('reset_token_expires')
        self.created_at = user_data.get('created_at', datetime.utcnow())
        self.last_login = user_data.get('last_login')
        self._is_active = user_data.get('is_active', True)
        self.is_admin = user_data.get('is_admin', False)
        self.resources = user_data.get('resources', [])
        self.discussions = user_data.get('discussions', [])
        self.total_views = user_data.get('total_views', 0)
        self.total_downloads = user_data.get('total_downloads', 0)
        self.profile_image = user_data.get('profile_image')
        
        # Monetization fields
        self.monetization_eligible = user_data.get('monetization_eligible', False)
        self.monetization_status = user_data.get('monetization_status', 'not_eligible')  # not_eligible, pending, approved, rejected
        self.monetization_applied_at = user_data.get('monetization_applied_at')
        self.monetization_approved_at = user_data.get('monetization_approved_at')
        self.pending_earnings = user_data.get('pending_earnings', 0.0)
        self.total_earnings = user_data.get('total_earnings', 0.0)
        self.latest_payout = user_data.get('latest_payout', None)

    def get_id(self):
        return str(self._id)

    @property
    def id(self):
        return str(self._id)

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    @property
    def avatar_url(self):
        """Get avatar URL using utils function or return None"""
        if not hasattr(self, '_avatar_url'):
            if self.profile_image:
                from app.auth.utils import get_profile_image_url
                self._avatar_url = get_profile_image_url(self.id, self.profile_image)
            else:
                self._avatar_url = None
        return self._avatar_url

    @staticmethod
    def create_user(db, username, email, password, country, profile_image=None):
        # First check if username or email already exists
        if db.users.find_one({'$or': [{'username': username.lower()}, {'email': email.lower()}]}):
            return None
            
        user_data = {
            'username': username.lower(),
            'email': email.lower(),
            'password_hash': generate_password_hash(password),
            'country': country,
            'created_at': datetime.utcnow(),
            'is_active': True,
            'is_admin': False,
            'resources': [],
            'discussions': [],
            'total_views': 0,
            'total_downloads': 0
        }
        
        # Add profile image if provided
        if profile_image:
            user_data['profile_image'] = profile_image
            
        result = db.users.insert_one(user_data)
        user_data['_id'] = result.inserted_id
        return User(user_data)

    def update_profile(self, db, **kwargs):
        update_data = {}
        for key, value in kwargs.items():
            if value is not None:
                if key == 'is_active':
                    self._is_active = value
                update_data[key] = value
        
        if update_data:
            db.users.update_one(
                {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
                {'$set': update_data}
            )
            for key, value in update_data.items():
                if key != 'is_active':  # Skip is_active as it's handled above
                    setattr(self, key, value)
            
            # Clear avatar URL cache if profile image was updated
            if 'profile_image' in update_data:
                if hasattr(self, '_avatar_url'):
                    delattr(self, '_avatar_url')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def update_last_login(self, db):
        """Update the user's last login time."""
        self.last_login = datetime.utcnow()
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {'$set': {'last_login': self.last_login}}
        )

    @staticmethod
    def get_by_username(username, db=None):
        from app.database import get_db
        # Use provided db or get from database module
        database = db if db is not None else get_db()
            
        user_data = database.users.find_one({'username': username.lower()})
        if user_data:
            return User(user_data)
        return None

    @staticmethod
    def get_by_email(email, db=None):
        from app.database import get_db
        # Use provided db or get from database module
        database = db if db is not None else get_db()
            
        user_data = database.users.find_one({'email': email.lower()})
        if user_data:
            return User(user_data)
        return None

    def add_resource(self, db, resource_id):
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {'$push': {'resources': resource_id}}
        )
        self.resources.append(resource_id)

    def add_discussion(self, db, discussion_id):
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {'$push': {'discussions': discussion_id}}
        )
        self.discussions.append(discussion_id)

    def update_earnings(self, db, amount):
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {
                '$inc': {
                    'pending_earnings': amount
                }
            }
        )
        self.pending_earnings += amount

    def request_payout(self, db):
        if self.pending_earnings >= 50.0:  # Minimum payout threshold
            db.users.update_one(
                {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
                {
                    '$inc': {
                        'total_earnings': self.pending_earnings,
                        'pending_earnings': -self.pending_earnings
                    }
                }
            )
            self.total_earnings += self.pending_earnings
            self.pending_earnings = 0
            return True
        return False

    @property
    def is_monetization_eligible(self):
        """Check if user meets all eligibility requirements for monetization"""
        from app.models.resource import Resource
        from app import create_app
        from datetime import datetime, timedelta
        
        # Check total views (10,000+)
        if self.total_views < 10000:
            return False
            
        # Check total resources (at least 5)
        app = create_app()
        total_resources = app.db.resources.count_documents({'user_id': self._id})
        if total_resources < 5:
            return False
            
        # Check resources published in the last 30 days (at least 5)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_resources = app.db.resources.count_documents({
            'user_id': self._id,
            'created_at': {'$gte': thirty_days_ago}
        })
        if recent_resources < 5:
            return False
            
        return True

    def apply_for_monetization(self, db):
        """Apply for account monetization if eligible"""
        if self.is_monetization_eligible and self.monetization_status == 'not_eligible':
            db.users.update_one(
                {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
                {
                    '$set': {
                        'monetization_status': 'pending',
                        'monetization_applied_at': datetime.utcnow()
                    }
                }
            )
            self.monetization_status = 'pending'
            self.monetization_applied_at = datetime.utcnow()
            return True
        return False

    def approve_monetization(self, db):
        """Approve monetization application"""
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {
                '$set': {
                    'monetization_status': 'approved',
                    'monetization_eligible': True,
                    'monetization_approved_at': datetime.utcnow()
                }
            }
        )
        self.monetization_status = 'approved'
        self.monetization_eligible = True
        self.monetization_approved_at = datetime.utcnow()

    def reject_monetization(self, db):
        """Reject monetization application"""
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {
                '$set': {
                    'monetization_status': 'rejected',
                    'monetization_eligible': False
                }
            }
        )
        self.monetization_status = 'rejected'
        self.monetization_eligible = False

    def calculate_earnings(self, db):
        """Calculate earnings based on views (called periodically via a cron job)"""
        if not self.monetization_eligible or self.monetization_status != 'approved':
            return 0
            
        # Simple earnings calculation: $0.002 per view
        # This would be calculated on new views since last payout
        earnings_per_view = 0.002
        
        # Get new views since last earnings update
        new_views = self.total_views - db.users.find_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id}
        ).get('last_paid_views', 0)
        
        if new_views <= 0:
            return 0
            
        earnings = new_views * earnings_per_view
        
        # Update user's earnings and record views that have been paid for
        db.users.update_one(
            {'_id': ObjectId(self._id) if isinstance(self._id, str) else self._id},
            {
                '$inc': {'pending_earnings': earnings},
                '$set': {'last_paid_views': self.total_views}
            }
        )
        
        self.pending_earnings += earnings
        return earnings