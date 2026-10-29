"""Single-process encrypted backup scheduling and admin restore drills."""
import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
import time
import recovery

LOG = logging.getLogger(__name__)
_lock = asyncio.Lock()

def enabled():
    return os.environ.get("BACKUP_ENABLED", "false").lower() == "true"

def _status_path():
    return Path(os.environ.get("BACKUP_STATUS_PATH", "/data/backup-status.json"))

def get_status():
    try:
        return json.loads(_status_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"last_success_at": None, "last_verify_at": None, "object": None}

def _persist(data):
    target = _status_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".writing")
    try:
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)

async def run_backup():
    if not enabled():
        raise RuntimeError("Encrypted backup scheduling is disabled")
    if _lock.locked():
        raise RuntimeError("Another backup or verification is active")
    async with _lock:
        try:
            result = await asyncio.to_thread(recovery.backup_to_s3)
            state = get_status()
            state.update(last_success_at=int(time.time()), object=result["object"],
                         encrypted_sha256=result["sha256"], counts=result["rows"],
                         last_failure_at=None)
            _persist(state)
            return {"status": "uploaded", "object": result["object"], "counts": result["rows"]}
        except BaseException as exc:
            state = get_status()
            state["last_failure_at"] = int(time.time())
            state["last_failure_kind"] = type(exc).__name__
            _persist(state)
            raise

async def verify_latest_offsite():
    if not enabled():
        raise RuntimeError("Encrypted backup scheduling is disabled")
    if _lock.locked():
        raise RuntimeError("Another backup or verification is active")
    async with _lock:
        state = get_status()
        key = state.get("object")
        if not key:
            raise RuntimeError("No successful encrypted backup is recorded")
        try:
            with tempfile.TemporaryDirectory(prefix="gilberto-restore-check-") as folder:
                destination = str(Path(folder) / "isolated")
                result = await asyncio.to_thread(
                    recovery.download_and_verify_s3, key, destination)
            state["last_verify_at"] = int(time.time())
            state["last_verify_object"] = key
            state["last_verify_rows"] = result["rows"]
            state["last_verify_failed_at"] = None
            _persist(state)
            return {"status": "restored_and_verified", "counts": result["rows"]}
        except BaseException as exc:
            state["last_verify_failed_at"] = int(time.time())
            state["last_verify_failure_kind"] = type(exc).__name__
            _persist(state)
            raise

async def periodic_backup():
    # No separate worker mounts the /data volume. The API is single worker.
    await asyncio.sleep(60)
    while True:
        if enabled():
            try:
                await run_backup()
                await verify_latest_offsite()
                LOG.info("Encrypted off-project backup downloaded and restored in isolation")
            except Exception as exc:
                LOG.error("Backup attempt failed (%s)", type(exc).__name__)
        try:
            hours = int(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))
        except ValueError:
            hours = 24
        await asyncio.sleep(max(1, min(hours, 168)) * 3600)
