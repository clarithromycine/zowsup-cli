"""
File-based IPC for md.link requests.

The dashboard/API process enqueues a task, the running bot process consumes it
after login, then writes the final result once the post-pair sync is complete.
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

_QUEUE_FILE = Path("data") / "md_link_queue.json"
_RESULTS_FILE = Path("data") / "md_link_results.json"


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


def enqueue_md_link_task(phone: str, qr_code: str, sync_timeout: float = 180.0) -> str:
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "phone": phone,
        "qr_code": qr_code,
        "sync_timeout": sync_timeout,
        "created_at": int(time.time()),
        "status": "pending",
    }
    queue: List[Dict] = _read_json(_QUEUE_FILE)
    if not isinstance(queue, list):
        queue = []
    queue.append(task)
    _write_json_atomic(_QUEUE_FILE, queue)
    logger.info("Enqueued md.link task %s phone=%s", task_id, phone)
    return task_id


def dequeue_md_link_tasks(phone: Optional[str] = None) -> List[Dict]:
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


def cancel_md_link_task(task_id: str) -> bool:
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


def write_md_link_result(
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


def get_md_link_result(task_id: str) -> Optional[Dict]:
    results: List[Dict] = _read_json(_RESULTS_FILE)
    if not isinstance(results, list):
        return None
    for result in results:
        if isinstance(result, dict) and result.get("id") == task_id:
            return result
    return None


def wait_md_link_result(task_id: str, timeout: float, poll_interval: float = 0.5) -> Optional[Dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = get_md_link_result(task_id)
        if result is not None:
            return result
        time.sleep(poll_interval)
    return None
