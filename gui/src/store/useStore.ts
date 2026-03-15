import { create } from 'zustand';
import type {
  AppState,
  ConnectionConfig,
  ConnectionStatus,
  MCPTool,
  ExecutionRecord,
  Language,
} from '../types/mcp';

const defaultConnectionConfig: ConnectionConfig = {
  type: 'stdio',
  command: '',
  args: [],
  url: '',
  headers: {},
};

export const useStore = create<AppState>((set) => ({
  // Connection state
  connectionConfig: defaultConnectionConfig,
  connectionStatus: 'disconnected',
  lastError: null,

  // Tools state
  tools: [],
  selectedTool: null,
  toolFilter: '',

  // Execution state
  isExecuting: false,
  executionHistory: [],

  // UI state
  language: 'en',
  auditLogEnabled: false,
  activeRightTab: 'history',

  // Connection actions
  setConnectionConfig: (config: Partial<ConnectionConfig>) =>
    set((state) => ({
      connectionConfig: { ...state.connectionConfig, ...config },
    })),

  setConnectionStatus: (status: ConnectionStatus) =>
    set({ connectionStatus: status }),

  setLastError: (error: string | null) =>
    set({ lastError: error }),

  // Tool actions
  setTools: (tools: MCPTool[]) =>
    set({ tools }),

  selectTool: (tool: MCPTool | null) =>
    set({ selectedTool: tool }),

  setToolFilter: (filter: string) =>
    set({ toolFilter: filter }),

  // Execution actions
  setIsExecuting: (executing: boolean) =>
    set({ isExecuting: executing }),

  addExecutionRecord: (record: ExecutionRecord) =>
    set((state) => ({
      executionHistory: [record, ...state.executionHistory],
    })),

  clearHistory: () =>
    set({ executionHistory: [] }),

  // UI actions
  setLanguage: (language: Language) =>
    set({ language }),

  toggleAuditLog: () =>
    set((state) => ({ auditLogEnabled: !state.auditLogEnabled })),

  setActiveRightTab: (tab: 'history' | 'metrics' | 'compare') =>
    set({ activeRightTab: tab }),
}));
