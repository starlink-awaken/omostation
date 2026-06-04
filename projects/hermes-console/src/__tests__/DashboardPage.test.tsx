import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DashboardPage from "../dashboard/DashboardPage";
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

describe("DashboardPage", () => {
  it("renders the search interface", () => {
    render(<DashboardPage mcp={mockMcp()} />);
    expect(screen.getByText("Knowledge Dashboard")).toBeTruthy();
    expect(screen.getByPlaceholderText(/Search/)).toBeTruthy();
    expect(screen.getByText("Search")).toBeTruthy();
  });

  it("shows offline indicator when disconnected", () => {
    render(<DashboardPage mcp={mockMcp({ connected: false })} />);
    expect(screen.getByText(/offline mock data/)).toBeTruthy();
  });

  it("hides offline indicator when connected", () => {
    render(<DashboardPage mcp={mockMcp({ connected: true })} />);
    expect(screen.queryByText(/offline mock data/)).toBeNull();
  });

  it("displays initial empty state", () => {
    render(<DashboardPage mcp={mockMcp()} />);
    expect(screen.getByText(/Enter a query above/)).toBeTruthy();
  });

  it("displays mock results when searching offline", async () => {
    render(<DashboardPage mcp={mockMcp()} />);
    const input = screen.getByPlaceholderText(/Search/);
    fireEvent.change(input, { target: { value: "ontology" } });
    fireEvent.click(screen.getByText("Search"));

    expect(await screen.findByText("Ontology Engineering with OWL 2")).toBeTruthy();
  });

  it("shows stats after search", async () => {
    render(<DashboardPage mcp={mockMcp()} />);
    const input = screen.getByPlaceholderText(/Search/);
    fireEvent.change(input, { target: { value: "knowledge" } });
    fireEvent.click(screen.getByText("Search"));

    expect(await screen.findByText("Total Results")).toBeTruthy();
    expect(screen.getByText("Sources")).toBeTruthy();
    expect(screen.getByText("Avg Score")).toBeTruthy();
  });

  it("shows no results message for unmatched query", async () => {
    render(<DashboardPage mcp={mockMcp()} />);
    const input = screen.getByPlaceholderText(/Search/);
    fireEvent.change(input, { target: { value: "xyznonexistent12345" } });
    fireEvent.click(screen.getByText("Search"));

    expect(await screen.findByText(/No results found/)).toBeTruthy();
  });
});
