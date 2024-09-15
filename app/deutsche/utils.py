# app/deutsche/utils.py

import os
import base64
import requests
from flask import current_app

def get_access_token(refresh_token):
    try:
        request_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        auth_header = base64.urlsafe_b64encode(
            (os.getenv("DEUTSCHE_CLIENT_ID")+":"+os.getenv("DEUTSCHE_CLIENT_KEY")).encode()
        )
        request_headers = {
            "Authorization": "Basic "+auth_header.decode("utf-8")
        }
        res = requests.post('https://simulator-api.db.com/gw/oidc/token', data=request_data, headers=request_headers)
        res.raise_for_status()
        return res.json().get("access_token")
    except requests.RequestException as e:
        current_app.logger.error(f"Error refreshing Deutsche Bank access token: {str(e)}")
        return None
