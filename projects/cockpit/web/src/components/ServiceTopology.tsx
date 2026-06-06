import { useMemo } from "react";

export interface TopologyNode {
  id: string;
  label: string;
  status: "healthy" | "degraded" | "offline";
}

export interface TopologyConnection {
  source: string;
  target: string;
  label?: string;
}

interface ServiceTopologyProps {
  nodes: TopologyNode[];
  connections: TopologyConnection[];
  width?: number;
  height?: number;
}

const NODE_W = 140;
const NODE_H = 44;
const STATUS_COLORS: Record<string, string> = {
  healthy: "#4caf50",
  degraded: "#ff9800",
  offline: "#f44336",
};

/**
 * 服务拓扑可视化 — 按层排列节点，用带箭头连线展示依赖关系。
 */
export default function ServiceTopology({
  nodes,
  connections,
  width = 600,
  height = 400,
}: ServiceTopologyProps) {
  const layout = useMemo(() => {
    // 分层布局：每 4 个节点一行
    const cols = 4;
    const padX = 40;
    const padY = 60;
    const cellW = (width - padX * 2) / cols;
    const positions: Record<string, { x: number; y: number }> = {};

    nodes.forEach((n, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      positions[n.id] = {
        x: padX + cellW * col + cellW / 2,
        y: padY + row * 90,
      };
    });

    return positions;
  }, [nodes, width, height]);

  if (nodes.length === 0) {
    return (
      <div
        style={{
          width,
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#666",
          fontSize: 13,
          backgroundColor: "#16213e",
          borderRadius: 8,
          border: "1px solid #1a1a3e",
        }}
      >
        No services to display
      </div>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      style={{ backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e", display: "block" }}
    >
      {/* Connections */}
      {connections.map((c, i) => {
        const src = layout[c.source];
        const tgt = layout[c.target];
        if (!src || !tgt) return null;

        const midX = (src.x + tgt.x) / 2;
        const midY = (src.y + tgt.y) / 2;

        return (
          <g key={`conn-${i}`}>
            <line
              x1={src.x}
              y1={src.y + NODE_H / 2}
              x2={tgt.x}
              y2={tgt.y - NODE_H / 2}
              stroke="#3a3a6a"
              strokeWidth={1.5}
              strokeDasharray={c.label ? "4,2" : undefined}
            />
            <polygon
              points={`${tgt.x - 5},${tgt.y - NODE_H / 2 - 5} ${tgt.x + 5},${tgt.y - NODE_H / 2 - 5} ${tgt.x},${tgt.y - NODE_H / 2 + 4}`}
              fill="#3a3a6a"
            />
            {c.label && (
              <text x={midX} y={midY - 8} fill="#666" fontSize={10} textAnchor="middle">
                {c.label}
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {nodes.map((n) => {
        const pos = layout[n.id];
        if (!pos) return null;
        const x = pos.x - NODE_W / 2;
        const y = pos.y - NODE_H / 2;

        return (
          <g key={n.id}>
            <rect
              x={x}
              y={y}
              width={NODE_W}
              height={NODE_H}
              rx={6}
              fill="#1a1a3e"
              stroke={STATUS_COLORS[n.status]}
              strokeWidth={2}
            />
            <circle
              cx={x + 14}
              cy={y + NODE_H / 2}
              r={5}
              fill={STATUS_COLORS[n.status]}
            />
            <text
              x={x + 24}
              y={y + NODE_H / 2 + 4}
              fill="#ddd"
              fontSize={12}
              fontWeight={600}
            >
              {n.label.length > 14 ? n.label.slice(0, 13) + ".." : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
