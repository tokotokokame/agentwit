use std::io::Write;

#[tauri::command]
async fn write_audit_log(entry: String) -> Result<(), String> {
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map_err(|e| format!("Cannot determine home directory: {}", e))?;

    let dir = std::path::PathBuf::from(&home).join(".agentwit");
    std::fs::create_dir_all(&dir)
        .map_err(|e| format!("Failed to create ~/.agentwit directory: {}", e))?;

    let path = dir.join("audit.jsonl");
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|e| format!("Failed to open audit log file: {}", e))?;

    writeln!(file, "{}", entry)
        .map_err(|e| format!("Failed to write audit log entry: {}", e))?;

    Ok(())
}

#[tauri::command]
async fn generate_report(
    session_path: String,
    output_path: String,
) -> Result<String, String> {
    let output = std::process::Command::new("agentwit")
        .args(["report", "--session", &session_path,
               "--format", "html", "--output", &output_path])
        .output()
        .map_err(|e| e.to_string())?;

    if output.status.success() {
        // ブラウザで自動オープン
        #[cfg(target_os = "linux")]
        std::process::Command::new("xdg-open")
            .arg(&output_path)
            .spawn()
            .ok();
        Ok(output_path)
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_generate_report_empty_path() {
        // Empty paths: agentwit CLI will either not be found or return non-zero.
        // Either way the error is propagated as Err(String).
        let result = generate_report("".to_string(), "".to_string()).await;
        assert!(result.is_err(), "empty paths should return an error");
    }

    #[tokio::test]
    async fn test_generate_report_nonexistent_session() {
        // A path guaranteed not to exist: CLI returns non-zero exit code.
        let result = generate_report(
            "/nonexistent/session/path/agentwit_test_xyz".to_string(),
            "/tmp/agentwit_test_report_xyz.html".to_string(),
        )
        .await;
        assert!(result.is_err(), "nonexistent session should return an error");
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![write_audit_log, generate_report])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
