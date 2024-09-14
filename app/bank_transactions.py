# app/bank_transactions.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from app.models import BankUser, BankTransaction
from app.database import db
from app.bank_handler import BankHandler
import os

bp = Blueprint('bank', __name__)

@bp.route('/')
@login_required
def index():
    bank_users = BankUser.query.filter_by(agency_id=current_user.agency_id).all()
    return render_template('bank/index.html', bank_users=bank_users)

@bp.route('/sync')
@login_required
def sync():
    handler = BankHandler()
    try:
        handler.sync_transactions(current_user.agency_id)
        flash('Bank transactions synced successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error syncing transactions: {str(e)}")
        flash('Error syncing bank transactions. Please try again later.', 'error')
    return redirect(url_for('bank.index'))

@bp.route('/transactions/<int:user_id>')
@login_required
def transactions(user_id):
    bank_user = BankUser.query.get_or_404(user_id)
    if bank_user.agency_id != current_user.agency_id:
        flash('You do not have permission to view these transactions.', 'error')
        return redirect(url_for('bank.index'))
    
    transactions = BankTransaction.query.filter_by(bank_user_id=user_id).order_by(BankTransaction.date.desc()).all()
    return render_template('bank/transactions.html', bank_user=bank_user, transactions=transactions)

@bp.route('/link_account', methods=['POST'])
@login_required
def link_account():
    public_token = request.form.get('public_token')
    if not public_token:
        return jsonify({'success': False, 'error': 'No public token provided'}), 400

    handler = BankHandler()
    success = handler.link_bank_account(current_user.id, public_token)

    if success:
        flash('Bank account linked successfully', 'success')
        return jsonify({'success': True})
    else:
        flash('Error linking bank account. Please try again.', 'error')
        return jsonify({'success': False, 'error': 'Failed to link account'}), 500

@bp.route('/account_balances/<int:user_id>')
@login_required
def account_balances(user_id):
    bank_user = BankUser.query.get_or_404(user_id)
    if bank_user.agency_id != current_user.agency_id:
        flash('You do not have permission to view these account balances.', 'error')
        return redirect(url_for('bank.index'))

    handler = BankHandler()
    balances = handler.get_account_balances(user_id)

    if balances is None:
        flash('Error fetching account balances. Please try again later.', 'error')
        return redirect(url_for('bank.index'))

    return render_template('bank/account_balances.html', bank_user=bank_user, balances=balances)

@bp.route('/transaction_summary/<int:user_id>')
@login_required
def transaction_summary(user_id):
    bank_user = BankUser.query.get_or_404(user_id)
    if bank_user.agency_id != current_user.agency_id:
        flash('You do not have permission to view this summary.', 'error')
        return redirect(url_for('bank.index'))

    # Calculate summary statistics
    total_income = db.session.query(db.func.sum(BankTransaction.amount)).filter(
        BankTransaction.bank_user_id == user_id,
        BankTransaction.amount > 0
    ).scalar() or 0

    total_expenses = db.session.query(db.func.sum(BankTransaction.amount)).filter(
        BankTransaction.bank_user_id == user_id,
        BankTransaction.amount < 0
    ).scalar() or 0

    category_breakdown = db.session.query(
        BankTransaction.category,
        db.func.sum(BankTransaction.amount).label('total')
    ).filter(
        BankTransaction.bank_user_id == user_id
    ).group_by(BankTransaction.category).all()

    summary = {
        'total_income': total_income,
        'total_expenses': abs(total_expenses),
        'net_income': total_income + total_expenses,
        'category_breakdown': category_breakdown
    }

    return render_template('bank/transaction_summary.html', bank_user=bank_user, summary=summary)

@bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500
