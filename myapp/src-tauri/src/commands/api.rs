use serde::{Deserialize, Serialize};
use tauri::State;

use crate::state::AppState;

#[tauri::command]
pub fn hello_world(){
    println!("I was invoked!!!!!");
}
