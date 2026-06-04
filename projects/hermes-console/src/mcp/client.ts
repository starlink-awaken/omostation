import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export type TransportType = "sse" | "stdio";

export interface ToolInfo {
  name: string;
  description?: string;
  inputSchema?: any;
}

export class McpClient {
  private client: Client;
  private transport: SSEClientTransport | StdioClientTransport | null = null;
  private _connected = false;
  private _tools: ToolInfo[] = [];

  constructor(name = "hermes-console", version = "0.1.0") {
    this.client = new Client({ name, version });
  }

  get connected() {
    return this._connected;
  }

  get tools() {
    return this._tools;
  }

  async connect(url: string, transport: TransportType = "sse"): Promise<void> {
    if (transport === "sse") {
      this.transport = new SSEClientTransport(new URL(url));
    } else {
      const [cmd, ...args] = url.split(" ");
      this.transport = new StdioClientTransport({ command: cmd, args });
    }
    await this.client.connect(this.transport);
    this._connected = true;
    const result = await this.client.listTools();
    this._tools = result.tools.map((t) => ({
      name: t.name,
      description: t.description,
      inputSchema: t.inputSchema,
    }));
  }

  async disconnect(): Promise<void> {
    if (this.transport) {
      await this.transport.close();
      this.transport = null;
    }
    this._connected = false;
    this._tools = [];
  }

  async callTool(
    name: string,
    args: Record<string, unknown> = {},
  ): Promise<any> {
    if (!this._connected) throw new Error("Not connected");
    return await this.client.callTool({ name, arguments: args });
  }

  async getTool(name: string): Promise<ToolInfo | undefined> {
    return this._tools.find((t) => t.name === name);
  }
}
