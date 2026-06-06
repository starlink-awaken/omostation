import React, { useState } from "react";
import type { McpHookState } from "../hooks/useMcp";

export default function SettingsPage({ mcp }: { mcp: McpHookState }) {
  const [url, setUrl] = useState(mcp.endpoint || "http://localhost:8000/mcp");

  const handleConnect = async () => {
    try {
      await mcp.connect(url);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Connection failed");
    }
  };

  return (
    <div style={{ padding: 32, maxWidth: 600 }}>
      <h2 style={{ color: "#eee", fontSize: 22, fontWeight: 700, marginBottom: 24 }}>Settings</h2>

      {/* MCP Connection */}
      <div style={{ marginBottom: 24, padding: 20, backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
        <h3 style={{ color: "#ddd", marginBottom: 12, fontSize: 15, fontWeight: 600 }}>MCP Connection</h3>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input value={url} onChange={e => setUrl(e.target.value)}
            placeholder="ws://localhost:8000/mcp"
            disabled={mcp.connected}
            style={{ flex: 1, padding: "10px 16px", borderRadius: 6, border: "1px solid #2a2a4a", backgroundColor: "#1a1a2e", color: "#c0c0d0", fontSize: 14, outline: "none" }} />
          {mcp.connected ? (
            <button onClick={mcp.disconnect} style={{ padding: "10px 24px", borderRadius: 6, border: "none", backgroundColor: "#f44336", color: "#fff", cursor: "pointer", fontWeight: 600 }}>Disconnect</button>
          ) : (
            <button onClick={handleConnect} style={{ padding: "10px 24px", borderRadius: 6, border: "none", backgroundColor: "#4caf50", color: "#fff", cursor: "pointer", fontWeight: 600 }}>Connect</button>
          )}
        </div>
        <div style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: mcp.connected ? "#4caf50" : "#888" }} />
          <span style={{ color: mcp.connected ? "#4caf50" : "#888" }}>
            {mcp.connected ? `Connected to ${mcp.endpoint} (${mcp.tools.length} tools)` : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Available Tools */}
      {mcp.connected && mcp.tools.length > 0 && (
        <div style={{ marginBottom: 24, padding: 20, backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
          <h3 style={{ color: "#ddd", marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Available Tools</h3>
          {mcp.tools.length === 0 && <p style={{ color: "#666", fontSize: 13 }}>No tools registered.</p>}
          {mcp.tools.map(t => (
            <div key={t.name} style={{ padding: "10px 0", borderBottom: "1px solid #1a1a3e", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#e94560", fontWeight: 600, fontSize: 13 }}>{t.name}</span>
              <span style={{ color: "#888", fontSize: 12 }}>{t.description || "—"}</span>
            </div>
          ))}
        </div>
      )}

      {/* System Info */}
      <div style={{ padding: 20, backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
        <h3 style={{ color: "#ddd", marginBottom: 12, fontSize: 15, fontWeight: 600 }}>System</h3>
        <div style={{ color: "#888", fontSize: 13, lineHeight: 2 }}>
          <div><span style={{ color: "#999" }}>Version:</span> Hermes Console v0.1.0</div>
          <div><span style={{ color: "#999" }}>Framework:</span> React 18 + TypeScript + Vite</div>
          <div><span style={{ color: "#999" }}>MCP SDK:</span> @modelcontextprotocol/sdk v1.29.0</div>
          <div><span style={{ color: "#999" }}>Theme:</span> Dark (0x0f0f23)</div>
        </div>
      </div>
    </div>
  );
}
