import os
from dotenv import load_dotenv
import requests

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def insert_account(account_data):
    url = f"{SUPABASE_URL}/rest/v1/accounts"
    try:
        response = requests.post(url, json=account_data, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Account insertion error: {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'No response'}")
        print(f"Response text: {response.text if 'response' in locals() else 'No response'}")
        return None

def insert_transactions(transaction_data):
    url = f"{SUPABASE_URL}/rest/v1/transactions"
    try:
        response = requests.post(url, json=transaction_data, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Transaction insertion error: {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'No response'}")
        print(f"Response text: {response.text if 'response' in locals() else 'No response'}")
        return None

def get_account_by_name_type(name, account_type):
    base_url = f"{SUPABASE_URL}/rest/v1/accounts"
    params = {
        "name": f"eq.{name}",
        "type": f"eq.{account_type}"
    }
    try:
        response = requests.get(base_url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except requests.exceptions.RequestException as e:
        print(f"Error checking existing account: {e}")
        return None

def get_transaction_by_details(account_id, description, date, amount):
    base_url = f"{SUPABASE_URL}/rest/v1/transactions"
    params = {
        "account_id": f"eq.{account_id}",
        "description": f"eq.{description}",
        "date": f"eq.{date}",
        "amount": f"eq.{amount}"
    }
    try:
        response = requests.get(base_url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except requests.exceptions.RequestException as e:
        print(f"Error checking existing transaction: {e}")
        return None

def get_transaction_by_plaid_id(plaid_transaction_id):
    """Check if a transaction already exists using Plaid's unique transaction ID"""
    base_url = f"{SUPABASE_URL}/rest/v1/transactions"
    params = {
        "plaid_transaction_id": f"eq.{plaid_transaction_id}"
    }
    try:
        response = requests.get(base_url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except requests.exceptions.RequestException as e:
        print(f"Error checking existing transaction by Plaid ID: {e}")
        return None

def insert_subscription(subscription_data):
    """Insert subscription into subscriptions table"""
    url = f"{SUPABASE_URL}/rest/v1/subscriptions"
    try:
        response = requests.post(url, json=subscription_data, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Subscription insertion error: {e}")
        return None

def insert_forecast(forecast_data):
    """Insert forecast data into forecasts table"""
    url = f"{SUPABASE_URL}/rest/v1/forecasts"
    try:
        response = requests.post(url, json=forecast_data, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Forecast insertion error: {e}")
        return None

def get_latest_forecast():
    """Fetch the latest forecast from the forecasts table"""
    url = f"{SUPABASE_URL}/rest/v1/forecasts?order=id.desc&limit=1"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest forecast: {e}")
        return None
