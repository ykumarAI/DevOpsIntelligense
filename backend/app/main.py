import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from .config import settings
from .database import Base, SessionLocal, engine
from .models import AwsAccount, MonitoredResource
from .routers import accounts, gitlab, monitor, resources, settings as settings_router


def _static_dir() -> Path | None:
    """Locate the built frontend, whether running from source or a frozen EXE."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent  # backend/
    candidate = base / "frontend_dist"
    return candidate if (candidate / "index.html").exists() else None


def _ensure_schema() -> None:
    """Additive migration for SQLite: add columns introduced after a DB already
    existed. create_all() handles brand-new tables; this covers new columns."""
    inspector = inspect(engine)
    if "aws_accounts" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("aws_accounts")}
    additions = {
        "access_key_id": "VARCHAR",
        "secret_access_key": "VARCHAR",
        "session_token": "TEXT",
    }
    with engine.begin() as conn:
        for col, coltype in additions.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE aws_accounts ADD COLUMN {col} {coltype}"))


Base.metadata.create_all(bind=engine)
_ensure_schema()

app = FastAPI(title="DevOps Operational Intelligence Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(resources.router)
app.include_router(monitor.router)
app.include_router(settings_router.router)
app.include_router(gitlab.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built frontend (single-page app) when it is bundled alongside the API.
_STATIC = _static_dir()
if _STATIC is not None:
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="frontend")


@app.on_event("startup")
def seed_demo_data() -> None:
    """Seed a demo mock account with a few resources on first run."""
    db = SessionLocal()
    try:
        if db.query(AwsAccount).count() > 0:
            return
        account = AwsAccount(
            name="Demo (mock)", mode="mock", region="us-east-1"
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        demo = [
            ("ec2", "i-0abc12345demo0001", "api-gateway-01"),
            ("ec2", "i-0abc12345demo0002", "worker-node-02"),
            ("ecs", "prod-cluster/orders-service", "orders-service"),
            ("ecs", "prod-cluster/payments-service", "payments-service"),
            ("ecr", "orders-service", "orders-service repo"),
            ("eks", "prod-eks-cluster", "prod-eks"),
            ("s3", "company-app-artifacts", "artifacts bucket"),
            ("cloudwatch", "prod-api-5xx-alarm", "API 5XX alarm"),
        ]
        for rtype, identifier, display in demo:
            db.add(
                MonitoredResource(
                    account_id=account.id,
                    resource_type=rtype,
                    identifier=identifier,
                    display_name=display,
                    region="us-east-1",
                    enabled=True,
                )
            )
        db.commit()
    finally:
        db.close()
