import React, { useCallback, useEffect } from 'react';
import ReactFlow, {
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';

interface WorkflowGraphProps {
  pipelineName?: string;
  activeSteps?: string[];
  onNodeClick?: (event: React.MouseEvent, node: any) => void;
  initialNodes?: any[];
  initialEdges?: any[];
}

export default function WorkflowGraph({ pipelineName, activeSteps = [], onNodeClick, initialNodes, initialEdges }: WorkflowGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (initialNodes && initialEdges) {
      const newNodes = initialNodes.map((n: any) => ({
        id: n.id,
        position: { x: 50 + n.index * 250, y: 100 + (n.index % 2 === 0 ? -50 : 50) },
        data: { label: n.label || n.id },
        style: { 
          background: '#0f172a', 
          color: '#e2e8f0', 
          border: '1px solid #38bdf8', 
          borderRadius: '8px', 
          padding: '10px',
          boxShadow: activeSteps.includes(n.id) ? '0 0 15px #38bdf8' : 'none'
        }
      }));
      const newEdges = initialEdges.map((e: any, i: number) => ({
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        animated: true,
        style: { stroke: '#38bdf8', strokeWidth: 2 }
      }));
      setNodes(newNodes);
      setEdges(newEdges);
      return;
    }

    if (!pipelineName) return;
    fetch(`/api/pipeline/${pipelineName}/dag`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'error') return;
        const newNodes = (data.nodes || []).map((n: any) => ({
          id: n.id,
          position: { x: 50 + n.index * 250, y: 100 + (n.index % 2 === 0 ? -50 : 50) },
          data: { label: n.label },
          style: { 
            background: '#0f172a', 
            color: '#e2e8f0', 
            border: '1px solid #38bdf8', 
            borderRadius: '8px', 
            padding: '10px',
            boxShadow: activeSteps.includes(n.id) ? '0 0 15px #38bdf8' : 'none',
            cursor: onNodeClick ? 'pointer' : 'default'
          }
        }));
        const newEdges = (data.edges || []).map((e: any, i: number) => ({
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          animated: true,
          style: { stroke: '#38bdf8', strokeWidth: 2 }
        }));
        setNodes(newNodes);
        setEdges(newEdges);
      });
  }, [pipelineName, activeSteps, setNodes, setEdges, initialNodes, initialEdges, onNodeClick]);

  const onConnect = useCallback(
    (params: any) => setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: '#38bdf8', strokeWidth: 2 } }, eds)),
    [setEdges]
  );

  return (
    <div style={{ width: '100%', height: '350px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginTop: '1rem' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        fitView
      >
        <Controls style={{ fill: '#38bdf8' }} />
        <Background color="rgba(56, 189, 248, 0.2)" gap={16} size={1} />
      </ReactFlow>
    </div>
  );
}
