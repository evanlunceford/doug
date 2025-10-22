use std::env;
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Clone)]
pub struct AppState {
  pub http: reqwest::Client,
  pub todoist_base: String,
  pub todoist_key: Arc<Mutex<String>>,
}

impl AppState {
  pub fn new() -> Self {
    Self {
      http: reqwest::Client::new(),
      todoist_base: env::var("TODOIST_BASE_URL")
        .unwrap_or_else(|_| "https://api.todoist.com/rest/v2".to_string()),
      todoist_key: Arc::new(Mutex::new(
        env::var("TODOIST_API_KEY").unwrap_or_default(),
      )),
    }
  }
}
