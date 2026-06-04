import { useMemo } from "react";

export interface GraphNode {
  id: string;
  label: string;
  color?: string;
  size?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

interface KnowledgeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width?: number;
  height?: number;
}

const NODE_RADIUS = 24;
const CENTER_PAD = 60;

/**
 * 纯 SVG 知识图谱可视化，无外部依赖。
 * 节点按圆形排列，边用直线连接，自带图例。
 */
export default function KnowledgeGraph({
  nodes,
  edges,
  width = 600,
  height = 400,
}: KnowledgeGraphProps) {
  const layout = useMemo(() => {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(cx, cy) - CENTER_PAD;
    const positions: Record<string, { x: number; y: number }> = {};

    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
      positions[n.id] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
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
        No data to display
      </div>
    );
  }

  const edgeColor = "#2a2a5a";

  return (
    <svg
      width={width}
      height={height}
      style={{ backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e", display: "block" }}
    >
      {/* Edges */}
      {edges.map((e, i) => {
        const src = layout[e.source];
        const tgt = layout[e.target];
        if (!src || !tgt) return null;
        return (
          <g key={`edge-${i}`}>
            <line
              x1={src.x}
              y1={src.y}
              x2={tgt.x}
              y2={tgt.y}
              stroke={edgeColor}
              strokeWidth={1.5}
            />
            {e.label && (
              <text
                x={(src.x + tgt.x) / 2}
                y={(src.y + tgt.y) / 2 - 6}
                fill="#666"
                fontSize={10}
                textAnchor="middle"
              >
                {e.label}
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {nodes.map((n) => {
        const pos = layout[n.id];
        if (!pos) return null;
        const r = n.size ?? NODE_RADIUS;
        return (
          <g key={n.id}>
            <circle
              cx={pos.x}
              cy={pos.y}
              r={r}
              fill={n.color ?? "#e94560"}
              opacity={0.85}
              stroke="#fff"
              strokeWidth={1}
            />
            <text
              x={pos.x}
              y={pos.y + 4}
              fill="#fff"
              fontSize={11}
              fontWeight={600}
              textAnchor="middle"
              style={{ pointerEvents: "none" }}
            >
              {n.label.length > 10 ? n.label.slice(0, 10) + ".." : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
