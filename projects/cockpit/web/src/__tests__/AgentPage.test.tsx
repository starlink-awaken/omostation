import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AgentPage from "../agent/AgentPage";
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

describe("AgentPage", () => {
  it("renders all agents", () => {
    render(<AgentPage mcp={mockMcp()} />);
    expect(screen.getByText("Researcher")).toBeTruthy();
    expect(screen.getByText("Code Assistant")).toBeTruthy();
    expect(screen.getByText("Data Analyst")).toBeTruthy();
    expect(screen.getByText("Scheduler")).toBeTruthy();
  });

  it("renders all tasks", () => {
    render(<AgentPage mcp={mockMcp()} />);
    expect(screen.getByText("Analyze knowledge graph connectivity")).toBeTruthy();
    expect(screen.getByText("Generate quarterly summary report")).toBeTruthy();
    expect(screen.getByText("Index new document corpus")).toBeTruthy();
    expect(screen.getByText("Validate ontology schema")).toBeTruthy();
  });

  it("renders chat interface", () => {
    render(<AgentPage mcp={mockMcp()} />);
    expect(screen.getByText("Chat")).toBeTruthy();
    expect(screen.getByPlaceholderText("Type a message...")).toBeTruthy();
    expect(screen.getByText("Send")).toBeTruthy();
  });

  it("shows empty chat state initially", () => {
    render(<AgentPage mcp={mockMcp()} />);
    expect(screen.getByText(/No messages yet/)).toBeTruthy();
  });

  it("adds user message on send", () => {
    render(<AgentPage mcp={mockMcp()} />);
    const input = screen.getByPlaceholderText("Type a message...");
    fireEvent.change(input, { target: { value: "hello agent" } });
    fireEvent.click(screen.getByText("Send"));

    expect(screen.getByText("hello agent")).toBeTruthy();
    expect(screen.getByText(/Simulated/)).toBeTruthy();
  });

  it("supports Enter key to send message", () => {
    render(<AgentPage mcp={mockMcp()} />);
    const input = screen.getByPlaceholderText("Type a message...");
    fireEvent.change(input, { target: { value: "enter message" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByText("enter message")).toBeTruthy();
  });

  it("does not send empty messages", () => {
    render(<AgentPage mcp={mockMcp()} />);
    const sendButton = screen.getByText("Send");
    fireEvent.click(sendButton);

    expect(screen.getByText(/No messages yet/)).toBeTruthy();
  });
});
