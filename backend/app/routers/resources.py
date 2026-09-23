from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AwsAccount, MonitoredResource
from ..schemas import (
    MonitoredResourceCreate,
    MonitoredResourceOut,
    MonitoredResourceUpdate,
)

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=list[MonitoredResourceOut])
def list_resources(
    account_id: int | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(MonitoredResource)
    if account_id is not None:
        query = query.filter(MonitoredResource.account_id == account_id)
    if resource_type is not None:
        query = query.filter(MonitoredResource.resource_type == resource_type)
    return query.order_by(MonitoredResource.id).all()


@router.post("", response_model=MonitoredResourceOut, status_code=201)
def create_resource(payload: MonitoredResourceCreate, db: Session = Depends(get_db)):
    if not db.get(AwsAccount, payload.account_id):
        raise HTTPException(status_code=400, detail="account_id does not exist")
    resource = MonitoredResource(**payload.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.put("/{resource_id}", response_model=MonitoredResourceOut)
def update_resource(
    resource_id: int, payload: MonitoredResourceUpdate, db: Session = Depends(get_db)
):
    resource = db.get(MonitoredResource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(resource, key, value)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/{resource_id}", status_code=204)
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.get(MonitoredResource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    db.delete(resource)
    db.commit()
