import React, { useState } from "react";
import type { McpHookState } from "../hooks/useMcp";

const MOCK_AGENTS = [
  { id: "a1", name: "Researcher", status: "online" as const, capabilities: ["search", "analyze", "summarize"], lastSeen: Date.now() },
  { id: "a2", name: "Code Assistant", status: "busy" as const, capabilities: ["generate", "review", "refactor"], lastSeen: Date.now() - 8000 },
  { id: "a3", name: "Data Analyst", status: "online" as const, capabilities: ["query", "visualize", "report"], lastSeen: Date.now() - 30000 },
  { id: "a4", name: "Scheduler", status: "offline" as const, capabilities: ["plan", "dispatch", "monitor"], lastSeen: Date.now() - 7200000 },
];

const MOCK_TASKS = [
  { id: "t1", description: "Analyze knowledge graph connectivity", status: "running" as const, agent: "Researcher", progress: 0.75, created: Date.now() - 600000 },
  { id: "t2", description: "Generate quarterly summary report", status: "completed" as const, agent: "Data Analyst", progress: 1.0, created: Date.now() - 3600000 },
  { id: "t3", description: "Index new document corpus", status: "running" as const, agent: "Scheduler", progress: 0.3, created: Date.now() - 120000 },
  { id: "t4", description: "Validate ontology schema", status: "pending" as const, agent: "Researcher", progress: 0, created: Date.now() - 5000 },
];

const statusColor = (s: string) =>
  s === "online" ? "#4caf50" : s === "busy" ? "#ff9800" : "#f44336";
const taskStatusColor = (s: string) =>
  s === "completed" ? "#4caf50" : s === "running" ? "#2196f3" : s === "failed" ? "#f44336" : "#888";

export default function AgentPage({ mcp: _mcp }: { mcp: McpHookState }) {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");

  const sendMessage = () => {
    if (!input.trim()) return;
    setMessages(prev => [...prev,
      { role: "user", content: input },
      { role: "assistant", content: `[Simulated] Processing request: "${input}". This demonstrates the chat interface. Connect to a real MCP backend for live agent interaction.` }
    ]);
    setInput("");
  };

  return (
    <div style={{ padding: 32, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, maxWidth: 1100 }}>
      {/* Left column: Agents + Tasks */}
      <div>
        <h2 style={{ color: "#eee", fontSize: 22, fontWeight: 700, marginBottom: 16 }}>Agents</h2>
        {MOCK_AGENTS.map(a => (
          <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", marginBottom: 8, backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: statusColor(a.status), flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ color: "#eee", fontWeight: 600, fontSize: 14 }}>{a.name}</div>
              <div style={{ color: "#888", fontSize: 11 }}>{a.capabilities.join(", ")}</div>
            </div>
            <span style={{ color: statusColor(a.status), fontSize: 12, fontWeight: 600 }}>{a.status}</span>
          </div>
        ))}

        <h2 style={{ color: "#eee", fontSize: 22, fontWeight: 700, margin: "24px 0 16px" }}>Tasks</h2>
        {MOCK_TASKS.map(t => {
          const pct = Math.round(t.progress * 100);
          return (
            <div key={t.id} style={{ padding: "12px 16px", marginBottom: 8, backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ color: "#eee", fontSize: 14 }}>{t.description}</span>
                <span style={{ color: taskStatusColor(t.status), fontSize: 11, fontWeight: 600 }}>{t.status}</span>
              </div>
              <div style={{ color: "#888", fontSize: 11, marginBottom: 8 }}>Agent: {t.agent}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ flex: 1, height: 6, backgroundColor: "#1a1a2e", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${pct}%`, backgroundColor: t.status === "completed" ? "#4caf50" : "#e94560", borderRadius: 3, transition: "width 0.4s" }} />
                </div>
                <span style={{ color: "#888", fontSize: 10, minWidth: 30, textAlign: "right" }}>{pct}%</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Right column: Chat */}
      <div style={{ display: "flex", flexDirection: "column" }}>
        <h2 style={{ color: "#eee", fontSize: 22, fontWeight: 700, marginBottom: 16 }}>Chat</h2>
        <div style={{ flex: 1, maxHeight: 400, overflowY: "auto", marginBottom: 12, padding: 8, backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
          {messages.length === 0 && (
            <p style={{ color: "#666", textAlign: "center", paddingTop: 150, fontSize: 13 }}>No messages yet. Type a message below to start a conversation.</p>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: 8, padding: "8px 12px", backgroundColor: m.role === "user" ? "#1a1a2e" : "#0f0f23", borderRadius: 6 }}>
              <span style={{ color: m.role === "user" ? "#e94560" : "#4caf50", fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>{m.role}</span>
              <div style={{ color: "#ccc", marginTop: 4, fontSize: 13, lineHeight: 1.5 }}>{m.content}</div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendMessage()}
            placeholder="Type a message..." style={{ flex: 1, padding: "10px 16px", borderRadius: 6, border: "1px solid #2a2a4a", backgroundColor: "#1a1a2e", color: "#c0c0d0", fontSize: 14, outline: "none" }} />
          <button onClick={sendMessage} style={{ padding: "10px 24px", borderRadius: 6, border: "none", backgroundColor: "#e94560", color: "#fff", cursor: "pointer", fontWeight: 600 }}>Send</button>
        </div>
      </div>
    </div>
  );
}
