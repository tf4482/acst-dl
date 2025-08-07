#!/usr/bin/env python3
"""
Podcast Downloader Web Interface

A FastAPI-based web interface for the acst-dl podcast downloader.
Provides a modern web UI for managing podcast downloads with real-time progress tracking.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid

from fastapi import (
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
    Form,
    HTTPException,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Import the main downloader functionality
import importlib.util

# Load the acst-dl module dynamically
spec = importlib.util.spec_from_file_location("acst_dl", "acst-dl.py")
acst_dl = importlib.util.module_from_spec(spec)
sys.modules["acst_dl"] = acst_dl
spec.loader.exec_module(acst_dl)

# Import the functions we need
load_config = acst_dl.load_config
download_html = acst_dl.download_html
create_output_directory = acst_dl.create_output_directory
extract_mp3_links = acst_dl.extract_mp3_links
download_mp3_files = acst_dl.download_mp3_files
clear_all_mp3_files = acst_dl.clear_all_mp3_files

app = FastAPI(
    title="ACST-DL Web Interface",
    description="Web interface for the podcast MP3 downloader",
    version="1.0.0",
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global state for managing downloads
download_sessions: Dict[str, Dict] = {}
active_websockets: List[WebSocket] = []


class DownloadManager:
    """Manages download sessions and progress tracking"""

    def __init__(self):
        self.sessions = {}

    def create_session(self, config: dict) -> str:
        """Create a new download session"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "config": config,
            "status": "pending",
            "progress": 0,
            "total_urls": len(config.get("urls", {})),
            "completed_urls": 0,
            "current_url": None,
            "mp3_stats": {"total": 0, "downloaded": 0, "failed": 0, "skipped": 0},
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, updates: dict):
        """Update session data"""
        if session_id in self.sessions:
            self.sessions[session_id].update(updates)

    def get_all_sessions(self) -> List[Dict]:
        """Get all sessions sorted by creation time"""
        return sorted(
            self.sessions.values(), key=lambda x: x["created_at"], reverse=True
        )


download_manager = DownloadManager()


async def broadcast_update(message: dict):
    """Broadcast update to all connected WebSocket clients"""
    if active_websockets:
        disconnected = []
        for websocket in active_websockets:
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(websocket)

        # Remove disconnected websockets
        for ws in disconnected:
            active_websockets.remove(ws)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main dashboard page"""
    # Get recent download sessions
    sessions = download_manager.get_all_sessions()[:10]  # Last 10 sessions

    # Load current config if exists
    try:
        config = load_config()
    except:
        config = {
            "urls": {},
            "timeout": 30,
            "max_mp3_links": 5,
            "download_mp3_files": True,
            "verify_ssl": True,
        }

    return templates.TemplateResponse(
        "index.html", {"request": request, "sessions": sessions, "config": config}
    )


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration management page"""
    try:
        config = load_config()
    except:
        config = {
            "urls": {},
            "timeout": 30,
            "max_mp3_links": 5,
            "download_mp3_files": True,
            "verify_ssl": True,
        }

    return templates.TemplateResponse(
        "config.html", {"request": request, "config": config}
    )


@app.post("/config/save")
async def save_config(
    urls_json: str = Form(...),
    timeout: int = Form(30),
    max_mp3_links: Optional[int] = Form(None),
    download_mp3_files: bool = Form(False),
    verify_ssl: bool = Form(True),
):
    """Save configuration"""
    try:
        # Parse URLs JSON
        urls = json.loads(urls_json)

        config = {
            "urls": urls,
            "timeout": timeout,
            "max_mp3_links": max_mp3_links,
            "download_mp3_files": download_mp3_files,
            "verify_ssl": verify_ssl,
        }

        # Save to config file
        config_path = "acst-dl-config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return JSONResponse(
            {"success": True, "message": "Configuration saved successfully"}
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid URLs JSON format")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving configuration: {str(e)}"
        )


@app.post("/download/start")
async def start_download():
    """Start a new download session"""
    try:
        # Load current config
        config = load_config()

        # Create new download session
        session_id = download_manager.create_session(config)

        # Start download in background
        asyncio.create_task(run_download_session(session_id))

        return JSONResponse(
            {
                "success": True,
                "session_id": session_id,
                "message": "Download started successfully",
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error starting download: {str(e)}"
        )


async def run_download_session(session_id: str):
    """Run download session in background"""
    session = download_manager.get_session(session_id)
    if not session:
        return

    try:
        # Update session status
        download_manager.update_session(
            session_id, {"status": "running", "started_at": datetime.now().isoformat()}
        )

        await broadcast_update(
            {
                "type": "session_update",
                "session": download_manager.get_session(session_id),
            }
        )

        config = session["config"]
        urls_dict = config.get("urls", {})

        # Hardcoded output directory
        output_dir = os.path.abspath(os.path.expanduser("~/podcasts"))
        create_output_directory(output_dir)

        total_mp3_stats = {"total": 0, "downloaded": 0, "failed": 0, "skipped": 0}

        for i, (url_name, url) in enumerate(urls_dict.items(), 1):
            # Update current URL
            download_manager.update_session(
                session_id,
                {
                    "current_url": url_name,
                    "progress": int((i - 1) / len(urls_dict) * 100),
                },
            )

            await broadcast_update(
                {
                    "type": "session_update",
                    "session": download_manager.get_session(session_id),
                }
            )

            # Create subfolder for this URL
            url_output_dir = os.path.join(output_dir, url_name)
            create_output_directory(url_output_dir)

            # Download and process URL
            result = download_html(
                url,
                url_output_dir,
                config.get("timeout", 30),
                config.get("max_mp3_links"),
                url_name,
                config.get("download_mp3_files", False),
                config.get("verify_ssl", True),
            )

            if isinstance(result, dict) and result.get("success"):
                mp3_stats = result.get("mp3_downloads", {})
                total_mp3_stats["total"] += mp3_stats.get("total", 0)
                total_mp3_stats["downloaded"] += mp3_stats.get("successful", 0)
                total_mp3_stats["failed"] += mp3_stats.get("failed", 0)
                total_mp3_stats["skipped"] += mp3_stats.get("skipped", 0)

            # Update completed URLs
            download_manager.update_session(
                session_id, {"completed_urls": i, "mp3_stats": total_mp3_stats}
            )

        # Mark session as completed
        download_manager.update_session(
            session_id,
            {
                "status": "completed",
                "progress": 100,
                "current_url": None,
                "completed_at": datetime.now().isoformat(),
            },
        )

        await broadcast_update(
            {
                "type": "session_update",
                "session": download_manager.get_session(session_id),
            }
        )

    except Exception as e:
        # Mark session as failed
        download_manager.update_session(
            session_id,
            {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            },
        )

        await broadcast_update(
            {
                "type": "session_update",
                "session": download_manager.get_session(session_id),
            }
        )


@app.get("/download/sessions")
async def get_sessions():
    """Get all download sessions"""
    sessions = download_manager.get_all_sessions()
    return JSONResponse({"sessions": sessions})


@app.get("/download/session/{session_id}")
async def get_session(session_id: str):
    """Get specific download session"""
    session = download_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse({"session": session})


@app.post("/files/clear")
async def clear_files():
    """Clear all downloaded MP3 files"""
    try:
        output_dir = os.path.abspath(os.path.expanduser("~/podcasts"))
        cleared_count = clear_all_mp3_files(output_dir)
        return JSONResponse(
            {
                "success": True,
                "message": f"Cleared {cleared_count} MP3 files",
                "cleared_count": cleared_count,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing files: {str(e)}")


@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    """File management page"""
    output_dir = os.path.abspath(os.path.expanduser("~/podcasts"))

    # Get file structure
    files_structure = {}
    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir):
            rel_path = os.path.relpath(root, output_dir)
            if rel_path == ".":
                rel_path = ""

            mp3_files = [f for f in files if f.lower().endswith(".mp3")]
            if mp3_files:
                files_structure[rel_path or "root"] = mp3_files

    return templates.TemplateResponse(
        "files.html",
        {
            "request": request,
            "files_structure": files_structure,
            "output_dir": output_dir,
        },
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_websockets.append(websocket)

    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
