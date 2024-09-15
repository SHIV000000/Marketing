# app/data_analysis.py

from flask import Blueprint, render_template, jsonify, request
from app.models import Agency, LexAcc, Customer, BankUser, BankTransaction, GoogleAdsAccount, GoogleAdsCampaign, MailUser, Email
from app.database import db
from sqlalchemy import func
from datetime import datetime, timedelta
from flask_login import login_required, current_user

bp = Blueprint('analysis', __name__)

@bp.route('/')
@login_required
def index():
    agencies = Agency.query.all()
    return render_template('analysis/index.html', agencies=agencies)

@bp.route('/analyze/<int:agency_id>')
@login_required
def analyze(agency_id):
    if not current_user.is_admin and current_user.id != agency_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    results = perform_analysis(agency_id)
    return jsonify(results)

def perform_analysis(agency_id):
    agency = db.get_or_404(Agency, agency_id)
    results = {}

    results['lex_office'] = analyze_lex_office(agency)
    results['bank_transactions'] = analyze_bank_transactions(agency)
    results['google_ads'] = analyze_google_ads(agency)
    results['email_analysis'] = analyze_emails(agency)

    return results

def analyze_lex_office(agency):
    lex_accounts = LexAcc.query.filter_by(agency_id=agency.id).all()
    total_gross = 0
    total_net = 0
    customer_count = 0

    for lex_acc in lex_accounts:
        customers = Customer.query.filter_by(lexAccId=lex_acc.id).all()
        customer_count += len(customers)
        for customer in customers:
            total_gross += customer.totalGrossAmount
            total_net += customer.totalNetAmount

    return {
        'total_gross': total_gross,
        'total_net': total_net,
        'customer_count': customer_count,
        'average_gross_per_customer': total_gross / customer_count if customer_count > 0 else 0
    }

def analyze_bank_transactions(agency):
    bank_users = BankUser.query.filter_by(agency_id=agency.id).all()
    total_transactions = 0
    total_amount = 0
    last_month = datetime.now() - timedelta(days=30)

    for bank_user in bank_users:
        transactions = BankTransaction.query.filter(
            BankTransaction.bank_user_id == bank_user.id,
            BankTransaction.date >= last_month
        ).all()
        total_transactions += len(transactions)
        total_amount += sum(t.amount for t in transactions)

    return {
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'average_transaction_amount': total_amount / total_transactions if total_transactions > 0 else 0
    }

def analyze_google_ads(agency):
    google_ads_accounts = GoogleAdsAccount.query.filter_by(agency_id=agency.id).all()
    total_budget = 0
    active_campaigns = 0

    for account in google_ads_accounts:
        campaigns = GoogleAdsCampaign.query.filter_by(account_id=account.id).all()
        total_budget += sum(c.budget for c in campaigns)
        active_campaigns += sum(1 for c in campaigns if c.status == 'ENABLED')

    return {
        'total_budget': total_budget,
        'active_campaigns': active_campaigns
    }

def analyze_emails(agency):
    mail_users = MailUser.query.filter_by(agency_id=agency.id).all()
    total_emails = 0
    last_week = datetime.now() - timedelta(days=7)

    for mail_user in mail_users:
        emails = Email.query.filter(
            Email.mail_user_id == mail_user.id,
            Email.date >= last_week
        ).all()
        total_emails += len(emails)

    return {
        'total_emails_last_week': total_emails
    }
