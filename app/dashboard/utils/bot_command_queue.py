"""
File-based IPC for small bot command requests.

The API/agent process enqueues a command for a phone.  The running bot process
dequeues commands for its own phone after login, executes them, and writes the
result for the requester to wait on.
"""

import json
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_QUEUE_FILE = Path("data") / "bot_command_queue.json"
_RESULTS_FILE = Path("data") / "bot_command_results.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_json_atomic(path: Path, data: Any) -> None:
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def enqueue_bot_command_task(
    phone: str,
    command: str,
    params: Optional[List[Any]] = None,
    options: Optional[Dict] = None,
) -> str:
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "phone": phone,
        "command": command,
        "params": params or [],
        "options": options or {},
        "created_at": int(time.time()),
        "status": "pending",
    }
    queue: List[Dict] = _read_json(_QUEUE_FILE)
    if not isinstance(queue, list):
        queue = []
    queue.append(task)
    _write_json_atomic(_QUEUE_FILE, queue)
    logger.info("Enqueued bot command task %s phone=%s command=%s", task_id, phone, command)
    return task_id


def dequeue_bot_command_tasks(phone: Optional[str] = None) -> List[Dict]:
    queue: List[Dict] = _read_json(_QUEUE_FILE)
    if not isinstance(queue, list) or not queue:
        return []

    mine: List[Dict] = []
    remaining: List[Dict] = []
    for task in queue:
        if not isinstance(task, dict):
            continue
        task_phone = str(task.get("phone", "")).strip().lstrip("+")
        if phone and task_phone == phone:
            mine.append(task)
        else:
            remaining.append(task)

    if not mine:
        return []

    _write_json_atomic(_QUEUE_FILE, remaining)
    return mine


def cancel_bot_command_task(task_id: str) -> bool:
    queue: List[Dict] = _read_json(_QUEUE_FILE)
    if not isinstance(queue, list) or not queue:
        return False

    remaining = [
        task for task in queue
        if not (isinstance(task, dict) and task.get("id") == task_id)
    ]
    if len(remaining) == len(queue):
        return False
    _write_json_atomic(_QUEUE_FILE, remaining)
    return True


def write_bot_command_result(
    task_id: str,
    success: bool,
    detail: str = "",
    result: Optional[Dict] = None,
) -> None:
    results: List[Dict] = _read_json(_RESULTS_FILE)
    if not isinstance(results, list):
        results = []
    results = [r for r in results if isinstance(r, dict) and r.get("id") != task_id]
    results.append({
        "id": task_id,
        "success": success,
        "detail": detail,
        "result": result or {},
        "done_at": int(time.time()),
    })
    results = results[-200:]
    _write_json_atomic(_RESULTS_FILE, results)


def get_bot_command_result(task_id: str) -> Optional[Dict]:
    results: List[Dict] = _read_json(_RESULTS_FILE)
    if not isinstance(results, list):
        return None
    for result in results:
        if isinstance(result, dict) and result.get("id") == task_id:
            return result
    return None


def wait_bot_command_result(task_id: str, timeout: float, poll_interval: float = 0.5) -> Optional[Dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = get_bot_command_result(task_id)
        if result is not None:
            return result
        time.sleep(poll_interval)
    return None
