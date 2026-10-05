from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AccountMode = Literal["mock", "profile", "env", "keys"]
ResourceType = Literal["ec2", "ecs", "ecr", "eks", "s3", "cloudwatch"]


# ---------- AWS Account ----------
class AwsAccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    mode: AccountMode = "mock"
    profile_name: Optional[str] = None
    region: str = "us-east-1"


class AwsAccountCreate(AwsAccountBase):
    # Write-only credential fields, used when mode="keys".
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None


class AwsAccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    mode: Optional[AccountMode] = None
    profile_name: Optional[str] = None
    region: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None


class AwsAccountOut(AwsAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    resource_count: int = 0
    # Secrets are never returned; these are safe indicators only.
    has_credentials: bool = False
    access_key_last4: Optional[str] = None


# ---------- Settings ----------
class SettingsBase(BaseModel):
    default_account_id: Optional[int] = None
    refresh_interval_seconds: int = Field(default=20, ge=5, le=3600)
    default_status_filter: Optional[
        Literal["all", "healthy", "warning", "critical", "unknown"]
    ] = "all"
    image_check_interval_seconds: int = Field(default=1800, ge=60, le=86400)


class SettingsUpdate(BaseModel):
    default_account_id: Optional[int] = None
    refresh_interval_seconds: Optional[int] = Field(default=None, ge=5, le=3600)
    default_status_filter: Optional[
        Literal["all", "healthy", "warning", "critical", "unknown"]
    ] = None
    image_check_interval_seconds: Optional[int] = Field(default=None, ge=60, le=86400)


class SettingsOut(SettingsBase):
    model_config = ConfigDict(from_attributes=True)


# ---------- GitLab Source ----------
class GitLabSourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    environment: Optional[str] = None
    base_url: str = Field(..., min_length=1)
    project: str = Field(..., min_length=1)
    ref: str = "main"
    job_name: str = Field(..., min_length=1)
    artifact_path: str = "devops-report.json"
    enabled: bool = True


class GitLabSourceCreate(GitLabSourceBase):
    token: Optional[str] = None  # write-only PAT


class GitLabSourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    environment: Optional[str] = None
    base_url: Optional[str] = None
    project: Optional[str] = None
    ref: Optional[str] = None
    job_name: Optional[str] = None
    artifact_path: Optional[str] = None
    token: Optional[str] = None
    enabled: Optional[bool] = None


class GitLabSourceOut(GitLabSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    has_token: bool = False


class GitLabPreview(BaseModel):
    ok: bool
    resource_count: int = 0
    environment: Optional[str] = None
    generated_at: Optional[str] = None
    error: Optional[str] = None




# ---------- Monitored Resource ----------
class MonitoredResourceBase(BaseModel):
    account_id: int
    resource_type: ResourceType
    identifier: str = Field(..., min_length=1, max_length=256)
    display_name: Optional[str] = None
    region: Optional[str] = None
    group_name: Optional[str] = None
    # Signal keys to display; None = collect everything.
    collect_options: Optional[list[str]] = None
    enabled: bool = True
    notes: Optional[str] = None


class MonitoredResourceCreate(MonitoredResourceBase):
    pass


class MonitoredResourceUpdate(BaseModel):
    resource_type: Optional[ResourceType] = None
    identifier: Optional[str] = Field(default=None, min_length=1, max_length=256)
    display_name: Optional[str] = None
    region: Optional[str] = None
    group_name: Optional[str] = None
    collect_options: Optional[list[str]] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class MonitoredResourceOut(MonitoredResourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------- Monitoring payloads ----------
class ResourceStatus(BaseModel):
    resource_id: int
    account_id: int
    account_name: str
    resource_type: str
    identifier: str
    display_name: Optional[str] = None
    region: Optional[str] = None
    group_name: Optional[str] = None
    status: Literal["healthy", "warning", "critical", "unknown"] = "unknown"
    summary: str = ""
    metrics: dict[str, Any] = {}
    details: dict[str, Any] = {}
    source: Literal["mock", "aws", "gitlab"] = "mock"
    error: Optional[str] = None
    collected_at: datetime
    # Real recorded history of the primary metric (oldest -> newest), if any.
    history: list[float] = []
    history_metric: Optional[str] = None


class DashboardSummary(BaseModel):
    total_resources: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    accounts: int
    resources: list[ResourceStatus]


# ---------- Image Monitor (ECS -> ECR -> GitLab) ----------
RiskLevel = Literal["healthy", "warning", "critical", "unknown"]


class ImageMonitorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    application: str = Field(..., min_length=1, max_length=120)
    account_id: Optional[int] = None
    ecs_cluster: str = Field(..., min_length=1)
    ecs_service: str = Field(..., min_length=1)
    ecr_repository: str = Field(..., min_length=1)
    region: Optional[str] = None
    gitlab_source_id: Optional[int] = None
    image_tag_prefix: Optional[str] = None
    retention_count: Optional[int] = Field(default=None, ge=1, le=10000)
    warn_threshold: int = Field(default=3, ge=1, le=1000)
    webhook_url: Optional[str] = None
    enabled: bool = True


class ImageMonitorCreate(ImageMonitorBase):
    pass


class ImageMonitorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    application: Optional[str] = Field(default=None, min_length=1, max_length=120)
    account_id: Optional[int] = None
    ecs_cluster: Optional[str] = None
    ecs_service: Optional[str] = None
    ecr_repository: Optional[str] = None
    region: Optional[str] = None
    gitlab_source_id: Optional[int] = None
    image_tag_prefix: Optional[str] = None
    retention_count: Optional[int] = Field(default=None, ge=1, le=10000)
    warn_threshold: Optional[int] = Field(default=None, ge=1, le=1000)
    webhook_url: Optional[str] = None
    enabled: Optional[bool] = None


class ImageMonitorOut(ImageMonitorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    has_webhook: bool = False
    last_checked_at: Optional[datetime] = None
    last_risk: Optional[RiskLevel] = None
    last_position: Optional[int] = None


# --- Evaluation result: the correlated ECS -> ECR -> GitLab chain ---
class EcsDeployment(BaseModel):
    found: bool = False
    cluster: Optional[str] = None
    service: Optional[str] = None
    task_definition: Optional[str] = None
    image: Optional[str] = None          # full image reference
    image_tag: Optional[str] = None
    image_digest: Optional[str] = None
    desired_count: Optional[int] = None
    running_count: Optional[int] = None
    error: Optional[str] = None


class EcrPosition(BaseModel):
    found: bool = False
    repository: Optional[str] = None
    total_images: Optional[int] = None
    retained: Optional[int] = None         # lifecycle retention window size
    position: Optional[int] = None         # 1 = newest; higher = older/closer to pruning
    slots_remaining: Optional[int] = None  # retained - position
    pushed_at: Optional[str] = None
    lifecycle_source: Optional[str] = None  # "policy" | "override" | "default"
    error: Optional[str] = None


class GitLabBuild(BaseModel):
    found: bool = False
    pipeline_id: Optional[int] = None
    pipeline_url: Optional[str] = None
    pipeline_status: Optional[str] = None
    created_at: Optional[str] = None
    image_tag: Optional[str] = None
    commit_id: Optional[str] = None
    commit_url: Optional[str] = None
    ref: Optional[str] = None
    error: Optional[str] = None


class ImageChainResult(BaseModel):
    monitor_id: int
    name: str
    application: str
    source: Literal["mock", "aws"] = "mock"
    risk: RiskLevel = "unknown"
    summary: str = ""
    checked_at: datetime
    ecs: EcsDeployment
    ecr: EcrPosition
    gitlab: GitLabBuild
    error: Optional[str] = None


class ImageAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    risk_level: RiskLevel
    position: Optional[int] = None
    retention_count: Optional[int] = None
    image_tag: Optional[str] = None
    image_digest: Optional[str] = None
    commit_id: Optional[str] = None
    message: str
    notified: bool = False
    created_at: datetime
