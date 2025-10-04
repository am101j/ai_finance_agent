from typing import TypedDict, List, Dict, Any
import requests, os, json
from dotenv import load_dotenv
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from agent_tools import search_web, send_negotiation_email, send_user_alert
from forecast_agent import forecast_overall_spending
from supadata import insert_subscription

load_dotenv()

# -------------------------------
# STATE DEFINITION
# -------------------------------
class FinanceState(TypedDict):
    transactions: List[dict]
    categorized_data: Dict[str, Any]
    forecast_results: Dict[str, Any]
    subscriptions: List[dict]
    alerts: List[str]
    emails: List[dict]
    user_query: str
    chat_response: str

# -------------------------------
# TOOL DEFINITIONS
# -------------------------------
class Tool:
    name: str
    description: str
    def __call__(self, **kwargs) -> Any:
        raise NotImplementedError

class FetchTransactionsTool(Tool):
    name = "fetch_transactions"
    description = "Fetch latest transactions from Supabase."
    def __call__(self) -> List[dict]:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        response = requests.get(f"{supabase_url}/rest/v1/transactions?order=date.desc", headers=headers)
        return response.json()

class ForecastTool(Tool):
    name = "forecast_spending"
    description = "Generate 2-week spending forecast."
    def __call__(self) -> dict:
        return forecast_overall_spending()

class SearchWebTool(Tool):
    name = "search_web"
    description = "Search the web for alternatives or contacts."
    def __call__(self, query: str) -> dict:
        return search_web(query)

class SendNegotiationEmailTool(Tool):
    name = "send_negotiation_email"
    description = "Send a negotiation email to merchant."
    def __call__(self, to_email: str, subject: str, body: str) -> dict:
        return send_negotiation_email(to_email=to_email, subject=subject, body=body)

class SendUserAlertTool(Tool):
    name = "send_user_alert"
    description = "Send alert email to the user."
    def __call__(self, message: str) -> None:
        return send_user_alert(message)

# -------------------------------
# AGENT BASE
# -------------------------------
class Agent:
    role: str
    goal: str
    tools: List[Tool]
    def __init__(self, role: str, goal: str, tools: List[Tool]):
        self.role = role
        self.goal = goal
        self.tools = tools
    def plan(self, state: FinanceState) -> FinanceState:
        raise NotImplementedError

# -------------------------------
# DATA AGENT
# -------------------------------
class DataAgent(Agent):
    def __init__(self):
        
        
        super().__init__(
            role="Data Collector",
            goal="Fetch and categorize latest user transactions.",
            tools=[FetchTransactionsTool()]
        )
    def plan(self, state: FinanceState) -> FinanceState:
        tx_tool = self.tools[0]
        transactions = tx_tool()
        state["transactions"] = transactions
        state["categorized_data"] = {"status": "fetched", "count": len(transactions)}
        return state

# -------------------------------
# FORECAST AGENT
# -------------------------------
class ForecastAgent(Agent):
    def __init__(self):
        super().__init__(
            role="Financial Forecaster",
            goal="Generate short-term spending forecasts.",
            tools=[ForecastTool()]
        )
    def plan(self, state: FinanceState) -> FinanceState:
        forecast_tool = self.tools[0]
        forecast_result = forecast_tool()
        if "forecasted_days" in forecast_result:
            for day in forecast_result.get("forecasted_days", []):
                if 'ds' in day and hasattr(day['ds'], 'strftime'):
                    day['ds'] = day['ds'].strftime('%Y-%m-%d')
        state["forecast_results"] = forecast_result
        return state

# -------------------------------
# AI-POWERED SUBSCRIPTION AGENT
# -------------------------------
class SubscriptionAgent(Agent):
    def __init__(self):
        super().__init__(
            role="Subscription Manager",
            goal="Identify recurring subscriptions and negotiate discounts using AI-powered alternative discovery.",
            tools=[SearchWebTool(), SendNegotiationEmailTool()]
        )
        self.llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)
    
    def plan(self, state: FinanceState) -> FinanceState:
        transactions = state.get("transactions", [])[:40]

        # Step 1: Identify recurring subscriptions
        prompt = f"""
        You are a financial assistant.
        Identify ONLY recurring subscriptions from the following transactions.
        Recurring subscriptions are payments that occur regularly for the same merchant, usually the same amount, weekly or monthly.
        Transactions:
        {json.dumps(transactions)}
        Return strictly JSON:
        {{
            "subscriptions": [
                {{
                    "merchant": "Merchant Name",
                    "amount": 123.45,
                    "frequency": "monthly",
                    "last_payment_date": "YYYY-MM-DD"
                }}
            ]
        }}
        Rent payments do not count as subscriptions.
        """
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        try:
            content = content.replace("```json", "").replace("```", "")
            subscriptions = json.loads(content).get("subscriptions", [])
            
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
                    subscription_data = {
                        "merchant": sub.get("merchant"),
                        "amount": sub.get("amount"),
                    }
                    insert_subscription(subscription_data)

        except Exception as e:
            print(f"Error analyzing subscriptions: {e}")
            subscriptions = []

        for sub in subscriptions:
            search_tool = self.tools[0]
            email_tool = self.tools[1]

            # Step 2: Find alternatives with pricing using AI-powered search
            search_results = search_tool(f"{sub['merchant']} alternatives competitors similar services pricing")
            alternatives = search_results.get("alternatives", [])
            alternatives_with_pricing = search_results.get("alternatives_with_pricing", [])
            
            # Step 3: Generate negotiation email with AI-powered alternative and pricing integration
            email_generation_prompt = f"""
            Write a professional yet friendly email requesting a discount on a subscription.

            Subscription Details:
            - Company: {sub['merchant']}
            - Current Amount: ${sub['amount']}
            - Frequency: {sub['frequency']}

            Available Alternatives with Pricing: {alternatives_with_pricing if alternatives_with_pricing else "None found"}

            Requirements:
            1. 60-90 words, 3-5 sentences
            2. Professional but conversational tone
            3. Mention being a loyal customer and budget consciousness
            4. If alternatives with pricing are available, mention them strategically (e.g., "I've been exploring options like [alternative1] at [price] and [alternative2] at [price]")
            5. If alternatives found but no pricing, mention companies without prices
            6. If no alternatives found, focus on loyalty and budget constraints
            7. Start with "Hi {sub['merchant']} team," 
            8. End with just "Thanks" (no name signature)
            9. Ask for a discount or promotional rate
            10. Use pricing information to create urgency but remain respectful
            11. Don't be overly aggressive with competitor pricing

            Output only the email body text, no subject line or additional formatting.
            """
            
            email_resp = self.llm.invoke([HumanMessage(content=email_generation_prompt)])
            sub["negotiation_email"] = email_resp.content.strip()
            sub["found_alternatives"] = alternatives  # Store for reference
            sub["found_alternatives_with_pricing"] = alternatives_with_pricing  # Store detailed pricing info

            # Step 4: Find real email address using AI
            email_search = search_tool(f"{sub['merchant']} contact email OR support email")
            email_addr = email_search.get("email")
            confidence = email_search.get("confidence", "low")
            reasoning = email_search.get("reasoning", "")
            
            # Store detailed email search results
            sub["email_search_confidence"] = confidence
            sub["email_search_reasoning"] = reasoning
            
            if not email_addr or email_addr.lower() == "not found":
                # Fallback to contact page URL
                contact_url = email_search.get("contact_url", "Not found")
                sub["contact_email"] = contact_url
                sub["email_sent"] = False
                sub["email_status"] = f"No email found - {reasoning}"
            else:
                # Store email for approval instead of sending automatically
                sub["contact_email"] = email_addr
                sub["email_sent"] = False
                sub["email_status"] = f"Email ready to send with {confidence} confidence - {reasoning}"
                sub["email_subject"] = "Subscription Discount Request"

        state["subscriptions"] = subscriptions
        # Store emails for approval
        emails_for_approval = []
        for sub in subscriptions:
            if sub.get("contact_email") and sub.get("contact_email") != "Not found" and "@" in sub.get("contact_email", ""):
                emails_for_approval.append({
                    "merchant": sub["merchant"],
                    "to": sub["contact_email"],
                    "subject": sub.get("email_subject", "Subscription Discount Request"),
                    "body": sub["negotiation_email"],
                    "email_sent": False
                })
        state["emails"] = emails_for_approval
        return state

# -------------------------------
# ALERT AGENT
# -------------------------------
class AlertAgent(Agent):
    def __init__(self):
        super().__init__(
            role="Financial Alert System",
            goal="Notify user of overspending or alerts.",
            tools=[SendUserAlertTool()]
        )
    def plan(self, state: FinanceState) -> FinanceState:
        forecast = state["forecast_results"]
        alerts = []
        alert_tool = self.tools[0]
        current_balance = 500
        total_forecast = forecast.get("total_forecast", forecast.get("total_2week_forecast", 0))
        if total_forecast > current_balance:
            msg = f"⚠️ OVERSPENDING ALERT: Forecasted ${total_forecast} exceeds balance ${current_balance}"
            alerts.append(msg)
            alert_tool(msg)
        if total_forecast > current_balance / 2:
            msg = f"⚠️ 2-week spending high: ${total_forecast}"
            alerts.append(msg)
            alert_tool(msg)
        state["alerts"] = alerts
        return state

# -------------------------------
# FULLY AGENTIC CHAT AGENT
# -------------------------------
class AgenticChatAgent(Agent):
    def __init__(self, data_agent: DataAgent, forecast_agent: ForecastAgent, subscription_agent: SubscriptionAgent):
        super().__init__(
            role="Agentic Financial Advisor",
            goal="Answer user questions using all available financial data, fetching or updating it as needed.",
            tools=[]
        )
        self.llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.3)
        self.data_agent = data_agent
        self.forecast_agent = forecast_agent
        self.subscription_agent = subscription_agent
        self.memory = {
            "transactions_fetched": False,
            "forecast_generated": False,
            "subscriptions_analyzed": False
        }
    def plan(self, state: FinanceState) -> FinanceState:
        user_query = state.get("user_query", "")
        needed_info = []
        
        if any(word in user_query.lower() for word in ["transactions", "spending", "expenses", "biggest", "categories", "money", "spent", "cost"]):
            needed_info.append("transactions")
        if any(word in user_query.lower() for word in ["forecast", "future", "predict", "next", "will spend"]):
            needed_info.append("forecast")
        if any(word in user_query.lower() for word in ["subscription", "recurring", "monthly", "netflix", "spotify"]):
            needed_info.append("subscriptions")
        if "transactions" in needed_info and not self.memory["transactions_fetched"]:
            state = self.data_agent.plan(state)
            self.memory["transactions_fetched"] = True
        if "forecast" in needed_info and not self.memory["forecast_generated"]:
            state = self.forecast_agent.plan(state)
            self.memory["forecast_generated"] = True
        if "subscriptions" in needed_info and not self.memory["subscriptions_analyzed"]:
            state = self.subscription_agent.plan(state)
            self.memory["subscriptions_analyzed"] = True
        context = {
            "transactions_count": len(state.get("transactions", [])),
            "forecast_total": state.get("forecast_results", {}).get("total_forecast", state.get("forecast_results", {}).get("total_2week_forecast", 0)),
            "subscriptions": state.get("subscriptions", []),
            "alerts": state.get("alerts", [])
        }
        messages = [
            SystemMessage(content=f"You are a smart financial assistant. Use this context: {json.dumps(context)}"),
            HumanMessage(content=user_query)
        ]
        response = self.llm.invoke(messages)
        state["chat_response"] = response.content
        return state

# -------------------------------
# ORCHESTRATOR
# -------------------------------

def create_finance_orchestrator():
    workflow = StateGraph(FinanceState)
    data_agent = DataAgent()
    forecast_agent = ForecastAgent()
    subscription_agent = SubscriptionAgent()
    alert_agent = AlertAgent()
    chat_agent = AgenticChatAgent(data_agent, forecast_agent, subscription_agent)
    agents = [data_agent, forecast_agent, subscription_agent, alert_agent, chat_agent]
    for agent in agents:
        workflow.add_node(agent.role, agent.plan)
    # Sequential flow
    workflow.set_entry_point("Data Collector")
    workflow.add_edge("Data Collector", "Financial Forecaster")
    workflow.add_edge("Financial Forecaster", "Subscription Manager")
    workflow.add_edge("Subscription Manager", "Financial Alert System")
    workflow.add_edge("Financial Alert System", "Agentic Financial Advisor")
    workflow.add_edge("Agentic Financial Advisor", END)
    return workflow.compile()

def create_chat_orchestrator():
    """Optimized orchestrator for chat - only runs needed agents"""
    workflow = StateGraph(FinanceState)
    
    # Create agents
    data_agent = DataAgent()
    forecast_agent = ForecastAgent()
    subscription_agent = SubscriptionAgent()
    chat_agent = AgenticChatAgent(data_agent, forecast_agent, subscription_agent)
    
    # Add only the chat agent as entry point - it decides what else to run
    workflow.add_node("Agentic Financial Advisor", chat_agent.plan)
    workflow.set_entry_point("Agentic Financial Advisor")
    workflow.add_edge("Agentic Financial Advisor", END)
    
    return workflow.compile()

def run_finance_analysis(user_query="Analyze my finances"):
    """Full workflow for dashboard - runs all agents"""
    orchestrator = create_finance_orchestrator()
    initial_state = {
        "transactions": [], "categorized_data": {}, "forecast_results": {},
        "subscriptions": [], "alerts": [], "emails": [], "user_query": user_query, "chat_response": ""
    }
    return orchestrator.invoke(initial_state)

def run_chat_analysis(user_query="Hello"):
    """Optimized workflow for chat - only runs needed agents"""
    orchestrator = create_chat_orchestrator()
    initial_state = {
        "transactions": [], "categorized_data": {}, "forecast_results": {},
        "subscriptions": [], "alerts": [], "emails": [], "user_query": user_query, "chat_response": ""
    }
    return orchestrator.invoke(initial_state)
