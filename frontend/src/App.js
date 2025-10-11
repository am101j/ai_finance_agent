import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import PlaidLogin from './components/PlaidLogin';
import Dashboard from './components/Dashboard';
import Chatbot from './components/Chatbot';
import './App.css';

function App() {
  const [authToken, setAuthToken] = useState(null);
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [subscriptions, setSubscriptions] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [emails, setEmails] = useState([]);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  useEffect(() => {
    const validateToken = async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) return;
      
      try {
        const response = await fetch('http://localhost:8001/api/create_link_token', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.status === 401) {
          localStorage.removeItem('auth_token');
          return;
        }
        
        setAuthToken(token);
      } catch (error) {
        localStorage.removeItem('auth_token');
      }
    };
    
    validateToken();
  }, []);

  const runFullAnalysis = async () => {
    try {
      setLoadingAnalysis(true);
      setAnalysisError(null);

      const res = await fetch('http://localhost:8001/api/analyze_finances', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
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

      // Clear emails since we removed the emails section
      setEmails([]);

    } catch (err) {
      console.error(err);
      setAnalysisError('Failed to run analysis.');
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handleSendEmail = async (emailData) => {
    try {
      const response = await fetch('http://localhost:8001/api/send_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: emailData.to,
          subject: emailData.subject,
          body: emailData.body
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        // Update subscription status only
        setSubscriptions(prevSubs => 
          prevSubs.map(sub => 
            sub.merchant === emailData.merchant
              ? { ...sub, email_sent: true }
              : sub
          )
        );
        
        alert(`Email sent successfully to ${emailData.to}!`);
      } else {
        alert(`Failed to send email: ${result.error}`);
      }
    } catch (error) {
      console.error('Error sending email:', error);
      alert('Failed to send email. Please try again.');
    }
  };

  const handlePlaidSuccess = async (token) => {
    setAccessToken(token);

    // 1) Insert accounts & transactions via backend
    try {
      const response = await fetch('http://localhost:8001/api/get_transactions', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
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

  const handleAuthSuccess = (token, userData) => {
    setAuthToken(token);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setAuthToken(null);
    setUser(null);
    setAccessToken(null);
  };

  return (
    <div className="app-container">
      {!authToken ? (
        <Auth onAuthSuccess={handleAuthSuccess} />
      ) : !accessToken ? (
        <div className="landing-page">
          <div className="hero-section">
            <div className="hero-content">
              <h1 className="hero-title">
                <span className="gradient-text">AI Finance</span> Assistant
              </h1>
              <p className="hero-subtitle">
                Smart financial insights powered by AI. Track spending, predict expenses, and optimize subscriptions.
              </p>
              <div className="features-grid">
                <div className="feature-card">
                  <span className="feature-icon">📊</span>
                  <span>Smart Forecasting</span>
                </div>
                <div className="feature-card">
                  <span className="feature-icon">💰</span>
                  <span>Subscription Management</span>
                </div>
                <div className="feature-card">
                  <span className="feature-icon">🤖</span>
                  <span>AI Chat Assistant</span>
                </div>
              </div>
            </div>
            <PlaidLogin onSuccess={handlePlaidSuccess} />
          </div>
        </div>
      ) : (
        <div className="main-app">
          <nav className="top-nav">
            <div className="nav-brand">
              <span className="gradient-text">💰 Finance AI</span>
            </div>
            <div>
              <span style={{marginRight: '1rem', color: '#9CA3AF'}}>{user?.email}</span>
              <button className="refresh-btn" onClick={runFullAnalysis} disabled={loadingAnalysis}>
                {loadingAnalysis ? '🔄' : '✨'}
              </button>
              <button className="logout-btn" onClick={handleLogout}>Logout</button>
            </div>
          </nav>
          <div className="app-layout">
            <main className="main-content">
              <Dashboard
                transactions={transactions}
                forecast={forecast}
                subscriptions={subscriptions}
                alerts={alerts}
                emails={emails}
                loadingAnalysis={loadingAnalysis}
                analysisError={analysisError}
                onRefreshAnalysis={runFullAnalysis}
                onSendEmail={handleSendEmail}
              />
            </main>
            <aside className="chat-sidebar">
              <Chatbot accessToken={accessToken} />
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
