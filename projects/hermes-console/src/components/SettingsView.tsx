import React, { useState, useEffect } from 'react';
import { Settings, Activity, GitBranch } from 'lucide-react';

export default function SettingsView() {
  const [metrics, setMetrics] = useState<any>(null);
  const [instanceUrl, setInstanceUrl] = useState('');
  const [instanceService, setInstanceService] = useState('');
  const [registerResult, setRegisterResult] = useState<any>(null);

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/metrics/history');
      if (res.ok) setMetrics(await res.json());
    } catch (e) {}
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const fd = new FormData();
      fd.append('service', instanceService);
      fd.append('mcp_endpoint', instanceUrl);
      const res = await fetch('/api/instance', { method: 'POST', body: fd });
      setRegisterResult(await res.json());
    } catch (e: any) {
      setRegisterResult({ error: e.message });
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      
      {/* Metrics History */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="section-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={20} className="text-success" />
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>System Metrics</h2>
        </div>
        
        {metrics ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
              <span style={{ color: 'var(--color-muted)' }}>Timestamp: </span> {metrics.timestamp}
            </div>
            <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between' }}>
              <div><span style={{ color: 'var(--color-muted)' }}>Services: </span> {metrics.services}</div>
              <div><span style={{ color: 'var(--color-muted)' }}>Healthy: </span> <span className="text-success">{metrics.healthy}</span></div>
            </div>
            <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
              <span style={{ color: 'var(--color-muted)', display: 'block', marginBottom: '0.5rem' }}>Latency Percentiles:</span>
              <pre style={{ margin: 0, color: '#38bdf8', fontSize: '0.85rem' }}>
                {JSON.stringify(metrics.latency, null, 2)}
              </pre>
            </div>
          </div>
        ) : (
          <p style={{ color: 'var(--color-muted)' }}>Loading metrics...</p>
        )}
      </div>

      {/* Instance Registration */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="section-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitBranch size={20} className="text-accent" />
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Register Instance</h2>
        </div>
        
        <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>Target Service Name</label>
            <input required type="text" className="glass-input" value={instanceService} onChange={e => setInstanceService(e.target.value)} placeholder="e.g. gbrain" />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>MCP Endpoint URL</label>
            <input required type="text" className="glass-input" value={instanceUrl} onChange={e => setInstanceUrl(e.target.value)} placeholder="http://10.0.0.5:7431" />
          </div>
          <button type="submit" className="btn-glass" style={{ width: 'fit-content' }}>Register Instance</button>
        </form>

        {registerResult && (
          <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <pre style={{ margin: 0, fontSize: '0.85rem', color: registerResult.error ? '#ff4444' : '#00ffcc' }}>
              {JSON.stringify(registerResult, null, 2)}
            </pre>
          </div>
        )}
      </div>

    </div>
  );
}
