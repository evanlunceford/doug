from calendar import week
from src.backend.services.canvas import CanvasService
from fastapi import APIRouter, Request, HTTPException
import os
from dotenv import load_dotenv
import traceback

load_dotenv()

router = APIRouter(
    prefix="/canvas",
    tags=["canvas"],
)

canvas_service = CanvasService()


@router.get("/remaining-assignments")
def get_weekly_assignments():
    try:
        weekly_assignments = canvas_service.get_remaining_weekly_assignments()

        if not weekly_assignments:
            return {
                "success": True,
                "message": "No more weekly assignments found for this week."
            }
        
        return {
            "success": True,
            "payload": weekly_assignments
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch remaining weekly assignments: {str(e)}"
        )
    

    
    

@router.post("/webhook")
async def canvas_webhook(request: Request):
    payload = await request.json()
    # Example: log or handle the event
    print("Canvas event received:", payload)
    return {"status": "ok", "received": payload}
