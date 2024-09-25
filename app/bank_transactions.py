# app/bank_transactions.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from app.models import Agency, BankConnection, BankAccount, BankTransaction
from app.database import db
from app.helpers.finapi_helper import FinAPIHelper
from datetime import datetime, timedelta
import os

bp = Blueprint('bank', __name__)

@bp.route('/')
@login_required
def index():
    bank_connections = BankConnection.query.filter_by(agency_id=current_user.agency_id).all()
    return render_template('bank/index.html', bank_connections=bank_connections)

@bp.route('/sync')
@login_required
def sync():
    try:
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
        flash('Bank transactions synced successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error syncing transactions: {str(e)}")
        flash('Error syncing bank transactions. Please try again later.', 'error')
    return redirect(url_for('bank.index'))

@bp.route('/transactions/<int:connection_id>')
@login_required
def transactions(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to view these transactions.', 'error')
        return redirect(url_for('bank.index'))
    
    accounts = BankAccount.query.filter_by(connection_id=connection_id).all()
    transactions = BankTransaction.query.filter(BankTransaction.account_id.in_([account.id for account in accounts])).order_by(BankTransaction.booking_date.desc()).all()
    return render_template('bank/transactions.html', bank_connection=bank_connection, transactions=transactions)

@bp.route('/link_account', methods=['POST'])
@login_required
def link_account():
    bank_id = request.form.get('bank_id')
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not bank_id or not username or not password:
        return jsonify({'success': False, 'error': 'Missing required information'}), 400

    try:
        access_token = FinAPIHelper.get_access_token()
        connection = FinAPIHelper.import_bank_connection(access_token, bank_id, {'username': username, 'password': password})
        
        new_connection = BankConnection(
            agency_id=current_user.agency_id,
            finapi_connection_id=connection['id'],
            bank_name=connection['bankName']
        )
        db.session.add(new_connection)
        
        for account in connection['accounts']:
            new_account = BankAccount(
                connection_id=new_connection.id,
                finapi_account_id=account['id'],
                account_name=account['accountName'],
                iban=account.get('iban')
            )
            db.session.add(new_account)
        
        db.session.commit()
        flash('Bank account linked successfully', 'success')
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error linking bank account: {str(e)}")
        flash('Error linking bank account. Please try again.', 'error')
        return jsonify({'success': False, 'error': 'Failed to link account'}), 500

@bp.route('/account_balances/<int:connection_id>')
@login_required
def account_balances(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to view these account balances.', 'error')
        return redirect(url_for('bank.index'))

    accounts = BankAccount.query.filter_by(connection_id=connection_id).all()
    balances = []
    for account in accounts:
        latest_transaction = BankTransaction.query.filter_by(account_id=account.id).order_by(BankTransaction.booking_date.desc()).first()
        balance = latest_transaction.amount if latest_transaction else 0
        balances.append({'account_name': account.account_name, 'balance': balance})

    return render_template('bank/account_balances.html', bank_connection=bank_connection, balances=balances)

@bp.route('/transaction_summary/<int:connection_id>')
@login_required
def transaction_summary(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to view this summary.', 'error')
        return redirect(url_for('bank.index'))

    accounts = BankAccount.query.filter_by(connection_id=connection_id).all()
    account_ids = [account.id for account in accounts]

    # Calculate summary statistics
    total_income = db.session.query(db.func.sum(BankTransaction.amount)).filter(
        BankTransaction.account_id.in_(account_ids),
        BankTransaction.amount > 0
    ).scalar() or 0

    total_expenses = db.session.query(db.func.sum(BankTransaction.amount)).filter(
        BankTransaction.account_id.in_(account_ids),
        BankTransaction.amount < 0
    ).scalar() or 0

    category_breakdown = db.session.query(
        BankTransaction.purpose,
        db.func.sum(BankTransaction.amount).label('total')
    ).filter(
        BankTransaction.account_id.in_(account_ids)
    ).group_by(BankTransaction.purpose).all()

    summary = {
        'total_income': total_income,
        'total_expenses': abs(total_expenses),
        'net_income': total_income + total_expenses,
        'category_breakdown': category_breakdown
    }

    return render_template('bank/transaction_summary.html', bank_connection=bank_connection, summary=summary)

@bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@bp.route('/delete_connection/<int:connection_id>', methods=['POST'])
@login_required
def delete_connection(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to delete this connection.', 'error')
        return redirect(url_for('bank.index'))

    try:
        access_token = FinAPIHelper.get_access_token()
        FinAPIHelper.delete_bank_connection(access_token, bank_connection.finapi_connection_id)

        # Delete associated accounts and transactions
        accounts = BankAccount.query.filter_by(connection_id=connection_id).all()
        for account in accounts:
            BankTransaction.query.filter_by(account_id=account.id).delete()
        BankAccount.query.filter_by(connection_id=connection_id).delete()

        db.session.delete(bank_connection)
        db.session.commit()

        flash('Bank connection deleted successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting bank connection: {str(e)}")
        flash('Error deleting bank connection. Please try again.', 'error')

    return redirect(url_for('bank.index'))

@bp.route('/update_connection/<int:connection_id>', methods=['POST'])
@login_required
def update_connection(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to update this connection.', 'error')
        return redirect(url_for('bank.index'))

    try:
        access_token = FinAPIHelper.get_access_token()
        updated_connection = FinAPIHelper.update_bank_connection(access_token, bank_connection.finapi_connection_id)

        bank_connection.last_sync = datetime.utcnow()
        db.session.commit()

        flash('Bank connection updated successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error updating bank connection: {str(e)}")
        flash('Error updating bank connection. Please try again.', 'error')

    return redirect(url_for('bank.transactions', connection_id=connection_id))

@bp.route('/search_transactions/<int:connection_id>', methods=['GET'])
@login_required
def search_transactions(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to view these transactions.', 'error')
        return redirect(url_for('bank.index'))

    query = request.args.get('query', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    accounts = BankAccount.query.filter_by(connection_id=connection_id).all()
    account_ids = [account.id for account in accounts]

    transactions_query = BankTransaction.query.filter(BankTransaction.account_id.in_(account_ids))

    if query:
        transactions_query = transactions_query.filter(BankTransaction.purpose.ilike(f'%{query}%'))
    
    if start_date:
        transactions_query = transactions_query.filter(BankTransaction.booking_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    
    if end_date:
        transactions_query = transactions_query.filter(BankTransaction.booking_date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    transactions = transactions_query.order_by(BankTransaction.booking_date.desc()).all()

    return render_template('bank/search_transactions.html', bank_connection=bank_connection, transactions=transactions, query=query, start_date=start_date, end_date=end_date)

def get_transaction_statistics(connection_id, start_date=None, end_date=None):
    accounts = BankAccount.query.filter_by(connection_id=connection_id).all()
    account_ids = [account.id for account in accounts]

    transactions_query = BankTransaction.query.filter(BankTransaction.account_id.in_(account_ids))

    if start_date:
        transactions_query = transactions_query.filter(BankTransaction.booking_date >= start_date)
    
    if end_date:
        transactions_query = transactions_query.filter(BankTransaction.booking_date <= end_date)

    total_income = transactions_query.filter(BankTransaction.amount > 0).with_entities(db.func.sum(BankTransaction.amount)).scalar() or 0
    total_expenses = transactions_query.filter(BankTransaction.amount < 0).with_entities(db.func.sum(BankTransaction.amount)).scalar() or 0

    category_breakdown = transactions_query.group_by(BankTransaction.purpose).with_entities(
        BankTransaction.purpose,
        db.func.sum(BankTransaction.amount).label('total')
    ).all()

    return {
        'total_income': total_income,
        'total_expenses': abs(total_expenses),
        'net_income': total_income + total_expenses,
        'category_breakdown': category_breakdown
    }

@bp.route('/transaction_report/<int:connection_id>', methods=['GET', 'POST'])
@login_required
def transaction_report(connection_id):
    bank_connection = BankConnection.query.get_or_404(connection_id)
    if bank_connection.agency_id != current_user.agency_id:
        flash('You do not have permission to view this report.', 'error')
        return redirect(url_for('bank.index'))

    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    else:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

    statistics = get_transaction_statistics(connection_id, start_date, end_date)

    return render_template('bank/transaction_report.html', bank_connection=bank_connection, statistics=statistics, start_date=start_date, end_date=end_date)
