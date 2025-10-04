from langchain_groq import ChatGroq
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()

def query_working_agent(question: str) -> str:
    """Simple working agent that actually responds"""
    try:
        # Get data from Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        
        # Get recent transactions
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        url = f"{supabase_url}/rest/v1/transactions?date=gte.{cutoff_date}&order=date.desc&limit=100"
        response = requests.get(url, headers=headers)
        transactions = response.json() if response.status_code == 200 else []
        
        # Analyze based on question
        question_lower = question.lower()
        
        if 'subscription' in question_lower:
            return analyze_subscriptions(transactions)
        elif 'forecast' in question_lower or 'next week' in question_lower:
            return forecast_spending(transactions)
        elif 'biggest' in question_lower or 'expense' in question_lower:
            return analyze_biggest_expenses(transactions)
        elif 'trend' in question_lower:
            return analyze_trends(transactions)
        else:
            return general_analysis(transactions)
            
    except Exception as e:
        return f"Error analyzing your finances: {str(e)}"

def analyze_subscriptions(transactions):
    """Find recurring subscriptions"""
    patterns = defaultdict(list)
    
    for tx in transactions:
        amount = abs(float(tx['amount']))
        if amount > 0:
            key = f"{tx['description']}_{amount}"
            patterns[key].append(tx['date'])
    
    subscriptions = []
    for key, dates in patterns.items():
        if len(dates) >= 2:
            desc, amount = key.rsplit('_', 1)
            subscriptions.append({
                'merchant': desc,
                'amount': float(amount),
                'frequency': len(dates)
            })
    
    if subscriptions:
        result = "🔄 **Your Subscriptions:**\n"
        for sub in sorted(subscriptions, key=lambda x: x['amount'], reverse=True)[:5]:
            result += f"• {sub['merchant']}: ${sub['amount']:.2f} ({sub['frequency']} charges)\n"
        return result
    return "No recurring subscriptions found in your recent transactions."

def forecast_spending(transactions):
    """Simple spending forecast"""
    daily_spending = defaultdict(float)
    
    for tx in transactions:
        if float(tx['amount']) > 0:
            daily_spending[tx['date']] += float(tx['amount'])
    
    if daily_spending:
        avg_daily = sum(daily_spending.values()) / len(daily_spending)
        weekly_forecast = avg_daily * 7
        return f"📈 **Next Week Forecast:** ${weekly_forecast:.2f}\n(Based on ${avg_daily:.2f} average daily spending)"
    
    return "Not enough spending data for forecast."

def analyze_biggest_expenses(transactions):
    """Find biggest expenses"""
    expenses = []
    categories = defaultdict(float)
    
    for tx in transactions:
        amount = float(tx['amount'])
        if amount > 0:
            expenses.append({
                'description': tx['description'],
                'amount': amount,
                'date': tx['date']
            })
            categories[tx.get('category', 'Uncategorized')] += amount
    
    expenses.sort(key=lambda x: x['amount'], reverse=True)
    
    result = "💰 **Biggest Expenses (Last 30 days):**\n"
    for i, exp in enumerate(expenses[:5], 1):
        result += f"{i}. ${exp['amount']:.2f} - {exp['description']} ({exp['date']})\n"
    
    result += "\n📊 **Top Categories:**\n"
    for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]:
        result += f"• {cat}: ${amount:.2f}\n"
    
    return result

def analyze_trends(transactions):
    """Analyze spending trends"""
    weekly_spending = defaultdict(float)
    
    for tx in transactions:
        if float(tx['amount']) > 0:
            tx_date = datetime.strptime(tx['date'], '%Y-%m-%d')
            week = tx_date.strftime('%Y-W%U')
            weekly_spending[week] += float(tx['amount'])
    
    weeks = sorted(weekly_spending.items())
    
    if len(weeks) >= 2:
        recent_avg = sum(week[1] for week in weeks[-2:]) / 2
        older_avg = sum(week[1] for week in weeks[:-2]) / max(1, len(weeks) - 2)
        
        trend = "increasing" if recent_avg > older_avg else "decreasing"
        change = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        result = f"📈 **Spending Trends:**\n"
        result += f"• Trend: {trend.upper()} ({change:+.1f}%)\n"
        result += f"• Recent weekly average: ${recent_avg:.2f}\n"
        result += f"• Previous average: ${older_avg:.2f}\n"
        
        return result
    
    return "Not enough data for trend analysis."

def general_analysis(transactions):
    """General financial summary"""
    total_spending = sum(float(tx['amount']) for tx in transactions if float(tx['amount']) > 0)
    transaction_count = len([tx for tx in transactions if float(tx['amount']) > 0])
    
    if transaction_count > 0:
        avg_transaction = total_spending / transaction_count
        
        result = f"📊 **Financial Summary (Last 30 days):**\n"
        result += f"• Total Spending: ${total_spending:.2f}\n"
        result += f"• Number of Transactions: {transaction_count}\n"
        result += f"• Average Transaction: ${avg_transaction:.2f}\n"
        
        return result
    
    return "No recent transactions found."