import React, { useState, useEffect } from 'react';
import { Server, Activity, DollarSign, Cpu } from 'lucide-react';

export default function ComputeView() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCompute = async () => {
      try {
        const res = await fetch('/api/compute/status');
        if (res.ok) {
          setData(await res.json());
        }
      } catch (err) {
        console.error('Failed to fetch compute data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCompute();
    const timer = setInterval(fetchCompute, 10000);
    return () => clearInterval(timer);
  }, []);

  if (loading) {
    return (
      <div className="glass-panel animate-fade-in" style={{ padding: '20px', marginTop: '20px' }}>
        <p className="text-muted">加载算力网格数据...</p>
      </div>
    );
  }

  const nodes = data?.nodes || [];
  const quota = data?.quota?.quota || [];

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '20px', marginTop: '20px' }}>
      <div className="section-header" style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>混合云算力监控 (Compute Grid)</h2>
        <p className="text-muted">Local-Mac / LAN / Cloud 流转与账单状态</p>
      </div>

      <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
        {/* Nodes section */}
        <div style={{ flex: '1 1 300px' }}>
          <h3 style={{ marginBottom: '10px', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} className="text-accent" /> 物理节点拓扑
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {nodes.map((node: any) => (
              <div key={node.id} style={{ 
                padding: '15px', 
                background: 'rgba(255,255,255,0.02)', 
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontWeight: 'bold' }}>{node.name}</div>
                  <div className="text-muted" style={{ fontSize: '0.85rem' }}>{node.model}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ 
                    color: node.status === 'online' ? '#10b981' : '#f59e0b',
                    fontSize: '0.85rem',
                    textTransform: 'uppercase'
                  }}>● {node.status}</span>
                  <div className="text-muted" style={{ fontSize: '0.8rem' }}>{node.type}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quota section */}
        <div style={{ flex: '1 1 300px' }}>
          <h3 style={{ marginBottom: '10px', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <DollarSign size={18} className="text-success" /> CodexBar 配额缓存
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {quota.length === 0 ? (
              <p className="text-muted">未找到配额数据 (可能缓存中无数据)</p>
            ) : (
              quota.map((q: any, i: number) => (
                <div key={i} style={{
                  padding: '15px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px'
                }}>
                  <div style={{ fontWeight: 'bold', textTransform: 'capitalize' }}>{q.provider}</div>
                  {q.error ? (
                    <div style={{ color: '#ef4444', fontSize: '0.85rem', marginTop: '4px' }}>{q.error.message || 'Error fetching quota'}</div>
                  ) : (
                    <div style={{ fontSize: '0.85rem', marginTop: '4px' }}>
                      可用: {q.available ? '是' : '否'}
                    </div>
                  )}
                  {q.provider === 'openai' && q.usage && (
                     <div style={{ fontSize: '0.85rem', marginTop: '4px' }}>
                       Token 额度: {q.usage.total_granted} / 已用: {q.usage.total_used}
                     </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
