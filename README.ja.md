# agentwit

**AIエージェントのMCPツール呼び出しを監査・デバッグする。**

```bash
pip install agentwit
agentwit proxy --target http://localhost:3000 --port 8765
```

```
[agentwit] 14:32:01  tools/call  bash       HIGH ⚠  shell_exec
[agentwit] 14:32:03  tools/call  read_file  LOW  ✓
[agentwit] 14:32:05  tools/call  bash       CRITICAL 🚨 privilege_escalation
```

接続先URLを1行変えるだけ。MCPサーバーの改造不要。

![agentwit demo](docs/demo.gif)

[English](README.md) · [PyPI](https://pypi.org/project/agentwit/) · [Releases](https://github.com/tokotokokame/agentwit/releases)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/badge/PyPI-v0.5.0-orange.svg)](https://pypi.org/project/agentwit/)
[![Tests](https://img.shields.io/badge/tests-226%20passing-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 問題

AIエージェントがMCPサーバーのツールを呼び出すとき、**何が起きているか見えない。**

```
AIエージェント
    ↓（ブラックボックス）
MCPサーバー → bash / read_file / fetch / ...
```

agentwitはその間に透過プロキシとして入り、全通信を記録する。

```
AIエージェント
    ↓
agentwit  ← ログ記録・リスク判定・改ざん検知
    ↓
MCPサーバー（変更不要）
```

---

## 5分で動かす

```bash
pip install agentwit

# 1. プロキシ起動
agentwit proxy --target http://localhost:3000 --port 8765

# 2. エージェントの接続先を 3000 → 8765 に変えるだけ
#    記録が始まる。

# 3. 監査レポート生成
agentwit report --session ./witness_logs/SESSION_ID --format html

# 4. ログの整合性検証
agentwit verify --session ./witness_logs/SESSION_ID
# Chain integrity:  VALID ✓
# Signature check:  VALID ✓
```

---

## 機能

### ログ記録
- SHA-256チェーンで改ざん検知
- ed25519署名で「誰が記録したか」を証明
- HTML / Markdown / JSON レポート自動生成
- セッション終了時に `~/.agentwit/backups/` へ自動バックアップ

### リスク検知
| パターン | Severity |
|---|---|
| `privilege_escalation`（sudo・SUID） | CRITICAL |
| `prompt_injection`（指示文上書き・ロール乗っ取り） | CRITICAL |
| `data_exfiltration`（外部URLへのPOST） | HIGH |
| `credential_access`（パスワード・APIキー） | HIGH |
| `tool_schema_change`（ツール追加・改ざん） | HIGH |
| `call_rate_anomaly`（1分30回超） | HIGH |
| `lateral_movement` | HIGH |
| `persistence`（cron・サービス登録） | HIGH |

### 通知
```bash
agentwit proxy --target http://localhost:3000 \
  --webhook https://hooks.slack.com/xxx \
  --webhook-on HIGH,CRITICAL
```
Slack / Discord に対応（URLで自動判定）。

---

## 既存ツールとの比較

| ツール | 通信ブロック | 改ざん検知 | 署名検証 |
|---|:---:|:---:|:---:|
| mcp-scan | ✅ | ❌ | ❌ |
| Intercept | ✅ | ❌ | ❌ |
| **agentwit** | **❌** | **✅** | **✅** |

ガードは止める。証人は記録する。agentwitは証人。

---

## LangChain統合

```bash
pip install agentwit[full]
```

```python
from agentwit import AgentwitCallback

agent.run(
    "タスク内容",
    callbacks=[AgentwitCallback(output="./audit.json")]
)
```

---

## MCP Inspector GUI

MCPサーバーのデバッグ専用デスクトップアプリ（Linux・Tauri + React）。

```bash
sudo dpkg -i mcp-inspector_0.1.0_amd64.deb
mcp-inspector
# 接続: HTTP → http://localhost:3000/mcp
```

機能: ツール一覧・パラメータ編集・レスポンス表示・セッション比較・コスト追跡

---

## Docker Compose監査スタック

agentwit + Grafana + Loki + Fluent Bitをワンコマンドで起動。

```bash
cd docker/
cp .env.example .env   # TARGET_URLを設定
docker compose up -d
# Grafanaダッシュボード: http://localhost:3000
```

APIキー・トークンはFluent Bitが自動マスク。

---

## コマンド一覧

| コマンド | 説明 |
|---|---|
| `agentwit proxy` | 透過Witnessプロキシを起動 |
| `agentwit verify` | チェーン整合性 + ed25519署名を検証 |
| `agentwit report` | 監査レポート生成（html/markdown/json） |
| `agentwit replay` | セッション再生・チェーン検証 |
| `agentwit diff` | 2セッションを比較 |

---

## Witness Logフォーマット

```json
{
  "witness_id":      "イベント全体のsha256",
  "session_chain":   "sha256(直前のchain + event_hash)",
  "timestamp":       "2026-03-21T12:00:00Z",
  "tool":            "bash",
  "signature":       "base64(ed25519署名)",
  "risk_indicators": [{ "pattern": "shell_exec", "severity": "HIGH" }]
}
```

---

## バージョン履歴

| バージョン | 主な内容 |
|---|---|
| v0.1.0 | プロキシ・SHA-256チェーンログ |
| v0.2.0 | HTMLレポート・LangChain・Slack/Discord |
| v0.3.0 | MCP Inspector GUI |
| v0.4.0 | プロンプトインジェクション検知・Tool監視・Dockerスタック |
| v0.5.0 | ed25519署名・バイパス検知・異常検知 |

---

## 記事
- [AIエージェントの「証人」を作った（Zenn）](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- [「公証人」はなぜデバッガーに進化したのか（Zenn）](https://zenn.dev/tokotokokame/articles/9183dd8a1734e2)

---

## 動作要件

- Python 3.10+
- 依存パッケージは自動インストール: FastAPI, uvicorn, httpx, click, cryptography

## ライセンス

[MIT](LICENSE) © agentwit contributors
