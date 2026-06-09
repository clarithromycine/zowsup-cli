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
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_QUEUE_FILE = Path("data") / "md_link_queue.json"
_RESULTS_FILE = Path("data") / "md_link_results.json"
_WAIT_LOG_INTERVAL = 5.0


def _abs_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _path_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _qr_code_meta(qr_code: str) -> dict:
    value = qr_code or ""
    return {
        "qr_len": len(value),
        "qr_sha": hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] if value else "",
        "qr_url": value.startswith(("https://", "http://")),
    }


def describe_md_link_ipc() -> dict:
    """Return md.link IPC paths for diagnostics."""
    return {
        "cwd": os.getcwd(),
        "queue_file": _abs_path(_QUEUE_FILE),
        "results_file": _abs_path(_RESULTS_FILE),
    }


def _read_json(path: Path) -> Any:
    try:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning(
            "md.link IPC JSON parse failed path=%s size=%s error=%s",
            _abs_path(path),
            _path_size(path),
            exc,
        )
        return []
    except OSError as exc:
        logger.warning("md.link IPC JSON read failed path=%s error=%s", _abs_path(path), exc)
        return []
    except Exception:
        logger.exception("md.link IPC JSON read failed path=%s", _abs_path(path))
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
    meta = _qr_code_meta(qr_code)
    logger.info(
        "Enqueued md.link task %s phone=%s sync_timeout=%.1fs queue_len=%d "
        "cwd=%s queue_file=%s qr_len=%d qr_sha=%s qr_url=%s",
        task_id,
        phone,
        float(sync_timeout),
        len(queue),
        os.getcwd(),
        _abs_path(_QUEUE_FILE),
        meta["qr_len"],
        meta["qr_sha"],
        meta["qr_url"],
    )
    return task_id


def dequeue_md_link_tasks(phone: Optional[str] = None) -> List[Dict]:
    queue: List[Dict] = _read_json(_QUEUE_FILE)
    if not isinstance(queue, list) or not queue:
        return []
    queue_len = len(queue)

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
    logger.info(
        "Dequeued %d md.link task(s) phone=%s task_ids=%s queue_before=%d "
        "queue_remaining=%d cwd=%s queue_file=%s",
        len(mine),
        phone,
        ",".join(str(task.get("id", "?")) for task in mine),
        queue_len,
        len(remaining),
        os.getcwd(),
        _abs_path(_QUEUE_FILE),
    )
    return mine


def cancel_md_link_task(task_id: str) -> bool:
    queue: List[Dict] = _read_json(_QUEUE_FILE)
    if not isinstance(queue, list) or not queue:
        logger.info(
            "Cancel md.link task no-op task_id=%s queue_empty=True cwd=%s queue_file=%s",
            task_id,
            os.getcwd(),
            _abs_path(_QUEUE_FILE),
        )
        return False

    remaining = [
        task for task in queue
        if not (isinstance(task, dict) and task.get("id") == task_id)
    ]
    if len(remaining) == len(queue):
        logger.info(
            "Cancel md.link task no-op task_id=%s queue_len=%d cwd=%s queue_file=%s",
            task_id,
            len(queue),
            os.getcwd(),
            _abs_path(_QUEUE_FILE),
        )
        return False
    _write_json_atomic(_QUEUE_FILE, remaining)
    logger.info(
        "Cancelled md.link task task_id=%s queue_before=%d queue_remaining=%d cwd=%s queue_file=%s",
        task_id,
        len(queue),
        len(remaining),
        os.getcwd(),
        _abs_path(_QUEUE_FILE),
    )
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
    logger.info(
        "Wrote md.link result task_id=%s success=%s detail=%s result_keys=%s "
        "results_len=%d cwd=%s results_file=%s",
        task_id,
        success,
        (detail or "")[:200],
        ",".join(sorted((result or {}).keys())),
        len(results),
        os.getcwd(),
        _abs_path(_RESULTS_FILE),
    )


def get_md_link_result(task_id: str) -> Optional[Dict]:
    results: List[Dict] = _read_json(_RESULTS_FILE)
    if not isinstance(results, list):
        return None
    for result in results:
        if isinstance(result, dict) and result.get("id") == task_id:
            return result
    return None


def wait_md_link_result(task_id: str, timeout: float, poll_interval: float = 0.5) -> Optional[Dict]:
    start = time.time()
    deadline = start + timeout
    last_log = start
    logger.info(
        "Waiting for md.link result task_id=%s timeout=%.1fs poll_interval=%.1fs "
        "cwd=%s results_file=%s",
        task_id,
        float(timeout),
        float(poll_interval),
        os.getcwd(),
        _abs_path(_RESULTS_FILE),
    )
    while time.time() < deadline:
        result = get_md_link_result(task_id)
        if result is not None:
            logger.info(
                "Observed md.link result task_id=%s success=%s elapsed=%.1fs detail=%s",
                task_id,
                result.get("success"),
                time.time() - start,
                str(result.get("detail") or "")[:200],
            )
            return result
        now = time.time()
        if now - last_log >= _WAIT_LOG_INTERVAL:
            logger.debug(
                "Still waiting for md.link result task_id=%s elapsed=%.1fs remaining=%.1fs results_file=%s",
                task_id,
                now - start,
                max(0.0, deadline - now),
                _abs_path(_RESULTS_FILE),
            )
            last_log = now
        time.sleep(min(poll_interval, max(0.0, deadline - time.time())))
    logger.warning("Timed out waiting for md.link result task_id=%s timeout=%.1fs", task_id, float(timeout))
    return None
