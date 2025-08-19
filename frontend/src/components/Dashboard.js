import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function ForecastChart({ data }) {
  if (!data || data.length === 0) return null;

  const chartData = data.map((day) => ({
    date: new Date(day.ds).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    spending: Math.round(day.yhat || day.value || 0),
  }));

  return (
    <div style={{ width: '100%', height: '300px', marginTop: '1rem' }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: '1px solid rgba(78, 205, 196, 0.3)',
              borderRadius: '12px',
              color: '#2d3748',
            }}
            formatter={(value) => [`$${value}`, 'Predicted Spending']}
          />
          <Line
            type="monotone"
            dataKey="spending"
            stroke="#4ecdc4"
            strokeWidth={3}
            dot={{ fill: '#4ecdc4', strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6, fill: '#ff6b6b' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Section({ title, children, right }) {
  return (
    <div className="section" style={{ marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>{title}</h3>
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
}) {
  const formatAmount = (amount) => {
    const isPositive = amount < 0;
    return {
      value: Math.abs(amount).toFixed(2),
      isPositive,
    };
  };

  // Normalize forecast totals from different backends
  const totalForecast =
    (forecast && (forecast.total_forecast || forecast.total_2week_forecast || forecast.total_4week_forecast)) || 0;

  const forecastDays =
    (forecast && (forecast.forecasted_days || forecast.days || forecast.weekly_breakdown)) || [];

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
    <div className="dashboard">
      {/* Forecast Section */}
      <Section
        title="1-Week Spending Forecast"
        right={
          <button
            onClick={onRefreshAnalysis}
            disabled={loadingAnalysis}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid #d1d5db',
              background: loadingAnalysis ? '#e5e7eb' : '#fff',
              cursor: loadingAnalysis ? 'not-allowed' : 'pointer',
            }}
          >
            {loadingAnalysis ? 'Running…' : 'Refresh Analysis'}
          </button>
        }
      >
        {analysisError && (
          <div
            style={{
              background: '#fee2e2',
              border: '1px solid #fecaca',
              color: '#991b1b',
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 12,
            }}
          >
            {analysisError}
          </div>
        )}

        {forecast ? (
          <div>
            <div className="forecast-amount" style={{ fontSize: 28, fontWeight: 700 }}>
              ${Number(totalForecast).toFixed(2)}
            </div>
            <p style={{ color: '#94a3b8' }}>Predicted spending for the next 7 days</p>
            {Array.isArray(forecastDays) && forecastDays.length > 0 && (
              <ForecastChart data={forecastDays} />
            )}
          </div>
        ) : (
          <div className="forecast-amount">Loading...</div>
        )}
      </Section>

      {/* Subscriptions Section */}
      <Section title="📺 Active Subscriptions">
        {subscriptions && subscriptions.length > 0 ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {subscriptions.map((sub, idx) => {
              const name = sub.merchant || sub.name || 'Unknown';
              const amount = sub.amount ?? sub.price ?? 0;
              const freq = sub.frequency || sub.cadence || 'recurring';
              const contact = sub.contact_email || sub.email || 'Not found';
              const sent = !!sub.email_sent;
              const last = sub.last_date || sub.last_charge || null;

              return (
                <div
                  key={`${name}-${idx}`}
                  className="subscription"
                  style={{
                    border: '1px solid #e5e7eb',
                    borderRadius: 12,
                    padding: '12px 14px',
                    background: '#fff',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{name}</div>
                      <div style={{ color: '#6b7280', fontSize: 13 }}>
                        {freq} • {last ? `last charged ${last}` : 'date unknown'}
                      </div>
                    </div>
                    <div style={{ fontWeight: 700 }}>${Number(amount).toFixed(2)}</div>
                  </div>

                  {(sub.negotiation_email || contact !== 'Not found') && (
                    <div style={{ marginTop: 8, color: '#374151', fontSize: 13 }}>
                      <div>
                        <strong>Contact:</strong> {contact}{' '}
                        <span style={{ color: sent ? '#059669' : '#b45309', marginLeft: 6 }}>
                          {sent ? '— email sent' : '— not sent'}
                        </span>
                      </div>
                      {sub.negotiation_email && (
                        <details style={{ marginTop: 6 }}>
                          <summary style={{ cursor: 'pointer' }}>View generated email</summary>
                          <pre
                            style={{
                              whiteSpace: 'pre-wrap',
                              background: '#f9fafb',
                              border: '1px solid #e5e7eb',
                              padding: 10,
                              borderRadius: 8,
                              marginTop: 6,
                            }}
                          >
                            {sub.negotiation_email}
                          </pre>
                        </details>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ color: '#718096' }}>No subscriptions found</p>
        )}
      </Section>

      {/* Alerts Section */}
      <Section title="⚠️ Alerts">
        {alerts && alerts.length > 0 ? (
          <ul style={{ paddingLeft: 18 }}>
            {alerts.map((a, idx) => renderAlert(a, idx))}
          </ul>
        ) : (
          <p style={{ color: '#718096' }}>No alerts</p>
        )}
      </Section>

      {/* Emails Section */}
      <Section title="📧 Emails Generated">
        {emails && emails.length > 0 ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {emails.map((em, idx) => (
              <div
                key={idx}
                style={{
                  border: '1px solid #e5e7eb',
                  borderRadius: 12,
                  padding: '12px 14px',
                  background: '#fff',
                }}
              >
                <div style={{ marginBottom: 6, color: '#6b7280', fontSize: 13 }}>
                  <div><strong>To:</strong> {em.to || 'Unknown'}</div>
                  {em.merchant && <div><strong>Merchant:</strong> {em.merchant}</div>}
                  <div>
                    <strong>Status:</strong>{' '}
                    <span style={{ color: em.email_sent ? '#059669' : '#b45309' }}>
                      {em.email_sent ? 'Sent' : 'Not Sent'}
                    </span>
                  </div>
                </div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {em.subject || 'Subscription Discount Request'}
                </div>
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    background: '#f9fafb',
                    border: '1px solid #e5e7eb',
                    padding: 10,
                    borderRadius: 8,
                    margin: 0,
                  }}
                >
                  {em.body || ''}
                </pre>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: '#718096' }}>No emails generated</p>
        )}
      </Section>

      {/* Transactions Section */}
      <Section title="💳 Recent Transactions">
        {transactions && transactions.length > 0 ? (
          <div>
            {transactions.slice(0, 10).map((tx, index) => {
              // Your DB uses {description, date, amount, category}; Plaid UI used {name, merchant_name, category[]}
              const title = tx.name || tx.merchant_name || tx.description || 'Unknown';
              const cat = Array.isArray(tx.category)
                ? tx.category.join(', ')
                : (tx.category || 'Uncategorized');

              const amountObj = formatAmount(tx.amount);
              return (
                <div key={index} className="transaction" style={{
                  border: '1px solid #e5e7eb',
                  borderRadius: 12,
                  padding: '12px 14px',
                  background: '#fff',
                  marginBottom: 10
                }}>
                  <div className="transaction-info">
                    <h4 style={{ margin: 0 }}>{title}</h4>
                    <p style={{ color: '#6b7280', margin: '4px 0 0 0' }}>
                      {tx.date} • {cat}
                    </p>
                  </div>
                  <div
                    className={`transaction-amount ${amountObj.isPositive ? 'positive' : ''}`}
                    style={{
                      marginTop: 6,
                      fontWeight: 700,
                      color: amountObj.isPositive ? '#16a34a' : '#dc2626',
                    }}
                  >
                    {amountObj.isPositive ? '+' : '-'}${amountObj.value}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ color: '#718096' }}>No transactions available</p>
        )}
      </Section>
    </div>
  );
}

export default Dashboard;
