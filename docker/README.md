# agentwit Docker Compose 監査スタック

MCP通信を透過的に監視・記録するための監査スタックです。

## 構成

| サービス | 役割 |
|---|---|
| `agentwit` | MCPプロキシ。ツール呼び出しをJSONLログとして記録 |
| `fluentbit` | ログ収集・機密情報マスク → Loki転送 |
| `loki` | ログ集約・インデックス |
| `grafana` | ダッシュボード可視化 |

## 起動方法

```bash
cp .env.example .env
# TARGET_URL を監視対象のMCPサーバーURLに変更
docker compose up -d
```

## アクセス

- **Grafana**: http://localhost:3000 (admin / changeme)
- **Loki API**: http://localhost:3100

## 環境変数

| 変数 | 必須 | 説明 |
|---|---|---|
| `TARGET_URL` | ✅ | 転送先MCPサーバーのURL |
| `WEBHOOK_URL` | 任意 | Slack/Discord Webhook URL（高リスク検知時に通知） |

## 注意事項

- **推奨スペック**: RAM 4GB以上
- ログは `./logs/` ディレクトリに保存されます
- APIキー・トークン・パスワード・Authorizationヘッダはフルエントビットで自動マスクされます
- Grafanaのデフォルトパスワード（`changeme`）は本番環境では必ず変更してください

## ログの確認

```bash
# リアルタイムログ
docker compose logs -f agentwit

# 監査ログ（JSONL形式）
tail -f logs/audit.jsonl | jq .
```

## 停止

```bash
docker compose down
# データも削除する場合
docker compose down -v
```
