from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import warnings
from prophet import Prophet

warnings.filterwarnings('ignore')
load_dotenv()

def forecast_overall_spending():
    """Forecast total spending for the next 2 weeks, including subscriptions, with a visual plot."""
    try:
        # Get transactions from database
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        }
        response = requests.get(f"{supabase_url}/rest/v1/transactions?order=date.asc", headers=headers)
        transactions = response.json()

        # Exclude non-spending categories
        excluded = ["TRANSFER_IN", "TRANSFER_OUT", "LOAN_PAYMENTS", "INCOME", "RENT_AND_UTILITIES"]

        # Aggregate spending per day, but only keep nonzero days
        daily_spending = {}
        for tx in transactions:
            date = datetime.strptime(tx['date'], '%Y-%m-%d').date()
            full_category = tx.get('category', 'Uncategorized')
            category = full_category.split(" > ")[0]
            if category in excluded:
                continue
            amount = abs(float(tx['amount']))
            daily_spending.setdefault(date, 0)
            daily_spending[date] += amount

        # Only keep nonzero days
        nonzero_days = {d: v for d, v in daily_spending.items() if v > 0}
        if not nonzero_days:
            return {"error": "No nonzero spending days available."}
        df = pd.DataFrame({
            'ds': list(nonzero_days.keys()),
            'y': list(nonzero_days.values())
        }).sort_values('ds')

        # Prophet expects at least 2 data points
        if len(df) < 2:
            return {"error": "Not enough data for forecasting."}

        # Fit Prophet model with fixed seed for consistency
        model = Prophet(
            weekly_seasonality=True, 
            daily_seasonality=False,  # Disable daily seasonality for stability
            yearly_seasonality=False,
            mcmc_samples=0  # Disable MCMC for consistent results
        )
        model.fit(df)

        # Forecast next 7 days
        last_date = df['ds'].max()
        future = pd.DataFrame({'ds': [last_date + timedelta(days=i) for i in range(1, 8)]})
        forecast = model.predict(future)

        # Prepare output values
        forecasted_values = forecast[['ds', 'yhat']].to_dict(orient='records')
        total_forecast = float(forecast['yhat'].sum())

        # Prepare forecasted days data for frontend chart
        forecasted_days = []
        for _, row in forecast.iterrows():
            forecasted_days.append({
                'ds': row['ds'].strftime('%Y-%m-%d'),
                'yhat': float(row['yhat'])
            })

        return {
            "total_forecast": round(total_forecast, 2),
            "forecasted_days": forecasted_days,
            "historical_days": len(df),
            "forecast_method": "Prophet (Nonzero Daily)"
        }
    except Exception as e:
        return {"error": str(e)}