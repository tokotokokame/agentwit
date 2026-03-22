import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { ExecutionRecord } from '../../types/mcp';

// ---------------------------------------------------------------------------
// Hoist mock fn references so they are available inside vi.mock factories
// ---------------------------------------------------------------------------

const { mockSave, mockInvoke, mockUseStore } = vi.hoisted(() => ({
  mockSave: vi.fn(),
  mockInvoke: vi.fn(),
  mockUseStore: vi.fn(),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  save: mockSave,
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: mockInvoke,
}));

vi.mock('../../store/useStore', () => ({
  useStore: mockUseStore,
}));

// Import component after mocks are registered
import { HistoryTab } from '../RightPanel/HistoryTab';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockClearHistory = vi.fn();

function makeRecord(overrides: Partial<ExecutionRecord> = {}): ExecutionRecord {
  return {
    id: '1',
    toolName: 'test-tool',
    params: {},
    response: { content: 'ok' },
    timestamp: new Date('2026-01-01T00:00:00Z'),
    duration: 100,
    status: 'success',
    ...overrides,
  };
}

function mockStore(history: ExecutionRecord[]) {
  mockUseStore.mockReturnValue({
    executionHistory: history,
    clearHistory: mockClearHistory,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HistoryTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSave.mockResolvedValue('/tmp/report.html');
    mockInvoke.mockResolvedValue('/tmp/report.html');
  });

  it('renders Export Report button', () => {
    mockStore([]);
    render(<HistoryTab />);
    expect(screen.getByText('Export Report')).toBeInTheDocument();
  });

  it('Export Report button is disabled when history is empty', () => {
    mockStore([]);
    render(<HistoryTab />);
    const btn = screen.getByText('Export Report');
    expect(btn).toBeDisabled();
  });

  it('Export Report button is enabled when history has items', () => {
    mockStore([makeRecord()]);
    render(<HistoryTab />);
    const btn = screen.getByText('Export Report');
    expect(btn).not.toBeDisabled();
  });

  it('calls save dialog when Export Report is clicked', async () => {
    mockStore([makeRecord()]);
    render(<HistoryTab />);
    fireEvent.click(screen.getByText('Export Report'));
    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledTimes(1);
    });
  });

  it('calls invoke generate_report after save dialog confirms', async () => {
    mockStore([makeRecord()]);
    render(<HistoryTab />);
    fireEvent.click(screen.getByText('Export Report'));
    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith(
        'generate_report',
        expect.objectContaining({ outputPath: '/tmp/report.html' }),
      );
    });
  });

  it('does not call invoke when save dialog is cancelled', async () => {
    mockSave.mockResolvedValue(null); // user cancelled
    mockStore([makeRecord()]);
    render(<HistoryTab />);
    fireEvent.click(screen.getByText('Export Report'));
    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledTimes(1);
    });
    expect(mockInvoke).not.toHaveBeenCalled();
  });

  it('shows empty-state message when history is empty', () => {
    mockStore([]);
    render(<HistoryTab />);
    expect(screen.getByText('◈')).toBeInTheDocument();
  });

  it('renders history entries when history has items', () => {
    mockStore([makeRecord({ toolName: 'my-special-tool' })]);
    render(<HistoryTab />);
    expect(screen.getByText('my-special-tool')).toBeInTheDocument();
  });
});
