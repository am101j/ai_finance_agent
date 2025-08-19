import requests
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

def extract_alternatives_with_pricing(original_query, search_results):
    """Use AI to intelligently extract alternative company names and their pricing from search results"""
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Initialize LLM
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)
        
        # Prepare search content for AI analysis
        content_text = ""
        for i, result in enumerate(search_results[:6], 1):
            content_text += f"\n--- Search Result {i} ---\n"
            content_text += f"Title: {result.get('title', '')}\n"
            content_text += f"Snippet: {result.get('snippet', '')}\n"
        
        # Create AI prompt for extracting alternatives with pricing
        system_prompt = """You are an expert at analyzing search results to find alternative companies/services and their pricing.

Your task: Extract company names and their pricing information from search results.

Rules:
1. Return ONLY actual company/brand names with their prices
2. Look for pricing like: $9.99/month, $15.99, starting at $8, from $12.99
3. Do NOT include article titles, website names, or generic terms
4. Focus on direct competitors or similar services
5. Return maximum 3 alternatives
6. If no price found for a company, set price as "Price not found"
7. Convert all prices to monthly format when possible

Return your response as JSON:
[
    {
        "company": "Company Name",
        "price": "$9.99/month",
        "price_note": "Basic plan" 
    }
]

If no clear alternatives are found, return: []"""

        user_prompt = f"""Original search query: "{original_query}"

Search results content:
{content_text}

Extract the alternative company names and their pricing from these search results."""

        # Get AI response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Clean and parse JSON response
        try:
            # Remove any markdown formatting
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            alternatives_with_pricing = json.loads(content)
            
            # Validate and clean results
            if isinstance(alternatives_with_pricing, list):
                cleaned_alternatives = []
                for alt in alternatives_with_pricing:
                    if isinstance(alt, dict) and alt.get("company"):
                        company = alt.get("company", "").strip()
                        price = alt.get("price", "Price not found").strip()
                        price_note = alt.get("price_note", "").strip()
                        
                        if len(company) > 1 and len(company) < 50:
                            # Remove common non-company words
                            if not any(word in company.lower() for word in 
                                     ['alternative', 'best', 'top', 'list', 'review', 'comparison', 'vs', 'versus']):
                                cleaned_alternatives.append({
                                    "company": company,
                                    "price": price,
                                    "price_note": price_note
                                })
                
                return cleaned_alternatives[:3]  # Return max 3
            else:
                return []
                
        except json.JSONDecodeError:
            # Fallback: try to extract company names without pricing
            fallback_matches = re.findall(r'"([^"]+)"', content)
            if not fallback_matches:
                fallback_matches = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b', content)
            
            # Filter and return reasonable company names without pricing
            valid_matches = []
            for match in fallback_matches:
                if len(match) > 1 and len(match) < 30 and not any(word in match.lower() 
                    for word in ['alternative', 'best', 'top', 'list', 'review']):
                    valid_matches.append({
                        "company": match,
                        "price": "Price not found",
                        "price_note": ""
                    })
            
            return valid_matches[:3]
    
    except Exception as e:
        print(f"AI extraction error: {e}")
        return []

def extract_alternatives_with_ai(original_query, search_results):
    """Wrapper function to maintain backward compatibility"""
    alternatives_with_pricing = extract_alternatives_with_pricing(original_query, search_results)
    # Return just company names for backward compatibility
    return [alt.get("company", "") for alt in alternatives_with_pricing if alt.get("company")]

def extract_email_with_ai(company_name, search_results):
    """Use AI to intelligently extract contact email from search results"""
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Initialize LLM
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)
        
        # Prepare search content for AI analysis
        content_text = ""
        for i, result in enumerate(search_results[:5], 1):
            content_text += f"\n--- Search Result {i} ---\n"
            content_text += f"Title: {result.get('title', '')}\n"
            content_text += f"Snippet: {result.get('snippet', '')}\n"
            content_text += f"Link: {result.get('link', '')}\n"
        
        # Create AI prompt for extracting email
        system_prompt = f"""You are an expert at finding customer support contact information for companies.

Your task: Find the best customer support email address for {company_name} from the search results.

Rules:
1. Look for official customer support, help, or contact email addresses
2. Prefer emails like: support@, help@, contact@, customerservice@
3. AVOID: noreply@, no-reply@, marketing@, sales@, info@ (unless it's the only option)
4. Must be a valid email format: name@domain.com
5. If multiple emails found, choose the most appropriate for customer support
6. If no direct email found, look for contact page URLs

Return your response as JSON:
{{
    "email": "support@company.com",
    "confidence": "high|medium|low",
    "contact_url": "https://company.com/contact",
    "reasoning": "Brief explanation of why this email was chosen"
}}

If no email or contact info found, return:
{{
    "email": "not found",
    "confidence": "none",
    "contact_url": "not found",
    "reasoning": "No contact information found in search results"
}}"""

        user_prompt = f"""Company: {company_name}
Search query was: "{company_name} contact email OR support email"

Search results:
{content_text}

Find the best customer support email for {company_name}."""

        # Get AI response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Clean and parse JSON response
        try:
            # Remove any markdown formatting
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            result = json.loads(content)
            
            return {
                "email": result.get("email", "not found"),
                "confidence": result.get("confidence", "low"),
                "contact_url": result.get("contact_url", "not found"),
                "reasoning": result.get("reasoning", "AI analysis completed")
            }
                
        except json.JSONDecodeError:
            # Fallback: try to extract email using regex
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, content)
            
            if emails:
                # Filter out common non-support emails
                valid_emails = [email for email in emails if not any(skip in email.lower() 
                               for skip in ['noreply', 'no-reply', 'donotreply', 'marketing'])]
                if valid_emails:
                    return {
                        "email": valid_emails[0],
                        "confidence": "medium",
                        "contact_url": "not found",
                        "reasoning": "Extracted from AI response text"
                    }
            
            return {
                "email": "not found",
                "confidence": "none",
                "contact_url": "not found",
                "reasoning": "Could not parse AI response"
            }
    
    except Exception as e:
        print(f"AI email extraction error: {e}")
        return {
            "email": "not found",
            "confidence": "none",
            "contact_url": "not found",
            "reasoning": f"Error: {str(e)}"
        }

def search_web(query):
    """Search web for alternatives or emails using SerpAPI and AI-powered extraction"""
    try:
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            return {"error": "No SerpAPI key", "alternatives": [], "email": "not found"}
            
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": 10
        }
        
        response = requests.get(url, params=params)
        results = response.json()
        
        # Collect search result content for AI analysis
        search_content = []
        
        for result in results.get("organic_results", [])[:8]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            
            search_content.append({
                "title": title,
                "snippet": snippet,
                "link": link
            })
        
        # Determine if this is an email search or alternatives search
        if "email" in query.lower() or "contact" in query.lower():
            # Extract company name from query for email search
            company_name = query.split()[0]  # First word is usually the company name
            
            # Use AI to extract email from search content
            email_result = extract_email_with_ai(company_name, search_content)
            
            return {
                "alternatives": [],
                "email": email_result.get("email", "not found"),
                "contact_url": email_result.get("contact_url", "not found"),
                "confidence": email_result.get("confidence", "low"),
                "reasoning": email_result.get("reasoning", ""),
                "search_content": search_content
            }
        else:
            # Use AI to extract alternatives with pricing from search content
            alternatives_with_pricing = extract_alternatives_with_pricing(query, search_content)
            alternatives = extract_alternatives_with_ai(query, search_content)  # For backward compatibility
            
            return {
                "alternatives": alternatives,
                "alternatives_with_pricing": alternatives_with_pricing,
                "email": "not found",
                "contact_url": "not found",
                "search_content": search_content
            }
        
    except Exception as e:
        return {"error": str(e), "alternatives": [], "email": "not found"}

def send_negotiation_email(to_email, subject, body):
    """Send negotiation email using SendGrid API"""
    try:
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        
        if not all([sendgrid_api_key, sender_email]):
            return {"error": "SendGrid credentials not configured"}
        
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "personalizations": [{
                "to": [{"email": to_email}],
                "subject": subject
            }],
            "from": {"email": sender_email},
            "content": [{
                "type": "text/plain",
                "value": body
            }]
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 202:
            print(f"✅ EMAIL SENT TO: {to_email}")
            print(f"📧 SUBJECT: {subject}")
            print(f"📝 BODY: {body[:200]}...")
            return {"success": True, "message": f"Email sent to {to_email}"}
        else:
            print(f"❌ EMAIL FAILED: {response.status_code} - {response.text}")
            return {"error": f"SendGrid error: {response.status_code}"}
            
    except Exception as e:
        return {"error": str(e)}

def send_user_alert(message):
    """Send alert email to user"""
    try:
        user_email = os.getenv("USER_EMAIL")
        if not user_email:
            print(f"ALERT (no email configured): {message}")
            return {"error": "User email not configured"}
        
        return send_negotiation_email(
            to_email=user_email,
            subject="🚨 Finance Alert",
            body=f"Finance Assistant Alert:\n\n{message}"
        )
    except Exception as e:
        return {"error": str(e)}

# Subscription provider email mapping
SUBSCRIPTION_EMAILS = {
    "NETFLIX": "help@netflix.com",
    "SPOTIFY": "support@spotify.com", 
    "AMAZON": "customer-service@amazon.com",
    "APPLE": "support@apple.com",
    "DISNEY": "help@disneyplus.com"
}