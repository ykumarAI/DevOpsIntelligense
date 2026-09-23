from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
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
    enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("AwsAccount", back_populates="resources")
