from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..gitlab_service import collect_gitlab, fetch_report
from ..models import GitLabSource
from ..schemas import (
    GitLabPreview,
    GitLabSourceCreate,
    GitLabSourceOut,
    GitLabSourceUpdate,
)

router = APIRouter(prefix="/api/gitlab", tags=["gitlab"])

_SECRET_FIELDS = ("token",)


def _to_out(source: GitLabSource) -> GitLabSourceOut:
    out = GitLabSourceOut.model_validate(source)
    out.has_token = bool(source.token)
    return out


@router.get("", response_model=list[GitLabSourceOut])
def list_sources(db: Session = Depends(get_db)):
    return [_to_out(s) for s in db.query(GitLabSource).order_by(GitLabSource.id).all()]


@router.post("", response_model=GitLabSourceOut, status_code=201)
def create_source(payload: GitLabSourceCreate, db: Session = Depends(get_db)):
    source = GitLabSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_out(source)


@router.put("/{source_id}", response_model=GitLabSourceOut)
def update_source(source_id: int, payload: GitLabSourceUpdate, db: Session = Depends(get_db)):
    source = db.get(GitLabSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="GitLab source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        # Blank secret means "leave unchanged" so tokens aren't wiped on re-save.
        if key in _SECRET_FIELDS and value in (None, ""):
            continue
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return _to_out(source)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(GitLabSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="GitLab source not found")
    db.delete(source)
    db.commit()


@router.post("/{source_id}/preview", response_model=GitLabPreview)
def preview_source(source_id: int, db: Session = Depends(get_db)):
    """Test a source by fetching the artifact and reporting what was found."""
    source = db.get(GitLabSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="GitLab source not found")
    try:
        report = fetch_report(source)
    except Exception as exc:  # noqa: BLE001 - report failure to the UI
        return GitLabPreview(ok=False, error=f"{type(exc).__name__}: {exc}")
    resources = report.get("resources") or []
    return GitLabPreview(
        ok=True,
        resource_count=len(resources),
        environment=report.get("environment") or source.environment,
        generated_at=report.get("generated_at"),
    )
