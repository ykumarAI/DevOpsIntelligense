"""Correlate a production ECS service's deployed image across ECS -> ECR ->
GitLab and evaluate how close it is to being pruned by the ECR lifecycle policy.

The evaluation builds the chain:

    ECS production service -> deployed image (tag + digest)
        -> position of that image in the ECR repository's retained window
        -> GitLab pipeline + commit that built it

and derives a risk level so the team can be warned *before* the image a running
production task definition references is removed from ECR.

Like the rest of the app it never raises: any failure is captured as an error on
the relevant section of the result. Accounts in ``mock`` mode (or monitors with
no account) produce deterministic synthetic data for demos and offline use.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from .aws import collectors
from .models import AwsAccount, GitLabSource, ImageAlert, ImageMonitor
from .schemas import (
    EcrPosition,
    EcsDeployment,
    GitLabBuild,
    ImageChainResult,
)

DEFAULT_RETENTION = 20


# --------------------------------------------------------------------------- #
# Risk model
# --------------------------------------------------------------------------- #
def evaluate_risk(position: Optional[int], retained: Optional[int], warn_threshold: int) -> tuple[str, str]:
    """Return ``(risk, summary)`` for an image at 1-based ``position`` (newest=1)
    within a window that retains ``retained`` images.

    - critical: the image is at/over the oldest retained slot (next lifecycle
      sweep is liable to remove it).
    - warning:  it is within ``warn_threshold`` slots of the boundary.
    - healthy:  comfortably inside the window.
    """
    if position is None or retained is None or retained <= 0:
        return "unknown", "could not determine image position"
    slots_remaining = retained - position
    if slots_remaining <= 0:
        return (
            "critical",
            f"deployed image is at position {position}/{retained} - at the ECR "
            "retention boundary and may be pruned",
        )
    if slots_remaining <= warn_threshold:
        return (
            "warning",
            f"deployed image is at position {position}/{retained} - "
            f"{slots_remaining} slot(s) from removal",
        )
    return (
        "healthy",
        f"deployed image is at position {position}/{retained} - "
        f"{slots_remaining} slot(s) of headroom",
    )


# --------------------------------------------------------------------------- #
# Deterministic mock chain
# --------------------------------------------------------------------------- #
def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def _num(text: str, low: int, high: int) -> int:
    return low + (_seed(text) % (high - low + 1))


def _mock_result(monitor: ImageMonitor, gitlab_source: Optional[GitLabSource]) -> ImageChainResult:
    app = monitor.application
    key = f"{app}/{monitor.ecs_cluster}/{monitor.ecs_service}"
    sha = hashlib.sha1(key.encode()).hexdigest()  # noqa: S324 - non-crypto id
    short = sha[:8]
    prefix = monitor.image_tag_prefix or f"{app}-prod"
    tag = f"{prefix}-{short}"
    digest = "sha256:" + hashlib.sha256(key.encode()).hexdigest()

    retained = monitor.retention_count or _num(key + "ret", 15, 25)
    total = retained + _num(key + "tot", 0, 8)
    position = 1 + (_seed(key + "pos") % retained)
    pushed = datetime.utcnow() - timedelta(days=_num(key + "age", 1, 120))

    ecs = EcsDeployment(
        found=True,
        cluster=monitor.ecs_cluster,
        service=monitor.ecs_service,
        task_definition=f"{app}:{_num(key + 'td', 3, 120)}",
        image=f"123456789012.dkr.ecr.amazonaws.com/{monitor.ecr_repository}:{tag}@{digest}",
        image_tag=tag,
        image_digest=digest,
        desired_count=_num(key + "des", 2, 6),
        running_count=_num(key + "run", 2, 6),
    )
    ecr = EcrPosition(
        found=True,
        repository=monitor.ecr_repository,
        total_images=total,
        retained=retained,
        position=position,
        slots_remaining=retained - position,
        pushed_at=pushed.isoformat() + "Z",
        lifecycle_source="override" if monitor.retention_count else "default",
    )

    base_url = (gitlab_source.base_url.rstrip("/") if gitlab_source else "https://gitlab.example.com")
    project = gitlab_source.project if gitlab_source else app
    ref = gitlab_source.ref if gitlab_source else "main"
    commit = sha[:40]
    created = (pushed - timedelta(minutes=_num(key + "pl", 2, 45))).isoformat() + "Z"
    gitlab = GitLabBuild(
        found=True,
        pipeline_id=_num(key + "pid", 10000, 99999),
        pipeline_url=f"{base_url}/{project}/-/pipelines/{_num(key + 'pid', 10000, 99999)}",
        pipeline_status="success",
        created_at=created,
        image_tag=tag,
        commit_id=commit,
        commit_url=f"{base_url}/{project}/-/commit/{commit}",
        ref=ref,
    )

    risk, summary = evaluate_risk(position, retained, monitor.warn_threshold)
    return ImageChainResult(
        monitor_id=monitor.id,
        name=monitor.name,
        application=app,
        source="mock",
        risk=risk,
        summary=summary,
        checked_at=datetime.utcnow(),
        ecs=ecs,
        ecr=ecr,
        gitlab=gitlab,
    )


# --------------------------------------------------------------------------- #
# Live chain
# --------------------------------------------------------------------------- #
def _image_position(inventory: dict[str, Any], tag: Optional[str], digest: Optional[str]) -> Optional[int]:
    """1-based position (newest=1) of the deployed image in the retained set."""
    for idx, img in enumerate(inventory.get("images", []), start=1):
        if digest and img.get("imageDigest") == digest:
            return idx
        tags = img.get("imageTags", []) or []
        if tag and tag in tags:
            return idx
    return None


def _live_result(monitor: ImageMonitor, account: AwsAccount,
                 gitlab_source: Optional[GitLabSource]) -> ImageChainResult:
    region = monitor.region or account.region
    now = datetime.utcnow()
    ecs = EcsDeployment()
    ecr = EcrPosition(repository=monitor.ecr_repository)
    gitlab = GitLabBuild()

    try:
        session = collectors.build_session(
            account.mode, account.profile_name, region,
            account.access_key_id, account.secret_access_key, account.session_token,
        )
    except Exception as exc:  # noqa: BLE001
        return ImageChainResult(
            monitor_id=monitor.id, name=monitor.name, application=monitor.application,
            source="aws", risk="unknown", summary="AWS session failed",
            checked_at=now, ecs=ecs, ecr=ecr, gitlab=gitlab,
            error=f"{type(exc).__name__}: {exc}",
        )

    # 1) ECS deployed image
    try:
        dep = collectors.get_ecs_deployed_image(session, monitor.ecs_cluster, monitor.ecs_service)
        ecs = EcsDeployment(**{k: v for k, v in dep.items() if k in EcsDeployment.model_fields})
    except Exception as exc:  # noqa: BLE001
        ecs.error = f"{type(exc).__name__}: {exc}"

    # 2) ECR position vs lifecycle policy
    try:
        inventory = collectors.get_ecr_inventory(
            session, monitor.ecr_repository, monitor.image_tag_prefix
        )
        retained = monitor.retention_count or inventory.get("retained") or DEFAULT_RETENTION
        lifecycle_source = (
            "override" if monitor.retention_count
            else ("policy" if inventory.get("retained") else "default")
        )
        position = _image_position(inventory, ecs.image_tag, ecs.image_digest)
        pushed_at = None
        if position is not None:
            img = inventory["images"][position - 1]
            ts = img.get("imagePushedAt")
            pushed_at = ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts else None)
        ecr = EcrPosition(
            found=position is not None,
            repository=monitor.ecr_repository,
            total_images=inventory.get("total_images"),
            retained=retained,
            position=position,
            slots_remaining=(retained - position) if position is not None else None,
            pushed_at=pushed_at,
            lifecycle_source=lifecycle_source,
            error=None if position is not None else "deployed image not found in repository",
        )
    except Exception as exc:  # noqa: BLE001
        ecr.error = f"{type(exc).__name__}: {exc}"

    # 3) GitLab build correlation (optional)
    if gitlab_source is not None:
        from .gitlab_service import find_pipeline_for_image

        found = find_pipeline_for_image(gitlab_source, ecs.image_tag)
        gitlab = GitLabBuild(**{k: v for k, v in found.items() if k in GitLabBuild.model_fields})

    risk, summary = evaluate_risk(ecr.position, ecr.retained, monitor.warn_threshold)
    return ImageChainResult(
        monitor_id=monitor.id, name=monitor.name, application=monitor.application,
        source="aws", risk=risk, summary=summary, checked_at=now,
        ecs=ecs, ecr=ecr, gitlab=gitlab,
    )


def evaluate_monitor(monitor: ImageMonitor, account: Optional[AwsAccount],
                     gitlab_source: Optional[GitLabSource]) -> ImageChainResult:
    """Evaluate a single monitor into a correlated chain result. Never raises."""
    if account is None or account.mode == "mock":
        return _mock_result(monitor, gitlab_source)
    return _live_result(monitor, account, gitlab_source)


# --------------------------------------------------------------------------- #
# Notifications + persistence
# --------------------------------------------------------------------------- #
def _notify_webhook(url: str, result: ImageChainResult) -> bool:
    """Post a compact message to a Slack/Teams-compatible incoming webhook.
    Returns True on a 2xx response. Never raises."""
    text = (
        f"[{result.risk.upper()}] {result.name} ({result.application})\n"
        f"{result.summary}\n"
        f"image: {result.ecs.image_tag or 'n/a'} | commit: {result.gitlab.commit_id or 'n/a'}"
    )
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - user-configured host
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001 - delivery failures must not break checks
        return False


def run_check(db: Session, monitor: ImageMonitor, notify: bool = True) -> ImageChainResult:
    """Evaluate a monitor, persist its snapshot, and raise a (de-duplicated)
    alert + optional webhook notification when the risk escalates."""
    account = db.get(AwsAccount, monitor.account_id) if monitor.account_id else None
    gitlab_source = (
        db.get(GitLabSource, monitor.gitlab_source_id) if monitor.gitlab_source_id else None
    )
    result = evaluate_monitor(monitor, account, gitlab_source)

    previous_risk = monitor.last_risk
    monitor.last_checked_at = result.checked_at
    monitor.last_risk = result.risk
    monitor.last_position = result.ecr.position
    monitor.last_result = result.model_dump(mode="json")

    # Alert only when crossing into / escalating within a risky state, so a
    # steady warning does not spam the team every interval.
    escalated = result.risk in ("warning", "critical") and result.risk != previous_risk
    if escalated:
        notified = False
        if notify and monitor.webhook_url:
            notified = _notify_webhook(monitor.webhook_url, result)
        db.add(
            ImageAlert(
                monitor_id=monitor.id,
                risk_level=result.risk,
                position=result.ecr.position,
                retention_count=result.ecr.retained,
                image_tag=result.ecs.image_tag,
                image_digest=result.ecs.image_digest,
                commit_id=result.gitlab.commit_id,
                message=result.summary,
                notified=notified,
            )
        )
    db.commit()
    return result
