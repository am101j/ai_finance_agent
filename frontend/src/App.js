import React, { useState } from 'react';
import PlaidLogin from './components/PlaidLogin';
import Dashboard from './components/Dashboard';
import Chatbot from './components/Chatbot';
import './App.css';

function App() {
  const [accessToken, setAccessToken] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [subscriptions, setSubscriptions] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [emails, setEmails] = useState([]);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const runFullAnalysis = async () => {
    try {
      setLoadingAnalysis(true);
      setAnalysisError(null);

      const res = await fetch('http://localhost:8000/api/analyze_finances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'Run full finance analysis' })
      });
      const data = await res.json();

      // forecast key can vary by backend; normalize
      const forecastPayload =
        data.forecast ||
        data.forecast_results || // finance_orchestrator
        null;

      setForecast(forecastPayload);

      // subscriptions may be an array of objects from the agent
      setSubscriptions(Array.isArray(data.subscriptions) ? data.subscriptions : []);

      // alerts can be array of strings or objects
      setAlerts(Array.isArray(data.alerts) ? data.alerts : []);

      // emails may not be sent as a top-level array; also derive from subscriptions
      const topLevelEmails = Array.isArray(data.emails) ? data.emails : [];
      const fromSubs = (Array.isArray(data.subscriptions) ? data.subscriptions : [])
        .filter(s => s.negotiation_email || s.email_sent || s.contact_email)
        .map(s => ({
          to: s.contact_email || 'Not found',
          subject: s.email_subject || 'Subscription Discount Request',
          body: s.negotiation_email || '',
          email_sent: !!s.email_sent,
          merchant: s.merchant || s.name || 'Unknown'
        }));
      setEmails([...topLevelEmails, ...fromSubs]);

    } catch (err) {
      console.error(err);
      setAnalysisError('Failed to run analysis.');
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handlePlaidSuccess = async (token) => {
    setAccessToken(token);

    // 1) Insert accounts & transactions via backend
    try {
      const response = await fetch('http://localhost:8000/api/get_transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: token })
      });
      const data = await response.json();
      setTransactions(data.transactions || []);
    } catch (e) {
      console.error('get_transactions error', e);
    }

    // 2) Immediately run the full agent workflow (non-linear orchestrator behind /analyze_finances)
    await runFullAnalysis();
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>AI Finance Assistant</h1>
      </header>

      {!accessToken ? (
        <PlaidLogin onSuccess={handlePlaidSuccess} />
      ) : (
        <div className="main-content">
          <Dashboard
            transactions={transactions}
            forecast={forecast}
            subscriptions={subscriptions}
            alerts={alerts}
            emails={emails}
            loadingAnalysis={loadingAnalysis}
            analysisError={analysisError}
            onRefreshAnalysis={runFullAnalysis}
          />
          <Chatbot accessToken={accessToken} />
        </div>
      )}
    </div>
  );
}

export default App;
