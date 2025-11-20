from calendar import week

from pydantic import BaseModel
from sqlalchemy import desc
from src.backend.agent.agent import TaskScheduler
from src.backend.database.sqlite import add_project
from fastapi import APIRouter, Request, HTTPException
import os
from dotenv import load_dotenv
import traceback

load_dotenv()

#REQUEST MODELS
class AddProjectRequest(BaseModel):
    title: str
    description: str
    tech_stack: str
    weekly_hours: str


router = APIRouter(
    prefix="/todoist",
    tags=["todoist"],
)

task_scheduler = TaskScheduler()

@router.get("/weekly-sync")
def run_weekly_sync():
    try:
        tasks_completed = task_scheduler.run_weekly_sync()

        if not tasks_completed:
            return {
                "success": False,
                "message": "No tasks were added to Todoist."
            }
        
        return {
            "success": True,
            "message": "Successfully added tasks to Todoist."
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync weekly tasks: {str(e)}"
        )
    
@router.post("/add-project")
def add_project(request: AddProjectRequest):
    try:
        title = request.title
        description = request.description
        tech_stack = request.tech_stack
        weekly_hours = request.weekly_hours


        project_added = add_project(title, description, tech_stack, weekly_hours)

        if not project_added:
            return HTTPException(status_code=500, detail="Failed to add project to database.")
        
        return {
            "success": True,
            "project": project_added
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

    

