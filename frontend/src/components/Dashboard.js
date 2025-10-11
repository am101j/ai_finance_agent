import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

function ForecastChart({ data }) {
  if (!data || data.length === 0) return null;

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(156, 163, 175, 0.1)" />
          <XAxis 
            dataKey="date" 
            stroke="#9CA3AF" 
            fontSize={11}
            tick={{ fill: '#9CA3AF' }}
          />
          <YAxis 
            stroke="#9CA3AF" 
            fontSize={11}
            tickFormatter={(v) => v > 0 ? `$${Math.round(v)}` : '$0'}
            tick={{ fill: '#9CA3AF' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1F2937',
              border: '1px solid #374151',
              borderRadius: '12px',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.25)',
              color: '#F9FAFB',
            }}
            formatter={(value, name) => {
              if (value === null) return [null, ''];
              return [
                `$${Math.round(value)}`, 
                name === 'historical' ? 'Actual Spending' : 'Predicted Spending'
              ];
            }}
            labelStyle={{ color: '#9CA3AF', fontSize: '12px' }}
          />
          <Line
            type="monotone"
            dataKey="historical"
            stroke="#9CA3AF"
            strokeWidth={3}
            dot={false}
            connectNulls={false}
            name="historical"
          />
          <Line
            type="monotone"
            dataKey="forecast"
            stroke="url(#tealGradient)"
            strokeWidth={3}
            strokeDasharray="8 4"
            dot={false}
            connectNulls={false}
            name="forecast"
          />
          <defs>
            <linearGradient id="tealGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#06B6D4" />
              <stop offset="100%" stopColor="#6366F1" />
            </linearGradient>
          </defs>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function CategoryPieChart({ data }) {
  if (!data || !data.categories || data.categories.length === 0) return null;

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data.categories}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
            paddingAngle={3}
            dataKey="value"
            stroke="none"
          >
            {data.categories.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.fill}
                stroke={entry.fill}
                strokeWidth={2}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#1F2937',
              border: '1px solid #374151',
              borderRadius: '12px',
              color: '#F9FAFB',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              fontSize: '14px',
              fontWeight: '500'
            }}
            formatter={(value, name) => {
              const category = data.categories.find(c => c.name === name);
              return [`$${value} (${category?.percentage}%)`, name];
            }}
            labelStyle={{ color: '#F9FAFB' }}
            itemStyle={{ color: '#F9FAFB' }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="category-legend">
        {data.categories.map((category, index) => (
          <div key={index} className="legend-item">
            <div 
              className="legend-color" 
              style={{ 
                backgroundColor: category.fill,
                boxShadow: `0 0 8px ${category.fill}40`
              }}
            ></div>
            <span className="legend-text">
              <strong>{category.name}</strong>: ${category.value} ({category.percentage}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Section({ title, children, right }) {
  return (
    <div className="glass-card">
      <div className="section-header">
        <h3 className="section-title">{title}</h3>
        <div>{right}</div>
      </div>
      {children}
    </div>
  );
}

function Dashboard({
  transactions,
  forecast,
  subscriptions,
  alerts,
  emails,
  loadingAnalysis,
  analysisError,
  onRefreshAnalysis,
  onSendEmail,
}) {
  const [darkMode, setDarkMode] = useState(true);
  const [categoryData, setCategoryData] = useState(null);

  useEffect(() => {
    const fetchCategoryData = async () => {
      try {
        const authToken = localStorage.getItem('auth_token');
        if (!authToken || loadingAnalysis) return;
        
        const response = await fetch('http://localhost:8001/api/spending_categories?days=30');
        const data = await response.json();
        setCategoryData(data);
      } catch (error) {
        console.error('Failed to fetch category data:', error);
      }
    };
    
    // Only fetch after analysis is complete
    if (!loadingAnalysis && forecast) {
      fetchCategoryData();
    }
  }, [loadingAnalysis, forecast]);
  const formatAmount = (amount) => {
    const isPositive = amount < 0;
    return {
      value: Math.abs(amount).toFixed(2),
      isPositive,
    };
  };

  // Normalize forecast totals from different backends
  const totalForecast =
    (forecast && (forecast.total_30day_forecast || forecast.total_4week_forecast || forecast.total_forecast)) || 0;

  const avgDaily = forecast?.avg_daily_forecast || 0;
  const historicalAvg = forecast?.historical_avg_daily || 0;
  const forecastData = (forecast && forecast.chart_data) || [];
  const weeklyBreakdown = (forecast && forecast.weekly_breakdown) || [];

  // Alerts can be strings or {type,message}
  const renderAlert = (a, idx) => {
    if (typeof a === 'string') return <li key={idx}>{a}</li>;
    return (
      <li key={idx}>
        <strong>{a.type || 'Alert'}:</strong> {a.message || JSON.stringify(a)}
      </li>
    );
  };

  return (
    <div className={`dashboard ${darkMode ? 'dark' : 'light'}`}>
      {/* Category Breakdown */}
      <Section title="📊 Top Categories">
        {categoryData ? (
          <div>
            <div className="stat-card" style={{ marginBottom: '1rem', textAlign: 'center' }}>
              <div className="stat-value gradient-text">
                ${categoryData.total_spending?.toFixed(2) || '0.00'}
              </div>
              <p className="stat-label">Total spent in last 30 days</p>
            </div>
            <CategoryPieChart data={categoryData} />
          </div>
        ) : (
          <div>Loading categories...</div>
        )}
      </Section>

      {/* Forecast Section */}
      <Section
        title="📊 30-Day Spending Forecast"
        right={
          <button
            onClick={onRefreshAnalysis}
            disabled={loadingAnalysis}
            className="gradient-button"
          >
            {loadingAnalysis ? '🔄 Running…' : '✨ Refresh Analysis'}
          </button>
        }
      >
        {analysisError && (
          <div className="error-card">
            ⚠️ {analysisError}
          </div>
        )}

        {forecast ? (
          <div>
            <div className="forecast-stats">
              <div className="stat-card primary">
                <div className="stat-value gradient-text">
                  ${Number(totalForecast).toFixed(2)}
                </div>
                <p className="stat-label">Next 30 days total</p>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  ${Number(avgDaily).toFixed(2)}
                </div>
                <p className="stat-label">Avg per day</p>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  ${Number(historicalAvg).toFixed(2)}
                </div>
                <p className="stat-label">Historical avg</p>
              </div>
            </div>
            
            {Array.isArray(forecastData) && forecastData.length > 0 && (
              <ForecastChart data={forecastData} />
            )}
            
            {weeklyBreakdown.length > 0 && (
              <div style={{ marginTop: '1.5rem' }}>
                <h4 className="section-title" style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>Weekly Breakdown</h4>
                <div className="weekly-breakdown">
                  {weeklyBreakdown.map((week, idx) => (
                    <div key={idx} className="week-card">
                      <div className="week-amount">
                        ${week.total}
                      </div>
                      <div className="week-label">
                        Week {idx + 1}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="forecast-amount">Loading...</div>
        )}
      </Section>

      {/* Subscriptions Section */}
      <Section title="📺 Active Subscriptions">
        {subscriptions && subscriptions.length > 0 ? (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {subscriptions.map((sub, idx) => {
              const name = sub.merchant || sub.name || 'Unknown';
              const amount = sub.amount ?? sub.price ?? 0;
              const freq = sub.frequency || sub.cadence || 'recurring';
              const contact = sub.contact_email || sub.email || 'Not found';
              const sent = !!sub.email_sent;
              const last = sub.last_date || sub.last_charge || null;

              return (
                <div key={`${name}-${idx}`} className="subscription-card">
                  <div className="subscription-header">
                    <div>
                      <div className="subscription-name">{name}</div>
                      <div className="subscription-meta">
                        {freq} • {last ? `last charged ${last}` : 'date unknown'}
                      </div>
                    </div>
                    <div className="subscription-amount">${Number(amount).toFixed(2)}</div>
                  </div>

                  {(sub.negotiation_email || contact !== 'Not found') && (
                    <div className="subscription-contact">
                      <div className="contact-info">
                        <strong>Contact:</strong> {contact}{' '}
                        <span className={sent ? 'status-sent' : 'status-ready'}>
                          {sent ? '— ✅ email sent' : '— 📧 ready to send'}
                        </span>
                        {!sent && contact !== 'Not found' && contact.includes('@') && onSendEmail && (
                          <button
                            onClick={() => onSendEmail({
                              to: contact,
                              subject: sub.email_subject || 'Subscription Discount Request',
                              body: sub.negotiation_email,
                              merchant: name
                            })}
                            className="send-button"
                            style={{ marginLeft: '1rem' }}
                          >
                            🚀 Send Email
                          </button>
                        )}
                      </div>
                      {sub.negotiation_email && (
                        <details style={{ marginTop: '1rem' }}>
                          <summary style={{ cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.875rem' }}>📧 View generated email</summary>
                          <div className="email-details">
                            {sub.negotiation_email}
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>📺 No subscriptions found</p>
        )}
      </Section>

      {/* Alerts Section */}
      <Section title="⚠️ Alerts">
        {alerts && alerts.length > 0 ? (
          <ul className="alerts-list">
            {alerts.map((a, idx) => renderAlert(a, idx))}
          </ul>
        ) : (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>✅ No alerts - you're doing great!</p>
        )}
      </Section>



      {/* Transactions Section */}
      <Section title="💳 Recent Transactions">
        {transactions && transactions.length > 0 ? (
          <div>
            {transactions.slice(0, 10).map((tx, index) => {
              const title = tx.name || tx.merchant_name || tx.description || 'Unknown';
              const cat = Array.isArray(tx.category)
                ? tx.category.join(', ')
                : (tx.category || 'Uncategorized');

              const amountObj = formatAmount(tx.amount);
              return (
                <div key={index} className="transaction-card">
                  <div className="transaction-header">
                    <div>
                      <div className="transaction-name">{title}</div>
                      <div className="transaction-meta">
                        {tx.date} • {cat}
                      </div>
                    </div>
                    <div className={`transaction-amount ${amountObj.isPositive ? 'positive' : 'negative'}`}>
                      {amountObj.isPositive ? '+' : '-'}${amountObj.value}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>💳 No transactions available</p>
        )}
      </Section>
    </div>
  );
}

export default Dashboard;
