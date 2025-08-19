import React, { useState } from 'react';

function Chatbot({ accessToken }) {
  const [messages, setMessages] = useState([
    { type: 'bot', text: 'Hi! I\'m your financial assistant. Ask me about your spending, subscriptions, or financial advice!' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { type: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Send message to chat agent
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input })
      });
      
      const data = await response.json();
      
      const botMessage = { 
        type: 'bot', 
        text: data.response || data.error || 'Sorry, I couldn\'t process that request.' 
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      const errorMessage = { 
        type: 'bot', 
        text: 'Sorry, there was an error processing your request.' 
      };
      setMessages(prev => [...prev, errorMessage]);
    }
    
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  };

  const quickQuestions = [
    "What are my biggest expenses?",
    "Find my subscriptions",
    "How much will I spend next week?",
    "Give me financial advice"
  ];

  return (
    <div className="chatbot">
      <h3>💬 Financial Assistant</h3>
      
      <div className="chat-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.type}`}>
            {message.text}
          </div>
        ))}
        {loading && (
          <div className="message bot">
            <div className="loading-spinner"></div> Thinking...
          </div>
        )}
      </div>

      {/* Quick Questions */}
      <div style={{ marginBottom: '1rem' }}>
        <p style={{ fontSize: '0.9rem', color: '#718096', margin: '0 0 0.5rem 0' }}>
          Quick questions:
        </p>
        <div className="quick-questions">
          {quickQuestions.map((question, index) => (
            <button
              key={index}
              onClick={() => setInput(question)}
              className="quick-question-btn"
            >
              {question}
            </button>
          ))}
        </div>
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask about your finances..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}

export default Chatbot;