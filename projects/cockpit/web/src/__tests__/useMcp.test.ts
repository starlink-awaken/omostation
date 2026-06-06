import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMcp } from "../hooks/useMcp";

const mockConnect = vi.fn();
const mockDisconnect = vi.fn();
const mockCallTool = vi.fn();

vi.mock("../mcp/client", () => ({
  McpClient: vi.fn(() => ({
    connect: mockConnect,
    disconnect: mockDisconnect,
    callTool: mockCallTool,
    get tools() {
      return [];
    },
    get connected() {
      return false;
    },
  })),
}));

describe("useMcp", () => {
  beforeEach(() => {
    mockConnect.mockReset().mockResolvedValue(undefined);
    mockDisconnect.mockReset();
    mockCallTool.mockReset().mockResolvedValue({});
  });

  it("returns initial disconnected state", () => {
    const { result } = renderHook(() => useMcp());

    expect(result.current.connected).toBe(false);
    expect(result.current.tools).toEqual([]);
    expect(result.current.endpoint).toBe("");
    expect(typeof result.current.connect).toBe("function");
    expect(typeof result.current.disconnect).toBe("function");
    expect(typeof result.current.callTool).toBe("function");
  });

  it("delegates connect to underlying client", async () => {
    const { result } = renderHook(() => useMcp());

    await act(async () => {
      await result.current.connect("http://test:8000/mcp");
    });

    expect(mockConnect).toHaveBeenCalledWith("http://test:8000/mcp");
  });

  it("delegates disconnect to underlying client", () => {
    const { result } = renderHook(() => useMcp());

    act(() => {
      result.current.disconnect();
    });

    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("delegates callTool to underlying client", async () => {
    mockCallTool.mockResolvedValue({ content: "done" });

    const { result } = renderHook(() => useMcp());

    const response = await result.current.callTool("search", { q: "test" });

    expect(mockCallTool).toHaveBeenCalledWith("search", { q: "test" });
    expect(response).toEqual({ content: "done" });
  });
});
