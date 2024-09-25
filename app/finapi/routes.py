# Marketing\app\finapi\routes.py

from app.finapi import bp
from app.models import Agency, BankConnection
from app.database import db
from flask import render_template, request, abort, session, flash, redirect, url_for
import requests as rq
from flask import current_app
import os
from datetime import datetime, timedelta
from app.helpers.finapi_helper import FinAPIHelper

@bp.route('/', methods=["GET", "POST"])
def main():
    current_agency = session.get('currentAgency')
    if not current_agency:
        flash("Please log in first", "warning")
        return redirect(url_for('main.login'))

    bank_connections = BankConnection.query.filter_by(agency_id=current_agency.get("id")).all()
    return render_template("fin_main.html", bank_connections=bank_connections)

@bp.route('/connect-bank', methods=["POST"])
def connect_bank():
    current_agency = session.get('currentAgency')
    if not current_agency:
        flash("Please log in first", "warning")
        return redirect(url_for('main.login'))

    try:
        access_token = FinAPIHelper.get_access_token()
        bank_id = request.form.get("bank_id")
        credentials = {
            "username": request.form.get("username"),
            "password": request.form.get("password")
        }
        
        connection = FinAPIHelper.import_bank_connection(access_token, bank_id, credentials)
        
        new_connection = BankConnection(
            agency_id=current_agency.get("id"),
            finapi_connection_id=connection['id'],
            bank_name=connection['bankName']
        )
        db.session.add(new_connection)
        db.session.commit()

        flash("Bank connected successfully", "success")
    except Exception as e:
        flash(f"Error connecting bank: {str(e)}", "danger")

    return redirect(url_for('finapi.main'))

@bp.route("/fetch-transactions")
def fetch_transactions():
    current_agency = session.get('currentAgency')
    if not current_agency:
        flash("Please log in first", "warning")
        return redirect(url_for('main.login'))

    connection_id = request.args.get("connection_id")
    if not connection_id:
        flash("No bank connection selected", "warning")
        return redirect(url_for("finapi.main"))

    try:
        access_token = FinAPIHelper.get_access_token()
        bank_connection = BankConnection.query.filter_by(id=connection_id, agency_id=current_agency.get("id")).first()
        
        if not bank_connection:
            flash("Invalid bank connection", "danger")
            return redirect(url_for("finapi.main"))

        transactions = FinAPIHelper.get_transactions(
            access_token,
            [bank_connection.finapi_connection_id],
            from_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            to_date=datetime.now().strftime('%Y-%m-%d')
        )

        return render_template("transactions.html", transactions=transactions, bank_name=bank_connection.bank_name)
    except Exception as e:
        flash(f"Error fetching transactions: {str(e)}", "danger")
        return redirect(url_for("finapi.main"))

@bp.route("/delete-connection/<int:connection_id>", methods=["POST"])
def delete_connection(connection_id):
    current_agency = session.get('currentAgency')
    if not current_agency:
        flash("Please log in first", "warning")
        return redirect(url_for('main.login'))

    try:
        bank_connection = BankConnection.query.filter_by(id=connection_id, agency_id=current_agency.get("id")).first()
        
        if not bank_connection:
            flash("Invalid bank connection", "danger")
            return redirect(url_for("finapi.main"))

        access_token = FinAPIHelper.get_access_token()
        FinAPIHelper.delete_bank_connection(access_token, bank_connection.finapi_connection_id)

        db.session.delete(bank_connection)
        db.session.commit()

        flash("Bank connection deleted successfully", "success")
    except Exception as e:
        flash(f"Error deleting bank connection: {str(e)}", "danger")

    return redirect(url_for("finapi.main"))

@bp.errorhandler(500)
def internal_server_error(error):
    db.session.rollback()
    flash("An internal server error occurred. Please try again later.", "danger")
    return redirect(url_for("finapi.main"))
