-- Create forecasts table
CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    total_forecast DECIMAL(10,2) NOT NULL,
    avg_daily_forecast DECIMAL(10,2) NOT NULL,
    historical_avg_daily DECIMAL(10,2) NOT NULL,
    chart_data JSONB,
    forecast_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    name VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    frequency VARCHAR(50) NOT NULL,
    next_payment_date DATE,
    category VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Enable RLS on new tables
ALTER TABLE forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for forecasts
CREATE POLICY "Users can view own forecasts" ON forecasts
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own forecasts" ON forecasts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own forecasts" ON forecasts
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own forecasts" ON forecasts
    FOR DELETE USING (auth.uid() = user_id);

-- Create RLS policies for subscriptions
CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own subscriptions" ON subscriptions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own subscriptions" ON subscriptions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own subscriptions" ON subscriptions
    FOR DELETE USING (auth.uid() = user_id);