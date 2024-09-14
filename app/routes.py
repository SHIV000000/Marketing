# Marketing\app\routes.py


from flask import Blueprint, request, render_template, redirect, flash, url_for, session
from app.models import Agency, LexAcc, Customer, Manual, BankUser, MailUser, GoogleAdsAccount
from app.database import db
from app.utils import login_required, admin_required, is_admin, add_invoice, fetch_sev_invoice, subscribe_to_invoice_event, unsubscribe_invoice_event
from app.google_ads_handler import GoogleAdsHandler
from app.bank_handler import BankHandler
from app.email_handler import EmailHandler
from app.data_analysis import perform_analysis
from app.errors import CustomerAlreadyExist
import os
import requests as rq
from datetime import datetime as dt

bp = Blueprint('main', __name__, template_folder="templates", static_folder="static")

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
    analysis_results = perform_analysis(agency_id)
    return render_template("dashboard.html", results=analysis_results)

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
        existing_entry.addedOn = dt.utcnow()
        db.session.commit()
        flash("Manual entry added successfully", "success")

    entries = Manual.query.filter_by(agency_id=current_agency.id).all()
    return render_template("manual.html", entries=entries)

@bp.route("/")
def home():
    return render_template("home.html")

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

# Additional routes for data visualization

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
    bank_data = BankUser.query.filter_by(agency_id=agency_id).all()
    
    # Process the data and prepare it for visualization
    # This is a placeholder - you'd need to implement the actual data processing logic
    visualization_data = {
        'lex': [{'name': lex.name, 'value': sum(customer.totalGrossAmount for customer in lex.customers)} for lex in lex_data],
        'manual': [{'name': entry.name, 'value': entry.totalAmount} for entry in manual_data],
        'bank': [{'name': user.email, 'value': sum(transaction.amount for transaction in user.transactions)} for user in bank_data]
    }
    
    return render_template('visualize.html', data=visualization_data)

# Route for exporting data
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
    bank_data = BankUser.query.filter_by(agency_id=agency_id).all()
    
    # Process and format the data for export
    # This is a placeholder - you'd need to implement the actual data export logic
    export_data = {
        'lex': [{'name': lex.name, 'orgID': lex.orgID, 'customers': [{'name': c.name, 'gross': c.totalGrossAmount, 'net': c.totalNetAmount} for c in lex.customers]} for lex in lex_data],
        'manual': [{'name': entry.name, 'source': entry.source, 'amount': entry.totalAmount, 'date': entry.addedOn} for entry in manual_data],
        'bank': [{'email': user.email, 'transactions': [{'amount': t.amount, 'description': t.description, 'date': t.date} for t in user.transactions]} for user in bank_data]
    }
    
    # Generate a CSV or JSON file
    # For this example, we'll use JSON
    import json
    from flask import Response
    
    response = Response(
        json.dumps(export_data, default=str),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename=agency_{agency_id}_export.json'}
    )
    
    return response
