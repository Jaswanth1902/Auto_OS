import os
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from utils.logger import api_logger as logger
from routers.face_auth import router as face_auth_router
from routers.voice import router as voice_router
from routers.workflows import router as workflows_router
from routers.executions import router as executions_router
from routers.threads import router as threads_router
from routers.system import router as system_router, background_heartbeat
from db import create_db_and_tables

load_dotenv(Path(__file__).with_name(".env"), override=True)
load_dotenv(override=True)

app = FastAPI(title="AutoOS Gateway API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(face_auth_router)
app.include_router(voice_router)
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(threads_router)
app.include_router(system_router)

# ── Static Files ─────────────────────────────────────────────────────────────
os.makedirs(os.path.join(os.path.dirname(__file__), "screenshots"), exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "screenshots")), name="screenshots")

@app.on_event("startup")
async def startup_event():
    # Setup Database
    create_db_and_tables()
    # Start the proactive guardian heartbeat
    asyncio.create_task(background_heartbeat())
    logger.info("AutoOS Gateway API started")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AUTOFLOW_PORT", 8765))
    uvicorn.run(app, host="0.0.0.0", port=port)
