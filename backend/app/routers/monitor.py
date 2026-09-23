from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..collector_service import collect_resource
from ..database import get_db
from ..gitlab_service import collect_gitlab
from ..models import AwsAccount, GitLabSource, MetricSample, MonitoredResource
from ..schemas import DashboardSummary, ResourceStatus

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

# Preferred numeric metric to trend per resource type; falls back to the first
# numeric metric available.
PRIMARY_METRIC = {
    "ec2": "cpu_percent",
    "ecs": "running_count",
    "ecr": "image_count",
    "eks": "node_count",
    "s3": "size_gb",
    "cloudwatch": "breaches_24h",
}
HISTORY_LEN = 40
HISTORY_RETENTION_DAYS = 7


def _primary_metric(status: ResourceStatus):
    key = PRIMARY_METRIC.get(status.resource_type)
    val = status.metrics.get(key) if key else None
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        key = None
    if key is None:
        for k, v in status.metrics.items():
            if not isinstance(v, bool) and isinstance(v, (int, float)):
                key, val = k, v
                break
    if key is None:
        return None, None
    return key, float(val)


def _attach_history(db: Session, status: ResourceStatus) -> None:
    key, _ = _primary_metric(status)
    if key is None:
        return
    rows = (
        db.query(MetricSample)
        .filter(
            MetricSample.resource_id == status.resource_id,
            MetricSample.metric_name == key,
        )
        .order_by(MetricSample.collected_at.desc())
        .limit(HISTORY_LEN)
        .all()
    )
    status.history = [r.value for r in reversed(rows)]
    status.history_metric = key


def _record_history(db: Session, statuses: list[ResourceStatus]) -> None:
    # Only AWS/mock resources are backed by stable DB ids we can trend reliably.
    recordable = [s for s in statuses if s.source in ("mock", "aws")]
    wrote = False
    for st in recordable:
        key, val = _primary_metric(st)
        if key is None:
            continue
        db.add(MetricSample(resource_id=st.resource_id, metric_name=key, value=val))
        wrote = True
    if wrote:
        cutoff = datetime.utcnow() - timedelta(days=HISTORY_RETENTION_DAYS)
        db.query(MetricSample).filter(MetricSample.collected_at < cutoff).delete()
        db.commit()
    for st in statuses:
        _attach_history(db, st)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    account_id: int | None = Query(default=None),
    include_gitlab: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    query = db.query(MonitoredResource)
    if account_id is not None:
        query = query.filter(MonitoredResource.account_id == account_id)
    resources = query.order_by(MonitoredResource.id).all()

    statuses: list[ResourceStatus] = []
    for resource in resources:
        account = db.get(AwsAccount, resource.account_id)
        if account is None:
            continue
        statuses.append(collect_resource(resource, account))

    # GitLab-sourced environments (pulled from CI artifacts). Only when viewing
    # all accounts, since these are not tied to an AWS account row.
    if include_gitlab and account_id is None:
        sources = (
            db.query(GitLabSource).filter(GitLabSource.enabled == True).all()  # noqa: E712
        )
        if sources:
            with ThreadPoolExecutor(max_workers=min(8, len(sources))) as pool:
                for result in pool.map(collect_gitlab, sources):
                    statuses.extend(result)

    _record_history(db, statuses)

    by_status = Counter(s.status for s in statuses)
    by_type = Counter(s.resource_type for s in statuses)
    account_count = db.query(AwsAccount).count()

    return DashboardSummary(
        total_resources=len(statuses),
        by_status=dict(by_status),
        by_type=dict(by_type),
        accounts=account_count,
        resources=statuses,
    )


@router.get("/resource/{resource_id}", response_model=ResourceStatus)
def resource_status(resource_id: int, db: Session = Depends(get_db)):
    resource = db.get(MonitoredResource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    account = db.get(AwsAccount, resource.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Owning account not found")
    status = collect_resource(resource, account)
    _attach_history(db, status)
    return status
