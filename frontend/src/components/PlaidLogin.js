import React, { useState, useEffect } from 'react';

function PlaidLogin({ onSuccess }) {
  const [linkToken, setLinkToken] = useState(null);

  useEffect(() => {
    // Get link token from backend
    fetch('http://localhost:8000/api/create_link_token', { method: 'POST' })
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
        const response = await fetch('http://localhost:8000/api/exchange_token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
    const sandboxResponse = await fetch('http://localhost:8000/api/create_sandbox_token', { method: 'POST' });
    const sandboxData = await sandboxResponse.json();
    
    // Exchange for access token
    const response = await fetch('http://localhost:8000/api/exchange_token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ public_token: sandboxData.public_token })
    });
    const data = await response.json();
    onSuccess(data.access_token);
  };

  return (
    <div className="plaid-login">
      <h2>Connect Your Bank Account</h2>
      <p>Securely link your bank account to get started with financial insights</p>
      
      <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
        <button 
          className="plaid-button" 
          onClick={handlePlaidLink}
          disabled={!linkToken}
        >
          Connect Real Bank Account
        </button>
        
        <button 
          className="plaid-button" 
          onClick={handleSandboxMode}
          style={{ background: '#6c757d' }}
        >
          Use Demo Data
        </button>
      </div>
      

    </div>
  );
}

export default PlaidLogin;