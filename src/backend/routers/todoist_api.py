from calendar import week
from src.backend.agent.agent import TaskScheduler
from fastapi import APIRouter, Request, HTTPException
import os
from dotenv import load_dotenv
import traceback

load_dotenv()


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

    

