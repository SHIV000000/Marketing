# app/helpers/finapi_helper.py

import requests
from flask import current_app
from requests.exceptions import RequestException
import logging

class FinAPIHelper:
    BASE_URL = "https://sandbox.finapi.io"
    API_VERSION = "v1"

    @classmethod
    def get_access_token(cls):
        url = f"{cls.BASE_URL}/oauth/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': current_app.config['FINAPI_CLIENT_ID'],
            'client_secret': current_app.config['FINAPI_CLIENT_SECRET']
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        try:
            response = requests.post(url, data=data, headers=headers)
            response.raise_for_status()
            return response.json()['access_token']
        except RequestException as e:
            logging.error(f"Error getting access token: {str(e)}")
            raise

    @classmethod
    def get_bank_connections(cls, access_token):
        url = f"{cls.BASE_URL}/api/{cls.API_VERSION}/bankConnections"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()['connections']
        except RequestException as e:
            logging.error(f"Error getting bank connections: {str(e)}")
            raise

    @classmethod
    def import_bank_connection(cls, access_token, bank_id, credentials):
        url = f"{cls.BASE_URL}/api/{cls.API_VERSION}/bankConnections/import"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        data = {
            'bankId': bank_id,
            'interface': 'XS2A',
            'loginCredentials': credentials
        }
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logging.error(f"Error importing bank connection: {str(e)}")
            raise

    @classmethod
    def get_transactions(cls, access_token, account_ids, from_date, to_date, page=1, per_page=100):
        url = f"{cls.BASE_URL}/api/{cls.API_VERSION}/transactions"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        params = {
            'accountIds': ','.join(map(str, account_ids)),
            'fromDate': from_date,
            'toDate': to_date,
            'page': page,
            'perPage': per_page,
            'order': 'date,desc'
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()['transactions']
        except RequestException as e:
            logging.error(f"Error getting transactions: {str(e)}")
            raise

    @classmethod
    def get_bank_details(cls, access_token, bank_id):
        url = f"{cls.BASE_URL}/api/{cls.API_VERSION}/banks/{bank_id}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logging.error(f"Error getting bank details: {str(e)}")
            raise

    @classmethod
    def delete_bank_connection(cls, access_token, connection_id):
        url = f"{cls.BASE_URL}/api/{cls.API_VERSION}/bankConnections/{connection_id}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        try:
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            return True
        except RequestException as e:
            logging.error(f"Error deleting bank connection: {str(e)}")
            raise
