import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SettingsPage from "../settings/SettingsPage";
import type { McpHookState } from "../hooks/useMcp";

function mockMcp(overrides: Partial<McpHookState> = {}): McpHookState {
  return {
    connected: false,
    tools: [],
    endpoint: "",
    connect: vi.fn(),
    disconnect: vi.fn(),
    callTool: vi.fn(),
    ...overrides,
  };
}

describe("SettingsPage", () => {
  it("renders settings title", () => {
    render(<SettingsPage mcp={mockMcp()} />);
    expect(screen.getByText("Settings")).toBeTruthy();
  });

  it("renders MCP connection section", () => {
    render(<SettingsPage mcp={mockMcp()} />);
    expect(screen.getByText("MCP Connection")).toBeTruthy();
    expect(screen.getByPlaceholderText(/ws:/)).toBeTruthy();
  });

  it("shows disconnected state with Connect button", () => {
    render(<SettingsPage mcp={mockMcp()} />);
    expect(screen.getByText("Disconnected")).toBeTruthy();
    expect(screen.getByText("Connect")).toBeTruthy();
  });

  it("shows connected state with Disconnect button", () => {
    render(
      <SettingsPage
        mcp={mockMcp({
          connected: true,
          endpoint: "ws://localhost:8000/mcp",
          tools: [{ name: "search", description: "Search tool" }],
        })}
      />
    );
    expect(screen.getByText(/Connected to ws/)).toBeTruthy();
    expect(screen.getByText("Disconnect")).toBeTruthy();
  });

  it("shows tool list when connected with tools", () => {
    render(
      <SettingsPage
        mcp={mockMcp({
          connected: true,
          endpoint: "ws://localhost:8000/mcp",
          tools: [
            { name: "search", description: "Search tool" },
            { name: "query", description: "Query tool" },
          ],
        })}
      />
    );
    expect(screen.getByText("Available Tools")).toBeTruthy();
    expect(screen.getByText("search")).toBeTruthy();
    expect(screen.getByText("query")).toBeTruthy();
  });

  it("renders system info section", () => {
    render(<SettingsPage mcp={mockMcp()} />);
    expect(screen.getByText("System")).toBeTruthy();
    expect(screen.getByText(/Hermes Console v0.1.0/)).toBeTruthy();
    expect(screen.getByText(/React 18/)).toBeTruthy();
    expect(screen.getByText(/Dark/)).toBeTruthy();
  });

  it("calls connect when Connect button is clicked", async () => {
    const connect = vi.fn().mockResolvedValue(undefined);
    const windowAlert = vi.spyOn(window, "alert").mockImplementation(() => {});

    render(<SettingsPage mcp={mockMcp({ connect })} />);

    const connectBtn = screen.getByText("Connect");
    fireEvent.click(connectBtn);

    expect(connect).toHaveBeenCalledWith("http://localhost:8000/mcp");
    windowAlert.mockRestore();
  });
});
