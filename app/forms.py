from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, TextAreaField, DecimalField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional, NumberRange
from app.models.user import User

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    country = SelectField('Country', validators=[DataRequired()], choices=[
        ('PK', 'Pakistan'),
        ('US', 'United States'),
        ('UK', 'United Kingdom'),
        ('CA', 'Canada'),
        ('AU', 'Australia'),
        ('IN', 'India')
    ])
    profile_image = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only (JPG, JPEG, PNG)')
    ])
    submit = SubmitField('Register')

    def validate_username(self, username):
        from flask import current_app
        user = User.get_by_username(username.data, db=current_app.db)
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        from flask import current_app
        user = User.get_by_email(email.data, db=current_app.db)
        if user is not None:
            raise ValidationError('Please use a different email address.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Reset Password')

class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')

class ProfileForm(FlaskForm):
    country = SelectField('Country', validators=[DataRequired()], choices=[
        ('PK', 'Pakistan'),
        ('US', 'United States'),
        ('UK', 'United Kingdom'),
        ('CA', 'Canada'),
        ('AU', 'Australia'),
        ('IN', 'India')
    ])
    grade_level = StringField('Grade Level', validators=[DataRequired()],
                           description="Enter grade level (eg. Grade 8, Undergraduate, etc)")
    profile_image = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only (JPG, JPEG, PNG)')
    ])
    submit = SubmitField('Update Profile')

class DiscussionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=5, max=100)])
    content = TextAreaField('Content', validators=[DataRequired(), Length(min=20)])
    subject = StringField('Subject', validators=[DataRequired()],
                       description="Enter subject (eg. Mathematics, Physics, etc)")
    grade_level = StringField('Grade Level', validators=[DataRequired()],
                           description="Enter grade level (eg. Grade 8, Undergraduate, etc)")
    visibility = SelectField('Visibility', validators=[DataRequired()], choices=[
        ('public', 'Public (Anyone can view and comment)'),
        ('private', 'Private (Only you can view and comment)')
    ])
    tags = StringField('Tags', validators=[Length(max=100)], 
                      description='Separate tags with commas. Maximum 5 tags allowed.')
    submit = SubmitField('Submit')

class ResourceForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=5, max=100)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=20, max=2000)])
    drive_link = StringField('Google Drive Link', validators=[
        DataRequired(),
        Length(min=10, max=500, message="Google Drive link must be between 10 and 500 characters"),
    ], description="Paste a Google Drive link to the file (must be accessible to anyone with the link)")
    country = SelectField('Country', validators=[Optional()], choices=[
        ('PK', 'Pakistan'),
        ('US', 'United States'),
        ('UK', 'United Kingdom'),
        ('CA', 'Canada'),
        ('AU', 'Australia'),
        ('IN', 'India')
    ])
    grade_level = StringField('Grade Level', validators=[Optional()],
                           description="Enter grade level (eg. Grade 8, Undergraduate, etc)")
    subject = StringField('Subject', validators=[Optional()],
                        description="Enter subject (eg. Mathematics, Physics, etc)")
    tags = StringField('Tags', validators=[Length(max=100)])
    resource_type = SelectField('Resource Type', validators=[DataRequired()], choices=[
        ('pdf', 'PDF Document'),
        ('doc', 'Word Document'),
        ('ppt', 'PowerPoint Presentation'),
        ('xls', 'Excel Spreadsheet'),
        ('zip', 'Zip Archive'),
        ('other', 'Other')
    ])
    submit = SubmitField('Upload Resource')

class CommentForm(FlaskForm):
    """Form for adding comments to resources and discussions"""
    content = TextAreaField('Comment', validators=[
        DataRequired(), 
        Length(min=3, max=1000, message="Comment must be between 3 and 1000 characters")
    ])
    submit = SubmitField('Post Comment')