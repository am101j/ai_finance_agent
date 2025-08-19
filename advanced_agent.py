from langchain_groq import ChatGroq
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import Tool
from langchain.prompts import PromptTemplate
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd

load_dotenv()

class AdvancedFinanceAgent:
    def __init__(self):
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}"
        }

    def get_transactions_tool(self, days: str = "30") -> str:
        """Get transactions from database for analysis"""
        try:
            days = int(days)
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&order=date.desc&limit=500"
            response = requests.get(url, headers=self.headers)
            transactions = response.json() if response.status_code == 200 else []
            return json.dumps(transactions)
        except Exception as e:
            return f"Error: {str(e)}"

    def find_subscriptions_tool(self, min_occurrences: str = "2") -> str:
        """Find recurring subscriptions by analyzing transaction patterns"""
        try:
            min_occ = int(min_occurrences)
            transactions = json.loads(self.get_transactions_tool("90"))
            
            # Group by merchant and amount
            patterns = defaultdict(list)
            for tx in transactions:
                amount = abs(float(tx['amount']))
                if amount > 0:  # Only expenses
                    key = f"{tx['description']}_{amount}"
                    patterns[key].append({
                        'date': tx['date'],
                        'amount': amount,
                        'description': tx['description']
                    })
            
            # Find recurring patterns
            subscriptions = []
            for key, txs in patterns.items():
                if len(txs) >= min_occ:
                    # Check if amounts are consistent
                    amounts = [tx['amount'] for tx in txs]
                    if len(set(amounts)) <= 2:  # Allow slight variation
                        dates = [datetime.strptime(tx['date'], '%Y-%m-%d') for tx in txs]
                        dates.sort()
                        
                        # Calculate average interval
                        if len(dates) > 1:
                            intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                            avg_interval = sum(intervals) / len(intervals)
                            
                            frequency = "Monthly" if 25 <= avg_interval <= 35 else \
                                       "Weekly" if 6 <= avg_interval <= 8 else \
                                       "Yearly" if 350 <= avg_interval <= 380 else \
                                       f"Every {avg_interval:.0f} days"
                            
                            subscriptions.append({
                                'merchant': txs[0]['description'],
                                'amount': txs[0]['amount'],
                                'frequency': frequency,
                                'occurrences': len(txs),
                                'last_charge': max(tx['date'] for tx in txs),
                                'avg_interval_days': avg_interval
                            })
            
            return json.dumps(sorted(subscriptions, key=lambda x: x['amount'], reverse=True))
        except Exception as e:
            return f"Error: {str(e)}"

    def analyze_spending_tool(self, days: str = "30", group_by: str = "category") -> str:
        """Analyze spending patterns by category or merchant"""
        try:
            days = int(days)
            transactions = json.loads(self.get_transactions_tool(str(days)))
            
            groups = defaultdict(lambda: {'total': 0, 'count': 0, 'transactions': []})
            total_spending = 0
            
            for tx in transactions:
                amount = float(tx['amount'])
                if amount > 0:  # Only expenses
                    key = tx.get('category', 'Uncategorized') if group_by == 'category' else tx['description']
                    groups[key]['total'] += amount
                    groups[key]['count'] += 1
                    groups[key]['transactions'].append({
                        'description': tx['description'],
                        'amount': amount,
                        'date': tx['date']
                    })
                    total_spending += amount
            
            # Sort and add percentages
            result = {}
            for key, data in groups.items():
                result[key] = {
                    'total': round(data['total'], 2),
                    'count': data['count'],
                    'percentage': round((data['total'] / total_spending * 100) if total_spending > 0 else 0, 1),
                    'avg_transaction': round(data['total'] / data['count'], 2),
                    'top_transactions': sorted(data['transactions'], key=lambda x: x['amount'], reverse=True)[:3]
                }
            
            return json.dumps({
                'total_spending': round(total_spending, 2),
                'period_days': days,
                'groups': dict(sorted(result.items(), key=lambda x: x[1]['total'], reverse=True))
            })
        except Exception as e:
            return f"Error: {str(e)}"

    def forecast_spending_tool(self, method: str = "average", periods: str = "7") -> str:
        """Forecast future spending using different methods"""
        try:
            periods = int(periods)
            transactions = json.loads(self.get_transactions_tool("84"))  # 12 weeks of data
            
            # Group by day
            daily_spending = defaultdict(float)
            for tx in transactions:
                if float(tx['amount']) > 0:
                    daily_spending[tx['date']] += float(tx['amount'])
            
            if not daily_spending:
                return json.dumps({'error': 'No spending data found'})
            
            # Convert to time series
            df = pd.DataFrame(list(daily_spending.items()), columns=['date', 'amount'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            if method == "average":
                # Simple average method
                avg_daily = df['amount'].mean()
                forecast = avg_daily * periods
                
            elif method == "trend":
                # Linear trend method
                df['days'] = (df['date'] - df['date'].min()).dt.days
                slope = df[['days', 'amount']].corr().iloc[0, 1] * df['amount'].std() / df['days'].std()
                intercept = df['amount'].mean() - slope * df['days'].mean()
                
                future_days = df['days'].max() + periods
                forecast = intercept + slope * future_days
                
            else:  # weekly_pattern
                # Use weekly pattern
                df['weekday'] = df['date'].dt.dayofweek
                weekly_avg = df.groupby('weekday')['amount'].mean()
                
                forecast = 0
                for i in range(periods):
                    future_date = datetime.now() + timedelta(days=i+1)
                    weekday = future_date.weekday()
                    forecast += weekly_avg.get(weekday, weekly_avg.mean())
            
            return json.dumps({
                'forecast_amount': round(max(0, forecast), 2),
                'forecast_periods': periods,
                'method': method,
                'confidence': 'medium' if len(df) > 30 else 'low',
                'daily_average': round(df['amount'].mean(), 2)
            })
        except Exception as e:
            return f"Error: {str(e)}"

    def search_transactions_tool(self, query: str, days: str = "30") -> str:
        """Search transactions by description, category, or amount"""
        try:
            days = int(days)
            transactions = json.loads(self.get_transactions_tool(str(days)))
            
            query_lower = query.lower()
            matches = []
            
            for tx in transactions:
                if (query_lower in tx['description'].lower() or 
                    query_lower in tx.get('category', '').lower() or
                    query in str(tx['amount'])):
                    matches.append(tx)
            
            return json.dumps(matches[:20])  # Limit results
        except Exception as e:
            return f"Error: {str(e)}"

    def create_agent(self):
        """Create the advanced agent with tools"""
        tools = [
            Tool(
                name="get_transactions",
                func=self.get_transactions_tool,
                description="Get transactions from database. Input: number of days (default 30)"
            ),
            Tool(
                name="find_subscriptions", 
                func=self.find_subscriptions_tool,
                description="Find recurring subscriptions. Input: minimum occurrences (default 2)"
            ),
            Tool(
                name="analyze_spending",
                func=self.analyze_spending_tool,
                description="Analyze spending by category or merchant. Input: 'days,group_by' (e.g., '30,category')"
            ),
            Tool(
                name="forecast_spending",
                func=self.forecast_spending_tool,
                description="Forecast future spending. Input: 'method,periods' (e.g., 'average,7' for 7-day forecast)"
            ),
            Tool(
                name="search_transactions",
                func=self.search_transactions_tool,
                description="Search transactions. Input: 'search_query,days' (e.g., 'netflix,30')"
            )
        ]

        prompt = PromptTemplate.from_template("""
You are an advanced financial AI agent with access to real transaction data. Answer user questions by using the appropriate tools.

Available tools:
{tools}

Tool names: {tool_names}

When answering:
1. Use tools to get real data
2. Provide specific numbers and insights
3. Give actionable recommendations
4. Format responses clearly with emojis

Question: {input}
{agent_scratchpad}
""")

        agent = create_react_agent(self.llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=3, handle_parsing_errors=True)

def query_advanced_agent(question: str) -> str:
    """Query the advanced finance agent"""
    try:
        agent_system = AdvancedFinanceAgent()
        agent = agent_system.create_agent()
        result = agent.invoke({"input": question})
        return result["output"]
    except Exception as e:
        return f"I encountered an error: {str(e)}. Please try rephrasing your question."