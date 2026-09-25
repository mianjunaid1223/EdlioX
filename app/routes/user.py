from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models.user import User
from datetime import datetime, timedelta
from bson import ObjectId

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/earnings')
@login_required
def earnings_dashboard():
    """
    Show user's earnings dashboard with monetization status and stats
    """
    app = current_app
    
    # Get user's payouts
    payouts = []
    if hasattr(app, 'db') and hasattr(app.db, 'payouts'):
        for payout_data in app.db.payouts.find({'user_id': current_user.id}).sort('date', -1):
            payouts.append(payout_data)
    
    return render_template('user/earnings.html', payouts=payouts)

@bp.route('/request-payout', methods=['POST'])
@login_required
def request_payout():
    """
    Request payout of pending earnings if eligible
    """
    app = current_app
    
    if current_user.request_payout(app.db):
        flash('Your payout request has been submitted successfully!', 'success')
    else:
        flash('You need at least $50 in pending earnings to request a payout.', 'warning')
    
    return redirect(url_for('user.earnings_dashboard')) 