# app/bank_handler.py

import plaid
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from datetime import datetime, timedelta
from app.models import Agency, BankConnection, BankAccount, BankTransaction
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
        bank_connections = BankConnection.query.filter_by(agency_id=agency_id).all()
        for connection in bank_connections:
            try:
                transactions = self._fetch_transactions(connection.finapi_connection_id)
                self._process_transactions(connection.id, transactions)
            except Exception as e:
                current_app.logger.error(f"Error syncing transactions for connection {connection.id}: {str(e)}")

        db.session.commit()

    def _fetch_transactions(self, connection_id):
        start_date = (datetime.now() - timedelta(days=30)).date()
        end_date = datetime.now().date()
        
        request = TransactionsGetRequest(
            access_token=connection_id,  # Assuming finapi_connection_id is used as access_token
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(
                count=500,
                offset=0
            )
        )
        
        response = self.client.transactions_get(request)
        return response['transactions']

    def _process_transactions(self, connection_id, transactions):
        for transaction in transactions:
            account = BankAccount.query.filter_by(
                connection_id=connection_id,
                finapi_account_id=transaction['account_id']
            ).first()

            if not account:
                current_app.logger.error(f"Account not found for transaction {transaction['transaction_id']}")
                continue

            existing_transaction = BankTransaction.query.filter_by(
                finapi_transaction_id=transaction['transaction_id'],
                account_id=account.id
            ).first()

            if not existing_transaction:
                new_transaction = BankTransaction(
                    account_id=account.id,
                    finapi_transaction_id=transaction['transaction_id'],
                    amount=float(transaction['amount']),
                    purpose=transaction['name'],
                    booking_date=datetime.strptime(transaction['date'], '%Y-%m-%d'),
                    value_date=datetime.strptime(transaction['date'], '%Y-%m-%d')  # Assuming same as booking_date
                )
                db.session.add(new_transaction)
            else:
                # Update existing transaction if needed
                existing_transaction.amount = float(transaction['amount'])
                existing_transaction.purpose = transaction['name']

    def link_bank_account(self, agency_id, public_token):
        try:
            exchange_response = self.client.item_public_token_exchange(public_token)
            access_token = exchange_response['access_token']
            
            agency = Agency.query.get(agency_id)
            if agency:
                new_connection = BankConnection(
                    agency_id=agency_id,
                    finapi_connection_id=access_token,
                    bank_name="Plaid Bank"  # You might want to fetch the actual bank name
                )
                db.session.add(new_connection)
                db.session.commit()
                return True
            else:
                current_app.logger.error(f"Agency {agency_id} not found")
                return False
        except plaid.ApiException as e:
            current_app.logger.error(f"Error linking bank account: {str(e)}")
            return False

    def get_account_balances(self, connection_id):
        connection = BankConnection.query.get(connection_id)
        if not connection:
            return None

        try:
            response = self.client.accounts_balance_get(connection.finapi_connection_id)
            return response['accounts']
        except plaid.ApiException as e:
            current_app.logger.error(f"Error fetching account balances: {str(e)}")
            return None
