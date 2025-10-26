from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any
import dspy
from dotenv import load_dotenv

from services.canvas import CanvasAPI
from services.todoist import TodoistAPI
from services.googleCalendar import list_events_for_days
from database.sqlite import store_task

load_dotenv()

# Configuration
TIMEZONE = "America/Phoenix"
CANVAS_AUTH = {
    "base_url": os.getenv("CANVAS_BASE_URL"),
    "api_token": os.getenv("CANVAS_API_KEY")
}

# DSPy configuration
dspy.configure(lm=dspy.LM(
    model="ollama_chat/qwen2.5:7b-instruct",
    api_base="http://127.0.0.1:11434",
    temperature=0.3,
    max_tokens=512,
))


class AssignmentSummarizerSig(dspy.Signature):
    """Quickly summarizes the title of an assingment to be easier to see in Todoist"""
    assignment_name = dspy.InputField(desc="Name of the assignment")
    summarized_name = dspy.OutputField(desc="Summarized name, leave chapter numbers (i.e 5.6)")


class AssignmentAnalysisSig(dspy.Signature):
    """Analyze an assignment and determine time estimates and whether to split across days."""
    assignment_name = dspy.InputField(desc="Name of the assignment")
    assignment_description = dspy.InputField(desc="Description text from Canvas")
    points_possible = dspy.InputField(desc="Points the assignment is worth")
    due_date = dspy.InputField(desc="Due date in ISO format")

    estimated_hours = dspy.OutputField(desc="Total estimated hours needed as a decimal number, e.g., 2.5")
    should_split = dspy.OutputField(desc="MUST be 'true' if estimated_hours > 1.0, otherwise 'false'")
    num_sessions = dspy.OutputField(desc="If should_split is true: 2 or 3 based on hours. If should_split is false: 1")
    session_duration = dspy.OutputField(desc="Minutes per session: estimated_hours * 60 / num_sessions")

    session_part_one = dspy.OutputField(desc=(
        "If should_split is true and num_sessions >= 1: short name for session #1 "
        "(e.g., 'Research sources', 'Outline', 'Draft intro'). "
        "If should_split is false: output ''"
    ))
    session_part_two = dspy.OutputField(desc=(
        "If should_split is true and num_sessions >= 2: short name for session #2. "
        "Otherwise output ''"
    ))
    session_part_three = dspy.OutputField(desc=(
        "If should_split is true and num_sessions == 3: short name for session #3. "
        "Otherwise output ''"
    ))


class TaskScheduler:    
    def __init__(self):
        self.canvas_api = CanvasAPI()
        self.todoist_api = TodoistAPI()
        self.tz = ZoneInfo(TIMEZONE)
        self.summarize_name = dspy.Predict(AssignmentSummarizerSig)
        self.assignment_analyzer = dspy.Predict(AssignmentAnalysisSig)
        # Track slots assigned during this run
        self.assigned_slots = {}  # {date_key: [(hour, duration_minutes), ...]}
        
    def get_next_week_data(self) -> Dict[str, Any]:
        print("Fetching Canvas assignments...")
        assignments = self.canvas_api.get_assignments_next_week(
            CANVAS_AUTH,
            tz_str=TIMEZONE,
            include_submissions=True
        )
    
        print("Fetching Google Calendar events...")
        calendar_events = list_events_for_days(7, tz=TIMEZONE)
        
        return {
            "assignments": assignments,
            "calendar_events": calendar_events
        }
    
    def analyze_assignment(self, assignment: Dict[str, Any]) -> Dict[str, Any]:
        assignment_obj = assignment.get("assignment", {})
        description = assignment.get("description_text", "")[:500]

        try:
            result = self.assignment_analyzer(
                assignment_name=assignment_obj.get("name", "Untitled"),
                assignment_description=description or "No description provided",
                points_possible=str(assignment_obj.get("points_possible", 0)),
                due_date=assignment.get("due_at", "")
            )

            should_split = _as_bool(getattr(result, "should_split", False))
            est_hours = _as_float(getattr(result, "estimated_hours", 1.0), 1.0)
            if est_hours <= 1.0:
                should_split = False

            num_sessions = _as_int(getattr(result, "num_sessions", 1), 1)
            if not should_split:
                num_sessions = 1
            if num_sessions < 1:
                num_sessions = 1

            session_duration = _as_int(getattr(result, "session_duration", 60), 60)
            if session_duration <= 0 and est_hours > 0:
                session_duration = max(15, _as_int(est_hours * 60 / num_sessions, 60))

            session_parts = []
            p1 = getattr(result, "session_part_one", "") or ""
            p2 = getattr(result, "session_part_two", "") or ""
            p3 = getattr(result, "session_part_three", "") or ""
            for p in (p1, p2, p3):
                if p.strip():
                    session_parts.append(p.strip())

            return {
                "estimated_hours": est_hours,
                "should_split": should_split,
                "num_sessions": num_sessions,
                "session_duration": session_duration,
                "task_name": assignment_obj.get("name", "Untitled"),
                "session_parts": session_parts
            }

        except Exception as e:
            print(f"Analysis failed for {assignment_obj.get('name')}: {e}")
            return {
                "estimated_hours": 1.0,
                "should_split": False,
                "num_sessions": 1,
                "session_duration": 60,
                "task_name": assignment_obj.get("name", "Untitled"),
                "session_parts": []
            }

    
    def get_busy_times(self, calendar_events: List[Dict]) -> Dict[str, List[tuple]]:
        busy_times = {}
        
        for event in calendar_events:
            start = event["start"].get("dateTime") or event["start"].get("date")
            if not start:
                continue
                
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start_local = start_dt.astimezone(self.tz)
                date_key = start_local.date().isoformat()
                
                end = event["end"].get("dateTime") or event["end"].get("date")
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                end_local = end_dt.astimezone(self.tz)
                
                if date_key not in busy_times:
                    busy_times[date_key] = []
                
                busy_times[date_key].append((start_local.hour, end_local.hour))
            except Exception as e:
                print(f"Could not parse event time: {e}")
                
        return busy_times
    
    def find_available_slot(self, date: datetime, busy_times: Dict, duration_minutes: int) -> tuple[str, int]:
        """
        Find an available slot and return (time_string, hour).
        Also marks the slot as assigned.
        """
        date_key = date.date().isoformat()
        busy = busy_times.get(date_key, [])
        
        # Get already assigned slots for this date
        assigned = self.assigned_slots.get(date_key, [])
        
        # Preferred work hours: 8 AM - 10 PM
        for hour in range(8, 22):
            # Check if this hour overlaps with calendar events
            is_free = True
            for busy_start, busy_end in busy:
                if busy_start <= hour < busy_end:
                    is_free = False
                    break
            
            # Check if this hour overlaps with already assigned tasks
            if is_free:
                duration_hours = duration_minutes / 60.0
                for assigned_hour, assigned_duration in assigned:
                    assigned_duration_hours = assigned_duration / 60.0
                    # Check for overlap
                    if (assigned_hour <= hour < assigned_hour + assigned_duration_hours or
                        hour <= assigned_hour < hour + duration_hours):
                        is_free = False
                        break
            
            if is_free:
                # Mark this slot as assigned
                if date_key not in self.assigned_slots:
                    self.assigned_slots[date_key] = []
                self.assigned_slots[date_key].append((hour, duration_minutes))
                
                # Format time nicely
                period = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                return f"{display_hour}:00 {period}", hour
        
        # Fallback to 6 PM if no slot found
        if date_key not in self.assigned_slots:
            self.assigned_slots[date_key] = []
        self.assigned_slots[date_key].append((18, duration_minutes))
        return "6:00 PM", 18
    
    def schedule_assignment_tasks(self, assignment, analysis, busy_times):
        assignment_obj = assignment.get("assignment", {})
        course_name = assignment.get("courseName", "Unknown").split()[0]

        summarized = self.summarize_name(assignment_name=assignment_obj.get("name", "Untitled"))
        summarized_name = getattr(summarized, "summarized_name", None) or assignment_obj.get("name", "Untitled")

        due_at = assignment.get("due_at")
        if not due_at:
            return []

        try:
            due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            due_local = due_dt.astimezone(self.tz)
        except Exception:
            return []

        tasks = []
        should_split = analysis["should_split"]
        num_sessions = analysis["num_sessions"] if should_split else 1
        session_duration = analysis["session_duration"]

        base_task_name = analysis.get("task_name") or summarized_name

        current_date = datetime.now(self.tz)
        days_until_due = (due_local.date() - current_date.date()).days

        session_dates = []
        
        # Spread sessions across available days
        if num_sessions == 1:
            # Single session: schedule 1-2 days before due date
            task_date = due_local - timedelta(days=min(2, max(1, days_until_due // 2)))
            
            # Skip Sundays
            while task_date.weekday() == 6:
                task_date -= timedelta(days=1)
            
            if task_date.date() >= current_date.date():
                session_dates.append(task_date)
        else:
            # Multiple sessions: spread evenly across available days
            # Calculate spacing between sessions
            available_days = max(1, days_until_due - 1)
            spacing = max(1, available_days // num_sessions)
            
            for i in range(num_sessions):
                # Schedule from earliest to latest
                offset = i * spacing
                task_date = current_date + timedelta(days=offset)
                
                # Skip Sundays
                while task_date.weekday() == 6:
                    task_date += timedelta(days=1)
                
                # Don't schedule on/after due date
                if task_date.date() >= due_local.date():
                    task_date = due_local - timedelta(days=1)
                    while task_date.weekday() == 6:
                        task_date -= timedelta(days=1)
                
                if task_date.date() >= current_date.date():
                    session_dates.append(task_date)

        for idx, task_date in enumerate(session_dates):
            hours = session_duration // 60
            minutes = session_duration % 60
            duration_str = f"{hours}h {minutes}min" if hours and minutes else (f"{hours}h" if hours else f"{minutes}min")

            suggested_time, _ = self.find_available_slot(task_date, busy_times, session_duration)

            if num_sessions > 1:
                if idx < len(analysis.get("session_parts", [])) and analysis["session_parts"][idx]:
                    session_label = f" - {analysis['session_parts'][idx]}"
                else:
                    session_label = f" (Part {idx + 1}/{num_sessions})"
                content = f"{duration_str} - {summarized_name}{session_label} - {course_name}"
            else:
                content = f"{duration_str} - {base_task_name} - {course_name}"

            due_date_str = f"{task_date.date().isoformat()} {suggested_time}"

            tasks.append({
                "content": content,
                "description": f"Canvas Assignment\n{assignment.get('html_url', '')}",
                "due_string": due_date_str,
                "priority": 3 if (due_local.date() - task_date.date()) <= timedelta(days=2) else 2,
                "labels": ["canvas", course_name[:20].lower().replace(" ", "-")]
            })

        return tasks

    
    def sync_to_todoist(self, tasks: List[Dict[str, Any]]) -> List[str]:
        created_ids = []
        
        for task in tasks:
            try:
                print(f"Creating: {task['content']}")
                result = self.todoist_api.create_task(**task)
                
                if result and result.get("id"):
                    created_ids.append(result["id"])
                    # Store task in SQLite
                    store_task(result)
                    
            except Exception as e:
                print(f"Failed to create task: {e}")
        
        return created_ids
    
    def run_weekly_sync(self):
        print("\n" + "="*60)
        print("Starting Weekly Canvas → Todoist Sync")
        print("="*60 + "\n")
        
        # Reset assigned slots for new sync run
        self.assigned_slots = {}
        
        data = self.get_next_week_data()
        assignments = data["assignments"]
        calendar_events = data["calendar_events"]
        
        print(f"Found {len(assignments)} assignments")
        print(f"Found {len(calendar_events)} calendar events\n")
        
        if not assignments:
            print("No assignments due in the next week!")
            return
        
        busy_times = self.get_busy_times(calendar_events)
        
        all_tasks = []
        for assignment in assignments:
            assignment_obj = assignment.get("assignment", {})
            name = assignment_obj.get("name", "Untitled")
            
            submission = assignment_obj.get("submission", {})
            if submission.get("submitted_at"):
                print(f"Skipping (already submitted): {name}")
                continue
            
            print(f"Analyzing: {name}")
            analysis = self.analyze_assignment(assignment)
            
            print(f"Estimate: {analysis['estimated_hours']}h, "
                  f"Split: {analysis['should_split']}, "
                  f"Sessions: {analysis['num_sessions']}")
            
            if analysis.get('session_parts'):
                print(f"Session parts: {', '.join(analysis['session_parts'])}")
            
            tasks = self.schedule_assignment_tasks(assignment, analysis, busy_times)
            all_tasks.extend(tasks)
        
        print(f"\nCreated {len(all_tasks)} tasks\n")
        
        if all_tasks:
            print("Syncing to Todoist...")
            created_ids = self.sync_to_todoist(all_tasks)
            print(f"\nSuccessfully created {len(created_ids)} tasks in Todoist!")
        else:
            print("No tasks to create")
        
        print("\n" + "="*60)
        print("Weekly sync complete!")
        print("="*60 + "\n")


def _as_float(x, default=0.0):
    try:
        if x is None or x == "":
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)

def _as_int(x, default=0):
    try:
        if x is None or x == "":
            return int(default)
        return int(float(x))
    except (TypeError, ValueError):
        return int(default)

def _as_bool(x, default=False):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    if isinstance(x, str):
        s = x.strip().lower()
        if s in {"true", "yes", "y", "1"}:
            return True
        if s in {"false", "no", "n", "0"}:
            return False
    return default

def main():
    scheduler = TaskScheduler()
    scheduler.run_weekly_sync()


if __name__ == "__main__":
    main()