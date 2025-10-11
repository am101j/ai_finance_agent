from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from auth import get_current_user, get_user_id, security
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
from finance_orchestrator import run_finance_analysis
from fastapi.responses import JSONResponse


class ExchangeTokenRequest(BaseModel):
    public_token: str

class GetTransactionsRequest(BaseModel):
    access_token: str

class AuthRequest(BaseModel):
    email: str
    password: str

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

@app.post("/api/auth/signup")
async def signup(request: AuthRequest):
    try:
        from supabase import create_client
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        response = supabase.auth.sign_up({"email": request.email, "password": request.password})
        return {"user": response.user, "session": response.session}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/auth/login")
async def login(request: AuthRequest):
    try:
        from supabase import create_client
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        response = supabase.auth.sign_in_with_password({"email": request.email, "password": request.password})
        return {"user": response.user, "session": response.session}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/create_link_token")
def create_link_token(user_id: str = Depends(get_user_id)):
    try:
        request = LinkTokenCreateRequest(
            products=[Products('transactions')],
            client_name="Finance Assistant",
            country_codes=[CountryCode('US')],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=user_id)
        )

        response = client.link_token_create(request)
        return {"link_token": response['link_token']}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/exchange_token")
async def exchange_token(request: ExchangeTokenRequest, user_id: str = Depends(get_user_id)):
    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=request.public_token)
        response = client.item_public_token_exchange(exchange_request)
        return {"access_token": response['access_token']}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/get_transactions")
async def get_transactions(request: GetTransactionsRequest, user_id: str = Depends(get_user_id), credentials: HTTPAuthorizationCredentials = Depends(security)):
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
            existing_account = get_account_by_name_type(account.get('name', f"{account['type']} {account['subtype']}"), account["type"], credentials.credentials)
            if existing_account:
                account_mapping[account["account_id"]] = existing_account['id']
                print(f"Account already exists: {existing_account['name']}")
            else:
                account_data = {
                    "name": account.get('name', f"{account['type']} {account['subtype']}"),
                    "type": account["type"],
                    "balance": account.get('balances', {}).get('current', 0)
                }
                auth_token = credentials.credentials
                print(f"Inserting account with user_id: {user_id}, auth_token: {auth_token[:20]}...")
                result = insert_account(account_data, user_id, auth_token)
                print(f"Insert account result: {result}")
                if result and isinstance(result, list) and len(result) > 0:
                    account_mapping[account["account_id"]] = result[0].get('id')
                    accounts_inserted += 1
                    print(f"Account inserted successfully: {result[0].get('id')}")
                else:
                    print(f"Failed to insert account: {account_data}")
                    print(f"Result type: {type(result)}, Result: {result}")
            
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
                    print(f"Transaction amount: {transaction['amount']} for {transaction['name']}")
                    result = insert_transactions(trans_data, user_id, auth_token)
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
        
        print(f"Final status: {accounts_inserted} accounts, {transactions_inserted} transactions inserted")
        
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
    try:
        result = forecast_overall_spending()
        print(f"Forecast result: {result}")
        return result
    except Exception as e:
        print(f"Forecast error: {e}")
        return {"total_forecast": 0, "avg_daily_forecast": 0, "historical_avg_daily": 0, "chart_data": []}

@app.get("/api/identify_subscriptions")
async def identify_subscriptions():
    """AI agent identifies recurring subscriptions from transaction data"""
    return run_subscription_analysis()

@app.post("/api/analyze_finances")
async def analyze_finances(request: dict = None):
    """Run complete AI finance analysis workflow"""
    try:
        user_query = request.get("query", "Analyze my finances") if request else "Analyze my finances"
        result = run_finance_analysis(user_query)
        print(f"Analysis result: {result}")
        return result
    except Exception as e:
        print(f"Analysis error: {e}")
        return {"error": str(e), "forecast": None, "subscriptions": [], "alerts": []}

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Chat with the advanced intelligent AI agent."""
    try:
        from intelligent_agent import query_finance_agent
        data = await request.json()
        user_query = data.get("query", "Hello")
        response = query_finance_agent(user_query)
        return JSONResponse({"response": response})
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

@app.post("/api/send_email")
async def send_email(request: dict):
    """Send an approved email"""
    try:
        from agent_tools import send_negotiation_email
        
        to_email = request.get("to")
        subject = request.get("subject")
        body = request.get("body")
        
        if not all([to_email, subject, body]):
            return {"error": "Missing required fields: to, subject, body"}
        
        result = send_negotiation_email(to_email, subject, body)
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/spending_categories")
async def get_spending_categories(days: int = 30):
    """Get spending breakdown by Plaid main categories for pie chart (strict, no description-based mapping)"""
    try:
        from datetime import datetime, timedelta
        import requests
        import os

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

        # Fetch transactions from last N days before Aug 15, 2025
        base_date = datetime(2025, 8, 15)
        cutoff_date = (base_date - timedelta(days=days)).strftime('%Y-%m-%d')
        
        print(f"Fetching transactions from {cutoff_date} onwards")
        print(f"Query URL: {supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}")
        
        response = requests.get(
            f"{supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}",
            headers=headers
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text[:500]}...")

        if response.status_code != 200:
            return {"error": "Failed to fetch transactions"}

        transactions = response.json()

        # Categories to exclude (fixed expenses, income, transfers, etc.)
        excluded = [
            "TRANSFER_IN", "TRANSFER_OUT", "LOAN_PAYMENTS", "INCOME", 
            "RENT_AND_UTILITIES", "RENT", "UTILITIES", "INSURANCE", 
            "MORTGAGE", "LOAN", "CREDIT_CARD_PAYMENT"
        ]

        category_totals = {}
        total_spending = 0

        print(f"Found {len(transactions)} transactions")
        
        for tx in transactions:
            amount = float(tx['amount'])
            print(f"Processing: {tx.get('description', 'Unknown')} - Amount: {amount}")
            
            full_category = tx.get('category', 'OTHER')
            main_category = full_category.split(" > ")[0].upper()
            
            print(f"Category: {main_category}, Amount: {amount}")
            
            # Skip income and excluded categories (negative amounts are typically income/credits in Plaid)
            if amount < 0 or main_category in excluded:
                print(f"Skipping - Category: {main_category}, Amount: {amount}")
                continue

            # Positive amounts are expenses in Plaid
            category_totals.setdefault(main_category, 0)
            category_totals[main_category] += amount
            total_spending += amount

        # Convert to chart format
        chart_data = []
        colors = ["#F59E0B", "#EC4899", "#8B5CF6", "#10B981", "#3B82F6", "#EF4444", "#14B8A6", "#A855F7"]
        for i, (name, value) in enumerate(category_totals.items()):
            chart_data.append({
                "name": name,
                "value": round(value, 2),
                "percentage": round((value / total_spending * 100), 1) if total_spending > 0 else 0,
                "fill": colors[i % len(colors)]
            })

        print(f"Total spending calculated: {total_spending}")
        print(f"Categories found: {list(category_totals.keys())}")
        
        return {
            "categories": chart_data,
            "total_spending": round(total_spending, 2),
            "period_days": days
        }

    except Exception as e:
        return {"error": str(e)}

@app.post("/api/cleanup_duplicates")
async def cleanup_duplicates():
    """Remove duplicate transactions based on Plaid transaction ID"""
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        
        # Find duplicates by Plaid transaction ID
        response = requests.get(
            f"{supabase_url}/rest/v1/transactions?select=id,plaid_transaction_id&order=created_at.asc",
            headers=headers
        )
        
        if response.status_code != 200:
            return {"error": "Failed to fetch transactions"}
        
        transactions = response.json()
        seen_plaid_ids = set()
        duplicates_to_delete = []
        
        for tx in transactions:
            plaid_id = tx.get('plaid_transaction_id')
            if plaid_id and plaid_id in seen_plaid_ids:
                duplicates_to_delete.append(tx['id'])
            elif plaid_id:
                seen_plaid_ids.add(plaid_id)
        
        # Delete duplicates
        deleted_count = 0
        for tx_id in duplicates_to_delete:
            delete_response = requests.delete(
                f"{supabase_url}/rest/v1/transactions?id=eq.{tx_id}",
                headers=headers
            )
            if delete_response.status_code == 204:
                deleted_count += 1
        
        return {
            "message": f"Cleanup complete: {deleted_count} duplicate transactions removed",
            "duplicates_found": len(duplicates_to_delete),
            "duplicates_deleted": deleted_count
        }
    except Exception as e:
        return {"error": str(e)}
