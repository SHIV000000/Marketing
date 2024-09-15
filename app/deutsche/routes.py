# app/deutsche/routes.py

import os
import secrets
import hashlib
import base64
import requests
from urllib import parse
from app.deutsche import bp
from app.deutsche.utils import get_access_token
from flask import request, render_template, redirect, flash, url_for, session, current_app
from app.models import Agency, BankUser
from app.database import db
from app.utils import login_required

@bp.route('/', methods=["GET", "POST"])
@login_required
def deutsche_bank():
    if not session.get('deutsche'):
        return redirect(url_for('deutsche.login_to_bank'))
    transactions = {}
    if request.method == "POST":
        if not session.get('deutsche').get("accessToken"):
            return redirect(url_for('deutsche.login_to_bank'))
        transactions = get_history(request.form)
    return render_template("deut_main.html", transactions=transactions)

@bp.route('/login-to-bank')
@login_required
def login_to_bank():
    sessionDeutsche = {}
    codeVerifier = secrets.token_hex(45)
    codeChallenge = hashlib.sha256(codeVerifier.encode("utf-8")).digest()
    codeChallenge = base64.urlsafe_b64encode(codeChallenge)
    codeChallenge = codeChallenge.decode("utf-8").replace("=", "")
    sessionDeutsche["codeVerifier"] = codeVerifier
    session['deutsche'] = sessionDeutsche
    requestParams = {
        "client_id": os.getenv("DEUTSCHE_CLIENT_ID"),
        "response_type": "code",
        "redirect_uri": os.getenv("HOST_URL")+"deutsche/deutsche-auth",
        "code_challenge_method": "S256",
        "code_challenge": codeChallenge,
    }
    qs = parse.urlencode(requestParams)
    return redirect('https://simulator-api.db.com/gw/oidc/authorize'+'?'+qs)

@bp.route('/deutsche-auth')
@login_required
def deutsche_auth():
    authCode = request.args.get('code')
    codeVerifier = session.get("deutsche", {}).get("codeVerifier")
    if not authCode or not codeVerifier:
        flash("Login Error with Deutsche Bank. Please try again.", "danger")
        return redirect(url_for("main.dashboard"))

    try:
        requestData = {
            "grant_type": "authorization_code",
            "code": authCode,
            "redirect_uri": os.getenv("HOST_URL")+"deutsche/deutsche-auth",
            "code_verifier": codeVerifier
        }
        authHeader = base64.urlsafe_b64encode(
            (os.getenv("DEUTSCHE_CLIENT_ID")+":"+os.getenv("DEUTSCHE_CLIENT_KEY")).encode()
        )
        requestHeaders = {
            "Authorization": "Basic "+authHeader.decode("utf-8")
        }
        res = requests.post('https://simulator-api.db.com/gw/oidc/token', data=requestData, headers=requestHeaders)
        res.raise_for_status()
        resultData = res.json()
        sessionDeutsche = session.get('deutsche', {})
        sessionDeutsche["accessToken"] = resultData.get("access_token")
        sessionDeutsche["refreshToken"] = resultData.get("refresh_token")
        session['deutsche'] = sessionDeutsche
        
        # Save the bank user information
        current_agency = Agency.query.get(session['currentAgency'].get("id"))
        bank_user = BankUser(
            email=session['currentAgency'].get("email"),
            agency_id=current_agency.id,
            agency=current_agency,
            refresh_token=sessionDeutsche["refreshToken"]
        )
        db.session.add(bank_user)
        db.session.commit()
        
        flash("Successfully connected to Deutsche Bank", "success")
        return redirect(url_for('deutsche.deutsche_bank'))
    except requests.RequestException as e:
        current_app.logger.error(f"Error during Deutsche Bank authentication: {str(e)}")
        flash("Error connecting to Deutsche Bank. Please try again.", "danger")
        return redirect(url_for("main.dashboard"))

def get_history(formData):
    sessionDeutsche = session.get('deutsche', {})
    accessToken = "Bearer " + sessionDeutsche.get("accessToken", "")
    requestHeaders = {
        "Authorization": accessToken
    }
    requestParams = {
        "iban": formData.get("iban"),
        "limit": 15,
    }
    if formData.get("form_date"):
        requestParams["bookingDateFrom"] = formData.get("form_date")
    if formData.get("to_date"):
        requestParams["bookingDateTo"] = formData.get("to_date")
    
    try:
        res = requests.get('https://simulator-api.db.com:443/gw/dbapi/banking/transactions/v2', 
                           headers=requestHeaders, params=requestParams)
        res.raise_for_status()
        return res.json().get("transactions", [])
    except requests.RequestException as e:
        current_app.logger.error(f"Error fetching Deutsche Bank transactions: {str(e)}")
        flash("Error fetching transactions. Please try again.", "danger")
        return []

@bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500
