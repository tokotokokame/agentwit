export const en = {
  // App
  appTitle: 'MCP Inspector',

  // Connection Panel
  connection: {
    title: 'Connection',
    configure: 'Configure Connection',
    transport: 'Transport Type',
    transportStdio: 'stdio',
    transportHttp: 'HTTP',
    transportSse: 'SSE',
    command: 'Command',
    commandPlaceholder: 'e.g. node, python, npx',
    args: 'Arguments',
    argsPlaceholder: 'e.g. server.js --port 8080',
    url: 'URL',
    urlPlaceholder: 'https://example.com/mcp',
    headers: 'Headers (JSON)',
    headersPlaceholder: '{"Authorization": "Bearer token"}',
    connect: 'Connect',
    disconnect: 'Disconnect',
    connecting: 'Connecting...',
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Connection Error',
    close: 'Close',
  },

  // Tool List
  tools: {
    title: 'Tools',
    search: 'Search tools...',
    noTools: 'No tools available',
    noResults: 'No tools match your search',
    connect: 'Connect to an MCP server to see tools',
    count: (n: number) => `${n} tool${n !== 1 ? 's' : ''}`,
    server: 'Server',
    statusLabel: 'status',
    protocolLabel: 'protocol',
  },

  // Execution Panel
  execution: {
    title: 'Execution',
    selectTool: 'Select a tool from the left panel',
    parameters: 'Parameters',
    parametersHint: 'Enter parameters as JSON or use the form below',
    run: 'RUN',
    execute: 'Execute',
    executing: 'Executing...',
    response: 'Response',
    noResponse: 'No response yet',
    pressRunHint: '// Press RUN to execute the tool',
    copyJson: 'COPY JSON',
    schema: 'SCHEMA',
    duration: 'Duration',
    ms: 'ms',
    error: 'Error',
    success: 'Success',
    copyResponse: 'COPY',
    copied: 'COPIED!',
    clearResponse: 'CLEAR',
    clearParams: 'CLEAR',
    required: 'required',
    optional: 'optional',
  },

  // History Tab
  history: {
    title: 'History',
    empty: 'No executions yet',
    runHint: 'Run a tool to see history',
    clear: 'Clear History',
    tool: 'Tool',
    status: 'Status',
    timestamp: 'Time',
    duration: 'Duration',
    params: 'Parameters',
    response: 'Response',
    error: 'Error',
    success: 'Success',
    expand: 'Show details',
    collapse: 'Hide details',
    rerun: 'Re-run',
  },

  // Metrics Tab
  metrics: {
    title: 'Metrics',
    empty: 'No metrics yet',
    sessionOverview: 'Session Overview',
    latencyLast: (n: number) => `Latency — last ${n} calls`,
    noData: 'no data',
    now: 'now',
    peak: 'peak',
    totalCalls: 'Total Calls',
    successRate: 'Success Rate',
    avgLatency: 'Avg Latency',
    lastCall: 'Last Call',
    perTool: 'Calls per Tool',
    never: 'Never',
    ms: 'ms',
    calls: 'calls',
  },

  // Compare Tab
  compare: {
    title: 'Compare',
    selectFirst: 'Select first entry',
    selectSecond: 'Select second entry',
    noHistory: 'No history entries to compare',
    diff: 'Differences',
    noDiff: 'No differences found',
    left: 'Left',
    right: 'Right',
    added: 'Added',
    removed: 'Removed',
    same: 'Identical responses',
    linesDiffer: (n: number) => `${n} lines differ`,
  },

  // Status Bar
  statusBar: {
    connected: 'Connected',
    disconnected: 'Disconnected',
    connecting: 'Connecting',
    error: 'Error',
    transport: 'Transport',
    tools: 'tools',
    auditLog: 'Audit Log',
    auditLogOn: 'ON',
    auditLogOff: 'OFF',
  },

  // General
  general: {
    yes: 'Yes',
    no: 'No',
    ok: 'OK',
    cancel: 'Cancel',
    close: 'Close',
    copy: 'Copy',
    clear: 'Clear',
    loading: 'Loading...',
    error: 'Error',
    success: 'Success',
    unknown: 'Unknown',
  },
};

// Deep-stringify: map all leaf string values to `string` so translations can use any language
type DeepString<T> = T extends string
  ? string
  : T extends (...args: infer A) => string
  ? (...args: A) => string
  : { [K in keyof T]: DeepString<T[K]> };

export type Translations = DeepString<typeof en>;
