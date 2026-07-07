"""Async report generation task management."""
import uuid
import threading
from datetime import datetime

# Simple in-memory task store (use Redis in production)
tasks = {}


def start_report_task(data: dict) -> str:
    """Start an async report generation and return task_id."""
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "started_at": datetime.now().isoformat(),
        "download_url": None,
        "error": None,
    }

    def run():
        try:
            tasks[task_id]["progress"] = 25
            from services.report_service import generate_word_report
            tasks[task_id]["progress"] = 50
            output_path, output_filename = generate_word_report(data)
            tasks[task_id]["progress"] = 100
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["download_url"] = f"/api/report/download/{output_filename}"
        except Exception as e:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return task_id


def get_task_status(task_id: str) -> dict:
    """Get the status of an async task."""
    return tasks.get(task_id, {"status": "not_found"})
