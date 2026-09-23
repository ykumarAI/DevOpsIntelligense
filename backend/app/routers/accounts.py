from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AwsAccount
from ..schemas import AwsAccountCreate, AwsAccountOut, AwsAccountUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _to_out(account: AwsAccount) -> AwsAccountOut:
    out = AwsAccountOut.model_validate(account)
    out.resource_count = len(account.resources)
    out.has_credentials = bool(account.secret_access_key)
    if account.access_key_id:
        out.access_key_last4 = account.access_key_id[-4:]
    return out


@router.get("", response_model=list[AwsAccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return [_to_out(a) for a in db.query(AwsAccount).order_by(AwsAccount.id).all()]


@router.post("", response_model=AwsAccountOut, status_code=201)
def create_account(payload: AwsAccountCreate, db: Session = Depends(get_db)):
    account = AwsAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return _to_out(account)


@router.put("/{account_id}", response_model=AwsAccountOut)
def update_account(account_id: int, payload: AwsAccountUpdate, db: Session = Depends(get_db)):
    account = db.get(AwsAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        # Empty credential strings mean "leave unchanged" so secrets aren't wiped
        # when the UI re-submits a form without re-entering them.
        if key in ("access_key_id", "secret_access_key", "session_token") and value in (None, ""):
            continue
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return _to_out(account)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(AwsAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
