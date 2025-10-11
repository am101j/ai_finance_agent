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
from supadata import insert_forecast

warnings.filterwarnings('ignore')
load_dotenv()

def forecast_overall_spending():
    """Advanced spending forecast with proper training and realistic predictions."""
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

        # Exclude fixed expenses, transfers, and income - only predict variable spending
        excluded = [
            "TRANSFER_IN", "TRANSFER_OUT", "INCOME", "CREDIT_CARD_PAYMENT", "RENT_AND_UTILITIES"
        ]
        
        # Create daily spending data with all dates (including zeros)
        daily_spending = {}
        min_date = None
        max_date = None
        
        for tx in transactions:
            date = datetime.strptime(tx['date'], '%Y-%m-%d').date()
            full_category = tx.get('category', 'Uncategorized')
            category = full_category.split(" > ")[0]
            
            # Skip fixed expenses and check description for rent/utilities
            if (category in excluded):
                continue
            
            amount = float(tx['amount'])
            if amount < 0: # Skip income & negative transactions
                continue

            daily_spending.setdefault(date, 0)
            daily_spending[date] += amount
            
            if min_date is None or date < min_date:
                min_date = date
            if max_date is None or date > max_date:
                max_date = date

        if not daily_spending or min_date is None:
            return {"error": "No spending data available."}

        # Fill in missing dates with 0 spending
        current_date = min_date
        while current_date <= max_date:
            if current_date not in daily_spending:
                daily_spending[current_date] = 0
            current_date += timedelta(days=1)

        # Create DataFrame for Prophet
        df = pd.DataFrame({
            'ds': list(daily_spending.keys()),
            'y': list(daily_spending.values())
        }).sort_values('ds')

        if len(df) < 14:  # Need at least 2 weeks of data
            return {"error": "Need at least 14 days of data for forecasting."}

        # Configure Prophet with proper seasonality
        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=len(df) > 365,
            seasonality_mode='multiplicative',
            changepoint_prior_scale=0.05,  # More flexible to changes
            seasonality_prior_scale=10.0,  # Strong seasonality
            interval_width=0.8
        )
        
        # Add custom seasonalities
        model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        model.fit(df)

        # Get last 30 days of historical data for context
        last_date = df['ds'].max()
        historical_start = last_date - timedelta(days=30)
        historical_data = df[df['ds'] >= historical_start].copy()

        # Forecast next 30 days
        future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=30, freq='D')
        future_df = pd.DataFrame({'ds': future_dates})
        forecast = model.predict(future_df)
        
        # Ensure realistic predictions (no negative spending)
        forecast['yhat'] = forecast['yhat'].clip(lower=0)
        
        # Calculate weekly totals for better understanding
        weekly_forecast = []
        for i in range(0, len(forecast), 7):
            week_data = forecast.iloc[i:i+7]
            week_total = week_data['yhat'].sum()
            week_start = week_data['ds'].iloc[0]
            weekly_forecast.append({
                'week_start': week_start.strftime('%Y-%m-%d'),
                'total': round(week_total, 2)
            })

        # Prepare chart data
        chart_data = []
        
        # Add last 30 days historical
        for _, row in historical_data.iterrows():
            chart_data.append({
                'date': row['ds'].strftime('%m/%d'),
                'historical': float(row['y']),
                'forecast': None
            })
        
        # Add 30 days forecast
        for _, row in forecast.iterrows():
            chart_data.append({
                'date': row['ds'].strftime('%m/%d'),
                'historical': None,
                'forecast': max(0, float(row['yhat']))
            })

        # Calculate totals
        total_forecast = float(forecast['yhat'].sum())
        avg_daily = total_forecast / 30
        historical_avg = historical_data['y'].mean()
        
        result = {
            "total_30day_forecast": round(total_forecast, 2),
            "avg_daily_forecast": round(avg_daily, 2),
            "historical_avg_daily": round(historical_avg, 2),
            "chart_data": chart_data,
            "weekly_breakdown": weekly_forecast,
            "confidence_interval": {
                "lower": round(forecast['yhat_lower'].sum(), 2),
                "upper": round(forecast['yhat_upper'].sum(), 2)
            },
            "forecast_method": "Prophet (Advanced 30-Day)"
        }
        
        # Note: insert_forecast requires user_id but we don't have it here
        # This will be handled when we add proper authentication to agents
        try:
            insert_forecast(
                total_30day_forecast=result["total_30day_forecast"],
                weekly_breakdown=result["weekly_breakdown"],
                user_id="00000000-0000-0000-0000-000000000000"  # Placeholder
            )
        except Exception as e:
            print(f"Could not save forecast to database: {e}")

        return result
    except Exception as e:
        return {"error": str(e)}
