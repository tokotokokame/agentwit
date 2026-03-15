// Transport types
export type TransportType = 'stdio' | 'http' | 'sse';

// Connection configuration
export interface ConnectionConfig {
  type: TransportType;
  // stdio fields
  command?: string;
  args?: string[];
  // HTTP/SSE fields
  url?: string;
  headers?: Record<string, string>;
}

// JSON Schema types
export interface JSONSchema {
  type?: string | string[];
  properties?: Record<string, JSONSchema>;
  required?: string[];
  items?: JSONSchema;
  description?: string;
  enum?: unknown[];
  default?: unknown;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  additionalProperties?: boolean | JSONSchema;
  anyOf?: JSONSchema[];
  oneOf?: JSONSchema[];
  allOf?: JSONSchema[];
  $ref?: string;
  title?: string;
}

// MCP Tool definition
export interface MCPTool {
  name: string;
  description?: string;
  inputSchema: JSONSchema;
}

// Execution record for history
export type ExecutionStatus = 'success' | 'error' | 'pending';

export interface ExecutionRecord {
  id: string;
  toolName: string;
  params: Record<string, unknown>;
  response?: unknown;
  error?: string;
  timestamp: Date;
  duration: number; // milliseconds
  status: ExecutionStatus;
}

// Connection status
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// Language
export type Language = 'en' | 'ja';

// App state for zustand store
export interface AppState {
  // Connection
  connectionConfig: ConnectionConfig;
  connectionStatus: ConnectionStatus;
  lastError: string | null;

  // Tools
  tools: MCPTool[];
  selectedTool: MCPTool | null;
  toolFilter: string;

  // Execution
  isExecuting: boolean;
  executionHistory: ExecutionRecord[];

  // UI
  language: Language;
  auditLogEnabled: boolean;
  activeRightTab: 'history' | 'metrics' | 'compare';

  // Actions
  setConnectionConfig: (config: Partial<ConnectionConfig>) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setLastError: (error: string | null) => void;
  setTools: (tools: MCPTool[]) => void;
  selectTool: (tool: MCPTool | null) => void;
  setToolFilter: (filter: string) => void;
  setIsExecuting: (executing: boolean) => void;
  addExecutionRecord: (record: ExecutionRecord) => void;
  clearHistory: () => void;
  setLanguage: (language: Language) => void;
  toggleAuditLog: () => void;
  setActiveRightTab: (tab: 'history' | 'metrics' | 'compare') => void;
}

// JSON-RPC types
export interface JSONRPCRequest {
  jsonrpc: '2.0';
  method: string;
  params?: unknown;
  id: number | string;
}

export interface JSONRPCResponse {
  jsonrpc: '2.0';
  result?: unknown;
  error?: {
    code: number;
    message: string;
    data?: unknown;
  };
  id: number | string | null;
}

// MCP protocol types
export interface MCPInitializeParams {
  protocolVersion: string;
  capabilities: Record<string, unknown>;
  clientInfo: {
    name: string;
    version: string;
  };
}

export interface MCPToolsListResult {
  tools: MCPTool[];
  nextCursor?: string;
}

export interface MCPToolCallResult {
  content: Array<{
    type: string;
    text?: string;
    data?: unknown;
    mimeType?: string;
  }>;
  isError?: boolean;
}
