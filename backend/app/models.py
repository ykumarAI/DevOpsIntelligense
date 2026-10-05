from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class AwsAccount(Base):
    __tablename__ = "aws_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # mode controls how credentials are resolved:
    #   mock    -> no AWS calls, synthetic data
    #   profile -> use a named profile from the local AWS credentials file
    #   env     -> use the default credential chain (env vars, IAM role, etc.)
    #   keys    -> use the access key / secret / optional session token stored below
    mode = Column(String, nullable=False, default="mock")
    profile_name = Column(String, nullable=True)
    region = Column(String, nullable=False, default="us-east-1")
    # Only populated for mode="keys". Stored locally under the user's data dir
    # (same trust model as ~/.aws/credentials) and never returned by the API.
    access_key_id = Column(String, nullable=True)
    secret_access_key = Column(String, nullable=True)
    session_token = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    resources = relationship(
        "MonitoredResource",
        back_populates="account",
        cascade="all, delete-orphan",
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)
    default_account_id = Column(Integer, nullable=True)
    refresh_interval_seconds = Column(Integer, nullable=False, default=20)
    default_status_filter = Column(String, nullable=True)  # all | healthy | warning | critical | unknown
    # How often the background scheduler evaluates image monitors (seconds).
    image_check_interval_seconds = Column(Integer, nullable=False, default=1800)


class GitLabSource(Base):
    """A self-managed GitLab project whose CI job publishes a normalized
    devops-report.json artifact. The dashboard pulls that artifact (read-only)
    so higher environments are collected by the pipeline's own identity, not the
    user's AWS credentials."""

    __tablename__ = "gitlab_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)               # e.g. "UAT (via GitLab)"
    environment = Column(String, nullable=True)          # e.g. "UAT", "PROD"
    base_url = Column(String, nullable=False)            # https://gitlab.company.com
    project = Column(String, nullable=False)             # numeric id or "group/subgroup/project"
    ref = Column(String, nullable=False, default="main") # branch/tag the collector runs on
    job_name = Column(String, nullable=False)            # CI job that produces the artifact
    artifact_path = Column(String, nullable=False, default="devops-report.json")
    token = Column(Text, nullable=True)                  # PAT (read_api); stored locally, never returned
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)




class MonitoredResource(Base):
    __tablename__ = "monitored_resources"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False
    )
    # ec2 | ecs | ecr | eks | s3 | cloudwatch
    resource_type = Column(String, nullable=False)
    # instance id, cluster name, repo name, bucket name, alarm name, etc.
    identifier = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    region = Column(String, nullable=True)
    # Optional label to group related resources together on the dashboard.
    group_name = Column(String, nullable=True)
    # Subset of signal keys to display for this resource. NULL = collect all.
    collect_options = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("AwsAccount", back_populates="resources")


class MetricSample(Base):
    """A single point-in-time sample of a resource's primary metric, recorded on
    each dashboard refresh so tiles can draw a real historical trend."""

    __tablename__ = "metric_samples"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, index=True, nullable=False)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)


class ImageMonitor(Base):
    """Configuration for a production application whose deployed container image
    is tracked across ECS -> ECR -> GitLab. The monitor correlates the image a
    production ECS service is running with its position in the ECR repository's
    lifecycle retention window and the GitLab pipeline/commit that built it, so
    the team is warned before the image is pruned out of ECR."""

    __tablename__ = "image_monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                 # e.g. "orders-service (prod)"
    application = Column(String, nullable=False)           # logical app/service name
    # AWS account whose credentials are used for the ECS/ECR calls. NULL = mock.
    account_id = Column(
        Integer, ForeignKey("aws_accounts.id", ondelete="SET NULL"), nullable=True
    )
    ecs_cluster = Column(String, nullable=False)           # prod ECS cluster
    ecs_service = Column(String, nullable=False)           # prod ECS service
    ecr_repository = Column(String, nullable=False)        # ECR repo holding the image
    region = Column(String, nullable=True)
    # Optional GitLab source used to correlate the build pipeline/commit.
    gitlab_source_id = Column(
        Integer, ForeignKey("gitlab_sources.id", ondelete="SET NULL"), nullable=True
    )
    # Only consider images whose tag starts with this prefix (NULL = all).
    image_tag_prefix = Column(String, nullable=True)
    # Override the retained-image count; NULL = read it from the lifecycle policy.
    retention_count = Column(Integer, nullable=True)
    # Warn when (retained - position) <= this many slots remain before pruning.
    warn_threshold = Column(Integer, nullable=False, default=3)
    # Optional Slack/Teams-compatible incoming webhook for notifications.
    webhook_url = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Snapshot of the most recent evaluation for quick listing.
    last_checked_at = Column(DateTime, nullable=True)
    last_risk = Column(String, nullable=True)              # healthy|warning|critical|unknown
    last_position = Column(Integer, nullable=True)
    last_result = Column(JSON, nullable=True)


class ImageAlert(Base):
    """A recorded notification raised for an image monitor, used both for
    traceability and to de-duplicate repeat notifications at the same risk."""

    __tablename__ = "image_alerts"

    id = Column(Integer, primary_key=True)
    monitor_id = Column(
        Integer, ForeignKey("image_monitors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    risk_level = Column(String, nullable=False)            # warning | critical
    position = Column(Integer, nullable=True)
    retention_count = Column(Integer, nullable=True)
    image_tag = Column(String, nullable=True)
    image_digest = Column(String, nullable=True)
    commit_id = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    notified = Column(Boolean, default=False)              # webhook delivery succeeded
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
