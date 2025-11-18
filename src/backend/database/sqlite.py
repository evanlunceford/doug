import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"

CONTEXT_DB_PATH = DATABASE_DIR / "context.db"
CANVAS_DB_PATH = DATABASE_DIR / "canvas.db"
TASKS_DB_PATH = DATABASE_DIR / "tasks.db"
PROJECTS_DB_PATH = DATABASE_DIR / "projects.db"



# CREATE FUNCTIONS
def create_context_db():
    """Create context database for storing conversation history."""
    conn = sqlite3.connect(CONTEXT_DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS context (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_question TEXT,
        agent_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


def create_tasks_db():
    """Create tasks database with enhanced schema."""
    conn = sqlite3.connect(TASKS_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        description TEXT,
        project_id TEXT,
        section_id TEXT,
        parent_id TEXT,
        priority INTEGER DEFAULT 1,
        due_date TEXT,
        due_string TEXT,
        labels TEXT,
        completed INTEGER DEFAULT 0,
        canvas_assignment_id TEXT,
        course_id TEXT,
        course_name TEXT,
        sync_source TEXT DEFAULT 'manual',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_due_date 
        ON tasks(due_date)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_completed 
        ON tasks(completed)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_canvas_id 
        ON tasks(canvas_assignment_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sync_type TEXT NOT NULL,
        tasks_created INTEGER DEFAULT 0,
        tasks_updated INTEGER DEFAULT 0,
        tasks_failed INTEGER DEFAULT 0,
        status TEXT DEFAULT 'success',
        error_message TEXT,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
    


def create_projects_db():
    conn = sqlite3.connect(PROJECTS_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE,
            description TEXT,
            tech_stack TEXT,
            weekly_hours INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


#PROJECT FUNCTIONS
def add_project(title: str, description: str, tech_stack: str, weekly_hours: int) -> None:
    """
    Insert a new project into the projects table.

    Raises sqlite3.IntegrityError if a project with the same title already exists.
    """
    conn = sqlite3.connect(PROJECTS_DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO projects (title, description, tech_stack, weekly_hours)
            VALUES (?, ?, ?, ?)
            """,
            (title, description, tech_stack, int(weekly_hours)),
        )
        conn.commit()
    finally:
        conn.close()


def update_project_value(title: str, column: str, value: Any) -> int:
    """
    Update a single column for a project identified by its title.

    Parameters:
        title (str): The project title (acts as a unique key).
        column (str): One of 'title', 'description', 'tech_stack', 'weekly_hours'.
        value (Any): New value to set.

    Returns:
        int: Number of rows updated (0 if no project with that title).
    """
    allowed_columns = {"title", "description", "tech_stack", "weekly_hours"}
    if column not in allowed_columns:
        raise ValueError(f"Invalid column name: {column}")

    if column == "weekly_hours":
        value = int(value)

    conn = sqlite3.connect(PROJECTS_DB_PATH)
    cursor = conn.cursor()

    try:

        cursor.execute(
            f"UPDATE projects SET {column} = ? WHERE title = ?",
            (value, title),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def get_project_by_title(title: str) -> dict | None:
    conn = sqlite3.connect(PROJECTS_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, title, description, tech_stack, weekly_hours FROM projects WHERE title = ?",
            (title,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "tech_stack": row[3],
        "weekly_hours": row[4],
    }

def delete_project(title: str) -> int:
    """
    Delete a project from the database by its title.

    Parameters:
        title (str): Title of the project to delete.

    Returns:
        int: Number of rows deleted (0 if no matching project).
    """
    conn = sqlite3.connect(PROJECTS_DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM projects WHERE title = ?",
            (title,),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()




# CONTEXT FUNCTIONS

def get_recent_context(hours: int = 24) -> str:
    """Get recent conversation context."""
    conn = sqlite3.connect(CONTEXT_DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
    SELECT user_question, agent_response, created_at
    FROM context
    WHERE created_at >= datetime('now', ?)
    ORDER BY created_at DESC
    LIMIT 20
    ''', (f'-{hours} hours',))

    db_context = cursor.fetchall()
    conn.close()
    
    if not db_context:
        return "No recent context available."
    
    recent_context = []
    for row in db_context:
        user_question, agent_response, timestamp = row
        recent_context.append(
            f"[{timestamp}] Q: {user_question}\nA: {agent_response}"
        )

    return "\n\n".join(recent_context)


def add_context(user_question: str, agent_response: str):
    """Add a new context entry."""
    conn = sqlite3.connect(CONTEXT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO context (user_question, agent_response)
        VALUES (?, ?)
    ''', (user_question, agent_response))
    
    conn.commit()
    conn.close()



# TASK FUNCTIONS

def store_task(task: Dict[str, Any], db_path: str = TASKS_DB_PATH) -> bool:
    """Store or update a task in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Convert labels list to string if present
    labels = task.get("labels")
    if isinstance(labels, list):
        labels = ",".join(labels)

    try:
        cursor.execute('''
            INSERT INTO tasks (
                id, content, description, project_id, section_id, parent_id,
                priority, due_date, due_string, labels, completed,
                canvas_assignment_id, course_id, course_name, sync_source,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                description = excluded.description,
                project_id = excluded.project_id,
                section_id = excluded.section_id,
                parent_id = excluded.parent_id,
                priority = excluded.priority,
                due_date = excluded.due_date,
                due_string = excluded.due_string,
                labels = excluded.labels,
                completed = excluded.completed,
                canvas_assignment_id = excluded.canvas_assignment_id,
                course_id = excluded.course_id,
                course_name = excluded.course_name,
                sync_source = excluded.sync_source,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            task.get("id"),
            task.get("content"),
            task.get("description"),
            task.get("project_id"),
            task.get("section_id"),
            task.get("parent_id"),
            task.get("priority", 1),
            task.get("due", {}).get("date") if isinstance(task.get("due"), dict) else task.get("due_date"),
            task.get("due", {}).get("string") if isinstance(task.get("due"), dict) else task.get("due_string"),
            labels,
            int(task.get("completed", False)),
            task.get("canvas_assignment_id"),
            task.get("course_id"),
            task.get("course_name"),
            task.get("sync_source", "manual")
        ))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error storing task: {e}")
        return False
    finally:
        conn.close()


def get_task(task_id: str, db_path: str = TASKS_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve a single task by ID."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_tasks_by_date_range(
    start_date: str,
    end_date: str,
    completed: Optional[bool] = None,
    db_path: str = TASKS_DB_PATH
) -> List[Dict[str, Any]]:
    """Get tasks within a date range."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT * FROM tasks 
        WHERE due_date >= ? AND due_date <= ?
    '''
    params = [start_date, end_date]
    
    if completed is not None:
        query += ' AND completed = ?'
        params.append(int(completed))
    
    query += ' ORDER BY due_date, priority DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_tasks_by_canvas_assignment(
    assignment_id: str,
    db_path: str = TASKS_DB_PATH
) -> List[Dict[str, Any]]:
    """Get all tasks associated with a Canvas assignment."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM tasks 
        WHERE canvas_assignment_id = ?
        ORDER BY due_date
    ''', (assignment_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def mark_task_completed(task_id: str, db_path: str = TASKS_DB_PATH) -> bool:
    """Mark a task as completed."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE tasks 
            SET completed = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (task_id,))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error marking task completed: {e}")
        return False
    finally:
        conn.close()


def delete_task(task_id: str, db_path: str = TASKS_DB_PATH) -> bool:
    """Delete a task from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting task: {e}")
        return False
    finally:
        conn.close()



# SYNC HISTORY FUNCTIONS
def log_sync(
    sync_type: str,
    tasks_created: int = 0,
    tasks_updated: int = 0,
    tasks_failed: int = 0,
    status: str = "success",
    error_message: str = None,
    db_path: str = TASKS_DB_PATH
):
    """Log a sync operation."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO sync_history 
        (sync_type, tasks_created, tasks_updated, tasks_failed, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (sync_type, tasks_created, tasks_updated, tasks_failed, status, error_message))
    
    conn.commit()
    conn.close()


def get_last_sync(sync_type: str, db_path: str = TASKS_DB_PATH) -> Optional[Dict[str, Any]]:
    """Get the most recent sync of a given type."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM sync_history
        WHERE sync_type = ?
        ORDER BY synced_at DESC
        LIMIT 1
    ''', (sync_type,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None



# UTILITY FUNCTIONS
def cleanup_old_tasks(days: int = 30, db_path: str = TASKS_DB_PATH) -> int:
    """Delete completed tasks older than specified days."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute('''
        DELETE FROM tasks
        WHERE completed = 1 AND updated_at < ?
    ''', (cutoff,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted


def get_task_stats(db_path: str = TASKS_DB_PATH) -> Dict[str, int]:
    """Get statistics about tasks."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Total tasks
    cursor.execute('SELECT COUNT(*) FROM tasks')
    stats['total'] = cursor.fetchone()[0]
    
    # Completed tasks
    cursor.execute('SELECT COUNT(*) FROM tasks WHERE completed = 1')
    stats['completed'] = cursor.fetchone()[0]
    
    # Overdue tasks
    today = datetime.now().date().isoformat()
    cursor.execute('''
        SELECT COUNT(*) FROM tasks 
        WHERE completed = 0 AND due_date < ?
    ''', (today,))
    stats['overdue'] = cursor.fetchone()[0]
    
    # Due today
    cursor.execute('''
        SELECT COUNT(*) FROM tasks 
        WHERE completed = 0 AND due_date = ?
    ''', (today,))
    stats['due_today'] = cursor.fetchone()[0]
    
    conn.close()
    return stats



# INITIALIZATION
def initialize_databases():
    """Initialize all databases."""
    print("Creating databases...")
    create_context_db()
    create_tasks_db()
    print("Databases created successfully!")


if __name__ == "__main__":
    initialize_databases()
    
    # Print stats
    print("\nDatabase Statistics:")
    stats = get_task_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")