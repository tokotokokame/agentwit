import type {
  ConnectionConfig,
  JSONRPCRequest,
  JSONRPCResponse,
  MCPTool,
  MCPToolCallResult,
  MCPToolsListResult,
} from '../types/mcp';

const MCP_PROTOCOL_VERSION = '2024-11-05';
const CLIENT_NAME = 'mcp-inspector';
const CLIENT_VERSION = '1.0.0';
const REQUEST_TIMEOUT_MS = 30000;

// Detect if running inside Tauri
const isTauri = (): boolean => {
  const hasTauriInternals = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
  console.debug('[isTauri]', {
    windowDefined: typeof window !== 'undefined',
    hasTauriInternals,
    tauriInternalsValue: typeof window !== 'undefined' ? (window as unknown as Record<string, unknown>)['__TAURI_INTERNALS__'] : undefined,
  });
  return hasTauriInternals;
};

export class MCPClientError extends Error {
  constructor(
    message: string,
    public readonly code?: number,
    public readonly data?: unknown
  ) {
    super(message);
    this.name = 'MCPClientError';
  }
}

// Pending request tracker
interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  timer: ReturnType<typeof setTimeout>;
}

export class MCPClient {
  private config: ConnectionConfig;
  private nextId = 1;
  private pendingRequests = new Map<number, PendingRequest>();
  private initialized = false;

  // stdio-specific
  private stdioProcess: import('@tauri-apps/plugin-shell').Child | null = null;
  private stdioBuffer = '';

  // SSE-specific
  private sseSource: EventSource | null = null;
  private ssePostUrl = '';

  constructor(config: ConnectionConfig) {
    this.config = config;
  }

  // -------------------------
  // Public API
  // -------------------------

  async connect(): Promise<void> {
    if (this.config.type === 'stdio') {
      await this.connectStdio();
    } else if (this.config.type === 'sse') {
      await this.connectSSE();
    }
    // HTTP needs no persistent connection
  }

  // -------------------------
  // Tauri HTTP helper
  // -------------------------

  private async tauriFetch(url: string, init: { method: string; headers: Record<string, string>; body: string }): Promise<Response> {
    if (isTauri()) {
      const { fetch: tFetch } = await import('@tauri-apps/plugin-http');
      return tFetch(url, init) as Promise<Response>;
    }
    return fetch(url, init);
  }

  async initialize(): Promise<void> {
    const result = await this.sendRequest('initialize', {
      protocolVersion: MCP_PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: {
        name: CLIENT_NAME,
        version: CLIENT_VERSION,
      },
    });

    if (!result) {
      throw new MCPClientError('Initialize returned no result');
    }

    // Send initialized notification
    await this.sendNotification('notifications/initialized', {});
    this.initialized = true;
  }

  async listTools(): Promise<MCPTool[]> {
    this.assertInitialized();
    const result = (await this.sendRequest('tools/list', {})) as MCPToolsListResult;
    return result?.tools ?? [];
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<MCPToolCallResult> {
    this.assertInitialized();
    const result = await this.sendRequest('tools/call', {
      name,
      arguments: args,
    });
    return result as MCPToolCallResult;
  }

  async disconnect(): Promise<void> {
    // Cancel all pending requests
    for (const [, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new MCPClientError('Client disconnected'));
    }
    this.pendingRequests.clear();

    if (this.stdioProcess) {
      try {
        await this.stdioProcess.kill();
      } catch {
        // Ignore errors during disconnect
      }
      this.stdioProcess = null;
    }

    if (this.sseSource) {
      this.sseSource.close();
      this.sseSource = null;
    }

    this.initialized = false;
    this.stdioBuffer = '';
  }

  // -------------------------
  // stdio transport
  // -------------------------

  private async connectStdio(): Promise<void> {
    if (!isTauri()) {
      throw new MCPClientError('stdio transport is only available in the desktop app (Tauri)');
    }

    const { Command } = await import('@tauri-apps/plugin-shell');
    const command = this.config.command;
    const args = this.config.args ?? [];

    if (!command) {
      throw new MCPClientError('No command specified for stdio transport');
    }

    const child = Command.create(command, args);

    // Handle stdout data
    child.stdout.on('data', (line: string) => {
      this.stdioBuffer += line;
      // Process complete lines
      const lines = this.stdioBuffer.split('\n');
      this.stdioBuffer = lines.pop() ?? '';
      for (const l of lines) {
        const trimmed = l.trim();
        if (trimmed) {
          this.handleIncomingMessage(trimmed);
        }
      }
    });

    child.stderr.on('data', (line: string) => {
      console.warn('[MCP stdio stderr]', line);
    });

    child.on('close', (data) => {
      console.log('[MCP stdio] process exited with code', data.code);
      this.stdioProcess = null;
    });

    child.on('error', (err) => {
      console.error('[MCP stdio] process error', err);
    });

    this.stdioProcess = await child.spawn();
  }

  private async sendStdio(message: JSONRPCRequest): Promise<void> {
    if (!this.stdioProcess) {
      throw new MCPClientError('stdio process not running');
    }
    const line = JSON.stringify(message) + '\n';
    await this.stdioProcess.write(line);
  }

  // -------------------------
  // HTTP transport
  // -------------------------

  private async sendHttp(message: JSONRPCRequest): Promise<unknown> {
    const url = this.config.url;
    if (!url) {
      throw new MCPClientError('No URL specified for HTTP transport');
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(this.config.headers ?? {}),
    };

    const response = await this.tauriFetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(message),
    });

    if (!response.ok) {
      throw new MCPClientError(
        `HTTP error ${response.status}: ${response.statusText}`,
        response.status
      );
    }

    const json = (await response.json()) as JSONRPCResponse;
    return this.extractResult(json);
  }

  // -------------------------
  // SSE transport
  // -------------------------

  private async connectSSE(): Promise<void> {
    const url = this.config.url;
    if (!url) {
      throw new MCPClientError('No URL specified for SSE transport');
    }

    this.ssePostUrl = url.replace(/\/sse$/, '') + '/message';

    return new Promise((resolve, reject) => {
      const source = new EventSource(url);
      this.sseSource = source;

      const connectTimeout = setTimeout(() => {
        reject(new MCPClientError('SSE connection timeout'));
      }, REQUEST_TIMEOUT_MS);

      source.addEventListener('open', () => {
        clearTimeout(connectTimeout);
        resolve();
      });

      source.addEventListener('message', (event) => {
        try {
          this.handleIncomingMessage(event.data as string);
        } catch (e) {
          console.error('[MCP SSE] error handling message', e);
        }
      });

      source.addEventListener('error', (event) => {
        clearTimeout(connectTimeout);
        console.error('[MCP SSE] error', event);
        reject(new MCPClientError('SSE connection error'));
      });
    });
  }

  private async sendSSE(message: JSONRPCRequest): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(this.config.headers ?? {}),
    };

    const response = await fetch(this.ssePostUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });

    if (!response.ok) {
      throw new MCPClientError(
        `SSE POST error ${response.status}: ${response.statusText}`,
        response.status
      );
    }
  }

  // -------------------------
  // JSON-RPC message handling
  // -------------------------

  private handleIncomingMessage(raw: string): void {
    let message: JSONRPCResponse;
    try {
      message = JSON.parse(raw) as JSONRPCResponse;
    } catch {
      console.warn('[MCP] Failed to parse JSON message:', raw);
      return;
    }

    if (message.id == null) {
      // Notification — ignore for now
      return;
    }

    const id = message.id as number;
    const pending = this.pendingRequests.get(id);
    if (!pending) {
      console.warn('[MCP] Received response for unknown request ID:', id);
      return;
    }

    clearTimeout(pending.timer);
    this.pendingRequests.delete(id);

    if (message.error) {
      pending.reject(
        new MCPClientError(
          message.error.message,
          message.error.code,
          message.error.data
        )
      );
    } else {
      pending.resolve(message.result);
    }
  }

  private extractResult(response: JSONRPCResponse): unknown {
    if (response.error) {
      throw new MCPClientError(
        response.error.message,
        response.error.code,
        response.error.data
      );
    }
    return response.result;
  }

  private sendRequest(method: string, params: unknown): Promise<unknown> {
    const id = this.nextId++;
    const message: JSONRPCRequest = {
      jsonrpc: '2.0',
      method,
      params,
      id,
    };

    if (this.config.type === 'http') {
      // HTTP is synchronous request-response, no pending map needed
      return this.sendHttp(message);
    }

    // For stdio and SSE, responses come asynchronously
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new MCPClientError(`Request timeout: ${method}`));
      }, REQUEST_TIMEOUT_MS);

      this.pendingRequests.set(id, { resolve, reject, timer });

      if (this.config.type === 'stdio') {
        this.sendStdio(message).catch((err) => {
          clearTimeout(timer);
          this.pendingRequests.delete(id);
          reject(err);
        });
      } else if (this.config.type === 'sse') {
        this.sendSSE(message).catch((err) => {
          clearTimeout(timer);
          this.pendingRequests.delete(id);
          reject(err);
        });
      }
    });
  }

  private async sendNotification(method: string, params: unknown): Promise<void> {
    const message: JSONRPCRequest = {
      jsonrpc: '2.0',
      method,
      params,
      id: this.nextId++,
    };

    if (this.config.type === 'stdio') {
      await this.sendStdio(message);
    } else if (this.config.type === 'http') {
      await this.tauriFetch(this.config.url!, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.config.headers ?? {}),
        },
        body: JSON.stringify(message),
      }).catch(() => {
        // Notifications don't need responses
      });
    } else if (this.config.type === 'sse') {
      await this.sendSSE(message).catch(() => {
        // Notifications don't need responses
      });
    }
  }

  private assertInitialized(): void {
    if (!this.initialized) {
      throw new MCPClientError('MCP client not initialized. Call initialize() first.');
    }
  }
}

// Singleton client instance
let currentClient: MCPClient | null = null;

export function getClient(): MCPClient | null {
  return currentClient;
}

export function setClient(client: MCPClient | null): void {
  currentClient = client;
}

export async function writeAuditLog(entry: object): Promise<void> {
  const tauriDetected = isTauri();
  console.debug('[writeAuditLog] called', { tauriDetected, entry });

  if (!tauriDetected) {
    console.warn('[writeAuditLog] Not running in Tauri — skipping file write. Run via `npm run tauri dev` to enable audit logging.');
    return;
  }

  try {
    console.debug('[writeAuditLog] invoking write_audit_log...');
    const { invoke } = await import('@tauri-apps/api/core');
    const serialized = JSON.stringify(entry);
    await invoke('write_audit_log', { entry: serialized });
    console.info('[writeAuditLog] ✓ written to ~/.agentwit/audit.jsonl', serialized);
  } catch (e) {
    console.error('[writeAuditLog] ✗ Failed to write audit log:', e);
  }
}
