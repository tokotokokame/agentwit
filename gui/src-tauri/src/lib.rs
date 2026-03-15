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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![write_audit_log])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
