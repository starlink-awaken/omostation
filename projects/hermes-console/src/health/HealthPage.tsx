import React from "react";
import type { McpHookState } from "../hooks/useMcp";

const MOCK_SERVICES = [
  { name: "Kairon KOS API", status: "healthy" as const, lastHeartbeat: Date.now() - 2000 },
  { name: "GBrain Postgres", status: "healthy" as const, lastHeartbeat: Date.now() - 5000 },
  { name: "AgentMesh Gateway", status: "degraded" as const, lastHeartbeat: Date.now() - 60000 },
  { name: "SharedBrain Bridge", status: "offline" as const, lastHeartbeat: Date.now() - 300000 },
  { name: "Agora MCP Hub", status: "healthy" as const, lastHeartbeat: Date.now() - 1000 },
  { name: "Ontology Indexer", status: "healthy" as const, lastHeartbeat: Date.now() - 15000 },
];

const MOCK_ALERTS = [
  { id: "a1", severity: "critical" as const, message: "SharedBrain Bridge has been unreachable for 5+ minutes", source: "Health Checker", timestamp: Date.now() - 60000 },
  { id: "a2", severity: "warning" as const, message: "AgentMesh Gateway response time exceeds 500ms threshold", source: "Latency Monitor", timestamp: Date.now() - 120000 },
  { id: "a3", severity: "warning" as const, message: "KOS index cycle duration above baseline (142%)", source: "Scheduler", timestamp: Date.now() - 300000 },
  { id: "a4", severity: "info" as const, message: "Ontology Indexer completed full reindex of 12,847 entities", source: "Indexer", timestamp: Date.now() - 600000 },
  { id: "a5", severity: "info" as const, message: "Agent Researcher dispatched to task analyze-graph-connectivity", source: "Agent Runtime", timestamp: Date.now() - 900000 },
];

const statusColor = (s: string) =>
  s === "healthy" ? "#4caf50" : s === "degraded" ? "#ff9800" : "#f44336";
const sevColor = (s: string) =>
  s === "critical" ? "#f44336" : s === "error" ? "#ff5722" : s === "warning" ? "#ff9800" : "#2196f3";

function timeAgo(ts: number): string {
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  return `${Math.floor(min / 60)}h ago`;
}

export default function HealthPage({ mcp: _mcp }: { mcp: McpHookState }) {
  return (
    <div style={{ padding: 32, maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ color: "#eee", fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Health Monitor</h2>
      <p style={{ color: "#888", fontSize: 13, marginBottom: 24 }}>System health metrics, service status, and alert history</p>

      <h3 style={{ color: "#ddd", fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Services</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 12, marginBottom: 32 }}>
        {MOCK_SERVICES.map(s => (
          <div key={s.name} style={{ padding: "16px 20px", backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: statusColor(s.status) }} />
              <span style={{ color: "#eee", fontWeight: 600, fontSize: 14 }}>{s.name}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span style={{ color: statusColor(s.status), fontWeight: 600 }}>{s.status}</span>
              <span style={{ color: "#666" }}>Last: {timeAgo(s.lastHeartbeat)}</span>
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ color: "#ddd", fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Alerts</h3>
      {MOCK_ALERTS.length === 0 && <p style={{ color: "#666" }}>No alerts.</p>}
      {MOCK_ALERTS.map(a => (
        <div key={a.id} style={{ display: "flex", gap: 12, padding: "12px 16px", marginBottom: 8, backgroundColor: "#16213e", borderRadius: 6, borderLeft: `3px solid ${sevColor(a.severity)}` }}>
          <span style={{ color: sevColor(a.severity), fontSize: 11, fontWeight: 700, minWidth: 60, textTransform: "uppercase" }}>{a.severity}</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.4 }}>{a.message}</div>
            <div style={{ color: "#666", fontSize: 11, marginTop: 2 }}>{a.source} &middot; {timeAgo(a.timestamp)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
