from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from typing import TypedDict, List
import requests
import os
from dotenv import load_dotenv
import json
from supadata import insert_subscription

load_dotenv()

class AgentState(TypedDict):
    transactions: List[dict]
    analysis: str
    subscriptions: List[dict]

def get_transactions(state: AgentState) -> AgentState:
    """Fetch transactions from database"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    response = requests.get(f"{supabase_url}/rest/v1/transactions?order=date.desc", headers=headers)
    state["transactions"] = response.json()
    return state

def analyze_subscriptions(state: AgentState) -> AgentState:
    """AI agent analyzes transactions to identify subscriptions"""
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Prepare transaction data for AI
    tx_summary = []
    for tx in state["transactions"][:50]:  # Limit for token efficiency
        tx_summary.append({
            "description": tx["description"],
            "amount": tx["amount"],
            "date": tx["date"]
        })
    
    messages = [
        SystemMessage(content="""You are a financial AI agent that identifies recurring subscriptions from transaction data.

Analyze the transactions and identify patterns that indicate subscriptions:
- Regular recurring charges (monthly, yearly)
- Consistent amounts from same merchants
- Common subscription services (Netflix, Spotify, gym memberships, etc.)

DO NOT INCLUDE:
- Rent payments or housing costs
- Credit card payments
- Transfers or savings
- Utilities or bills

Return a JSON array of subscriptions with this format:
[
  {
    "merchant": "NETFLIX.COM",
    "amount": 15.99,
  }
]

Only include high-confidence subscriptions with clear recurring patterns."""),
        HumanMessage(content=f"Analyze these transactions for subscriptions:\n{json.dumps(tx_summary, indent=2)}")
    ]
    
    response = llm.invoke(messages)
    state["analysis"] = response.content
    
    # Parse AI response
    try:
        # Extract JSON from response
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        subscriptions = json.loads(content.strip())
        print(f"AI found {len(subscriptions)} subscriptions: {subscriptions}")
        
        # Save each subscription to database (check for duplicates)
        for sub in subscriptions:
            # Check if subscription already exists
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
            
            existing = requests.get(
                f"{supabase_url}/rest/v1/subscriptions?merchant=eq.{sub.get('merchant')}",
                headers=headers
            ).json()
            
            # Skip rent and other excluded items
            merchant = sub.get("merchant", "").upper()
            if any(word in merchant for word in ["RENT", "CREDIT CARD", "TRANSFER", "PAYMENT"]):
                continue
                
            if not existing:  # Only insert if doesn't exist
                try:
                    insert_subscription(
                        merchant=sub.get("merchant"),
                        amount=sub.get("amount"),
                        status="active",
                        user_id="00000000-0000-0000-0000-000000000000"  # Placeholder
                    )
                except Exception as e:
                    print(f"Could not save subscription to database: {e}")
        
        state["subscriptions"] = subscriptions
    except:
        state["subscriptions"] = []
    
    return state

def create_subscription_agent():
    """Create the LangGraph agent"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("get_transactions", get_transactions)
    workflow.add_node("analyze_subscriptions", analyze_subscriptions)
    
    workflow.set_entry_point("get_transactions")
    workflow.add_edge("get_transactions", "analyze_subscriptions")
    workflow.add_edge("analyze_subscriptions", END)
    
    return workflow.compile()

def run_subscription_analysis():
    """Run the subscription analysis agent"""
    try:
        agent = create_subscription_agent()
        result = agent.invoke({"transactions": [], "analysis": "", "subscriptions": []})
        
        total_monthly = sum(sub.get("amount", 0) for sub in result["subscriptions"] if sub.get("frequency") == "monthly")
        
        return {
            "subscriptions": result["subscriptions"],
            "total_monthly_cost": round(total_monthly, 2),
            "subscription_count": len(result["subscriptions"]),
            "ai_analysis": result["analysis"]
        }
    except Exception as e:
        return {"error": str(e)}
