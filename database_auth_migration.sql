-- Clean slate: Delete existing data (if tables exist)
DELETE FROM transactions WHERE true;
DELETE FROM accounts WHERE true;
DELETE FROM subscriptions WHERE true;
DELETE FROM forecasts WHERE true;
DELETE FROM alerts WHERE true;

-- Add user_id columns to all tables
ALTER TABLE accounts ADD COLUMN user_id UUID REFERENCES auth.users(id) NOT NULL;
ALTER TABLE transactions ADD COLUMN user_id UUID REFERENCES auth.users(id) NOT NULL;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) NOT NULL;
ALTER TABLE forecasts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) NOT NULL;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) NOT NULL;

-- Enable Row Level Security on all tables
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- Create policies for user data isolation
CREATE POLICY "Users can only see their own accounts" ON accounts FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can only see their own transactions" ON transactions FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can only see their own subscriptions" ON subscriptions FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can only see their own forecasts" ON forecasts FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can only see their own alerts" ON alerts FOR ALL USING (auth.uid() = user_id);

-- Create indexes for performance
CREATE INDEX idx_accounts_user_id ON accounts(user_id);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_user_id ON forecasts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON alerts(user_id);