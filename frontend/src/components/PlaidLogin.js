import React, { useState, useEffect } from 'react';

function PlaidLogin({ onSuccess }) {
  const [linkToken, setLinkToken] = useState(null);

  useEffect(() => {
    const authToken = localStorage.getItem('auth_token');
    if (!authToken) return;
    
    // Get link token from backend
    fetch('http://localhost:8001/api/create_link_token', { 
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    })
      .then(res => res.json())
      .then(data => setLinkToken(data.link_token));
  }, []);

  const handlePlaidLink = () => {
    if (!linkToken) return;
    
    if (!window.Plaid) {
      alert('Plaid SDK not loaded. Please refresh the page.');
      return;
    }

    // Initialize Plaid Link
    const handler = window.Plaid.create({
      token: linkToken,
      onSuccess: async (publicToken, metadata) => {
        // Exchange public token for access token
        const authToken = localStorage.getItem('auth_token');
        const response = await fetch('http://localhost:8001/api/exchange_token', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({ public_token: publicToken })
        });
        const data = await response.json();
        onSuccess(data.access_token);
      },
      onExit: (err, metadata) => {
        if (err) console.error('Plaid Link error:', err);
      }
    });

    handler.open();
  };

  const handleSandboxMode = async () => {
    // Create sandbox token
    const sandboxResponse = await fetch('http://localhost:8001/api/create_sandbox_token', { method: 'POST' });
    const sandboxData = await sandboxResponse.json();
    
    // Exchange for access token
    const response = await fetch('http://localhost:8001/api/exchange_token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ public_token: sandboxData.public_token })
    });
    const data = await response.json();
    onSuccess(data.access_token);
  };

  return (
    <div className="connect-section">
      <div className="connect-buttons">
        <button 
          className="connect-btn primary" 
          onClick={handlePlaidLink}
          disabled={!linkToken}
        >
          🏦 Connect Bank Account
        </button>
        
        <button 
          className="connect-btn secondary" 
          onClick={handleSandboxMode}
        >
          📊 Use Demo Data
        </button>
      </div>
      
      <p className="connect-note">
        🔒 Bank-grade security powered by Plaid
      </p>
    </div>
  );
}

export default PlaidLogin;