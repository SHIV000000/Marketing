# Marketing\app\routes.py

from flask import Blueprint, request, render_template, redirect, flash, url_for, session, jsonify, current_app, Response
from app.models import Agency, LexAcc, Customer, Manual, BankConnection, BankAccount, BankTransaction, MailUser, GoogleAdsAccount
from app.database import db
from app.utils import login_required, admin_required, is_admin, add_invoice, fetch_sev_invoice, subscribe_to_invoice_event, unsubscribe_invoice_event
from app.google_ads.google_ads_handler import GoogleAdsHandler
from app.bank_handler import BankHandler
from app.mail.email_handler import EmailHandler
from app.helpers.finapi_helper import FinAPIHelper
from app.data_analysis import perform_analysis
from app.errors import CustomerAlreadyExist
import os
from flask_login import current_user, login_required
import requests as rq
from datetime import datetime, timedelta
import json

bp = Blueprint('main', __name__, template_folder="templates", static_folder="static")

@bp.route('/banks', methods=['GET'])
@login_required
def get_banks():
    access_token = FinAPIHelper.get_access_token()
    banks = FinAPIHelper.get_bank_connections(access_token)
    return jsonify(banks)

@bp.route('/connect_bank', methods=['POST'])
@login_required
def connect_bank():
    data = request.json
    access_token = FinAPIHelper.get_access_token()
    
    try:
        connection = FinAPIHelper.import_bank_connection(access_token, data['bank_id'], data['credentials'])
        
        bank_connection = BankConnection(
            agency_id=current_user.agency_id,
            finapi_connection_id=connection['id'],
            bank_name=connection['bank']['name']
        )
        db.session.add(bank_connection)
        
        for account in connection['accounts']:
            bank_account = BankAccount(
                connection_id=bank_connection.id,
                finapi_account_id=account['id'],
                account_name=account['accountName'],
                iban=account.get('iban')
            )
            db.session.add(bank_account)
        
        db.session.commit()
        return jsonify({'message': 'Bank connected successfully'}), 201
    except Exception as e:
        current_app.logger.error(f"Error connecting bank: {str(e)}")
        return jsonify({'error': 'Failed to connect bank'}), 400

@bp.route('/sync_transactions', methods=['POST'])
@login_required
def sync_transactions():
    access_token = FinAPIHelper.get_access_token()
    
    bank_connections = BankConnection.query.filter_by(agency_id=current_user.agency_id).all()
    for connection in bank_connections:
        accounts = BankAccount.query.filter_by(connection_id=connection.id).all()
        account_ids = [account.finapi_account_id for account in accounts]
        
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        to_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        transactions = FinAPIHelper.get_transactions(access_token, account_ids, from_date, to_date)
        
        for transaction in transactions:
            existing_transaction = BankTransaction.query.filter_by(finapi_transaction_id=transaction['id']).first()
            if not existing_transaction:
                new_transaction = BankTransaction(
                    account_id=BankAccount.query.filter_by(finapi_account_id=transaction['accountId']).first().id,
                    finapi_transaction_id=transaction['id'],
                    amount=transaction['amount'],
                    purpose=transaction.get('purpose'),
                    booking_date=datetime.strptime(transaction['bookingDate'], '%Y-%m-%d').date(),
                    value_date=datetime.strptime(transaction['valueDate'], '%Y-%m-%d').date()
                )
                db.session.add(new_transaction)
        
        connection.last_sync = datetime.utcnow()
        db.session.commit()
    
    return jsonify({'message': 'Transactions synced successfully'}), 200

@bp.route('/transactions', methods=['GET'])
@login_required
def get_transactions():
    start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.utcnow().strftime('%Y-%m-%d'))
    
    transactions = BankTransaction.query.join(BankAccount).join(BankConnection).filter(
        BankConnection.agency_id == current_user.agency_id,
        BankTransaction.booking_date >= start_date,
        BankTransaction.booking_date <= end_date
    ).all()
    
    return jsonify([{
        'id': t.id,
        'amount': t.amount,
        'purpose': t.purpose,
        'booking_date': t.booking_date.strftime('%Y-%m-%d'),
        'value_date': t.value_date.strftime('%Y-%m-%d'),
        'account_name': t.account.account_name,
        'bank_name': t.account.connection.bank_name
    } for t in transactions]), 200

@bp.route("/session")
def check_session():
    current_agency = session.get('currentAgency')
    if not current_agency:
        return "No active session"
    agency = db.session.get(Agency, current_agency.get("id"))
    return f"Current agency: {agency.email}" if agency else "Couldn't fetch agency"

@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get('currentAgency'):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        agency = Agency.get_agency_from_email(request.form['email'])
        if agency and agency.check_password(request.form.get("password")):
            session['currentAgency'] = {'id': agency.id, 'email': agency.email, 'isAdmin': is_admin(agency.email)}
            flash("Agency is logged in", "success")
            return redirect(url_for("main.dashboard"))
        flash("Invalid email or password", "danger")
    return render_template("login.html")

@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            Agency.create_agency(request.form['email'], password=request.form['password'])
            db.session.commit()
            flash("Agency is registered. Please login.", "success")
            return redirect(url_for("main.login"))
        except Exception as e:
            flash(str(e), "danger")
    return render_template("register.html")

@bp.route('/logout')
@login_required
def logout():
    session.pop('currentAgency', None)
    return redirect(url_for("main.home"))

@bp.route('/dashboard')
@login_required
def dashboard():
    agency_id = session['currentAgency'].get("id")
    try:
        analysis_results = perform_analysis(agency_id)
        lex_data = LexAcc.query.filter_by(agency_id=agency_id).all()
        manual_data = Manual.query.filter_by(agency_id=agency_id).all()
        bank_connections = BankConnection.query.filter_by(agency_id=agency_id).all()
        google_ads_data = GoogleAdsAccount.query.filter_by(agency_id=agency_id).all()
        
        return render_template("dashboard.html", 
                               results=analysis_results,
                               lex_data=lex_data,
                               manual_data=manual_data,
                               bank_connections=bank_connections,
                               google_ads_data=google_ads_data)
    except Exception as e:
        current_app.logger.error(f"Error in dashboard: {str(e)}")
        flash("An error occurred while loading the dashboard. Please try again.", "error")
        return redirect(url_for("main.home"))

@bp.route('/sync-data')
@login_required
def sync_data():
    agency_id = session['currentAgency'].get("id")
    
    google_ads_handler = GoogleAdsHandler(os.getenv('GOOGLE_ADS_CREDENTIALS_PATH'))
    google_ads_handler.sync_campaigns(agency_id)
    
    bank_handler = BankHandler(os.getenv('BANK_API_KEY'))
    bank_handler.sync_transactions(agency_id)
    
    email_handler = EmailHandler()
    email_handler.sync_emails(agency_id)
    
    flash("Data synchronization completed", "success")
    return redirect(url_for("main.dashboard"))

@bp.route('/analyze-data')
@login_required
def analyze_data():
    agency_id = session['currentAgency'].get("id")
    analysis_results = perform_analysis(agency_id)
    return render_template("analysis_results.html", results=analysis_results)

@bp.route('/lex-main', methods=["GET", "POST"])
@login_required
def lex_main():
    agency_id = session['currentAgency'].get("id")
    current_agency = db.get_or_404(Agency, agency_id)
    if request.method == "POST":
        apikey = request.form.get("key")
        orgname = request.form.get("orgname")
        orgid = request.form.get("orgid")
        existing_lex = LexAcc.query.filter_by(key=apikey).first()
        if existing_lex:
            flash("This account is already added for this agency", "danger")
            return redirect(url_for("main.lex_main"))
        lexacc = LexAcc(
                key=apikey,
                orgID=orgid,
                agency_id=agency_id,
                agency=current_agency,
                name=orgname,
                source="Lex"
                )
        db.session.add(lexacc)
        db.session.commit()
        lexacc.eventID = subscribe_to_invoice_event(lexacc.id)
        db.session.commit()
        return redirect(url_for("main.lex_main"))

    lexaccs = LexAcc.query.filter_by(agency_id=agency_id, source="Lex").all()
    return render_template("lex_main.html", lexaccs=lexaccs)

@bp.route('/lex-get-org')
@login_required
def lex_get_org():
    key = request.args.get("key")
    if not key:
        return "No key found"
    key = "Bearer " + key.strip()
    headers = {"Authorization": key, "Accept": "application/json"}
    res = rq.get("https://api.lexoffice.io/v1/profile", headers=headers)
    if res.status_code != 200:
        return render_template("htmx/lex_org_name.html", orgname=None)
    return render_template(
            "htmx/lex_org_name.html",
            orgname=res.json().get("companyName"),
            orgid=res.json().get("organizationId")
            )

@bp.route('/lex-delete/<int:lexid>')
@login_required
def lex_delete(lexid: int):
    current_agency = session['currentAgency']
    current_lexacc = db.get_or_404(LexAcc, lexid)
    if not (current_lexacc.agency_id == current_agency.get('id') or current_agency.get('isAdmin')):
        flash("Delete cannot be performed", "warning")
        return redirect(url_for('main.lex_main'))
    if current_lexacc.eventID:
        unsubscribe_invoice_event(current_lexacc)
    db.session.delete(current_lexacc)
    db.session.commit()
    flash(f"{current_lexacc.name} is deleted", "danger")
    return redirect(url_for('main.lex_main'))

@bp.route('/lex-customer/<int:lexid>', methods=["GET", "POST"])
@login_required
def lex_customer(lexid: int):
    agency_id = session['currentAgency'].get("id")
    current_lexacc = db.get_or_404(LexAcc, lexid)
    if current_lexacc.agency_id != agency_id:
        flash("Incorrect lex account id", "danger")
        return redirect(url_for("main.lex_main"))
    if request.method == "POST":
        customer_id = request.form.get("customerId")
        customer_name = request.form.get("customerName")
        try:
            current_lexacc.add_customer(lexID=customer_id, name=customer_name)
            db.session.commit()
        except CustomerAlreadyExist as e:
            flash(e.msg, e.category)

    customers = Customer.query.filter_by(lexAccId=current_lexacc.id).all()
    return render_template(
            "lex_customer.html",
            lexApiKey=current_lexacc.key,
            customers=customers
            )

@bp.route('/lex-get-customer')
@login_required
def lex_get_customer():
    customer_id = request.args.get("customerId")
    key = request.args.get("lexApiKey")
    if not key or not customer_id:
        return "Missing key or customerId"
    key = "Bearer " + key.strip()
    headers = {"Authorization": key, "Accept": "application/json"}
    url = f"https://api.lexoffice.io/v1/contacts/{customer_id.strip()}"
    res = rq.get(url, headers=headers)
    if res.status_code != 200:
        return render_template("htmx/lex_customer_name.html", customerName=None)
    return render_template(
            "htmx/lex_customer_name.html",
            customerName=res.json().get("company", {}).get("name")
            )

@bp.route("/invoice-event-callback", methods=["POST"])
def invoice_event_callback():
    request_data = request.get_json()
    if request_data.get("eventType") == "invoice.created":
        res_id = request_data.get("resourceId")
        org_id = request_data.get("organizationId")
        fetch_invoice_data(res_id, org_id)
    return "Thanks"

def fetch_invoice_data(invoice_id, org_id):
    current_lexacc = LexAcc.query.filter_by(orgID=org_id).first()
    if not current_lexacc:
        return None
    key = "Bearer " + current_lexacc.key.strip()
    headers = {"Authorization": key, "Accept": "application/json"}
    url = f"https://api.lexoffice.io/v1/invoices/{invoice_id.strip()}"
    res = rq.get(url, headers=headers)
    add_invoice(res.json())

@bp.route("/sev-main", methods=["GET", "POST"])
@login_required
def sev_main():
    agency_id = session['currentAgency'].get("id")
    current_agency = db.get_or_404(Agency, agency_id)
    if request.method == "POST":
        apikey = request.form.get("key")
        orgname = request.form.get("orgname")
        orgid = request.form.get("orgid")
        existing_lex = LexAcc.query.filter_by(key=apikey).first()
        if existing_lex:
            flash("This account is already added for this agency", "danger")
            return redirect(url_for("main.sev_main"))
        sevacc = LexAcc(
                key=apikey,
                orgID=orgid,
                agency_id=agency_id,
                agency=current_agency,
                name=orgname,
                source="Sev"
                )
        db.session.add(sevacc)
        db.session.commit()

    sevaccs = LexAcc.query.filter_by(agency_id=agency_id, source="Sev").all()
    return render_template("sev_main.html", sevaccs=sevaccs)

@bp.route("/sev-get-org")
@login_required
def sev_get_org():
    key = request.args.get("key")
    if not key:
        return "No key found"
    headers = {"Authorization": key, "Accept": "application/json"}
    payloads = {"embed": "sevClient"}
    url = "https://my.sevdesk.de/api/v1/CheckAccount"
    res = rq.get(url, headers=headers, params=payloads)
    if res.status_code != 200:
        return render_template("htmx/sev_org_name.html", orgname=None)
    orgname = res.json().get("objects", [{}])[0].get("sevClient", {}).get("name")
    orgid = res.json().get("objects", [{}])[0].get("sevClient", {}).get("id")
    return render_template("htmx/sev_org_name.html", orgname=orgname, orgid=orgid)

@bp.route("/sev-invoice/<int:sevid>", methods=["GET", "POST"])
@login_required
def sev_invoice(sevid: int):
    agency_id = session['currentAgency'].get("id")
    current_sevacc = db.get_or_404(LexAcc, sevid)
    sev_api_key = current_sevacc.key
    if current_sevacc.agency_id != agency_id:
        flash("Incorrect lex account id", "danger")
        return redirect(url_for("main.lex_main"))
    if request.method == "POST":
        invoice_id = request.form.get("invoiceid")
        customer_name = request.form.get("customerName")
        res = fetch_sev_invoice(sev_api_key, invoice_id.strip()).json()
        customer_sev_id = res.get("objects", [{}])[0].get("contact", {}).get("id")
        existing_customer = Customer.query.filter_by(lexID=customer_sev_id).first()
        if not existing_customer:
            existing_customer = current_sevacc.add_customer(customer_sev_id, customer_name)
        existing_customer.totalGrossAmount += float(res.get("objects", [{}])[0].get("sumGross", 0))
        existing_customer.totalNetAmount += float(res.get("objects", [{}])[0].get("sumNet", 0))
        db.session.commit()

    customers = Customer.query.filter_by(lexAccId=current_sevacc.id).all()
    return render_template("sev_invoice.html",
                           sevApiKey=sev_api_key,
                           customers=customers
                           )

@bp.route("/sev-get-invoice")
@login_required
def sev_get_invoice():
    invoice_id = request.args.get("invoiceid")
    key = request.args.get("sevApiKey")
    if not key or not invoice_id:
        return "Missing key or invoiceId"
    res = fetch_sev_invoice(key, invoice_id.strip())
    if res.status_code != 200:
        return render_template("htmx/sev_invoice_details.html", customerName=None)
    contact = res.json().get('objects', [{}])[0].get('contact', {})
    customer_name = f"{contact.get('surename', '')} {contact.get('familyname', '')}".strip()
    return render_template("htmx/sev_invoice_details.html", customerName=customer_name)

@bp.route("/manual-entry", methods=["GET", "POST"])
@login_required
def manual_entry():
    agency_id = session['currentAgency'].get("id")
    current_agency = db.get_or_404(Agency, agency_id)
    if request.method == "POST":
        form_data = request.form
        existing_entry = Manual.query.filter_by(identifier=form_data["identifier"]).first()
        if not existing_entry:
            new_entry = Manual(
                name=form_data["name"],
                source=form_data["source"],
                identifier=form_data["identifier"],
                agency_id=current_agency.id,
                agency=current_agency
            )
            db.session.add(new_entry)
            db.session.commit()
            existing_entry = new_entry
        existing_entry.totalAmount += float(form_data["amount"])
        existing_entry.addedOn = datetime.utcnow()
        db.session.commit()
        flash("Manual entry added successfully", "success")

    entries = Manual.query.filter_by(agency_id=current_agency.id).all()
    return render_template("manual.html", entries=entries)

@bp.route("/")
def home():
    return render_template("home.html")

@bp.route('/bank-connection')
@login_required
def bank_connection():
    return render_template('bank_connection.html')

@bp.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404

# Additional utility functions

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance

# Error handling routes

@bp.errorhandler(500)
def internal_server_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@bp.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403

@bp.route('/visualize/<int:agency_id>')
@login_required
def visualize_data(agency_id):
    agency = db.get_or_404(Agency, agency_id)
    if agency.id != session['currentAgency'].get("id") and not session['currentAgency'].get("isAdmin"):
        flash("You don't have permission to view this data", "danger")
        return redirect(url_for("main.dashboard"))
    
    # Fetch and process data for visualization
    lex_data = LexAcc.query.filter_by(agency_id=agency_id).all()
    manual_data = Manual.query.filter_by(agency_id=agency_id).all()
    bank_connections = BankConnection.query.filter_by(agency_id=agency_id).all()
    
    # Process the data and prepare it for visualization
    visualization_data = {
        'lex': [{'name': lex.name, 'value': sum(customer.totalGrossAmount for customer in lex.customers)} for lex in lex_data],
        'manual': [{'name': entry.name, 'value': entry.totalAmount} for entry in manual_data],
        'bank': [{'name': conn.bank_name, 'value': sum(transaction.amount for account in conn.accounts for transaction in account.transactions)} for conn in bank_connections]
    }
    
    return render_template('visualize.html', data=visualization_data)

@bp.route('/export/<int:agency_id>')
@login_required
def export_data(agency_id):
    agency = db.get_or_404(Agency, agency_id)
    if agency.id != session['currentAgency'].get("id") and not session['currentAgency'].get("isAdmin"):
        flash("You don't have permission to export this data", "danger")
        return redirect(url_for("main.dashboard"))
    
    # Fetch all relevant data
    lex_data = LexAcc.query.filter_by(agency_id=agency_id).all()
    manual_data = Manual.query.filter_by(agency_id=agency_id).all()
    bank_connections = BankConnection.query.filter_by(agency_id=agency_id).all()
    
    # Process and format the data for export
    export_data = {
        'lex': [{'name': lex.name, 'orgID': lex.orgID, 'customers': [{'name': c.name, 'gross': c.totalGrossAmount, 'net': c.totalNetAmount} for c in lex.customers]} for lex in lex_data],
        'manual': [{'name': entry.name, 'source': entry.source, 'amount': entry.totalAmount, 'date': entry.addedOn} for entry in manual_data],
        'bank': [{'bank_name': conn.bank_name, 'accounts': [{'account_name': acc.account_name, 'transactions': [{'amount': t.amount, 'purpose': t.purpose, 'booking_date': t.booking_date} for t in acc.transactions]} for acc in conn.accounts]} for conn in bank_connections]
    }
    
    # Generate a JSON file
    response = Response(
        json.dumps(export_data, default=str),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename=agency_{agency_id}_export.json'}
    )
    
    return response

@bp.route('/analysis/<int:agency_id>')
@login_required
def analysis(agency_id):
    agency = db.get_or_404(Agency, agency_id)
    if agency.id != session['currentAgency'].get("id") and not session['currentAgency'].get("isAdmin"):
        flash("You don't have permission to view this analysis", "danger")
        return redirect(url_for("main.dashboard"))

    analysis_results = perform_analysis(agency_id)
    return render_template('analysis.html', results=analysis_results)

@bp.route('/settings')
@login_required
def settings():
    agency_id = session['currentAgency'].get("id")
    agency = db.get_or_404(Agency, agency_id)
    return render_template('settings.html', agency=agency)

@bp.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    agency_id = session['currentAgency'].get("id")
    agency = db.get_or_404(Agency, agency_id)

    agency.email = request.form.get('email')
    if request.form.get('password'):
        agency.set_password(request.form.get('password'))

    db.session.commit()
    flash("Settings updated successfully", "success")
    return redirect(url_for('main.settings'))

@bp.route('/google_ads_setup')
@login_required
def google_ads_setup():
    agency_id = session['currentAgency'].get("id")
    google_ads_account = GoogleAdsAccount.query.filter_by(agency_id=agency_id).first()
    return render_template('google_ads_setup.html', google_ads_account=google_ads_account)

@bp.route('/update_google_ads', methods=['POST'])
@login_required
def update_google_ads():
    agency_id = session['currentAgency'].get("id")
    google_ads_account = GoogleAdsAccount.query.filter_by(agency_id=agency_id).first()

    if not google_ads_account:
        google_ads_account = GoogleAdsAccount(agency_id=agency_id)

    google_ads_account.client_id = request.form.get('client_id')
    google_ads_account.client_secret = request.form.get('client_secret')
    google_ads_account.developer_token = request.form.get('developer_token')
    google_ads_account.refresh_token = request.form.get('refresh_token')

    db.session.add(google_ads_account)
    db.session.commit()

    flash("Google Ads account updated successfully", "success")
    return redirect(url_for('main.google_ads_setup'))

@bp.route('/mail_setup')
@login_required
def mail_setup():
    agency_id = session['currentAgency'].get("id")
    mail_user = MailUser.query.filter_by(agency_id=agency_id).first()
    return render_template('mail_setup.html', mail_user=mail_user)

@bp.route('/update_mail', methods=['POST'])
@login_required
def update_mail():
    agency_id = session['currentAgency'].get("id")
    mail_user = MailUser.query.filter_by(agency_id=agency_id).first()

    if not mail_user:
        mail_user = MailUser(agency_id=agency_id)

    mail_user.email = request.form.get('email')
    mail_user.password = request.form.get('password')
    mail_user.imap_server = request.form.get('imap_server')
    mail_user.imap_port = request.form.get('imap_port')

    db.session.add(mail_user)
    db.session.commit()

    flash("Mail settings updated successfully", "success")
    return redirect(url_for('main.mail_setup'))

