# agentwit

> AIエージェントとMCPサーバー間の通信を記録する透過型Witnessプロキシ

[English](README.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-132%20passing-brightgreen.svg)](#)
[![PyPI](https://img.shields.io/badge/PyPI-v0.3.0-orange.svg)](https://pypi.org/project/agentwit/)

## 記事
- 📝 [AIエージェントの「証人」を作った——設計思想（Zenn）](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- 📝 [実践ガイド：agentwitでMCPサーバーを5分で監査する（Zenn）](https://zenn.dev/tokotokokame/articles/)
- 📝 [WitnessからInspectorへ——agentwitはどう進化したか（Zenn）](https://zenn.dev/tokotokokame/articles/)

## agentwit とは？

agentwit は、AIエージェントとMCPサーバーの間に置く透過型プロキシです。
すべての通信を改ざん検知可能なWitness Log として記録します。

不審なトラフィックをブロックする **「ガード」** 型の既存ツールとは異なり、
agentwit は **「証人（Witness）」** として動作します。
通信をブロックせず、改変もせず、SHA-256チェーン整合性付きですべてを記録します。

**v0.3.0 では MCP Inspector GUI を追加**しました。
MCPサーバーをリアルタイムでデバッグできるデスクトップアプリです。
CLIプロキシと同じ監査ログ形式で記録が統一されています。

## Guard（ガード）vs. Witness（証人）

| ツール       | アプローチ          | 通信のブロック | 改ざん検知ログ |
|--------------|---------------------|:--------------:|:--------------:|
| mcp-scan     | プロキシ + ガード   | ✅             | ❌             |
| Proximity    | 静的スキャナー      | —              | ❌             |
| Intercept    | ポリシープロキシ    | ✅             | ❌             |
| **agentwit** | **Witnessプロキシ** | **❌**         | **✅**         |

## 仕組み

```
AIエージェント
   │
   ▼
agentwit proxy  ◄── 全メッセージをChainハッシュ付きで記録
   │                 ブロックなし・完全透過
   ▼
MCPサーバー      ◄── 変更不要・そのまま動作
```

記録された各イベントは SHA-256 でチェーン状に連結されます：

```
genesis_hash = sha256("genesis:" + session_id)
      │
      ▼
event_1:  session_chain = sha256(genesis_hash  +  hash(event_1))
      │
      ▼
event_2:  session_chain = sha256(event_1_chain +  hash(event_2))
```

どのイベントに対しても1バイトの変更を加えると、その時点からチェーン全体が壊れます。
これにより改ざんを即座に検出できます。

## クイックスタート

### インストール

```bash
pip install agentwit
pip install agentwit[full]  # LangChain統合込み
```

### 1. Witnessプロキシを起動

```bash
agentwit proxy --target http://localhost:3000 --port 8765
# Starting agentwit proxy → http://localhost:3000
# Listening on 127.0.0.1:8765
# Session: ./witness_logs/session_20260314_120000
```

### 2. エージェントの向き先をプロキシに変更

```
# 変更前: http://localhost:3000
# 変更後: http://localhost:8765
# 以上です。他に変更は不要です。
```

### 3. 監査レポートを生成

```bash
agentwit report --session ./witness_logs/session_20260314_120000 \
                --format html --output report.html
```

### 4. Chain Integrityを検証

```bash
agentwit replay --session ./witness_logs/session_20260314_120000
# Session: session_20260314_120000  (6 events)
# Chain integrity: VALID
```

## MCP Inspector GUI（v0.3.0）

MCPサーバーのデバッグ専用デスクトップアプリです。Tauri + React 製。
Windows / Linux に対応しています。

```
左パネル   サーバー情報 + ツール一覧（READ/WRITE/EXECタグ）
中央パネル パラメータエディタ + JSONレスポンスビューアー
右パネル   History / Metrics / Compare の3タブ
```

### 起動方法

```bash
# .debパッケージ（Linux）
sudo dpkg -i mcp-inspector_0.1.0_amd64.deb
mcp-inspector

# ソースから
cd gui && npm install && npx tauri dev
```

### MCPサーバーへの接続

```
Transport: HTTP
URL: http://localhost:3000/mcp
```

リモートサーバー（SSH経由）の場合：

```bash
ssh -fNL 3000:localhost:3000 your-server
# その後 http://localhost:3000/mcp に接続
```

### 監査ログとの統合

GUIヘッダーの **「agentwit audit」ボタン** をONにすると、
Inspector経由の全実行が `~/.agentwit/audit.jsonl` に記録されます。

```
開発中（GUI）  ─┐
                 ├→ 同じ audit.jsonl → agentwit report で一括レポート
本番（CLIプロキシ）─┘
```

開発フェーズと本番フェーズで記録形式が統一されます。

### 既存ツールとの比較

| 機能                 | Anthropic CLI | Postman | agentwit Inspector |
|----------------------|:-------------:|:-------:|:------------------:|
| GUI                  | ❌            | ✅      | ✅                 |
| MCPネイティブ        | ✅            | ❌      | ✅                 |
| stdio対応            | ✅            | ❌      | ✅                 |
| 監査ログ             | ❌            | ❌      | **✅**             |
| コスト追跡           | ❌            | ❌      | **✅**             |
| セッション比較       | ❌            | 限定的  | **✅**             |
| ローカル完結         | ✅            | ✅      | ✅                 |

## コマンド一覧

```
agentwit proxy   --target URL [--port 8765] [--log-dir ./witness_logs] [--actor NAME]
agentwit report  --session DIR [--format json|markdown|html] [--output FILE]
agentwit replay  --session DIR [--verify/--no-verify]
agentwit diff    --session-a DIR --session-b DIR
```

| コマンド  | 説明                                                     |
|-----------|----------------------------------------------------------|
| `proxy`   | 透過Witnessプロキシを起動                                |
| `report`  | 監査レポートを生成（json / markdown / html）             |
| `replay`  | セッションを再生しChain Integrityを検証                  |
| `diff`    | 2つのセッションを並べて比較                              |

### Webhook通知（Slack / Discord）

```bash
agentwit proxy --target http://localhost:3000 --port 8765 \
  --webhook https://hooks.slack.com/services/xxx \
  --webhook-on HIGH,CRITICAL
```

Slack / Discord の両方に対応（URLの形式で自動判定）。

### stdioトランスポート

```bash
agentwit proxy --stdio -- python my_mcp_server.py
```

## Witness Logのフォーマット

傍受された各イベントは `witness.jsonl` に1行のJSONとして記録されます：

```json
{
  "witness_id":      "イベント全体のsha256",
  "session_chain":   "sha256(直前のchain_hash + event_hash)",
  "timestamp":       "2026-03-14T12:18:53.708937+00:00",
  "actor":           "demo-agent",
  "action":          "tools/call",
  "tool":            "bash",
  "input_hash":      "入力ペイロードのsha256",
  "output_hash":     "出力ペイロードのsha256",
  "full_payload":    { "params": {}, "result": {} },
  "risk_indicators": [
    { "pattern": "shell_exec", "severity": "high", "matched": "bash" }
  ]
}
```

## 改ざん検知

```bash
# 改ざんのシミュレーション: event[0] の "actor" フィールドを変更
python3 -c "
import json; lines=open('witness.jsonl').readlines()
e=json.loads(lines[0]); e['actor']='ATTACKER'
lines[0]=json.dumps(e)+'\n'; open('witness.jsonl','w').writelines(lines)
"

agentwit replay --session ./witness_logs/session_20260314_120000
# Chain integrity: TAMPERED
#   [event 0] FAIL - session_chain mismatch:
#     expected '0fd4d24bcb3dab7d171e…'
#     got      'a79a9e4cdb19795a521e…'
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

## Python API

```python
from agentwit import WitnessLogger, ChainManager

# プロキシなしで直接ログを記録
logger = WitnessLogger(session_dir="./logs", actor="my-agent")
logger.log_event(
    action="tools/call",
    tool="bash",
    full_payload={"params": {"command": "ls"}, "result": {"stdout": "..."}}
)
logger.close()

# 記録済みセッションのChain Integrityを検証
chain = ChainManager(session_id="session_20260314_120000")
results = chain.verify_chain(events)
all_valid = all(r["valid"] for r in results)
```

## バージョン履歴

| バージョン | 日付       | 主な変更内容                                                      |
|------------|------------|-------------------------------------------------------------------|
| v0.1.0     | 2026-03-14 | MVP: HTTP/SSE/stdioプロキシ・改ざん検知Witnessログ               |
| v0.2.0     | 2026-03-15 | HTML/Markdownレポート・タイムライン比較・LangChain・Slack/Discord |
| v0.3.0     | 2026-03-16 | MCP Inspector GUI・監査ログ統合・標準MCP `/mcp` エンドポイント対応 |

## ユースケース

- **セキュリティエンジニア** — 改ざん不能な証拠としてAIエージェントの挙動を監査
- **エンタープライズチーム** — AI活動のコンプライアンスログとして保存
- **AI研究者** — エージェントセッションを再現可能な形式で比較・検証
- **ペネトレーションテスター** — MCPツール使用状況を証跡として文書化
- **MCPサーバー開発者** — デプロイ前にGUIでデバッグ

## ロードマップ

- [ ] MCP仕様の自動追従（月次変更検知 + 自動テスト）
- [ ] GUIからHTMLレポート直接生成
- [ ] stdioトランスポートの実環境テスト
- [ ] Windowsビルド確認
- [ ] GUIテストカバレッジ（Rust + Reactコンポーネント）
- [ ] 接続切れ時の自動再接続
- [ ] OWASP LLM Top 10マッピング

## 動作要件

- Python 3.10+
- FastAPI, uvicorn, httpx, click（インストール時に自動導入）
- GUI: Node.js 18+、Rust 1.70+（ソースからビルドする場合）

## ライセンス

[MIT](LICENSE) © agentwit contributors
