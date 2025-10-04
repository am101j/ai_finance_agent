from langchain_groq import ChatGroq
from langchain.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import pandas as pd
from functools import lru_cache
from supadata import get_latest_forecast

load_dotenv()

# Global variables for database connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

@tool
def get_transactions(days: int = 30, limit: int = 1000) -> str:
    """Get recent transactions from database with categories"""
    try:
        # Use August 15, 2024 as reference date
        reference_date = datetime(2025, 8, 15)
        cutoff_date = (reference_date - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = reference_date.strftime('%Y-%m-%d')
        url = f"{SUPABASE_URL}/rest/v1/transactions?date=gte.{cutoff_date}&date=lte.{end_date}&order=date.desc&limit={limit}"
        response = requests.get(url, headers=HEADERS)
        transactions = response.json() if response.status_code == 200 else []
        return json.dumps(transactions)
    except Exception as e:
        return f"Error fetching transactions: {str(e)}"

@tool
def analyze_spending_by_category(days: int = 30) -> str:
    """Analyze spending grouped by existing categories in database"""
    try:
        reference_date = datetime(2024, 8, 15)
        cutoff_date = (reference_date - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = reference_date.strftime('%Y-%m-%d')
        url = f"{SUPABASE_URL}/rest/v1/transactions?date=gte.{cutoff_date}&date=lte.{end_date}&amount=gt.0"
        response = requests.get(url, headers=HEADERS)
        transactions = response.json() if response.status_code == 200 else []
        
        # Group by category
        category_totals = {}
        total_spending = 0
        
        for tx in transactions:
            category = tx.get('category', 'Uncategorized')
            amount = float(tx['amount'])
            total_spending += amount
            
            if category not in category_totals:
                category_totals[category] = {'total': 0, 'count': 0, 'transactions': []}
            
            category_totals[category]['total'] += amount
            category_totals[category]['count'] += 1
            category_totals[category]['transactions'].append({
                'description': tx['description'],
                'amount': amount,
                'date': tx['date']
            })
        
        # Sort by total spending
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1]['total'], reverse=True)
        
        result = {
            'total_spending': total_spending,
            'period_days': days,
            'categories': {}
        }
        
        for category, data in sorted_categories:
            result['categories'][category] = {
                'total': data['total'],
                'count': data['count'],
                'percentage': (data['total'] / total_spending * 100) if total_spending > 0 else 0,
                'top_transactions': sorted(data['transactions'], key=lambda x: x['amount'], reverse=True)[:3]
            }
        
        return json.dumps(result)
    except Exception as e:
        return f"Error analyzing spending: {str(e)}"

@tool
def get_biggest_expenses(days: int = 30, limit: int = 10) -> str:
    """Get the largest individual expenses"""
    try:
        # First try all transactions to see if any exist
        url = f"{SUPABASE_URL}/rest/v1/transactions?amount=gt.0&order=amount.desc&limit={limit}"
        response = requests.get(url, headers=HEADERS)
        transactions = response.json() if response.status_code == 200 else []
        
        # Debug info
        debug_info = {
            "status_code": response.status_code,
            "transaction_count": len(transactions),
            "url": url
        }
        
        return json.dumps({"transactions": transactions, "debug": debug_info})
    except Exception as e:
        return f"Error fetching biggest expenses: {str(e)}"

@tool
def get_spending_trends(days: int = 90) -> str:
    """Analyze spending trends over time"""
    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        url = f"{SUPABASE_URL}/rest/v1/transactions?date=gte.{cutoff_date}&amount=gt.0&order=date.asc"
        response = requests.get(url, headers=HEADERS)
        transactions = response.json() if response.status_code == 200 else []
        
        # Group by week
        weekly_spending = {}
        for tx in transactions:
            tx_date = datetime.strptime(tx['date'], '%Y-%m-%d')
            week_start = tx_date - timedelta(days=tx_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            
            if week_key not in weekly_spending:
                weekly_spending[week_key] = 0
            weekly_spending[week_key] += float(tx['amount'])
        
        # Calculate trend
        weeks = sorted(weekly_spending.items())
        if len(weeks) >= 4:
            recent_avg = sum(week[1] for week in weeks[-2:]) / 2
            older_avg = sum(week[1] for week in weeks[:2]) / 2
            trend_direction = "increasing" if recent_avg > older_avg else "decreasing"
            trend_percentage = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            trend_direction = "insufficient_data"
            trend_percentage = 0
        
        return json.dumps({
            'weekly_spending': weeks,
            'trend_direction': trend_direction,
            'trend_percentage': trend_percentage,
            'total_weeks': len(weeks)
        })
    except Exception as e:
        return f"Error analyzing trends: {str(e)}"

@tool
def search_transactions(query: str, days: int = 30) -> str:
    """Search transactions by description or category"""
    try:
        reference_date = datetime(2024, 8, 15)
        cutoff_date = (reference_date - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = reference_date.strftime('%Y-%m-%d')
        url = f"{SUPABASE_URL}/rest/v1/transactions?date=gte.{cutoff_date}&date=lte.{end_date}&or=(description.ilike.%{query}%,category.ilike.%{query}%)&order=date.desc"
        response = requests.get(url, headers=HEADERS)
        transactions = response.json() if response.status_code == 200 else []
        return json.dumps(transactions)
    except Exception as e:
        return f"Error searching transactions: {str(e)}"

@tool
def get_subscriptions() -> str:
    """Get all subscriptions from the subscriptions table"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/subscriptions?order=amount.desc"
        response = requests.get(url, headers=HEADERS)
        subscriptions = response.json() if response.status_code == 200 else []
        return json.dumps(subscriptions)
    except Exception as e:
        return f"Error fetching subscriptions: {str(e)}"

@tool
def analyze_and_save_subscriptions() -> str:
    """Analyze transactions to identify and save new subscriptions"""
    try:
        from subscription_agent import run_subscription_analysis
        result = run_subscription_analysis()
        return json.dumps(result)
    except Exception as e:
        return f"Error analyzing subscriptions: {str(e)}"

@tool
def get_spending_forecast() -> str:
    """Get the latest spending forecast from the database."""
    try:
        forecast_data = get_latest_forecast()
        if not forecast_data:
            return "No forecast available."
        
        # Handle both string and dict cases for weekly_breakdown
        weekly_breakdown = forecast_data.get("weekly_breakdown")
        if isinstance(weekly_breakdown, str):
            import json
            weekly_breakdown = json.loads(weekly_breakdown)
        
        if not weekly_breakdown or not isinstance(weekly_breakdown, list):
            return "No forecast available."

        next_week_forecast = weekly_breakdown[0].get('total', 0) if weekly_breakdown else 0
        return f"Next week: ${next_week_forecast:.2f}"

    except Exception as e:
        return "No forecast available."

class FinanceAgent:
    def __init__(self):
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

    def create_agent(self):
        """Create the intelligent finance agent"""
        tools = [
            get_transactions,
            analyze_spending_by_category,
            get_biggest_expenses,
            get_spending_trends,
            search_transactions,
            get_subscriptions,
            get_spending_forecast
        ]

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an intelligent financial advisor AI agent. You have access to real-time financial data through tools.

When users ask about their finances:
1. Use the appropriate tools to fetch current data
2. If you use get_spending_forecast, STOP and provide that answer - do not call any other tools
3. Keep responses SHORT and CONCISE - provide only essential information
4. If tools return empty data [], inform the user they need to connect their bank account first
5. NEVER make up fake data or provide example numbers
6. Only analyze actual data from the database

CRITICAL: Never invent or assume financial data. Only use actual results from tools."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        agent = create_tool_calling_agent(self.llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)

def create_finance_agent():
    """Factory function to create finance agent"""
    finance_agent = FinanceAgent()
    return finance_agent.create_agent()

def query_finance_agent(question: str):
    """Query the finance agent with a question"""
    try:
        agent = create_finance_agent()
        result = agent.invoke({
            "input": question,
            "chat_history": []
        })
        return result["output"]
    except Exception as e:
        print(f"Agent error: {str(e)}")  # Debug print
        return f"I encountered an error: {str(e)}. Please try again."
