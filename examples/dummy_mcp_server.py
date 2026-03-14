#!/usr/bin/env python3
"""Minimal dummy MCP server (JSON-RPC 2.0) for demo purposes.

Usage:
    python examples/dummy_mcp_server.py [port]   # default 3999
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from disk",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "bash",
        "description": "Run a shell command",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
]


def _handle_request(req: dict) -> dict:
    method = req.get("method", "")
    params = req.get("params") or {}
    rid = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "dummy-mcp", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name == "read_file":
            path = args.get("path", "?")
            content = f"[simulated contents of {path}]\nline1\nline2\n"
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": content}}
        if name == "bash":
            cmd = args.get("command", "")
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "stdout": f"$ {cmd}\nhello from dummy bash\n",
                    "stderr": "",
                    "exit_code": 0,
                },
            }
        if name == "write_file":
            path = args.get("path", "?")
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"written": True, "path": path},
            }
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Unknown tool: {name}"},
        }

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            req = {}

        result = _handle_request(req)
        payload = json.dumps(result, ensure_ascii=False).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        body = b'{"status":"ok","server":"dummy-mcp"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dummy-mcp] {fmt % args}", flush=True)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3999
    server = HTTPServer(("127.0.0.1", port), MCPHandler)
    print(f"[dummy-mcp] Listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
