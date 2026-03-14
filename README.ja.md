# agentwit

> AIエージェントとMCPサーバー間の通信を記録する透過型Witnessプロキシ

[English](README.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-48%20passing-brightgreen.svg)](#)

## agentwit とは？

agentwit は、AIエージェントとMCPサーバーの間に置く透過型プロキシです。
すべての通信を改ざん検知可能なWitness Log（改ざん検知ログ）として記録します。

不審なトラフィックをブロックする **「ガード」** 型の既存ツールとは異なり、
agentwit は **「証人（Witness）」** として動作します。
通信をブロックせず、改変もせず、ただ暗号化されたChain Integrity（チェーン整合性）付きですべてを記録します。

## Guard（ガード）vs. Witness（証人）

| ツール       | アプローチ        | 通信のブロック | 改ざん検知ログ |
|--------------|-------------------|:--------------:|:--------------:|
| mcp-scan     | プロキシ + ガード | ✅             | ❌             |
| Proximity    | 静的スキャナー    | —              | ❌             |
| Intercept    | ポリシープロキシ  | ✅             | ❌             |
| **agentwit** | **Witnessプロキシ** | **❌**       | **✅**         |

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
      │
      ▼
     ...
```

どのイベントに対しても1バイトの変更を加えると、その時点からチェーン全体が壊れます。
これにより改ざんを即座に検出できます。

## クイックスタート

### インストール

```bash
pip install agentwit
```

### 1. Witnessプロキシを起動

```bash
agentwit proxy --target http://localhost:3000 --port 8765
# Starting agentwit proxy → http://localhost:3000
# Listening on 127.0.0.1:8765
# Session: ./witness_logs/session_20260314_120000
```

### 2. エージェントの向き先をプロキシに変更

```bash
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

## コマンド一覧

```
agentwit proxy   --target URL [--port 8765] [--log-dir ./witness_logs] [--actor NAME]
agentwit report  --session DIR [--format json|markdown|html] [--output FILE]
agentwit replay  --session DIR [--verify/--no-verify]
agentwit diff    --session-a DIR --session-b DIR
```

| コマンド  | 説明                                                     |
|-----------|----------------------------------------------------------|
| `proxy`   | 透過Witnessプロキシを起動                                 |
| `report`  | 監査レポートを生成（json / markdown / html）              |
| `replay`  | セッションを再生しChain Integrityを検証                   |
| `diff`    | 2つのセッションを並べて比較                               |

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

イベントは到着と同時にJSONLファイルへ追記されます。
プロキシは上流のレスポンスをバッファリングせず、遅延も発生しません。

## 改ざん検知

ログのどのフィールドを変更しても、agentwit は即座に検出します：

```bash
# 改ざんのシミュレーション: event[0] の "actor" フィールドを変更
python3 -c "
import json; lines=open('witness.jsonl').readlines()
e=json.loads(lines[0]); e['actor']='ATTACKER'
lines[0]=json.dumps(e)+'\n'; open('witness.jsonl','w').writelines(lines)
"

agentwit replay --session ./witness_logs/session_20260314_120000
# Session: session_20260314_120000  (6 events)
# Chain integrity: TAMPERED
#   [event 0] FAIL - session_chain mismatch:
#     expected '0fd4d24bcb3dab7d171e…'
#     got      'a79a9e4cdb19795a521e…'
```

## ユースケース

- **セキュリティエンジニア** — 本番環境でのAIエージェントの挙動を監査
- **エンタープライズチーム** — AI活動のコンプライアンスログとして保存
- **AI研究者** — エージェントセッションを再現可能な形式で比較・検証
- **ペネトレーションテスター** — MCPツール使用状況を証跡として文書化

## Python API

```python
from agentwit import WitnessLogger, ChainManager

# プロキシなしで直接ログを記録
logger = WitnessLogger(session_dir="./logs", actor="my-agent")
event = logger.log_event(
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

## 動作要件

- Python 3.10+
- FastAPI, uvicorn, httpx, click（インストール時に自動導入）

## ライセンス

[MIT](LICENSE) © agentwit contributors
