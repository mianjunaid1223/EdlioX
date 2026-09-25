from flask import Blueprint, request, jsonify, render_template, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
import stripe
from app.models.user import User
from app.models.resource import Resource
from datetime import datetime, timedelta
from bson.objectid import ObjectId

bp = Blueprint('monetization', __name__)

@bp.route('/monetization/dashboard')
@login_required
def monetization_dashboard():
    # Get user's resources
    resources = []
    recent_resources = []
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    try:
        for resource_data in current_app.db.resources.find({'user_id': current_user.id}):
            resource = Resource(resource_data)
            resources.append(resource)
            
            # Check if resource was published in the last 30 days
            if hasattr(resource, 'created_at') and resource.created_at >= thirty_days_ago:
                recent_resources.append(resource)
    except Exception as e:
        current_app.logger.error(f"Error fetching resources: {str(e)}")
        flash("Error loading resources. Please try again later.", "danger")
    
    # Calculate total earnings
    total_earnings = getattr(current_user, 'total_earnings', 0)
    pending_earnings = getattr(current_user, 'pending_earnings', 0)
    
    # Get eligibility information
    resource_count = len(resources)
    recent_resource_count = len(recent_resources)
    total_views = sum(resource.views or 0 for resource in resources)
    
    return render_template('monetization/dashboard.html',
                         resources=resources,
                         total_earnings=total_earnings,
                         pending_earnings=pending_earnings,
                         resource_count=resource_count,
                         total_views=total_views,
                         recent_resource_count=recent_resource_count)

@bp.route('/monetization/request-payout', methods=['POST'])
@login_required
def request_payout():
    # Check if user meets minimum payout threshold
    if current_user.pending_earnings < current_app.config['MINIMUM_PAYOUT_THRESHOLD']:
        return jsonify({
            'error': f'Minimum payout threshold is ${current_app.config["MINIMUM_PAYOUT_THRESHOLD"]}'
        }), 400
    
    # Create Stripe payout
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    try:
        # Create a Stripe account for the user if they don't have one
        if not current_user.stripe_account_id:
            account = stripe.Account.create(
                type='express',
                country='US',
                email=current_user.email,
                capabilities={
                    'transfers': {'requested': True},
                }
            )
            
            # Update user with Stripe account ID
            current_user.update_profile(
                db=current_app.db,
                stripe_account_id=account.id
            )
        
        # Create a payout
        payout = stripe.Payout.create(
            amount=int(current_user.pending_earnings * 100),  # Convert to cents
            currency='usd',
            destination=current_user.stripe_account_id
        )
        
        # Update user's earnings
        current_user.request_payout(current_app.db)
        
        return jsonify({
            'message': 'Payout request submitted successfully',
            'payout_id': payout.id
        })
    
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/monetization/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event.type == 'payout.paid':
        payout = event.data.object
        
        # Find user by Stripe account ID
        user_data = current_app.db.users.find_one({'stripe_account_id': payout.destination})
        if user_data:
            user = User(user_data)
            # Update user's payout status
            user.update_profile(
                db=current_app.db,
                last_payout_id=payout.id,
                last_payout_amount=payout.amount / 100,  # Convert from cents
                last_payout_date=payout.created
            )
    
    return jsonify({'status': 'success'})

@bp.route('/monetization/earnings-history')
@login_required
def earnings_history():
    # Get user's payout history
    payouts = []
    if current_user.stripe_account_id:
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        try:
            stripe_payouts = stripe.Payout.list(
                destination=current_user.stripe_account_id,
                limit=100
            )
            for payout in stripe_payouts.data:
                payouts.append({
                    'id': payout.id,
                    'amount': payout.amount / 100,  # Convert from cents
                    'status': payout.status,
                    'created': payout.created
                })
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Failed to fetch Stripe payouts: {str(e)}")
    
    return render_template('monetization/earnings_history.html', payouts=payouts)

@bp.route('/monetization/resource/<resource_id>/stats')
@login_required
def resource_stats(resource_id):
    try:
        # Handle both string and ObjectId formats
        try:
            if not isinstance(resource_id, ObjectId):
                resource_id = ObjectId(resource_id)
        except:
            current_app.logger.error(f"Invalid resource ID format: {resource_id}")
            flash('Invalid resource ID format', 'danger')
            return redirect(url_for('monetization.monetization_dashboard'))
        
        resource_data = current_app.db.resources.find_one({'_id': resource_id})
        if not resource_data:
            flash('Resource not found. It may have been deleted or is not available.', 'danger')
            return redirect(url_for('monetization.monetization_dashboard'))
        
        resource = Resource(resource_data)
        
        # Check if user owns the resource
        if resource.user_id != current_user.id:
            flash('You do not have permission to view stats for this resource.', 'danger')
            return redirect(url_for('monetization.monetization_dashboard'))
        
        # Calculate earnings
        earnings = 0
        if hasattr(resource, 'monetization_status') and resource.monetization_status == 'approved':
            earnings = resource.calculate_earnings()
        
        stats = {
            'views': resource.views,
            'downloads': resource.downloads,
            'earnings': earnings,
            'monetization_status': getattr(resource, 'monetization_status', None),
            'monetization_applied_at': getattr(resource, 'monetization_applied_at', None),
            'monetization_approved_at': getattr(resource, 'monetization_approved_at', None)
        }
        
        return render_template('monetization/resource_stats.html', stats=stats, resource=resource)
    except Exception as e:
        current_app.logger.error(f"Error in resource_stats: {str(e)}")
        flash('An error occurred while fetching resource statistics', 'danger')
        return redirect(url_for('monetization.monetization_dashboard'))

@bp.route('/monetization/connect-stripe', methods=['GET', 'POST'])
@login_required
def connect_stripe():
    if request.method == 'POST':
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        try:
            # Create a Stripe account
            account = stripe.Account.create(
                type='express',
                country='US',
                email=current_user.email,
                capabilities={
                    'transfers': {'requested': True},
                }
            )
            
            # Create an account link
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=url_for('monetization.connect_stripe', _external=True),
                return_url=url_for('monetization.monetization_dashboard', _external=True),
                type='account_onboarding'
            )
            
            # Update user with Stripe account ID
            current_user.update_profile(
                db=current_app.db,
                stripe_account_id=account.id
            )
            
            return redirect(account_link.url)
        
        except stripe.error.StripeError as e:
            return jsonify({'error': str(e)}), 400
    
    return render_template('monetization/connect_stripe.html')

@bp.route('/monetization/apply', methods=['POST'])
@login_required
def apply_monetization():
    """
    Apply for account monetization if eligible
    """
    # Check if user already has a pending or approved application
    if current_user.monetization_status in ['pending', 'approved']:
        flash('You already have a pending or approved monetization application.', 'warning')
        return redirect(url_for('monetization.monetization_dashboard'))
    
    # Get bank details from form
    bank_details = {
        'account_holder_name': request.form.get('account_holder_name'),
        'account_number': request.form.get('account_number'),
        'bank_name': request.form.get('bank_name'),
        'routing_number': request.form.get('routing_number'),
        'account_type': request.form.get('account_type')
    }
    
    # Validate bank details
    if not all(bank_details.values()):
        flash('Please provide all required bank details.', 'danger')
        return redirect(url_for('monetization.monetization_dashboard'))
    
    # Get user's resources
    resources = []
    recent_resources = []
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    try:
        for resource_data in current_app.db.resources.find({'user_id': current_user.id}):
            resource = Resource(resource_data)
            resources.append(resource)
            
            # Check if resource was published in the last 30 days
            if hasattr(resource, 'created_at') and resource.created_at >= thirty_days_ago:
                recent_resources.append(resource)
    except Exception as e:
        current_app.logger.error(f"Error fetching resources: {str(e)}")
        flash("Error loading resources. Please try again later.", "danger")
        return redirect(url_for('monetization.monetization_dashboard'))
    
    # Calculate eligibility metrics
    total_views = sum(resource.views or 0 for resource in resources)
    total_resources = len(resources)
    recent_resource_count = len(recent_resources)
    
    # Check eligibility requirements
    if total_views >= 50 and total_resources >= 3 and recent_resource_count >= 3:
        try:
            # Create monetization request
            monetization_request = {
                'user_id': current_user.id,
                'status': 'pending',
                'bank_details': bank_details,
                'eligibility_metrics': {
                    'total_views': total_views,
                    'total_resources': total_resources,
                    'recent_resources': recent_resource_count
                },
                'applied_at': datetime.utcnow()
            }
            
            # Insert request into database
            current_app.db.monetization_requests.insert_one(monetization_request)
            
            # Update user's monetization status
            current_app.db.users.update_one(
                {'_id': current_user.id},
                {'$set': {'monetization_status': 'pending'}}
            )
            
            # Refresh current_user data
            user_data = current_app.db.users.find_one({'_id': current_user.id})
            if user_data:
                current_user.monetization_status = user_data.get('monetization_status', 'not_applied')
            
            flash('Your monetization application has been submitted successfully!', 'success')
        except Exception as e:
            current_app.logger.error(f"Error creating monetization request: {str(e)}")
            flash("Error submitting application. Please try again later.", "danger")
    else:
        # Generate detailed error message
        requirements_missing = []
        if total_views < 50:
            requirements_missing.append(f"10,000+ total views (you have {total_views})")
        if total_resources < 3:
            requirements_missing.append(f"5+ total resources (you have {total_resources})")
        if recent_resource_count < 3:
            requirements_missing.append(f"5+ resources published in the last 30 days (you have {recent_resource_count})")
        
        flash(f"You don't meet all monetization requirements. Missing: {', '.join(requirements_missing)}", 'danger')
    
    return redirect(url_for('monetization.monetization_dashboard')) 