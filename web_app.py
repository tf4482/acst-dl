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
from datetime import datetime, timedelta
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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
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

# Scheduler state
scheduler_task: Optional[asyncio.Task] = None
scheduler_enabled = False
scheduler_interval_minutes = 60
last_scheduled_run: Optional[datetime] = None
next_scheduled_run: Optional[datetime] = None


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


class SchedulerManager:
    """Manages automatic download scheduling"""

    def __init__(self):
        self.enabled = False
        self.interval_minutes = 60
        self.last_run = None
        self.next_run = None
        self.task = None

    def start(self, interval_minutes: int):
        """Start the scheduler with given interval"""
        self.stop()  # Stop any existing scheduler
        self.enabled = True
        self.interval_minutes = interval_minutes
        self.next_run = datetime.now() + timedelta(minutes=interval_minutes)
        self.task = asyncio.create_task(self._scheduler_loop())
        print(f"📅 Scheduler started with {interval_minutes} minute interval")

    def stop(self):
        """Stop the scheduler"""
        if self.task and not self.task.done():
            self.task.cancel()
        self.enabled = False
        self.next_run = None
        print("📅 Scheduler stopped")

    def get_status(self) -> dict:
        """Get current scheduler status"""
        return {
            "enabled": self.enabled,
            "interval_minutes": self.interval_minutes,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        try:
            while self.enabled:
                # Wait until next scheduled time
                if self.next_run:
                    now = datetime.now()
                    if now >= self.next_run:
                        # Time to run scheduled download
                        print(f"📅 Running scheduled download at {now.isoformat()}")
                        await self._run_scheduled_download()

                        # Schedule next run
                        self.last_run = now
                        self.next_run = now + timedelta(minutes=self.interval_minutes)

                        # Broadcast scheduler status update
                        await broadcast_scheduler_update()

                # Check every minute
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            print("📅 Scheduler task cancelled")
        except Exception as e:
            print(f"📅 Scheduler error: {e}")
            self.enabled = False

    async def _run_scheduled_download(self):
        """Run a scheduled download"""
        try:
            # Load current config
            config = load_config()

            # Check if there are URLs configured
            urls_dict = config.get("urls", {})
            if not urls_dict:
                print("📅 Scheduled download skipped: No URLs configured")
                return

            # Create new download session with scheduler flag
            session_id = download_manager.create_session(config)
            session = download_manager.get_session(session_id)
            if session:
                session["scheduled"] = True  # Mark as scheduled download

            # Start download in background
            asyncio.create_task(run_download_session(session_id))

            # Broadcast sessions update
            await broadcast_sessions_update()

            print(f"📅 Scheduled download started: session {session_id}")

        except Exception as e:
            print(f"📅 Error running scheduled download: {e}")


scheduler_manager = SchedulerManager()


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


async def get_file_structure():
    """Get current file structure for live updates"""
    output_dir = os.path.abspath("./podcasts")
    files_structure = {}

    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir):
            rel_path = os.path.relpath(root, output_dir)
            if rel_path == ".":
                rel_path = ""

            mp3_files = [f for f in files if f.lower().endswith(".mp3")]
            if mp3_files:
                files_structure[rel_path or "root"] = mp3_files

    return files_structure


async def broadcast_file_update():
    """Broadcast file structure updates to all clients"""
    files_structure = await get_file_structure()
    total_files = sum(len(files) for files in files_structure.values())

    await broadcast_update(
        {
            "type": "file_update",
            "files_structure": files_structure,
            "total_folders": len(files_structure),
            "total_files": total_files,
        }
    )


async def broadcast_config_update():
    """Broadcast configuration updates to all clients"""
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

    await broadcast_update({"type": "config_update", "config": config})


async def broadcast_sessions_update():
    """Broadcast sessions list updates to all clients"""
    sessions = download_manager.get_all_sessions()
    await broadcast_update({"type": "sessions_update", "sessions": sessions})


async def broadcast_scheduler_update():
    """Broadcast scheduler status updates to all clients"""
    status = scheduler_manager.get_status()
    await broadcast_update({"type": "scheduler_update", "scheduler": status})


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
            "scheduler": {"enabled": False, "interval_minutes": 60},
        }

    # Get scheduler status
    scheduler_status = scheduler_manager.get_status()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "sessions": sessions,
            "config": config,
            "scheduler": scheduler_status,
        },
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
            "scheduler": {"enabled": False, "interval_minutes": 60},
        }

    # Get scheduler status
    scheduler_status = scheduler_manager.get_status()

    return templates.TemplateResponse(
        "config.html",
        {"request": request, "config": config, "scheduler": scheduler_status},
    )


@app.post("/config/save")
async def save_config(
    urls_json: str = Form(...),
    timeout: int = Form(30),
    max_mp3_links: Optional[int] = Form(None),
    download_mp3_files: bool = Form(False),
    verify_ssl: bool = Form(True),
    scheduler_enabled: bool = Form(False),
    scheduler_interval: int = Form(60),
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
            "scheduler": {
                "enabled": scheduler_enabled,
                "interval_minutes": scheduler_interval,
            },
        }

        # Save to config file
        config_path = "acst-dl-config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        # Update scheduler based on new configuration
        if scheduler_enabled:
            scheduler_manager.start(scheduler_interval)
        else:
            scheduler_manager.stop()

        # Broadcast config and scheduler updates to all clients
        await broadcast_config_update()
        await broadcast_scheduler_update()

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

        # Validate URLs before creating session
        urls_dict = config.get("urls", {})
        if not urls_dict:
            raise HTTPException(status_code=400, detail="No URLs configured")

        # Quick validation of first URL to catch obvious errors early
        first_url = next(iter(urls_dict.values()))
        try:
            import requests

            # Quick HEAD request to validate URL accessibility
            response = requests.head(first_url, timeout=5, allow_redirects=True)
            if response.status_code >= 400:
                return JSONResponse(
                    {
                        "success": False,
                        "message": f"URL validation failed: {response.status_code} {response.reason}",
                    },
                    status_code=400,
                )
        except requests.exceptions.RequestException as e:
            return JSONResponse(
                {
                    "success": False,
                    "message": f"URL validation failed: {str(e)}",
                },
                status_code=400,
            )

        # Create new download session
        session_id = download_manager.create_session(config)

        # Start download in background
        asyncio.create_task(run_download_session(session_id))

        # Broadcast sessions update
        await broadcast_sessions_update()

        return JSONResponse(
            {
                "success": True,
                "session_id": session_id,
                "message": "Download started successfully",
            }
        )

    except HTTPException:
        raise
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
        # Update session status to running
        download_manager.update_session(
            session_id, {"status": "running", "started_at": datetime.now().isoformat()}
        )

        # Broadcast session update immediately
        await broadcast_update(
            {
                "type": "session_update",
                "session": download_manager.get_session(session_id),
            }
        )

        # Also broadcast sessions list update
        await broadcast_sessions_update()

        config = session["config"]
        urls_dict = config.get("urls", {})

        # Hardcoded output directory
        output_dir = os.path.abspath(os.path.expanduser("./podcasts"))
        create_output_directory(output_dir)

        total_mp3_stats = {"total": 0, "downloaded": 0, "failed": 0, "skipped": 0}

        for i, (url_name, url) in enumerate(urls_dict.items(), 1):
            # Update current URL
            download_manager.update_session(
                session_id,
                {
                    "current_url": url_name,
                },
            )

            # Broadcast both session update and sessions list update
            await broadcast_update(
                {
                    "type": "session_update",
                    "session": download_manager.get_session(session_id),
                }
            )

            await broadcast_sessions_update()

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
            elif isinstance(result, dict) and not result.get("success"):
                # Handle download failure - mark session as failed
                download_manager.update_session(
                    session_id,
                    {
                        "status": "failed",
                        "error": result.get("error", "Download failed"),
                        "completed_at": datetime.now().isoformat(),
                    },
                )

                await broadcast_update(
                    {
                        "type": "session_update",
                        "session": download_manager.get_session(session_id),
                    }
                )

                # Broadcast sessions update for statistics
                await broadcast_sessions_update()
                return

            # Update completed URLs
            download_manager.update_session(
                session_id, {"completed_urls": i, "mp3_stats": total_mp3_stats}
            )

        # Mark session as completed
        download_manager.update_session(
            session_id,
            {
                "status": "completed",
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

        # Broadcast sessions update for statistics
        await broadcast_sessions_update()

        # Broadcast file update since new files may have been downloaded
        await broadcast_file_update()

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

        # Broadcast sessions update for statistics
        await broadcast_sessions_update()


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
        output_dir = os.path.abspath(os.path.expanduser("./podcasts"))
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
    output_dir = os.path.abspath(os.path.expanduser("./podcasts"))

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


@app.get("/files/serve/{folder_name}/{file_name}")
async def serve_audio_file(folder_name: str, file_name: str):
    """Serve MP3 files for audio playback and downloads"""
    try:
        output_dir = os.path.abspath("./podcasts")
        file_path = os.path.join(output_dir, folder_name, file_name)

        # Security check: ensure the file is within the output directory
        if not os.path.abspath(file_path).startswith(output_dir):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if file exists and is an MP3
        if not os.path.exists(file_path) or not file_name.lower().endswith(".mp3"):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            file_path,
            media_type="audio/mpeg",
            filename=file_name,
            headers={"Accept-Ranges": "bytes"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")


@app.get("/scheduler/status")
async def get_scheduler_status():
    """Get current scheduler status"""
    status = scheduler_manager.get_status()
    return JSONResponse({"scheduler": status})


@app.post("/scheduler/start")
async def start_scheduler(interval_minutes: int = Form(60)):
    """Start the scheduler with specified interval"""
    try:
        scheduler_manager.start(interval_minutes)
        await broadcast_scheduler_update()
        return JSONResponse(
            {
                "success": True,
                "message": f"Scheduler started with {interval_minutes} minute interval",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error starting scheduler: {str(e)}"
        )


@app.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the scheduler"""
    try:
        scheduler_manager.stop()
        await broadcast_scheduler_update()
        return JSONResponse({"success": True, "message": "Scheduler stopped"})
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error stopping scheduler: {str(e)}"
        )


@app.get("/api/trigger-updates")
async def trigger_updates():
    """Trigger all live updates for newly connected clients"""
    await broadcast_file_update()
    await broadcast_config_update()
    await broadcast_scheduler_update()
    return JSONResponse({"success": True, "message": "Updates triggered"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_websockets.append(websocket)

    try:
        # Send initial updates when client connects
        await asyncio.sleep(0.1)  # Small delay to ensure connection is ready
        await broadcast_file_update()
        await broadcast_config_update()
        await broadcast_scheduler_update()

        while True:
            # Keep connection alive and handle incoming messages
            message = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


@app.on_event("startup")
async def startup_event():
    """Initialize scheduler on startup"""
    try:
        config = load_config()
        scheduler_config = config.get("scheduler", {})
        if scheduler_config.get("enabled", False):
            interval = scheduler_config.get("interval_minutes", 60)
            scheduler_manager.start(interval)
            print(f"📅 Scheduler auto-started with {interval} minute interval")
    except Exception as e:
        print(f"📅 Could not auto-start scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up scheduler on shutdown"""
    scheduler_manager.stop()


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=5000, reload=True, log_level="info")
