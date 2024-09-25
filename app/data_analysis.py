from flask import Blueprint, render_template, jsonify, request
from app.models import Agency, LexAcc, Customer, Manual, BankConnection, BankAccount, BankTransaction, GoogleAdsAccount, GoogleAdsCampaign, MailUser, Email
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
    results = {}
    
    # LexOffice and Sevdesk Analysis
    results['lex_sev'] = analyze_lex_sev(agency_id)
    
    # Manual Entry Analysis
    results['manual'] = analyze_manual(agency_id)
    
    # Bank Transaction Analysis
    results['bank'] = analyze_bank(agency_id)
    
    # Google Ads Analysis
    results['google_ads'] = analyze_google_ads(agency_id)
    
    # Overall Comparison
    results['comparison'] = compare_all_sources(results)
    
    return results

def analyze_lex_sev(agency_id):
    lex_accounts = LexAcc.query.filter_by(agency_id=agency_id).all()
    total_gross = sum(sum(c.totalGrossAmount for c in acc.customers) for acc in lex_accounts)
    total_net = sum(sum(c.totalNetAmount for c in acc.customers) for acc in lex_accounts)
    customer_count = sum(len(acc.customers) for acc in lex_accounts)
    
    return {
        'total_gross': total_gross,
        'total_net': total_net,
        'customer_count': customer_count,
        'average_per_customer': total_gross / customer_count if customer_count else 0
    }

def analyze_manual(agency_id):
    manual_entries = Manual.query.filter_by(agency_id=agency_id).all()
    total_amount = sum(entry.totalAmount for entry in manual_entries)
    entry_count = len(manual_entries)
    
    return {
        'total_amount': total_amount,
        'entry_count': entry_count,
        'average_per_entry': total_amount / entry_count if entry_count else 0
    }

def analyze_bank(agency_id):
    bank_connections = BankConnection.query.filter_by(agency_id=agency_id).all()
    total_transactions = 0
    total_amount = 0
    
    for connection in bank_connections:
        accounts = BankAccount.query.filter_by(connection_id=connection.id).all()
        for account in accounts:
            transactions = BankTransaction.query.filter_by(account_id=account.id).all()
            total_transactions += len(transactions)
            total_amount += sum(t.amount for t in transactions)
    
    return {
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'average_per_transaction': total_amount / total_transactions if total_transactions else 0
    }

def analyze_google_ads(agency_id):
    ads_accounts = GoogleAdsAccount.query.filter_by(agency_id=agency_id).all()
    total_budget = sum(sum(c.budget for c in account.campaigns) for account in ads_accounts)
    total_campaigns = sum(len(account.campaigns) for account in ads_accounts)
    
    return {
        'total_budget': total_budget,
        'total_campaigns': total_campaigns,
        'average_budget_per_campaign': total_budget / total_campaigns if total_campaigns else 0
    }

def compare_all_sources(results):
    total_revenue = (
        results['lex_sev']['total_gross'] +
        results['manual']['total_amount'] +
        results['bank']['total_amount']
    )
    
    return {
        'total_revenue': total_revenue,
        'lex_sev_percentage': (results['lex_sev']['total_gross'] / total_revenue * 100) if total_revenue else 0,
        'manual_percentage': (results['manual']['total_amount'] / total_revenue * 100) if total_revenue else 0,
        'bank_percentage': (results['bank']['total_amount'] / total_revenue * 100) if total_revenue else 0,
        'google_ads_budget_percentage': (results['google_ads']['total_budget'] / total_revenue * 100) if total_revenue else 0
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
