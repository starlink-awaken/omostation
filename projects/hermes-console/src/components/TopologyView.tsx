import { useState, useEffect, memo } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MarkerType,
  useNodesState,
  useEdgesState,
  Handle,
  Position
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { Server, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

const ServiceNode = memo(({ data }: any) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle size={14} style={{ color: '#10b981' }} />;
      case 'offline': return <XCircle size={14} style={{ color: '#ef4444' }} />;
      case 'degraded': return <AlertTriangle size={14} style={{ color: '#f59e0b' }} />;
      default: return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return '#10b981';
      case 'offline': return '#ef4444';
      case 'degraded': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  return (
    <div style={{ 
      padding: '12px 16px', 
      borderRadius: '8px',
      background: 'rgba(20, 20, 25, 0.95)',
      border: `1px solid ${getStatusColor(data.status)}`,
      color: '#fff',
      minWidth: '160px',
      boxShadow: '0 8px 16px -4px rgba(0, 0, 0, 0.5), 0 4px 8px -4px rgba(0, 0, 0, 0.3)',
      backdropFilter: 'blur(8px)'
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <Server size={18} color={getStatusColor(data.status)} />
        <span style={{ fontWeight: 600, fontSize: '14px', letterSpacing: '0.02em' }}>{data.name}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#9ca3af' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {getStatusIcon(data.status)} 
          <span style={{ textTransform: 'capitalize' }}>{data.status}</span>
        </span>
        {data.latency && <span>{data.latency}</span>}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

const nodeTypes = {
  serviceNode: ServiceNode,
};

export default function TopologyView() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchServices = async () => {
      try {
        const response = await fetch('/api/services');
        let rawServices = [];
        if (response.ok) {
          rawServices = await response.json();
        } else {
          // Fallback mock data
          rawServices = [
            { name: 'Agora Mesh', circuit: '闭合', uptime: '99.9%', latency: '12ms' },
            { name: 'Minerva Research', circuit: '闭合', uptime: '99.5%', latency: '45ms' },
            { name: 'SharedBrain Bridge', circuit: '断路', uptime: '0%', latency: '-' },
            { name: 'LLM Gateway', circuit: '半开', uptime: '98.2%', latency: '850ms' },
            { name: 'KOS Substrate', circuit: '闭合', uptime: '100%', latency: '2ms' },
          ];
        }

        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];
        
        const centerX = 350;
        const centerY = 250;
        const radius = 200;

        const meshNode = rawServices.find((s: any) => s.name.includes('Agora')) || rawServices[0];
        const otherNodes = rawServices.filter((s: any) => s !== meshNode);

        // Add Mesh (Central Node)
        if (meshNode) {
          const status = meshNode.circuit === '断路' ? 'offline' : meshNode.circuit === '半开' ? 'degraded' : 'online';
          newNodes.push({
            id: meshNode.name,
            type: 'serviceNode',
            position: { x: centerX, y: centerY },
            data: { name: meshNode.name, status, latency: meshNode.latency, uptime: meshNode.uptime }
          });
        }

        // Add Others
        otherNodes.forEach((svc: any, index: number) => {
          const angle = (index / otherNodes.length) * 2 * Math.PI - Math.PI / 2; // Start from top
          const x = centerX + radius * Math.cos(angle);
          const y = centerY + radius * Math.sin(angle);
          const status = svc.circuit === '断路' ? 'offline' : svc.circuit === '半开' ? 'degraded' : 'online';

          newNodes.push({
            id: svc.name,
            type: 'serviceNode',
            position: { x, y },
            data: { name: svc.name, status, latency: svc.latency, uptime: svc.uptime }
          });

          // Connect to mesh
          if (meshNode) {
            newEdges.push({
              id: `edge-${meshNode.name}-${svc.name}`,
              source: meshNode.name,
              target: svc.name,
              animated: status === 'online', // animate flow if online
              style: { stroke: status === 'offline' ? '#ef4444' : '#6366f1', strokeWidth: 2, opacity: 0.7 },
              markerEnd: { 
                type: MarkerType.ArrowClosed, 
                color: status === 'offline' ? '#ef4444' : '#6366f1' 
              }
            });
          }
        });

        setNodes(newNodes);
        setEdges(newEdges);
      } catch (error) {
        console.error('Failed to load topology:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchServices();
    const interval = setInterval(fetchServices, 5000);
    return () => clearInterval(interval);
  }, [setNodes, setEdges]);

  return (
    <div className="glass-panel animate-fade-in" style={{ width: '100%', height: 'calc(100vh - 180px)', marginTop: '20px', display: 'flex', flexDirection: 'column' }}>
      <div className="section-header" style={{ padding: '20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#e5e7eb', margin: 0 }}>全局拓扑地图 (Sage View)</h2>
        <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '4px' }}>上帝视角：实时网络流、路由策略与熔断状态</p>
      </div>
      <div style={{ flex: 1, position: 'relative' }}>
        {loading ? (
          <div className="loading-state" style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <div className="spinner" style={{ marginBottom: '16px' }}></div>
            <p className="text-muted">正在探测微服务网格拓扑...</p>
          </div>
        ) : (
          <ReactFlow 
            nodes={nodes} 
            edges={edges} 
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-right"
          >
            <Background color="rgba(255,255,255,0.05)" gap={24} size={2} />
            <Controls style={{ background: 'rgba(20,20,25,0.8)', border: '1px solid rgba(255,255,255,0.1)', fill: '#fff' }} />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
