use serde::Deserialize;
use tauri::State;

use crate::state::AppState;

#[derive(Deserialize)]
pub struct AgentReq {
  pub persona: String,
  pub task: String,
  pub user_msg: String,
}

// Example: hit a local Ollama server that’s running 24/7 on the machine
#[tauri::command]
pub async fn agent_respond(state: State<'_, AppState>, req: AgentReq)
  -> Result<String, String>
{
  let system = format!(
    "You are an on-device assistant.\nPersonality: {}\nTask: {}\n- Be concise.\n",
    req.persona, req.task
  );
  let prompt = format!("{system}\n\nUser: {}\nAssistant:", req.user_msg);

  let body = serde_json::json!({
    "model": "llama3.2:3b-instruct", // or read from state
    "prompt": prompt,
    "stream": false,
    "options": { "temperature": 0.3, "num_predict": 256 }
  });

  let resp = state.http
    .post("http://127.0.0.1:11434/api/generate")
    .json(&body).send().await
    .map_err(|e| e.to_string())?;

  let v: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
  Ok(v["response"].as_str().unwrap_or("").to_string())
}
