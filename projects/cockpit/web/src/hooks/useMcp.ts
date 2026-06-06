import { useState, useCallback, useEffect, useRef, createContext, useContext } from "react";
import { McpClient, ToolInfo } from "../mcp/client";

export interface McpHookState {
  connected: boolean;
  tools: ToolInfo[];
  endpoint: string;
  connect: (url: string) => Promise<void>;
  disconnect: () => void;
  callTool: (name: string, args?: Record<string, unknown>) => Promise<any>;
}

export function useMcp(): McpHookState {
  const clientRef = useRef(new McpClient());
  const [connected, setConnected] = useState(false);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [endpoint, setEndpoint] = useState("");

  const connect = useCallback(async (url: string) => {
    await clientRef.current.connect(url);
    setConnected(true);
    setTools(clientRef.current.tools);
    setEndpoint(url);
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current.disconnect();
    setConnected(false);
    setTools([]);
  }, []);

  const callTool = useCallback(
    async (name: string, args?: Record<string, unknown>) => {
      return await clientRef.current.callTool(name, args);
    },
    []
  );

  useEffect(() => {
    return () => {
      clientRef.current.disconnect();
    };
  }, []);

  return { connected, tools, endpoint, connect, disconnect, callTool };
}

export const McpContext = createContext<McpHookState>(null!);

export function useMcpContext() {
  return useContext(McpContext);
}
