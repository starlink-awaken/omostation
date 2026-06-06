import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

describe("App", () => {
  it("renders the brand name", () => {
    render(<App />);
    expect(screen.getByText("Hermes Console")).toBeTruthy();
  });

  it("renders all navigation items", () => {
    render(<App />);
    expect(screen.getAllByText("Knowledge Dashboard").length).toBe(2);
    expect(screen.getByText("Agent Console")).toBeTruthy();
    expect(screen.getByText("Health Monitor")).toBeTruthy();
    expect(screen.getByText("Settings")).toBeTruthy();
  });

  it("shows MCP connection status in footer", () => {
    render(<App />);
    expect(screen.getByText(/MCP:/)).toBeTruthy();
    expect(screen.getByText(/Hermes Console v0.1.0/)).toBeTruthy();
  });

  it("renders dashboard page by default", () => {
    render(<App />);
    expect(screen.getByText(/Enter a query above/)).toBeTruthy();
  });
});
