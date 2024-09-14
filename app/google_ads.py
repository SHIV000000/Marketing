# app/google_ads.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.models import GoogleAdsAccount
from app.google_ads_handler import GoogleAdsHandler
import os

bp = Blueprint('google_ads', __name__)

@bp.route('/')
def index():
    accounts = GoogleAdsAccount.query.all()
    return render_template('google_ads/index.html', accounts=accounts)

@bp.route('/sync')
def sync():
    handler = GoogleAdsHandler(os.getenv('GOOGLE_ADS_CREDENTIALS_PATH'))
    handler.sync_campaigns()
    flash('Google Ads campaigns synced successfully', 'success')
    return redirect(url_for('google_ads.index'))
