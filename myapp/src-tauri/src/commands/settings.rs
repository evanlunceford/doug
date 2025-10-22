use tauri::State;
use serde::Deserialize;
use crate::state::AppState;

#[derive(Deserialize)]
pub struct SetModelReq { pub model: String }

#[tauri::command]
pub async fn set_model(state: State<'_, AppState>, req: SetModelReq) -> Result<(), String> {
  let mut name = state.model_name.lock().await;
  *name = req.model;
  Ok(())
}
