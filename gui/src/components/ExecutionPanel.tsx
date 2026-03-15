import { useState, useCallback, useEffect } from 'react';
import { useStore } from '../store/useStore';
import { useI18n } from '../i18n';
import { getClient, MCPClientError, writeAuditLog } from '../lib/mcpClient';
import type { JSONSchema, ExecutionRecord } from '../types/mcp';

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ExecutionPanel() {
  const t = useI18n();
  const {
    selectedTool,
    connectionStatus,
    isExecuting,
    setIsExecuting,
    addExecutionRecord,
    auditLogEnabled,
    setActiveRightTab,
  } = useStore();

  const [paramsJson, setParamsJson] = useState('{}');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<unknown>(null);
  const [lastError, setLastExecutionError] = useState<string | null>(null);
  const [lastDuration, setLastDuration] = useState<number | null>(null);
  const [lastStatus, setLastStatus] = useState<'success' | 'error' | null>(null);
  const [copied, setCopied] = useState(false);

  // Reset when tool changes
  useEffect(() => {
    if (selectedTool) {
      const defaults = buildDefaultParams(selectedTool.inputSchema);
      setParamsJson(JSON.stringify(defaults, null, 2));
      setJsonError(null);
      setLastResponse(null);
      setLastExecutionError(null);
      setLastDuration(null);
      setLastStatus(null);
    }
  }, [selectedTool]);

  const validateJson = useCallback((value: string) => {
    try {
      JSON.parse(value);
      setJsonError(null);
      return true;
    } catch (e) {
      setJsonError((e as Error).message);
      return false;
    }
  }, []);

  const handleParamsChange = useCallback(
    (value: string) => {
      setParamsJson(value);
      validateJson(value);
    },
    [validateJson]
  );

  const handleExecute = useCallback(async () => {
    if (!selectedTool || isExecuting || connectionStatus !== 'connected') return;
    if (!validateJson(paramsJson)) return;

    const client = getClient();
    if (!client) return;

    let params: Record<string, unknown> = {};
    try {
      params = JSON.parse(paramsJson) as Record<string, unknown>;
    } catch { return; }

    setIsExecuting(true);
    setLastResponse(null);
    setLastExecutionError(null);
    setLastStatus(null);

    const startTime = Date.now();

    try {
      const result = await client.callTool(selectedTool.name, params);
      const duration = Date.now() - startTime;

      setLastResponse(result);
      setLastDuration(duration);
      setLastStatus('success');
      setLastExecutionError(null);

      const record: ExecutionRecord = {
        id: generateId(),
        toolName: selectedTool.name,
        params,
        response: result,
        timestamp: new Date(),
        duration,
        status: 'success',
      };
      addExecutionRecord(record);
      setActiveRightTab('history');

      if (auditLogEnabled) {
        await writeAuditLog({
          type: 'tool_call',
          tool: selectedTool.name,
          params,
          response: result,
          duration,
          timestamp: new Date().toISOString(),
          status: 'success',
        });
      }
    } catch (e) {
      const duration = Date.now() - startTime;
      const errorMsg = e instanceof MCPClientError ? e.message : String(e);

      setLastExecutionError(errorMsg);
      setLastDuration(duration);
      setLastStatus('error');
      setLastResponse(null);

      const record: ExecutionRecord = {
        id: generateId(),
        toolName: selectedTool.name,
        params,
        error: errorMsg,
        timestamp: new Date(),
        duration,
        status: 'error',
      };
      addExecutionRecord(record);
      setActiveRightTab('history');

      if (auditLogEnabled) {
        await writeAuditLog({
          type: 'tool_call',
          tool: selectedTool.name,
          params,
          error: errorMsg,
          duration,
          timestamp: new Date().toISOString(),
          status: 'error',
        });
      }
    } finally {
      setIsExecuting(false);
    }
  }, [
    selectedTool, isExecuting, connectionStatus, paramsJson,
    validateJson, setIsExecuting, addExecutionRecord, setActiveRightTab, auditLogEnabled,
  ]);

  const handleCopy = useCallback(async () => {
    const text = lastResponse != null ? JSON.stringify(lastResponse, null, 2) : lastError ?? '';
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [lastResponse, lastError]);

  const handleClear = useCallback(() => {
    setLastResponse(null);
    setLastExecutionError(null);
    setLastDuration(null);
    setLastStatus(null);
  }, []);

  const canExecute = selectedTool != null && connectionStatus === 'connected' && !isExecuting && !jsonError;

  if (!selectedTool) {
    return (
      <main className="execution-panel">
        <div className="execution-empty">
          <div className="execution-empty-icon">◈</div>
          <div>{t.execution.selectTool}</div>
        </div>
      </main>
    );
  }

  return (
    <main className="execution-panel">
      {/* Tool header */}
      <div className="tool-hdr">
        <div className="th-left">
          <div className="th-name">
            <span>{selectedTool.name}</span>
            <span className="method-tag">CALL</span>
          </div>
          {selectedTool.description && (
            <div className="th-desc">{selectedTool.description}</div>
          )}
        </div>
        <div className="th-right">
          <button className="btn btn-ghost" onClick={() => handleParamsChange('{}')}>
            {t.execution.clearParams}
          </button>
          <button
            className="btn btn-run"
            onClick={handleExecute}
            disabled={!canExecute}
          >
            {isExecuting ? (
              <>
                <span className="spinner" />
                {t.execution.executing}
              </>
            ) : (
              <>
                <span>▶</span>
                {t.execution.run}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Params / Response split */}
      <div className="center-split">
        {/* ── Params pane ── */}
        <div className="cpane">
          <div className="cpane-hdr">
            {t.execution.parameters}
            <div className="cpane-actions">
              <button
                className="mini-btn"
                onClick={() => navigator.clipboard.writeText(paramsJson)}
              >
                {t.execution.copyJson}
              </button>
              <button className="mini-btn">{t.execution.schema}</button>
            </div>
          </div>
          <div className="params-body">
            {selectedTool.inputSchema?.properties && (
              <SchemaForm
                schema={selectedTool.inputSchema}
                value={paramsJson}
                onChange={handleParamsChange}
              />
            )}
            <div className="json-editor-wrap">
              <textarea
                className={`json-editor ${jsonError ? 'json-editor-error' : ''}`}
                value={paramsJson}
                onChange={(e) => handleParamsChange(e.target.value)}
                rows={6}
                spellCheck={false}
                aria-label="Parameters JSON"
              />
              {jsonError && <div className="json-error-msg">{jsonError}</div>}
            </div>
          </div>
        </div>

        {/* ── Response pane ── */}
        <div className="cpane">
          <div className="cpane-hdr">
            {t.execution.response}
            <div className="cpane-actions">
              {isExecuting && (
                <div className="running-wrap">
                  {t.execution.executing}
                  <div className="running-dots">
                    <span /><span /><span />
                  </div>
                </div>
              )}
              <button className="mini-btn" onClick={handleCopy}>
                {copied ? t.execution.copied : t.execution.copyResponse}
              </button>
              {(lastResponse != null || lastError) && (
                <button className="mini-btn" onClick={handleClear}>{t.execution.clearResponse}</button>
              )}
            </div>
          </div>
          <div className="resp-body">
            {!isExecuting && lastResponse == null && !lastError && (
              <div className="resp-placeholder">{t.execution.pressRunHint}</div>
            )}

            {(lastStatus || lastDuration != null) && !isExecuting && (
              <div className={`resp-banner ${lastStatus === 'success' ? 'ok' : 'err'}`}>
                <span className="resp-status">
                  {lastStatus === 'success' ? `✓ ${t.execution.success}` : `✗ ${t.execution.error}`}
                </span>
                <span style={{ fontSize: '10px', color: 'var(--text-lo)' }}>
                  {selectedTool.name}
                </span>
                <div className="resp-meta-row">
                  {lastDuration != null && <span>{lastDuration} ms</span>}
                </div>
              </div>
            )}

            {!isExecuting && lastError && (
              <div className="resp-error">
                <div className="resp-error-label">{t.execution.error}</div>
                <div className="resp-error-text">{lastError}</div>
              </div>
            )}

            {!isExecuting && lastResponse != null && (
              <div className="json-viewer">
                <SyntaxHighlight value={JSON.stringify(lastResponse, null, 2)} />
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

// ── Build default param values from JSON Schema ──────────────
function buildDefaultParams(schema: JSONSchema): Record<string, unknown> {
  if (!schema.properties) return {};
  const result: Record<string, unknown> = {};
  for (const [key, prop] of Object.entries(schema.properties)) {
    if (prop.default !== undefined) {
      result[key] = prop.default;
    } else if (prop.type === 'string') {
      result[key] = '';
    } else if (prop.type === 'number' || prop.type === 'integer') {
      result[key] = 0;
    } else if (prop.type === 'boolean') {
      result[key] = false;
    } else if (prop.type === 'array') {
      result[key] = [];
    } else if (prop.type === 'object') {
      result[key] = {};
    }
  }
  return result;
}

// ── Syntax highlighter ────────────────────────────────────────
function SyntaxHighlight({ value }: { value: string }) {
  const tokens: { text: string; cls?: string }[] = [];
  const patterns: [RegExp, string][] = [
    [/^(\s+)/, ''],
    [/^("(?:[^"\\]|\\.)*":)/, 'json-key'],
    [/^("(?:[^"\\]|\\.)*")/, 'json-string'],
    [/^(-?\d+\.?\d*(?:[eE][+-]?\d+)?)/, 'json-number'],
    [/^(true|false)/, 'json-boolean'],
    [/^(null)/, 'json-null'],
    [/^([{}[\],])/, ''],
    [/^(.)/, ''],
  ];

  let remaining = value;
  while (remaining.length > 0) {
    let matched = false;
    for (const [pat, cls] of patterns) {
      const m = remaining.match(pat);
      if (m) {
        tokens.push({ text: m[1], cls: cls || undefined });
        remaining = remaining.slice(m[1].length);
        matched = true;
        break;
      }
    }
    if (!matched) break;
  }

  return (
    <>
      {tokens.map((tok, i) =>
        tok.cls
          ? <span key={i} className={tok.cls}>{tok.text}</span>
          : <span key={i}>{tok.text}</span>
      )}
    </>
  );
}

// ── Schema-driven form ─────────────────────────────────────────
interface SchemaFormProps {
  schema: JSONSchema;
  value: string;
  onChange: (value: string) => void;
}

function SchemaForm({ schema, value, onChange }: SchemaFormProps) {
  if (!schema.properties) return null;

  let currentParams: Record<string, unknown> = {};
  try { currentParams = JSON.parse(value) as Record<string, unknown>; } catch { /* ignore */ }

  const required = schema.required ?? [];

  const handleField = (name: string, val: unknown) => {
    onChange(JSON.stringify({ ...currentParams, [name]: val }, null, 2));
  };

  return (
    <div className="schema-form">
      {Object.entries(schema.properties).map(([name, prop]) => {
        const type = (Array.isArray(prop.type) ? prop.type[0] : prop.type) ?? 'string';
        const isReq = required.includes(name);
        return (
          <div
            key={name}
            className={`param-item ${isReq ? 'required' : ''}`}
          >
            {/* Name column */}
            <div>
              <div className="pi-name">
                <span className="pi-name-text">{name}</span>
                {isReq && <span className="pi-req">*</span>}
              </div>
              {prop.description && (
                <div className="pi-desc">{prop.description}</div>
              )}
            </div>
            {/* Type badge */}
            <span className={`pi-type ${prop.enum ? 'pt-enum' : `pt-${type}`}`}>
              {prop.enum ? 'enum' : type}
            </span>
            {/* Input */}
            <FieldInput
              name={name}
              schema={prop}
              value={currentParams[name]}
              onChange={(v) => handleField(name, v)}
            />
          </div>
        );
      })}
    </div>
  );
}

interface FieldInputProps {
  name: string;
  schema: JSONSchema;
  value: unknown;
  onChange: (v: unknown) => void;
}

function FieldInput({ name, schema, value, onChange }: FieldInputProps) {
  const type = (Array.isArray(schema.type) ? schema.type[0] : schema.type) ?? 'string';

  if (schema.enum) {
    return (
      <select
        className="pi-input"
        value={value as string ?? ''}
        onChange={(e) => onChange(e.target.value)}
        aria-label={name}
      >
        <option value="">-- select --</option>
        {schema.enum.map((opt, i) => (
          <option key={i} value={String(opt)}>{String(opt)}</option>
        ))}
      </select>
    );
  }

  if (type === 'boolean') {
    return (
      <label className="toggle-label">
        <input
          type="checkbox"
          className="toggle-input"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
          aria-label={name}
        />
        <span className="toggle-track" />
      </label>
    );
  }

  if (type === 'number' || type === 'integer') {
    return (
      <input
        type="number"
        className="pi-input"
        value={value as number ?? 0}
        min={schema.minimum}
        max={schema.maximum}
        step={type === 'integer' ? 1 : 'any'}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={name}
      />
    );
  }

  if (type === 'array' || type === 'object') {
    return (
      <textarea
        className="pi-input"
        style={{ resize: 'vertical', minHeight: '40px', fontSize: '10px' }}
        value={value !== undefined && value !== null
          ? JSON.stringify(value, null, 2)
          : type === 'array' ? '[]' : '{}'}
        onChange={(e) => {
          try { onChange(JSON.parse(e.target.value)); } catch { /* keep editing */ }
        }}
        rows={2}
        aria-label={name}
      />
    );
  }

  return (
    <input
      type="text"
      className="pi-input"
      value={value as string ?? ''}
      maxLength={schema.maxLength}
      onChange={(e) => onChange(e.target.value)}
      placeholder={schema.description ?? ''}
      aria-label={name}
    />
  );
}
