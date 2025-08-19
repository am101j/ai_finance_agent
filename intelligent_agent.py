from langchain_groq import ChatGroq
from langchain.tools import tool
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import pandas as pd

load_dotenv()

class FinanceAgent:
    def __init__(self):
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}"
        }

    @tool
    def get_transactions(self, days: int = 30, limit: int = 1000) -> str:
        """Get recent transactions from database with categories"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&order=date.desc&limit={limit}"
            response = requests.get(url, headers=self.headers)
            transactions = response.json() if response.status_code == 200 else []
            return json.dumps(transactions)
        except Exception as e:
            return f"Error fetching transactions: {str(e)}"

    @tool
    def analyze_spending_by_category(self, days: int = 30) -> str:
        """Analyze spending grouped by existing categories in database"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&amount=gt.0"
            response = requests.get(url, headers=self.headers)
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
    def get_biggest_expenses(self, days: int = 30, limit: int = 10) -> str:
        """Get the largest individual expenses"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&amount=gt.0&order=amount.desc&limit={limit}"
            response = requests.get(url, headers=self.headers)
            transactions = response.json() if response.status_code == 200 else []
            return json.dumps(transactions)
        except Exception as e:
            return f"Error fetching biggest expenses: {str(e)}"

    @tool
    def get_spending_trends(self, days: int = 90) -> str:
        """Analyze spending trends over time"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&amount=gt.0&order=date.asc"
            response = requests.get(url, headers=self.headers)
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
    def search_transactions(self, query: str, days: int = 30) -> str:
        """Search transactions by description or category"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&or=(description.ilike.%{query}%,category.ilike.%{query}%)&order=date.desc"
            response = requests.get(url, headers=self.headers)
            transactions = response.json() if response.status_code == 200 else []
            return json.dumps(transactions)
        except Exception as e:
            return f"Error searching transactions: {str(e)}"

    def create_agent(self):
        """Create the intelligent finance agent"""
        tools = [
            self.get_transactions,
            self.analyze_spending_by_category,
            self.get_biggest_expenses,
            self.get_spending_trends,
            self.search_transactions
        ]

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an intelligent financial advisor AI agent. You have access to real-time financial data through tools.

When users ask about their finances:
1. Use the appropriate tools to fetch current data
2. Analyze the data intelligently 
3. Provide actionable insights and recommendations
4. Be specific with numbers, percentages, and trends
5. Suggest concrete actions to improve their financial situation

Always use the actual data from the database, never make assumptions or use hardcoded values."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        agent = create_openai_functions_agent(self.llm, tools, prompt)
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
        return f"Error: {str(e)}"