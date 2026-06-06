import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import HealthPage from "../health/HealthPage";
import type { McpHookState } from "../hooks/useMcp";

function mockMcp(): McpHookState {
  return {
    connected: false,
    tools: [],
    endpoint: "",
    connect: vi.fn(),
    disconnect: vi.fn(),
    callTool: vi.fn(),
  };
}

describe("HealthPage", () => {
  it("renders the page title", () => {
    render(<HealthPage mcp={mockMcp()} />);
    expect(screen.getByText("Health Monitor")).toBeTruthy();
  });

  it("renders all service cards", () => {
    render(<HealthPage mcp={mockMcp()} />);
    expect(screen.getByText("Kairon KOS API")).toBeTruthy();
    expect(screen.getByText("GBrain Postgres")).toBeTruthy();
    expect(screen.getByText("AgentMesh Gateway")).toBeTruthy();
    expect(screen.getByText("SharedBrain Bridge")).toBeTruthy();
    expect(screen.getByText("Agora MCP Hub")).toBeTruthy();
    expect(screen.getByText("Ontology Indexer")).toBeTruthy();
  });

  it("renders service status labels", () => {
    render(<HealthPage mcp={mockMcp()} />);
    const healthy = screen.getAllByText("healthy");
    expect(healthy.length).toBeGreaterThanOrEqual(3);

    expect(screen.getByText("degraded")).toBeTruthy();
    expect(screen.getByText("offline")).toBeTruthy();
  });

  it("renders alerts section", () => {
    render(<HealthPage mcp={mockMcp()} />);
    expect(screen.getByText("Alerts")).toBeTruthy();
  });

  it("renders all alert severities", () => {
    render(<HealthPage mcp={mockMcp()} />);
    expect(screen.getByText("critical")).toBeTruthy();
    const warnings = screen.getAllByText("warning");
    expect(warnings.length).toBe(2);
    const infos = screen.getAllByText("info");
    expect(infos.length).toBe(2);
  });

  it("renders alert messages", () => {
    render(<HealthPage mcp={mockMcp()} />);
    expect(screen.getByText(/SharedBrain Bridge has been unreachable/)).toBeTruthy();
    expect(screen.getByText(/AgentMesh Gateway response time exceeds/)).toBeTruthy();
  });
});
