export interface ServiceEndpoint {
  name: string;
  url: string;
  transport: "sse" | "stdio";
  description: string;
  connected: boolean;
}

export interface SearchResult {
  id: string;
  title: string;
  snippet: string;
  score: number;
  source: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  status: "online" | "busy" | "offline";
  capabilities: string[];
  lastSeen: number;
}

export interface AlertMessage {
  id: string;
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  source: string;
  timestamp: number;
}

export interface TaskInfo {
  id: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  agent: string;
  progress: number;
  created: number;
}
