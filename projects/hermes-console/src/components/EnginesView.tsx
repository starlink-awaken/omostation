import React, { useState, useEffect } from 'react';
import { Cpu, Play, Activity, List, GitCommit } from 'lucide-react';

interface EventLog {
  id: string;
  type: string;
  timestamp: string;
  source: string;
  payload: any;
}

export default function EnginesView() {
  const [pipelines, setPipelines] = useState<string[]>([]);
  const [events, setEvents] = useState<EventLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPipeline, setSelectedPipeline] = useState('');
  const [pipelineInput, setPipelineInput] = useState('');
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);

  const fetchData = async () => {
    try {
      const [pipeRes, eventRes] = await Promise.all([
        fetch('/api/pipelines'),
        fetch('/api/event-log?limit=10')
      ]);
      if (pipeRes.ok) {
        const pipeData = await pipeRes.json();
        setPipelines(pipeData.pipelines || []);
        if (pipeData.pipelines?.length > 0 && !selectedPipeline) {
          setSelectedPipeline(pipeData.pipelines[0]);
        }
      }
      if (eventRes.ok) {
        const eventData = await eventRes.json();
        setEvents(eventData || []);
      }
    } catch (e) {
      console.error('Failed to fetch engines data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleRunPipeline = async () => {
    if (!selectedPipeline) return;
    setRunning(true);
    setRunResult(null);
    try {
      const fd = new FormData();
      fd.append('name', selectedPipeline);
      fd.append('goal', pipelineInput);
      
      const res = await fetch('/api/pipeline', {
        method: 'POST',
        body: fd
      });
      const data = await res.json();
      setRunResult(data);
      fetchData(); // refresh events
    } catch (e: any) {
      setRunResult({ error: e.message });
    } finally {
      setRunning(false);
    }
  };

  if (loading && pipelines.length === 0) {
    return (
      <div className="glass-panel animate-fade-in" style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-muted)' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem' }}></div>
        <p>Initializing Engines...</p>
      </div>
    );
  }

  return (
    <div className="engines-container animate-fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      {/* Pipeline Runner */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="section-header" style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cpu size={20} className="text-accent" />
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Pipeline Orchestrator</h2>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>Select Engine Pipeline</label>
          <select 
            className="glass-input" 
            value={selectedPipeline}
            onChange={(e) => setSelectedPipeline(e.target.value)}
            style={{ width: '100%', appearance: 'none' }}
          >
            {pipelines.map(p => (
              <option key={p} value={p} style={{ background: '#090a0f', color: '#fff' }}>{p}</option>
            ))}
            {pipelines.length === 0 && <option>No pipelines found</option>}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>Instruction / Goal</label>
          <textarea 
            className="glass-input" 
            placeholder="E.g., Analyze the performance metrics..."
            value={pipelineInput}
            onChange={(e) => setPipelineInput(e.target.value)}
            style={{ minHeight: '100px', resize: 'vertical' }}
          />
        </div>

        <button 
          className="btn-glass" 
          onClick={handleRunPipeline}
          disabled={running || !selectedPipeline}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: running ? 'transparent' : 'rgba(56, 189, 248, 0.1)', borderColor: 'var(--color-accent)' }}
        >
          {running ? <div className="spinner" style={{ width: 16, height: 16 }}></div> : <Play size={16} />}
          {running ? 'Executing Pipeline...' : 'Dispatch Engine'}
        </button>

        {runResult && (
          <div style={{ 
            marginTop: '1rem', 
            padding: '1rem', 
            background: 'rgba(0,0,0,0.3)', 
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.05)',
            maxHeight: '200px',
            overflowY: 'auto',
            fontSize: '0.85rem',
            fontFamily: 'monospace'
          }}>
            <pre style={{ whiteSpace: 'pre-wrap', color: runResult.error ? '#ff4444' : '#00ffcc', margin: 0 }}>
              {JSON.stringify(runResult, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Event Log */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="section-header" style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={20} className="text-warning" />
            <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Event Bus Trace</h2>
          </div>
          <List size={16} className="text-muted" />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto', maxHeight: '500px', paddingRight: '0.5rem' }}>
          {events.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', textAlign: 'center', marginTop: '2rem' }}>No events in the bus yet.</p>
          ) : (
            events.map((ev, i) => (
              <div key={i} className="animate-fade-in" style={{ 
                animationDelay: `${i * 0.05}s`,
                padding: '0.75rem', 
                background: 'rgba(255,255,255,0.02)', 
                borderLeft: '2px solid var(--color-warning)',
                borderRadius: '0 4px 4px 0'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.8rem' }}>
                  <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{ev.type}</span>
                  <span style={{ color: 'var(--color-muted)' }}>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.5rem' }}>
                  <GitCommit size={10} /> source: {ev.source}
                </div>
                <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#94a3b8', background: 'rgba(0,0,0,0.3)', padding: '0.5rem', borderRadius: '4px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(ev.payload)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
