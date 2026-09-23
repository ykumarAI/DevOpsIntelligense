from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..collector_service import collect_resource
from ..database import get_db
from ..gitlab_service import collect_gitlab
from ..models import AwsAccount, GitLabSource, MonitoredResource
from ..schemas import DashboardSummary, ResourceStatus

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


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
    return collect_resource(resource, account)
