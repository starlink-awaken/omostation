import { useState } from "react";
import { useMcp, McpContext } from "./hooks/useMcp";
import DashboardPage from "./dashboard/DashboardPage";
import AgentPage from "./agent/AgentPage";
import HealthPage from "./health/HealthPage";
import SettingsPage from "./settings/SettingsPage";

type NavItem = "knowledge" | "agent" | "health" | "settings";

const NAV: { key: NavItem; label: string }[] = [
  { key: "knowledge", label: "Knowledge Dashboard" },
  { key: "agent", label: "Agent Console" },
  { key: "health", label: "Health Monitor" },
  { key: "settings", label: "Settings" },
];

function NavBar({ active, onNav }: { active: NavItem; onNav: (n: NavItem) => void }) {
  return (
    <nav style={{ display: "flex", gap: 0, backgroundColor: "#1a1a2e", padding: "0 24px", borderBottom: "2px solid #16213e" }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#e94560", padding: "14px 24px 14px 0", marginRight: 32, letterSpacing: 1 }}>Hermes Console</div>
      {NAV.map(item => (
        <button key={item.key} onClick={() => onNav(item.key)}
          style={{ background: "none", border: "none", borderBottom: active === item.key ? "3px solid #e94560" : "3px solid transparent", color: active === item.key ? "#e94560" : "#a0a0b8", fontSize: 14, fontWeight: active === item.key ? 600 : 400, padding: "14px 20px", cursor: "pointer", transition: "color 0.2s" }}>
          {item.label}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [active, setActive] = useState<NavItem>("knowledge");
  const mcp = useMcp();
  const render = () => {
    switch (active) {
      case "knowledge": return <DashboardPage mcp={mcp} />;
      case "agent": return <AgentPage mcp={mcp} />;
      case "health": return <HealthPage mcp={mcp} />;
      case "settings": return <SettingsPage mcp={mcp} />;
    }
  };

  return (
    <McpContext.Provider value={mcp}>
      <div style={{ minHeight: "100vh", backgroundColor: "#0f0f23", color: "#c0c0d0", fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
        <NavBar active={active} onNav={setActive} />
        <main>{render()}</main>
        <footer style={{ position: "fixed", bottom: 0, left: 0, right: 0, padding: "10px 24px", backgroundColor: "#1a1a2e", borderTop: "1px solid #16213e", fontSize: 12, color: "#555", display: "flex", justifyContent: "space-between" }}>
          <span>MCP: {mcp.connected ? "Connected" : "Disconnected"}</span>
          <span>Hermes Console v0.1.0</span>
        </footer>
      </div>
    </McpContext.Provider>
  );
}
