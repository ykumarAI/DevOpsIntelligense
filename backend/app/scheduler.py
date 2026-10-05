"""Background scheduler that periodically evaluates image monitors so the team
is notified before a deployed production image is pruned from ECR.

Runs a single daemon thread that wakes on a configurable interval (from app
settings, overridable via ``IMAGE_MONITOR_INTERVAL_SECONDS``), evaluates every
enabled monitor, and lets ``run_check`` persist snapshots and fire alerts.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from .database import SessionLocal
from .image_monitor_service import run_check
from .models import AppSetting, ImageMonitor

_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_DEFAULT_INTERVAL = 1800
_MIN_INTERVAL = 60


def _interval_seconds() -> int:
    override = os.getenv("IMAGE_MONITOR_INTERVAL_SECONDS")
    if override:
        try:
            return max(_MIN_INTERVAL, int(override))
        except ValueError:
            pass
    db = SessionLocal()
    try:
        row = db.get(AppSetting, 1)
        value = getattr(row, "image_check_interval_seconds", None) if row else None
        return max(_MIN_INTERVAL, int(value)) if value else _DEFAULT_INTERVAL
    except Exception:  # noqa: BLE001
        return _DEFAULT_INTERVAL
    finally:
        db.close()


def _run_once() -> None:
    db = SessionLocal()
    try:
        monitors = (
            db.query(ImageMonitor).filter(ImageMonitor.enabled == True).all()  # noqa: E712
        )
        for monitor in monitors:
            try:
                run_check(db, monitor)
            except Exception:  # noqa: BLE001 - one bad monitor must not stop the loop
                db.rollback()
    finally:
        db.close()


def _loop() -> None:
    # Initial delay lets the app finish starting before the first sweep.
    if _stop.wait(min(_interval_seconds(), 30)):
        return
    while not _stop.is_set():
        _run_once()
        if _stop.wait(_interval_seconds()):
            return


def start() -> None:
    global _thread
    if os.getenv("IMAGE_MONITOR_DISABLE_SCHEDULER"):
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="image-monitor-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
