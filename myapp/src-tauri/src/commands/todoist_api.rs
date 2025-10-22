use serde::{Deserialize, Serialize};
use tauri::State;

use crate::state::AppState;

#[derive(Debug, Deserialize, Serialize)]
pub struct TodoistTask {
  pub id: String,
  pub content: String,
  #[serde(default)]
  pub is_completed: bool,
  #[serde(default)]
  pub project_id: Option<String>,
  #[serde(default)]
  pub section_id: Option<String>,
  #[serde(default)]
  pub labels: Option<Vec<String>>,
  #[serde(default)]
  pub priority: Option<i32>,
  #[serde(default)]
  pub due: Option<serde_json::Value>,
  #[serde(flatten)]
  pub extra: serde_json::Value,
}

#[tauri::command]
pub async fn get_all_tasks(state: State<'_, AppState>) -> Result<Vec<TodoistTask>, String> {
  let key = state.todoist_key.lock().await.clone();
  if key.is_empty() {
    return Err("Missing TODOIST_API_KEY (set it in your env)".to_string());
  }

  let url = format!("{}/tasks", state.todoist_base);

  let resp = state.http
    .get(url)
    .bearer_auth(&key)
    .header("Accept", "application/json")
    .timeout(std::time::Duration::from_secs(10))
    .send()
    .await
    .map_err(|e| format!("Request error: {e}"))?;

  if !resp.status().is_success() {
    let code = resp.status();
    let body = resp.text().await.unwrap_or_default();
    return Err(format!("Upstream error {code}: {body}"));
  }

  let tasks = resp
    .json::<Vec<TodoistTask>>()
    .await
    .map_err(|e| format!("JSON error: {e}"))?;

  Ok(tasks)
}
