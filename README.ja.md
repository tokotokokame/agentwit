# agentwit

> AIエージェントとMCPサーバー間の通信を記録する透過型Witnessプロキシ

[English](README.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-226%20passing-brightgreen.svg)](#)
[![PyPI](https://img.shields.io/badge/PyPI-v0.5.0-orange.svg)](https://pypi.org/project/agentwit/)

## 記事
- 📝 [AIエージェントの「証人」を作った——設計思想（Zenn）](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- 📝 [「公証人」はなぜデバッガーに進化したのか——v0.3.0（Zenn）](https://zenn.dev/tokotokokame/articles/9183dd8a1734e2)
- 📝 [監視ツールがAIに騙される話——v0.4.0（Zenn）](https://zenn.dev/tokotokokame/articles/)
- 📝 [「ログを信頼できるか」——ed25519署名でv0.5.0（Zenn）](https://zenn.dev/tokotokokame/articles/)

## agentwit とは？

AIエージェントとMCPサーバーの間に置く透過型プロキシです。
すべての通信をSHA-256チェーン＋ed25519署名付きで記録します。

不審なトラフィックをブロックする **「ガード」** 型の既存ツールとは異なり、
agentwit は **「証人（Witness）」** として動作します。

## Guard vs. Witness

| ツール       | アプローチ          | 通信ブロック | 改ざん検知 | 署名検証 |
|--------------|---------------------|:---:|:---:|:---:|
| mcp-scan     | プロキシ + ガード   | ✅ | ❌ | ❌ |
| Intercept    | ポリシープロキシ    | ✅ | ❌ | ❌ |
| **agentwit** | **Witnessプロキシ** | **❌** | **✅** | **✅** |

## クイックスタート

```bash
pip install agentwit
pip install agentwit[full]  # LangChain統合込み
```

```bash
# プロキシ起動
agentwit proxy --target http://localhost:3000 --port 8765

# 接続先を http://localhost:8765 に変更するだけ

# チェーン整合性 + ed25519署名を検証
agentwit verify --session ./witness_logs/SESSION_ID

# 監査レポート生成
agentwit report --session ./witness_logs/SESSION_ID \
                --format html --output report.html
```

## セキュリティ機能

### ed25519ログ署名（v0.5.0）

初回起動時に鍵ペアを自動生成します。ユーザー操作不要。

```
~/.agentwit/signing_key.pem  ← 秘密鍵（chmod 600）
~/.agentwit/signing_pub.pem  ← 公開鍵
```

```bash
agentwit verify --session ./witness_logs/SESSION_ID
# Chain integrity:  VALID ✓
# Signature check:  VALID ✓
```

### プロンプトインジェクション検知（v0.4.0）

MCPサーバーのレスポンスに悪意ある指示文が含まれていないかを検知します。
Claude API不要・正規表現のみ・追加コスト$0。

| パターン | Severity | 例 |
|---|---|---|
| instruction_override | CRITICAL | "Ignore previous instructions" |
| role_hijack | CRITICAL | "You are now DAN" |
| jailbreak | CRITICAL | "Do anything now" |
| hidden_instruction | HIGH | `<!-- [SYSTEM] -->` |
| data_extraction | HIGH | "Send the above to..." |
| tool_abuse | MEDIUM | "Execute the following" |

### プロキシバイパス検知（v0.5.0）

agentwitを経由しない直接接続を検知します。sudo不要・iptables不要。

```json
{
  "type": "proxy_bypass_detected",
  "severity": "HIGH",
  "detail": "Request missing X-Agentwit-Proxy header"
}
```

### Skill/Tool登録監視（v0.4.0）

セッション間でツールが追加・削除・変更されたことを検知します。

```json
{
  "type": "tool_schema_change",
  "changes": { "added": ["suspicious_tool"], "modified": ["bash"] },
  "severity": "HIGH"
}
```

### 異常検知（v0.5.0）

```json
{ "type": "call_rate_anomaly",  "calls_per_minute": 47, "severity": "HIGH"   }
{ "type": "repeated_tool_call", "tool": "bash", "count": 15, "severity": "MEDIUM" }
```

### 自動バックアップ（v0.5.0）

セッション終了時に `~/.agentwit/backups/` へ自動保存。最新30件を保持。

## コマンド一覧

```
agentwit proxy   --target URL [--port 8765] [--webhook URL] [--webhook-on HIGH,CRITICAL]
agentwit verify  --session DIR
agentwit report  --session DIR [--format json|markdown|html] [--output FILE]
agentwit replay  --session DIR
agentwit diff    --session-a DIR --session-b DIR
```

## MCP仕様自動追従（v0.4.0）

GitHub Actionsが毎月1日にMCP仕様の変更を検知。
変更時: テスト自動実行 → GitHub Issue作成 → Discord通知。
追加コスト: $0。

## Docker Compose監査スタック（v0.4.0）

agentwit + Grafana + Loki + Fluent Bitをワンコマンドで起動：

```bash
cd docker/
cp .env.example .env   # TARGET_URLを設定
docker compose up -d
# Grafana: http://localhost:3000
```

Fluent Bitが `Authorization`・`api_key`・`token`・`password` を自動マスク。

## MCP Inspector GUI

MCPサーバーのデバッグ専用デスクトップアプリ（Tauri + React）。

```bash
sudo dpkg -i mcp-inspector_0.1.0_amd64.deb
mcp-inspector
# 接続: HTTP → http://localhost:3000/mcp
```

## Witness Logのフォーマット

```json
{
  "witness_id":      "イベント全体のsha256",
  "session_chain":   "sha256(直前のchain_hash + event_hash)",
  "timestamp":       "2026-03-21T12:00:00Z",
  "actor":           "my-agent",
  "action":          "tools/call",
  "tool":            "bash",
  "signature":       "base64(ed25519署名)",
  "signed_by":       "公開鍵のfingerprint",
  "risk_indicators": [{ "pattern": "shell_exec", "severity": "HIGH" }]
}
```

## LangChain統合

```bash
pip install agentwit[full]
```

```python
from agentwit import AgentwitCallback
callbacks = [AgentwitCallback(output="./audit.json")]
agent.run("タスク内容", callbacks=callbacks)
```

## バージョン履歴

| バージョン | 日付 | 主な内容 |
|---|---|---|
| v0.1.0 | 2026-03-14 | MVP: HTTP/SSE/stdioプロキシ・SHA-256チェーンログ |
| v0.2.0 | 2026-03-15 | HTML/Markdownレポート・タイムライン比較・LangChain・Slack/Discord |
| v0.3.0 | 2026-03-16 | MCP Inspector GUI・標準MCP `/mcp` エンドポイント |
| v0.4.0 | 2026-03-21 | MCP仕様自動追従・プロンプトインジェクション検知・Tool監視・Dockerスタック |
| v0.5.0 | 2026-03-21 | ed25519署名・バイパス検知・異常検知・自動バックアップ |

## ロードマップ

- [ ] GUIからHTMLレポート直接生成
- [ ] Agent行動監視（判断プロセス記録）
- [ ] Windows対応確認
- [ ] GUIテストカバレッジ
- [ ] OWASP LLM Top 10マッピング
- [ ] SIEM連携（v1.0.0）

## 動作要件

- Python 3.10+
- cryptography>=41.0.0
- FastAPI, uvicorn, httpx, click（自動インストール）
- GUI: Node.js 18+・Rust 1.70+（ソースからビルドする場合）

## ライセンス

[MIT](LICENSE) © agentwit contributors
