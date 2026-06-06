import React, { useState } from 'react';
import { Terminal, Play, Loader2, ShieldAlert } from 'lucide-react';

export default function SandboxTerminal() {
  const [code, setCode] = useState('print("Hello from eCOS Sandbox!")\n');
  const [output, setOutput] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  const handleExecute = async () => {
    setIsRunning(true);
    setOutput('Executing in secure sandbox...');
    
    try {
      const response = await fetch('/api/sandbox/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ code })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        setOutput(`Error: ${data.error || response.statusText}`);
        return;
      }

      if (data.success) {
        setOutput(`[Success] Duration: ${data.duration_ms.toFixed(2)}ms\n\n[STDOUT]\n${data.stdout}\n\n[RETURN]\n${JSON.stringify(data.output, null, 2)}`);
      } else {
        setOutput(`[Blocked/Failed]\n\n${data.error}`);
      }
    } catch (err: any) {
      setOutput(`Network Error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="sandbox-container animate-fade-in" style={{ animationDelay: '0.2s', padding: '1rem' }}>
      <div className="section-header" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Terminal size={24} className="text-accent" />
        <h2>Runtime Sandbox (KEI)</h2>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-warning)', fontSize: '0.85rem' }}>
          <ShieldAlert size={16} />
          <span>AST & OS-Level Isolation Active</span>
        </div>
      </div>
      
      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '1rem' }}>
        <div style={{ display: 'flex', gap: '1rem' }}>
          {/* Editor */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.9rem', color: 'var(--color-muted)' }}>Python Code</label>
            <textarea 
              value={code}
              onChange={(e) => setCode(e.target.value)}
              style={{
                width: '100%',
                height: '300px',
                backgroundColor: 'rgba(0,0,0,0.3)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                padding: '1rem',
                color: '#00ffcc',
                fontFamily: 'monospace',
                fontSize: '14px',
                resize: 'none',
                outline: 'none'
              }}
              spellCheck="false"
            />
            <button 
              className="btn-glass" 
              onClick={handleExecute} 
              disabled={isRunning}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '0.5rem' }}
            >
              {isRunning ? <Loader2 size={16} className="spinner" /> : <Play size={16} />}
              {isRunning ? 'Executing...' : 'Execute Code'}
            </button>
          </div>
          
          {/* Output */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.9rem', color: 'var(--color-muted)' }}>Console Output</label>
            <pre style={{
              flex: 1,
              backgroundColor: 'rgba(0,0,0,0.5)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              padding: '1rem',
              color: 'var(--color-text)',
              fontFamily: 'monospace',
              fontSize: '13px',
              whiteSpace: 'pre-wrap',
              overflowY: 'auto'
            }}>
              {output}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
