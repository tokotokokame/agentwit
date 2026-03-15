// MCP protocol types and helpers for potential future Rust-side MCP processing.
// Currently the MCP client logic lives in the frontend (TypeScript).
// This module is reserved for future Tauri commands related to MCP.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub method: String,
    pub params: Option<serde_json::Value>,
    pub id: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
    pub id: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpTool {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    pub input_schema: serde_json::Value,
}

impl JsonRpcRequest {
    pub fn new(method: impl Into<String>, params: serde_json::Value, id: u64) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
            method: method.into(),
            params: Some(params),
            id: serde_json::Value::Number(id.into()),
        }
    }

    pub fn initialize(id: u64) -> Self {
        Self::new(
            "initialize",
            serde_json::json!({
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-inspector",
                    "version": "1.0.0"
                }
            }),
            id,
        )
    }

    pub fn list_tools(id: u64) -> Self {
        Self::new("tools/list", serde_json::json!({}), id)
    }

    pub fn call_tool(name: impl Into<String>, arguments: serde_json::Value, id: u64) -> Self {
        Self::new(
            "tools/call",
            serde_json::json!({
                "name": name.into(),
                "arguments": arguments
            }),
            id,
        )
    }
}
