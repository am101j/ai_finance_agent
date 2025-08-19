from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
import plaid
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
from supadata import insert_account, insert_transactions, get_account_by_name_type, get_transaction_by_details, get_transaction_by_plaid_id #, get_all_transactions, get_all_accounts
from forecast_agent import forecast_overall_spending
from subscription_agent import run_subscription_analysis
from finance_orchestrator import run_finance_analysis, run_chat_analysis
from fastapi.responses import JSONResponse


class ExchangeTokenRequest(BaseModel):
    public_token: str

class GetTransactionsRequest(BaseModel):
    access_token: str

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configuration = Configuration(
    host=plaid.Environment.Sandbox,
    api_key={
        'clientId': os.getenv("PLAID_CLIENT_ID"),
        'secret': os.getenv("PLAID_SECRET")
    }
)
api_client = ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

@app.post("/api/create_link_token")
def create_link_token():
    try:
        request = LinkTokenCreateRequest(
            products=[Products('transactions')],
            client_name="Finance Assistant",
            country_codes=[CountryCode('US')],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="user-id-123")
        )

        response = client.link_token_create(request)
        return {"link_token": response['link_token']}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/exchange_token")
async def exchange_token(request: ExchangeTokenRequest):
    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=request.public_token)
        response = client.item_public_token_exchange(exchange_request)
        return {"access_token": response['access_token']}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/get_transactions")
async def get_transactions(request: GetTransactionsRequest):
    try:
        start_date = (datetime.now() - timedelta(days=300)).date()  
        end_date = datetime.now().date()
        transactions_request = TransactionsGetRequest(
            access_token=request.access_token,
            start_date=start_date,
            end_date=end_date
        )

        response = client.transactions_get(transactions_request)
        data = response.to_dict()
        
        # Convert date objects to strings for JSON serialization
        for transaction in data.get("transactions", []):
            if 'date' in transaction and hasattr(transaction['date'], 'strftime'):
                transaction['date'] = transaction['date'].strftime('%Y-%m-%d')

        # Process accounts from Plaid API response
        accounts_inserted = 0
        account_mapping = {}  # Map Plaid IDs to database IDs
        
        for account in data.get("accounts", []):
            # Check if account already exists
            existing_account = get_account_by_name_type(account.get('name', f"{account['type']} {account['subtype']}"), account["type"])
            if existing_account:
                account_mapping[account["account_id"]] = existing_account['id']
                print(f"Account already exists: {existing_account['name']}")
            else:
                account_data = {
                    "name": account.get('name', f"{account['type']} {account['subtype']}"),
                    "type": account["type"],
                    "balance": account.get('balances', {}).get('current', 0)
                }
                result = insert_account(account_data)
                if result and isinstance(result, list) and len(result) > 0:
                    account_mapping[account["account_id"]] = result[0].get('id')
                    accounts_inserted += 1
                else:
                    print(f"Failed to insert account: {account_data}")
            
        # Process transactions from Plaid API response
        transactions_inserted = 0
        for transaction in data.get("transactions", []):
            db_account_id = account_mapping.get(transaction["account_id"])
            if db_account_id:
                # Check if transaction already exists using Plaid transaction ID (primary check)
                plaid_transaction_id = transaction.get("transaction_id")
                existing_transaction = get_transaction_by_plaid_id(plaid_transaction_id) if plaid_transaction_id else None
                
                # Fallback to old method if Plaid ID check fails or doesn't exist
                if not existing_transaction:
                    existing_transaction = get_transaction_by_details(db_account_id, transaction["name"], transaction["date"], transaction["amount"])
                
                if existing_transaction:
                    print(f"Transaction already exists: {transaction['name']} on {transaction['date']} (Plaid ID: {plaid_transaction_id})")
                else:
                    # Extract category information
                    category = None
                    if transaction.get('category'):
                        category = ' > '.join(transaction['category'])
                    elif transaction.get('personal_finance_category'):
                        pfc = transaction['personal_finance_category']
                        category = f"{pfc.get('primary', '')} > {pfc.get('detailed', '')}"
                    
                    trans_data = {
                        "account_id": db_account_id,
                        "description": transaction["name"],
                        "date": transaction["date"],
                        "amount": transaction["amount"],
                        "category": category or "Uncategorized",
                        "plaid_transaction_id": plaid_transaction_id  # Store Plaid's unique ID
                    }
                    result = insert_transactions(trans_data)
                    if result:
                        transactions_inserted += 1
                    else:
                        print(f"Failed to insert transaction: {trans_data}")
            else:
                print(f"No account mapping found for transaction: {transaction['account_id']}")
        
        # Add database insertion status to response
        data["database_status"] = {
            "accounts_inserted": accounts_inserted,
            "transactions_inserted": transactions_inserted,
            "total_accounts": len(data.get("accounts", [])),
            "total_transactions": len(data.get("transactions", []))
        }
        
        return data
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/get_recurring_transactions")
async def get_recurring_transactions(request: GetTransactionsRequest):
    try:
        recurring_request = TransactionsRecurringGetRequest(
            access_token=request.access_token
        )
        response = client.transactions_recurring_get(recurring_request)
        return response.to_dict()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/get_categories")
async def get_categories():
    try:
        response = client.categories_get({})
        return response.to_dict()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/forecast_spending")
async def forecast_spending():
    """Time series forecasting for spending by category"""
    return forecast_overall_spending()

@app.get("/api/identify_subscriptions")
async def identify_subscriptions():
    """AI agent identifies recurring subscriptions from transaction data"""
    return run_subscription_analysis()

@app.post("/api/analyze_finances")
async def analyze_finances(request: dict = None):
    """Run complete AI finance analysis workflow"""
    user_query = request.get("query", "Analyze my finances") if request else "Analyze my finances"
    return run_finance_analysis(user_query)

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Chat with the financial AI agent using optimized orchestrator."""
    try:
        data = await request.json()
        user_query = data.get("query", "Hello")  # default if none provided
        state_result = run_chat_analysis(user_query=user_query)
        chat_response = state_result.get("chat_response", "")
        return JSONResponse({"response": chat_response})
    except Exception as e:
        return JSONResponse({"error": str(e)})

@app.get("/api/analyze_expenses")
async def analyze_expenses(query: str = "biggest expenses", days: int = 30):
    """Intelligent expense analysis using AI agent"""
    try:
        from intelligent_agent import query_finance_agent
        response = query_finance_agent(f"Analyze my {query} for the last {days} days")
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}




