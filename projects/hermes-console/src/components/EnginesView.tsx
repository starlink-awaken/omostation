import React, { useState, useEffect } from 'react';
import { Cpu, Play, Activity, List, GitCommit } from 'lucide-react';
import WorkflowGraph from './WorkflowGraph';

interface EventLog {
  id: string;
  type: string;
  time: string;
  source: string;
  payload: any;
}

export default function EnginesView() {
  const [pipelines, setPipelines] = useState<string[]>([]);
  const [events, setEvents] = useState<EventLog[]>([]);
  const [activeSteps, setActiveSteps] = useState<string[]>([]);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPipeline, setSelectedPipeline] = useState('');
  const [pipelineInput, setPipelineInput] = useState('');
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);
  
  const [planning, setPlanning] = useState(false);
  const [metaosPlan, setMetaosPlan] = useState<any>(null);

  const fetchData = async () => {
    try {
      const pipeRes = await fetch('/api/pipelines');
      if (pipeRes.ok) {
        const pipeData = await pipeRes.json();
        setPipelines(pipeData.pipelines || []);
        if (pipeData.pipelines?.length > 0 && !selectedPipeline) {
          setSelectedPipeline(pipeData.pipelines[0]);
        }
      }
    } catch (e) {
      console.error('Failed to fetch pipelines', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Polling for pipelines
    
    // SSE setup for real-time events
    const eventSource = new EventSource('/api/events');
    eventSource.onmessage = (e) => {
      try {
        const eventData = JSON.parse(e.data);
        
        if (eventData.type === 'node_running' || eventData.type === 'node_completed' || eventData.type === 'node_failed' || eventData.type === 'node_awaiting_approval') {
            const nodeId = eventData.payload?.node_id;
            if (nodeId !== undefined) {
                setActiveSteps(prev => {
                    return prev.includes(nodeId) ? prev : [...prev, nodeId];
                });
            }
        } else if (eventData.type === 'pipeline:step:ok' || eventData.type === 'pipeline:step:error') {
            const stepIndex = eventData.payload?.step_index;
            if (stepIndex !== undefined) {
                setActiveSteps(prev => {
                    const stepId = `step_${stepIndex}`;
                    return prev.includes(stepId) ? prev : [...prev, stepId];
                });
            }
        } else if (eventData.type === 'pipeline:started' || eventData.type === 'workflow_started') {
            setActiveSteps([]);
        }

        setEvents(prev => {
          // Keep the latest 50 events to avoid memory bloat
          const updated = [eventData, ...prev];
          return updated.slice(0, 50);
        });
      } catch (err) {
        // parsing error or keep-alive ping
      }
    };
    
    return () => {
      clearInterval(interval);
      eventSource.close();
    };
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

  const handlePlanTask = async () => {
    if (!pipelineInput) return;
    setPlanning(true);
    setRunResult(null);
    setMetaosPlan(null);
    try {
      const res = await fetch('/api/metaos/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: pipelineInput })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setMetaosPlan(data);
      } else {
        setRunResult(data);
      }
    } catch (e: any) {
      setRunResult({ error: e.message });
    } finally {
      setPlanning(false);
    }
  };

  const handleExecuteTask = async () => {
    if (!pipelineInput) return;
    setRunning(true);
    try {
      const res = await fetch('/api/metaos/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: pipelineInput })
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
        <p>引擎初始化中...</p>
      </div>
    );
  }

  return (
    <div className="engines-container animate-fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      {/* Pipeline Runner */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="section-header" style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cpu size={20} className="text-accent" />
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>管线编排器</h2>
        </div>
        
        <WorkflowGraph 
          pipelineName={metaosPlan ? undefined : selectedPipeline} 
          initialNodes={metaosPlan?.nodes}
          initialEdges={metaosPlan?.edges}
          activeSteps={activeSteps} 
          onNodeClick={(_, node) => setSelectedNode(node)}
        />
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '1rem' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>选择执行管线</label>
          <select 
            className="glass-input" 
            value={selectedPipeline}
            onChange={(e) => setSelectedPipeline(e.target.value)}
            style={{ width: '100%', appearance: 'none' }}
          >
            {pipelines.map(p => (
              <option key={p} value={p} style={{ background: '#090a0f', color: '#fff' }}>{p}</option>
            ))}
            {pipelines.length === 0 && <option>未发现可用管线</option>}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>执行指令 / 目标</label>
          <textarea 
            className="glass-input" 
            placeholder="例如：分析当前系统的性能指标..."
            value={pipelineInput}
            onChange={(e) => setPipelineInput(e.target.value)}
            style={{ minHeight: '100px', resize: 'vertical' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button 
            className="btn-glass" 
            onClick={handlePlanTask}
            disabled={planning || running || !pipelineInput}
            style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: planning ? 'transparent' : 'rgba(56, 189, 248, 0.1)', borderColor: 'var(--color-accent)' }}
          >
            {planning ? <div className="spinner" style={{ width: 16, height: 16 }}></div> : <Activity size={16} />}
            {planning ? '规划中...' : '新任务'}
          </button>

          {metaosPlan && (
            <button 
              className="btn-glass" 
              onClick={handleExecuteTask}
              disabled={running}
              style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: running ? 'transparent' : 'rgba(16, 185, 129, 0.1)', borderColor: '#10b981', color: '#10b981' }}
            >
              {running ? <div className="spinner" style={{ width: 16, height: 16 }}></div> : <Play size={16} />}
              {running ? '执行中...' : 'Start Execution'}
            </button>
          )}

          {!metaosPlan && (
            <button 
              className="btn-glass" 
              onClick={handleRunPipeline}
              disabled={running || !selectedPipeline}
              style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: running ? 'transparent' : 'rgba(56, 189, 248, 0.1)', borderColor: 'var(--color-accent)' }}
            >
              {running ? <div className="spinner" style={{ width: 16, height: 16 }}></div> : <Play size={16} />}
              {running ? '管线执行中...' : '调度引擎'}
            </button>
          )}
        </div>

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

        {selectedNode && (
          <div className="animate-fade-in" style={{ 
            marginTop: '1rem', 
            padding: '1rem', 
            background: 'rgba(15, 23, 42, 0.8)', 
            borderRadius: '8px',
            border: '1px solid #38bdf8'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, fontSize: '1rem', color: '#e2e8f0' }}>节点详情: {selectedNode.data?.label || selectedNode.id}</h3>
              <button 
                onClick={() => setSelectedNode(null)} 
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                ✕
              </button>
            </div>
            
            {(() => {
                const stepIndexMatch = selectedNode.id.match(/\d+/);
                const stepIndex = stepIndexMatch ? parseInt(stepIndexMatch[0], 10) : -1;
                
                const nodeEvents = events.filter(e => e.payload?.step_index === stepIndex || e.source === selectedNode.data?.label);
                
                let status = 'waiting';
                if (nodeEvents.some(e => e.type === 'pipeline:step:ok')) status = 'ok';
                else if (nodeEvents.some(e => e.type === 'pipeline:step:error')) status = 'error';
                else if (activeSteps.includes(selectedNode.id)) status = 'running';
                
                return (
                    <div style={{ fontSize: '0.85rem' }}>
                        <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                          <p style={{ margin: 0 }}><strong>ID:</strong> {selectedNode.id}</p>
                          <p style={{ margin: 0 }}>
                            <strong>状态:</strong>{' '}
                            <span style={{ 
                              color: status === 'ok' ? '#00ffcc' : 
                                     status === 'error' ? '#ff4444' : 
                                     status === 'running' ? '#38bdf8' : '#94a3b8',
                              fontWeight: 'bold'
                            }}>
                              {status.toUpperCase()}
                            </span>
                          </p>
                        </div>
                        
                        {nodeEvents.length > 0 && (
                            <div style={{ marginTop: '1rem' }}>
                                <strong style={{ color: '#94a3b8' }}>输出日志:</strong>
                                <div style={{ 
                                  marginTop: '0.5rem', 
                                  maxHeight: '200px', 
                                  overflowY: 'auto', 
                                  background: 'rgba(0,0,0,0.5)', 
                                  padding: '0.75rem', 
                                  borderRadius: '6px', 
                                  fontFamily: 'monospace', 
                                  color: '#e2e8f0' 
                                }}>
                                    {nodeEvents.map((e, i) => (
                                        <div key={i} style={{ marginBottom: '0.75rem', wordBreak: 'break-all', borderBottom: i < nodeEvents.length - 1 ? '1px solid rgba(255,255,255,0.1)' : 'none', paddingBottom: i < nodeEvents.length - 1 ? '0.75rem' : '0' }}>
                                            <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
                                              [{new Date(e.time).toLocaleTimeString()}] {e.type}
                                            </div>
                                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                                                {JSON.stringify(e.payload, null, 2)}
                                            </pre>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                );
            })()}
          </div>
        )}
      </div>

      {/* Event Log */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="section-header" style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={20} className="text-warning" />
            <h2 style={{ fontSize: '1.2rem', margin: 0 }}>消息总线追踪</h2>
          </div>
          <List size={16} className="text-muted" />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto', maxHeight: '500px', paddingRight: '0.5rem' }}>
          {events.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', textAlign: 'center', marginTop: '2rem' }}>总线暂无事件流。</p>
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
                  <span style={{ color: 'var(--color-muted)' }}>{new Date(ev.time).toLocaleString()}</span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.5rem' }}>
                  <GitCommit size={10} /> 来源: {ev.source}
                </div>
                <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#94a3b8', background: 'rgba(0,0,0,0.3)', padding: '0.5rem', borderRadius: '4px', overflowX: 'auto' }}>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
