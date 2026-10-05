"""CRUD + evaluation endpoints for ECS -> ECR -> GitLab image monitors."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..image_monitor_service import evaluate_monitor, run_check
from ..models import AwsAccount, GitLabSource, ImageAlert, ImageMonitor
from ..schemas import (
    ImageAlertOut,
    ImageChainResult,
    ImageMonitorCreate,
    ImageMonitorOut,
    ImageMonitorUpdate,
)

router = APIRouter(prefix="/api/image-monitors", tags=["image-monitors"])

_SECRET_FIELDS = ("webhook_url",)


def _to_out(monitor: ImageMonitor) -> ImageMonitorOut:
    out = ImageMonitorOut.model_validate(monitor)
    out.has_webhook = bool(monitor.webhook_url)
    return out


def _validate_refs(db: Session, account_id: int | None, gitlab_source_id: int | None) -> None:
    if account_id is not None and db.get(AwsAccount, account_id) is None:
        raise HTTPException(status_code=400, detail="account_id does not exist")
    if gitlab_source_id is not None and db.get(GitLabSource, gitlab_source_id) is None:
        raise HTTPException(status_code=400, detail="gitlab_source_id does not exist")


@router.get("", response_model=list[ImageMonitorOut])
def list_monitors(db: Session = Depends(get_db)):
    return [_to_out(m) for m in db.query(ImageMonitor).order_by(ImageMonitor.id).all()]


@router.post("", response_model=ImageMonitorOut, status_code=201)
def create_monitor(payload: ImageMonitorCreate, db: Session = Depends(get_db)):
    _validate_refs(db, payload.account_id, payload.gitlab_source_id)
    monitor = ImageMonitor(**payload.model_dump())
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return _to_out(monitor)


@router.put("/{monitor_id}", response_model=ImageMonitorOut)
def update_monitor(monitor_id: int, payload: ImageMonitorUpdate, db: Session = Depends(get_db)):
    monitor = db.get(ImageMonitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Image monitor not found")
    data = payload.model_dump(exclude_unset=True)
    _validate_refs(db, data.get("account_id", monitor.account_id),
                   data.get("gitlab_source_id", monitor.gitlab_source_id))
    for key, value in data.items():
        # Blank secret means "leave unchanged" so the webhook isn't wiped on re-save.
        if key in _SECRET_FIELDS and value in (None, ""):
            continue
        setattr(monitor, key, value)
    db.commit()
    db.refresh(monitor)
    return _to_out(monitor)


@router.delete("/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.get(ImageMonitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Image monitor not found")
    db.delete(monitor)
    db.commit()


@router.post("/{monitor_id}/check", response_model=ImageChainResult)
def check_monitor(monitor_id: int, db: Session = Depends(get_db)):
    """Evaluate one monitor now, persisting the snapshot and raising alerts."""
    monitor = db.get(ImageMonitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Image monitor not found")
    return run_check(db, monitor)


@router.post("/check", response_model=list[ImageChainResult])
def check_all(db: Session = Depends(get_db)):
    """Evaluate every enabled monitor now."""
    monitors = db.query(ImageMonitor).filter(ImageMonitor.enabled == True).all()  # noqa: E712
    return [run_check(db, m) for m in monitors]


@router.get("/{monitor_id}/preview", response_model=ImageChainResult)
def preview_monitor(monitor_id: int, db: Session = Depends(get_db)):
    """Evaluate without persisting or notifying (dry run for the UI)."""
    monitor = db.get(ImageMonitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Image monitor not found")
    account = db.get(AwsAccount, monitor.account_id) if monitor.account_id else None
    gitlab_source = (
        db.get(GitLabSource, monitor.gitlab_source_id) if monitor.gitlab_source_id else None
    )
    return evaluate_monitor(monitor, account, gitlab_source)


@router.get("/{monitor_id}/alerts", response_model=list[ImageAlertOut])
def list_alerts(monitor_id: int, limit: int = 50, db: Session = Depends(get_db)):
    if db.get(ImageMonitor, monitor_id) is None:
        raise HTTPException(status_code=404, detail="Image monitor not found")
    return (
        db.query(ImageAlert)
        .filter(ImageAlert.monitor_id == monitor_id)
        .order_by(ImageAlert.created_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
