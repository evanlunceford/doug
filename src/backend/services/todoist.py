import os
import requests
from typing import Any, Dict, List, Optional

class TodoistAPI:
    def __init__(self, token: Optional[str] = None):
        self.base = "https://api.todoist.com/api/v1"
        self.token = token or os.getenv("TODOIST_API_KEY")
        if not self.token:
            raise ValueError("Set TODOIST_API_TOKEN env or pass token=...")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        })

    def _get(self, path: str, params: Dict[str, Any] = None):
        r = self.session.get(self.base + path, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: Dict[str, Any] = None):
        r = self.session.post(self.base + path, json=json, timeout=20)
        r.raise_for_status()
        return r.json() if r.content else None

    def _post_nojson(self, path: str):
        r = self.session.post(self.base + path, timeout=20)
        r.raise_for_status()
        return None

    def _put(self, path: str, json: Dict[str, Any]):
        r = self.session.put(self.base + path, json=json, timeout=20)
        r.raise_for_status()
        return r.json() if r.content else None

    def _delete(self, path: str):
        r = self.session.delete(self.base + path, timeout=20)
        r.raise_for_status()
        return None

    # ---------- TASKS ----------
    def list_tasks(self, **filters):
        """Filters: project_id, section_id, label, filter, lang, priority, due_before, due_after, etc."""
        return self._get("/tasks", params=filters)

    def get_task(self, task_id: str):
        return self._get(f"/tasks/{task_id}")

    def create_task(self, **fields):
        """
        Common fields: content (str, required), description, project_id, section_id,
        parent_id, labels (list[str]), priority (1-4), due_string | due_date | due_datetime | due_lang,
        duration, duration_unit, order, assignee_id, etc.
        """
        return self._post("/tasks", json=fields)

    def update_task(self, task_id: str, **fields):
        return self._put(f"/tasks/{task_id}", json=fields)

    def close_task(self, task_id: str):
        """Marks task complete (same as 'complete')."""
        return self._post_nojson(f"/tasks/{task_id}/close")

    def reopen_task(self, task_id: str):
        return self._post_nojson(f"/tasks/{task_id}/reopen")

    def delete_task(self, task_id: str):
        return self._delete(f"/tasks/{task_id}")

    # ---------- PROJECTS ----------
    def list_projects(self):
        return self._get("/projects")

    def create_project(self, name: str, **fields):
        """Fields: parent_id, is_favorite, view_style ('list'|'board'), description (teams), color, etc."""
        payload = {"name": name, **fields}
        return self._post("/projects", json=payload)

    def update_project(self, project_id: str, **fields):
        return self._put(f"/projects/{project_id}", json=fields)

    def delete_project(self, project_id: str):
        return self._delete(f"/projects/{project_id}")

    # ---------- SECTIONS ----------
    def list_sections(self, project_id: Optional[str] = None):
        params = {"project_id": project_id} if project_id else None
        return self._get("/sections", params=params)

    def create_section(self, project_id: str, name: str):
        return self._post("/sections", json={"project_id": project_id, "name": name})

    def update_section(self, section_id: str, name: str):
        return self._put(f"/sections/{section_id}", json={"name": name})

    def delete_section(self, section_id: str):
        return self._delete(f"/sections/{section_id}")

    # ---------- COMMENTS ----------
    def list_task_comments(self, task_id: str):
        return self._get("/comments", params={"task_id": task_id})

    def list_project_comments(self, project_id: str):
        return self._get("/comments", params={"project_id": project_id})

    def create_comment(self, content: str, task_id: str = None, project_id: str = None):
        if not task_id and not project_id:
            raise ValueError("Provide task_id or project_id")
        payload = {"content": content}
        if task_id: payload["task_id"] = task_id
        if project_id: payload["project_id"] = project_id
        return self._post("/comments", json=payload)

    def update_comment(self, comment_id: str, content: str):
        return self._put(f"/comments/{comment_id}", json={"content": content})

    def delete_comment(self, comment_id: str):
        return self._delete(f"/comments/{comment_id}")

    # ---------- LABELS ----------
    def list_labels(self):
        return self._get("/labels")

    def create_label(self, name: str, **fields):
        """Fields: order, color, is_favorite, etc."""
        return self._post("/labels", json={"name": name, **fields})

    def update_label(self, label_id: str, **fields):
        return self._put(f"/labels/{label_id}", json=fields)

    def delete_label(self, label_id: str):
        return self._delete(f"/labels/{label_id}")
