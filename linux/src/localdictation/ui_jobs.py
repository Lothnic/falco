"""Local background operations for Rune, with progress and cooperative cancellation.

The UI never blocks on model downloads. One operation runs per session, in a
separate process; its private runtime file contains no dictated audio or text.
"""
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager

from . import config, single_instance


def _path():
    return os.path.join(single_instance.private_session_dir() or single_instance.runtime_dir(), "dashboard-job.json")


@contextmanager
def _locked():
    with open(_path() + ".lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _read():
    try:
        with open(_path(), encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data):
    config.write_text_atomic(_path(), json.dumps(data), keep_backup=False)


def status():
    with _locked():
        data = _read()
        if data.get("busy") and data.get("pid"):
            try:
                os.kill(data["pid"], 0)
            except ProcessLookupError:
                data.update(busy=False, failed=True, message="The operation was interrupted. Try again.")
                _write(data)
        return {key: data[key] for key in ("id", "busy", "failed", "cancelled", "cancellable", "message", "progress", "result") if key in data}


def start(kind, payload=None):
    with _locked():
        if _read().get("busy"):
            raise ValueError("Another operation is running. Finish or cancel it first.")
        job_id = uuid.uuid4().hex
        _write(dict(id=job_id, kind=kind, payload=payload or {}, busy=True, failed=False,
                    message="Starting…", progress=0, cancelled=False, cancellable=kind in ("save_settings", "download_models", "hotkey_test"), started=time.time()))
        try:
            proc = subprocess.Popen([sys.executable, "-m", __name__], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    start_new_session=True)
        except OSError:
            data = _read()
            data.update(busy=False, failed=True, message="Could not start the operation. Try again.")
            _write(data)
            raise
        data = _read()
        data["pid"] = proc.pid
        _write(data)
    return {"ok": True, "message": "Working…", "job_id": job_id}


def cancel():
    with _locked():
        data = _read()
        if data.get("busy") and data.get("cancellable"):
            data["cancelled"] = True
            data["message"] = "Cancelling…"
            _write(data)
    return {"ok": True}


class Cancelled(Exception):
    pass


class Cancellation:
    def is_set(self):
        with _locked():
            return bool(_read().get("cancelled"))


def report(message, percent=0):
    with _locked():
        data = _read()
        data.update(message=str(message), progress=max(0, min(100, int(percent or 0))))
        _write(data)


def run():
    from .ui_operations import perform
    with _locked():
        data = _read()
    try:
        result = perform(data["kind"], data["payload"], report, Cancellation())
        update = dict(busy=False, failed=False, progress=100, message="Done.", result=result or {})
    except Cancelled:
        update = dict(busy=False, failed=False, message="Cancelled. Unapplied settings changes were kept.")
    except Exception as error:
        update = dict(busy=False, failed=True, message=str(error) or "The operation failed. Try again.")
    with _locked():
        current = _read()
        current.update(update)
        current.pop("payload", None)
        _write(current)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        run()
