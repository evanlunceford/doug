import os
import logging
from datetime import timedelta
from typing import Any, Dict

from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Response

from src.backend.routers import canvas_api
from src.backend.routers import todoist_api
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

APP_NAME = os.getenv("APP_NAME", "My FastAPI App")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


app.include_router(
    canvas_api.router
)
app.include_router(
    todoist_api.router
)


if __name__ == "__main__":
    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )
