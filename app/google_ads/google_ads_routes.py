# app\google_ads\google_ads_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models import GoogleAdsAccount, GoogleAdsCampaign
from app.database import db
from app.google_ads.google_ads_handler import GoogleAdsHandler


bp = Blueprint('google_ads', __name__)

@bp.route('/')
@login_required
def index():
    accounts = GoogleAdsAccount.query.filter_by(agency_id=current_user.agency_id).all()
    return render_template('google_ads/index.html', accounts=accounts)

@bp.route('/sync')
@login_required
def sync():
    handler = GoogleAdsHandler()
    try:
        handler.sync_campaigns(current_user.agency_id)
        flash('Google Ads campaigns synced successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error syncing Google Ads campaigns: {str(e)}")
        flash('Error syncing Google Ads campaigns. Please try again later.', 'error')
    return redirect(url_for('google_ads.index'))



@bp.route('/campaigns/<int:account_id>')
@login_required
def campaigns(account_id):
    account = GoogleAdsAccount.query.get_or_404(account_id)
    if account.agency_id != current_user.agency_id:
        flash('You do not have permission to view these campaigns.', 'error')
        return redirect(url_for('google_ads.index'))
    
    campaigns = GoogleAdsCampaign.query.filter_by(account_id=account_id).order_by(GoogleAdsCampaign.name).all()
    return render_template('google_ads/campaigns.html', account=account, campaigns=campaigns)

@bp.route('/performance/<int:account_id>')
@login_required
def performance(account_id):
    account = GoogleAdsAccount.query.get_or_404(account_id)
    if account.agency_id != current_user.agency_id:
        flash('You do not have permission to view this account performance.', 'error')
        return redirect(url_for('google_ads.index'))
    
    handler = GoogleAdsHandler()
    performance_data = handler.get_account_performance(account_id)
    
    if performance_data is None:
        flash('Error fetching account performance. Please try again later.', 'error')
        return redirect(url_for('google_ads.index'))
    
    return render_template('google_ads/performance.html', account=account, performance=performance_data)

@bp.route('/link_account', methods=['GET', 'POST'])
@login_required
def link_account():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        refresh_token = request.form.get('refresh_token')
        
        if not customer_id or not refresh_token:
            flash('Please provide both Customer ID and Refresh Token.', 'error')
            return redirect(url_for('google_ads.link_account'))
        
        handler = GoogleAdsHandler()
        success = handler.link_google_ads_account(current_user.agency_id, customer_id, refresh_token)
        
        if success:
            flash('Google Ads account linked successfully.', 'success')
            return redirect(url_for('google_ads.index'))
        else:
            flash('Error linking Google Ads account. Please check your credentials and try again.', 'error')
    
    return render_template('google_ads/link_account.html')

@bp.route('/unlink_account/<int:account_id>', methods=['POST'])
@login_required
def unlink_account(account_id):
    account = GoogleAdsAccount.query.get_or_404(account_id)
    if account.agency_id != current_user.agency_id:
        flash('You do not have permission to unlink this account.', 'error')
        return redirect(url_for('google_ads.index'))
    
    try:
        db.session.delete(account)
        db.session.commit()
        flash('Google Ads account unlinked successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error unlinking Google Ads account: {str(e)}")
        db.session.rollback()
        flash('Error unlinking Google Ads account. Please try again later.', 'error')
    
    return redirect(url_for('google_ads.index'))

@bp.route('/export_campaigns/<int:account_id>')
@login_required
def export_campaigns(account_id):
    account = GoogleAdsAccount.query.get_or_404(account_id)
    if account.agency_id != current_user.agency_id:
        flash('You do not have permission to export these campaigns.', 'error')
        return redirect(url_for('google_ads.index'))
    
    campaigns = GoogleAdsCampaign.query.filter_by(account_id=account_id).order_by(GoogleAdsCampaign.name).all()
    
    csv_data = "Campaign ID,Name,Status,Budget,Impressions,Clicks,Cost\n"
    for campaign in campaigns:
        csv_data += f"{campaign.campaign_id},{campaign.name},{campaign.status},{campaign.budget},{campaign.impressions},{campaign.clicks},{campaign.cost}\n"
    
    response = current_app.response_class(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=google_ads_campaigns_{account_id}.csv'}
    )
    return response

@bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500
