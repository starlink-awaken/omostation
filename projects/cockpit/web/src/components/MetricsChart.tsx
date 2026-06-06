import { useMemo } from "react";

export interface ChartDataPoint {
  label: string;
  value: number;
  color?: string;
}

interface MetricsChartProps {
  data: ChartDataPoint[];
  type?: "bar" | "line";
  width?: number;
  height?: number;
  title?: string;
  maxValue?: number;
}

const BAR_GAP = 4;
const CHART_PAD = { top: 24, right: 16, bottom: 32, left: 16 };

/**
 * 纯 SVG 柱状图 / 折线图，用于展示系统指标。
 */
export default function MetricsChart({
  data,
  type = "bar",
  width = 480,
  height = 240,
  title,
  maxValue,
}: MetricsChartProps) {
  const chartW = width - CHART_PAD.left - CHART_PAD.right;
  const chartH = height - CHART_PAD.top - CHART_PAD.bottom;

  const max = maxValue ?? Math.max(...data.map((d) => d.value), 1);

  const barWidth = useMemo(() => {
    if (data.length === 0) return 0;
    return Math.max(4, Math.floor((chartW - (data.length - 1) * BAR_GAP) / data.length));
  }, [data.length, chartW]);

  if (data.length === 0) {
    return (
      <div
        style={{
          width,
          height,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#666",
          fontSize: 13,
          backgroundColor: "#16213e",
          borderRadius: 8,
          border: "1px solid #1a1a3e",
        }}
      >
        {title && <div style={{ marginBottom: 8, color: "#ddd", fontSize: 14, fontWeight: 600 }}>{title}</div>}
        <div>No data to display</div>
      </div>
    );
  }

  const defaultColors = ["#e94560", "#4ecdc4", "#ff9800", "#2196f3", "#9c27b0", "#4caf50"];

  if (type === "line") {
    // 折线图
    const points = data.map((d, i) => {
      const x = CHART_PAD.left + (chartW / (data.length - 1 || 1)) * i;
      const y = CHART_PAD.top + chartH * (1 - d.value / max);
      return `${x},${y}`;
    });

    const polyline = points.join(" ");
    const areaPoints = `${CHART_PAD.left + chartW},${CHART_PAD.top + chartH} ${CHART_PAD.left},${CHART_PAD.top + chartH} ${polyline}`;

    return (
      <svg
        width={width}
        height={height}
        style={{ backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e", display: "block" }}
      >
        {title && (
          <text x={width / 2} y={16} fill="#ddd" fontSize={13} fontWeight={600} textAnchor="middle">
            {title}
          </text>
        )}

        {/* Area fill */}
        <polygon points={areaPoints} fill="rgba(233,69,96,0.1)" />

        {/* Line */}
        <polyline
          points={polyline}
          fill="none"
          stroke="#e94560"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Dots + Labels */}
        {data.map((d, i) => {
          const x = CHART_PAD.left + (chartW / (data.length - 1 || 1)) * i;
          const y = CHART_PAD.top + chartH * (1 - d.value / max);
          return (
            <g key={i}>
              <circle cx={x} cy={y} r={3} fill={d.color ?? "#e94560"} stroke="#16213e" strokeWidth={1} />
              <text x={x} y={CHART_PAD.top + chartH + 16} fill="#888" fontSize={10} textAnchor="middle">
                {d.label.length > 6 ? d.label.slice(0, 6) + ".." : d.label}
              </text>
              <text x={x} y={y - 8} fill="#aaa" fontSize={10} textAnchor="middle">
                {d.value}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  // 柱状图
  return (
    <svg
      width={width}
      height={height}
      style={{ backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e", display: "block" }}
    >
      {title && (
        <text x={width / 2} y={16} fill="#ddd" fontSize={13} fontWeight={600} textAnchor="middle">
          {title}
        </text>
      )}

      {data.map((d, i) => {
        const x = CHART_PAD.left + i * (barWidth + BAR_GAP);
        const barH = (d.value / max) * chartH;
        const y = CHART_PAD.top + chartH - barH;
        const color = d.color ?? defaultColors[i % defaultColors.length];

        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={barWidth}
              height={Math.max(barH, 1)}
              rx={2}
              fill={color}
              opacity={0.85}
            >
              <title>{`${d.label}: ${d.value}`}</title>
            </rect>
            <text x={x + barWidth / 2} y={CHART_PAD.top + chartH + 14} fill="#888" fontSize={10} textAnchor="middle">
              {d.label.length > 6 ? d.label.slice(0, 6) + ".." : d.label}
            </text>
            <text x={x + barWidth / 2} y={y - 4} fill="#aaa" fontSize={10} textAnchor="middle">
              {d.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
