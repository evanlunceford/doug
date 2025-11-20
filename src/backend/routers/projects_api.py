from src.backend.agent.agent import ProjectTaskAnalysisSig
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal, Any, Dict
import traceback
import sqlite3

from src.backend.database.sqlite import (
    add_project as add_project_db,
    create_projects_db,
    update_project_value as update_project_value_db,
    get_project_by_title,
    delete_project as delete_project_db,
    get_all_projects as get_all_projects_db
)

router = APIRouter(
    prefix="/projects",
    tags=['projects']
)


class AddProjectRequest(BaseModel):
    title: str
    description: Optional[str] = None
    tech_stack: Optional[str] = None
    weekly_hours: int = 0

class UpdateProjectRequest(BaseModel):
    title: str
    column: Literal["title", "description", "tech_stack", "weekly_hours"]
    value: Any


@router.post("/add")
def add_project(request: AddProjectRequest):
    """
    Create a new project.
    """
    try:
        try:
            add_project_db(
                request.title,
                request.description or "",
                request.tech_stack or "",
                request.weekly_hours,
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="A project with that title already exists.",
            )

        project = get_project_by_title(request.title)
        if not project:
            raise HTTPException(
                status_code=500,
                detail="Project was inserted but could not be retrieved.",
            )

        return {
            "success": True,
            "project": project,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/")
def get_all_projects():
    try:

        projects = get_all_projects_db()
        if not projects:
            raise HTTPException(
                status_code=500,
                detail=f"Could not retrieve all projects",
            )
        return {
            "success": True,
            "projects": projects,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{title}")
def get_project(title: str):
    """
    Get a single project by title.
    """
    try:
        project = get_project_by_title(title)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project with title '{title}' not found.",
            )
        return {
            "success": True,
            "project": project,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/update")
def update_project(request: UpdateProjectRequest):
    """
    Update a single column on a project (by title).
    """
    try:
        existing = get_project_by_title(request.title)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Project with title '{request.title}' not found.",
            )

        try:
            rows_updated = update_project_value_db(
                request.title,
                request.column,
                request.value,
            )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

        if rows_updated == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Project with title '{request.title}' not found or not updated.",
            )

        lookup_title = (
            request.value
            if request.column == "title"
            else request.title
        )

        updated_project = get_project_by_title(lookup_title)
        return {
            "success": True,
            "project": updated_project,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete-project/{title}")
def delete_project(title: str):
    """
    Delete a project by title.
    """
    try:
        rows_deleted = delete_project_db(title)
        if rows_deleted == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Project with title '{title}' not found.",
            )

        return {
            "success": True,
            "deleted": True,
            "title": title,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
