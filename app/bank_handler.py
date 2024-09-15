# app/bank_handler.py

import plaid
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from datetime import datetime, timedelta
from app.models import BankUser, BankTransaction
from app.database import db
import os
from flask import current_app
import logging

class BankHandler:
    def __init__(self):
        self.client = self._create_plaid_client()

    def _create_plaid_client(self):
        configuration = plaid.Configuration(
            host=plaid.Environment.Development,
            api_key={
                'clientId': os.getenv('PLAID_CLIENT_ID'),
                'secret': os.getenv('PLAID_SECRET'),
            }
        )
        api_client = plaid.ApiClient(configuration)
        return plaid_api.PlaidApi(api_client)

    def sync_transactions(self, agency_id):
        bank_users = BankUser.query.filter_by(agency_id=agency_id).all()
        for user in bank_users:
            try:
                transactions = self._fetch_transactions(user.access_token)
                self._process_transactions(user.id, transactions)
            except Exception as e:
                current_app.logger.error(f"Error syncing transactions for user {user.id}: {str(e)}")

        db.session.commit()

    def _fetch_transactions(self, access_token):
        start_date = (datetime.now() - timedelta(days=30)).date()
        end_date = datetime.now().date()
        
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(
                count=500,
                offset=0
            )
        )
        
        response = self.client.transactions_get(request)
        return response['transactions']

    def _process_transactions(self, user_id, transactions):
        for transaction in transactions:
            existing_transaction = BankTransaction.query.filter_by(
                transaction_id=transaction['transaction_id'],
                bank_user_id=user_id
            ).first()

            if not existing_transaction:
                new_transaction = BankTransaction(
                    transaction_id=transaction['transaction_id'],
                    amount=float(transaction['amount']),
                    description=transaction['name'],
                    date=datetime.strptime(transaction['date'], '%Y-%m-%d'),
                    bank_user_id=user_id,
                    category=transaction.get('category', [None])[0],
                    merchant_name=transaction.get('merchant_name'),
                    payment_channel=transaction.get('payment_channel')
                )
                db.session.add(new_transaction)
            else:
                # Update existing transaction if needed
                existing_transaction.amount = float(transaction['amount'])
                existing_transaction.description = transaction['name']
                existing_transaction.category = transaction.get('category', [None])[0]
                existing_transaction.merchant_name = transaction.get('merchant_name')
                existing_transaction.payment_channel = transaction.get('payment_channel')

    def link_bank_account(self, user_id, public_token):
        try:
            exchange_response = self.client.item_public_token_exchange(public_token)
            access_token = exchange_response['access_token']
            
            bank_user = BankUser.query.get(user_id)
            if bank_user:
                bank_user.access_token = access_token
                db.session.commit()
                return True
            else:
                current_app.logger.error(f"User {user_id} not found")
                return False
        except plaid.ApiException as e:
            current_app.logger.error(f"Error linking bank account: {str(e)}")
            return False

    def get_account_balances(self, user_id):
        bank_user = BankUser.query.get(user_id)
        if not bank_user or not bank_user.access_token:
            return None

        try:
            response = self.client.accounts_balance_get(bank_user.access_token)
            return response['accounts']
        except plaid.ApiException as e:
            current_app.logger.error(f"Error fetching account balances: {str(e)}")
            return None
