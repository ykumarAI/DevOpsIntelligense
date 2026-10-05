"""Live AWS collectors using boto3.

Every collector returns the same normalized shape:
    {status, summary, metrics, details}

Collectors are defensive: any AWS/boto3 error is caught by the calling
service layer and surfaced as an `error` on the resource status, so a single
misconfigured resource never breaks the whole dashboard.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    import boto3
except ImportError:  # boto3 optional until live mode is used
    boto3 = None  # type: ignore


@lru_cache(maxsize=32)
def _session(mode: str, profile_name: str | None, region: str,
             access_key_id: str | None = None, secret_access_key: str | None = None,
             session_token: str | None = None):
    if boto3 is None:
        raise RuntimeError("boto3 is not installed; run 'pip install boto3'")
    if mode == "keys" and access_key_id and secret_access_key:
        return boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token or None,
            region_name=region,
        )
    if mode == "profile" and profile_name:
        return boto3.Session(profile_name=profile_name, region_name=region)
    return boto3.Session(region_name=region)


def build_session(mode: str, profile_name: str | None, region: str,
                  access_key_id: str | None = None, secret_access_key: str | None = None,
                  session_token: str | None = None):
    """Public accessor for a cached boto3 session (used by image monitoring)."""
    return _session(mode, profile_name, region, access_key_id, secret_access_key, session_token)


def _status_from_metric(value: float, warn: float, crit: float) -> str:
    if value >= crit:
        return "critical"
    if value >= warn:
        return "warning"
    return "healthy"


def _cpu_average(session, dimension_name: str, dimension_value: str, namespace: str, metric: str) -> float | None:
    from datetime import datetime, timedelta

    cw = session.client("cloudwatch")
    end = datetime.utcnow()
    start = end - timedelta(hours=1)
    resp = cw.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric,
        Dimensions=[{"Name": dimension_name, "Value": dimension_value}],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
    return round(points[-1]["Average"], 1) if points else None


def collect_ec2(session, identifier: str) -> dict[str, Any]:
    ec2 = session.client("ec2")
    resp = ec2.describe_instances(InstanceIds=[identifier])
    reservations = resp.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        return {"status": "unknown", "summary": "instance not found", "metrics": {}, "details": {}}
    inst = reservations[0]["Instances"][0]
    state = inst["State"]["Name"]
    cpu = _cpu_average(session, "InstanceId", identifier, "AWS/EC2", "CPUUtilization")
    metrics: dict[str, Any] = {}
    if cpu is not None:
        metrics["cpu_percent"] = cpu
    status = "warning" if state != "running" else (
        _status_from_metric(cpu, 75, 90) if cpu is not None else "healthy"
    )
    return {
        "status": status,
        "summary": f"{state}" + (f" · cpu {cpu}%" if cpu is not None else ""),
        "metrics": metrics,
        "details": {
            "instance_id": identifier,
            "state": state,
            "instance_type": inst.get("InstanceType"),
            "availability_zone": inst.get("Placement", {}).get("AvailabilityZone"),
            "private_ip": inst.get("PrivateIpAddress"),
            "public_ip": inst.get("PublicIpAddress"),
        },
    }


def collect_ecs(session, identifier: str) -> dict[str, Any]:
    # identifier format: "cluster/service"
    ecs = session.client("ecs")
    if "/" in identifier:
        cluster, service = identifier.split("/", 1)
    else:
        cluster, service = "default", identifier
    resp = ecs.describe_services(cluster=cluster, services=[service])
    services = resp.get("services", [])
    if not services:
        return {"status": "unknown", "summary": "service not found", "metrics": {}, "details": {}}
    svc = services[0]
    desired = svc.get("desiredCount", 0)
    running = svc.get("runningCount", 0)
    pending = svc.get("pendingCount", 0)
    status = "healthy" if running == desired and desired > 0 else (
        "critical" if running == 0 else "warning"
    )
    return {
        "status": status,
        "summary": f"{running}/{desired} tasks running",
        "metrics": {"desired_count": desired, "running_count": running, "pending_count": pending},
        "details": {
            "cluster": cluster,
            "service": service,
            "launch_type": svc.get("launchType"),
            "task_definition": svc.get("taskDefinition", "").split("/")[-1],
        },
    }


def collect_ecr(session, identifier: str) -> dict[str, Any]:
    ecr = session.client("ecr")
    resp = ecr.describe_images(repositoryName=identifier)
    images = resp.get("imageDetails", [])
    total = len(images)
    return {
        "status": "healthy" if total else "warning",
        "summary": f"{total} images",
        "metrics": {"image_count": total},
        "details": {"repository": identifier},
    }


def collect_eks(session, identifier: str) -> dict[str, Any]:
    eks = session.client("eks")
    resp = eks.describe_cluster(name=identifier)
    cluster = resp.get("cluster", {})
    state = cluster.get("status", "UNKNOWN")
    status = "healthy" if state == "ACTIVE" else ("warning" if state == "UPDATING" else "critical")
    return {
        "status": status,
        "summary": f"cluster {state}",
        "metrics": {},
        "details": {
            "cluster": identifier,
            "version": cluster.get("version"),
            "status": state,
            "endpoint": cluster.get("endpoint"),
        },
    }


def collect_s3(session, identifier: str) -> dict[str, Any]:
    s3 = session.client("s3")
    public = False
    encrypted = True
    try:
        pab = s3.get_public_access_block(Bucket=identifier)
        cfg = pab.get("PublicAccessBlockConfiguration", {})
        public = not all(cfg.values()) if cfg else True
    except Exception:
        public = True
    try:
        s3.get_bucket_encryption(Bucket=identifier)
    except Exception:
        encrypted = False
    status = "critical" if public else ("warning" if not encrypted else "healthy")
    return {
        "status": status,
        "summary": f"{'public' if public else 'private'}",
        "metrics": {},
        "details": {"bucket": identifier, "public_access": public, "encrypted": encrypted},
    }


def collect_cloudwatch(session, identifier: str) -> dict[str, Any]:
    cw = session.client("cloudwatch")
    resp = cw.describe_alarms(AlarmNames=[identifier])
    alarms = resp.get("MetricAlarms", [])
    if not alarms:
        return {"status": "unknown", "summary": "alarm not found", "metrics": {}, "details": {}}
    alarm = alarms[0]
    state = alarm.get("StateValue", "INSUFFICIENT_DATA")
    status = {"OK": "healthy", "ALARM": "critical", "INSUFFICIENT_DATA": "unknown"}.get(state, "unknown")
    return {
        "status": status,
        "summary": f"alarm state: {state}",
        "metrics": {},
        "details": {
            "alarm_name": identifier,
            "state": state,
            "metric": alarm.get("MetricName"),
            "threshold": alarm.get("Threshold"),
        },
    }


def _split_image_ref(image: str) -> tuple[str | None, str | None]:
    """Split an image reference into (tag, digest). Handles both
    ``repo:tag`` and ``repo@sha256:...`` and ``repo:tag@sha256:...`` forms."""
    tag: str | None = None
    digest: str | None = None
    ref = image
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    # Only treat the last colon segment as a tag if it is not part of host:port.
    if ":" in ref:
        candidate = ref.rsplit(":", 1)[1]
        if "/" not in candidate:
            tag = candidate
    return tag, digest


def get_ecs_deployed_image(session, cluster: str, service: str) -> dict[str, Any]:
    """Resolve the container image a production ECS service is currently running
    by reading its active task definition's first container."""
    ecs = session.client("ecs")
    resp = ecs.describe_services(cluster=cluster, services=[service])
    services = resp.get("services", [])
    if not services:
        return {"found": False, "error": "service not found"}
    svc = services[0]
    task_def_arn = svc.get("taskDefinition")
    if not task_def_arn:
        return {"found": False, "error": "no task definition on service"}
    td = ecs.describe_task_definition(taskDefinition=task_def_arn).get("taskDefinition", {})
    containers = td.get("containerDefinitions", [])
    image = containers[0].get("image") if containers else None
    tag, digest = _split_image_ref(image) if image else (None, None)
    return {
        "found": True,
        "cluster": cluster,
        "service": service,
        "task_definition": task_def_arn.split("/")[-1],
        "image": image,
        "image_tag": tag,
        "image_digest": digest,
        "desired_count": svc.get("desiredCount"),
        "running_count": svc.get("runningCount"),
    }


def _lifecycle_retained_count(ecr, repository: str) -> int | None:
    """Return the largest ``countNumber`` from any ``imageCountMoreThan`` rule in
    the repository's lifecycle policy, i.e. how many images ECR retains."""
    import json as _json

    try:
        resp = ecr.get_lifecycle_policy(repositoryName=repository)
    except Exception:  # noqa: BLE001 - no policy configured
        return None
    try:
        policy = _json.loads(resp.get("lifecyclePolicyText", "{}"))
    except Exception:  # noqa: BLE001
        return None
    counts: list[int] = []
    for rule in policy.get("rules", []):
        sel = rule.get("selection", {})
        if sel.get("countType") == "imageCountMoreThan":
            try:
                counts.append(int(sel.get("countNumber")))
            except (TypeError, ValueError):
                continue
    return max(counts) if counts else None


def get_ecr_inventory(session, repository: str, tag_prefix: str | None = None) -> dict[str, Any]:
    """Return the repository's images (newest first) filtered by an optional tag
    prefix, plus the retained-image count implied by the lifecycle policy."""
    ecr = session.client("ecr")
    paginator = ecr.get_paginator("describe_images")
    images: list[dict[str, Any]] = []
    for page in paginator.paginate(repositoryName=repository):
        images.extend(page.get("imageDetails", []))

    def _matches(img: dict[str, Any]) -> bool:
        if not tag_prefix:
            return True
        return any(str(t).startswith(tag_prefix) for t in img.get("imageTags", []))

    filtered = [i for i in images if _matches(i)]
    # Newest first; images missing a push time sort oldest to avoid mixed-type
    # comparisons between datetimes and a numeric sentinel.
    from datetime import datetime, timezone

    def _pushed(img: dict[str, Any]):
        ts = img.get("imagePushedAt")
        return ts if hasattr(ts, "timestamp") else datetime.min.replace(tzinfo=timezone.utc)

    filtered.sort(key=_pushed, reverse=True)
    retained = _lifecycle_retained_count(ecr, repository)
    return {
        "repository": repository,
        "images": filtered,
        "total_images": len(filtered),
        "retained": retained,
    }


LIVE_DISPATCH = {
    "ec2": collect_ec2,
    "ecs": collect_ecs,
    "ecr": collect_ecr,
    "eks": collect_eks,
    "s3": collect_s3,
    "cloudwatch": collect_cloudwatch,
}


def collect_live(mode: str, profile_name: str | None, region: str, resource_type: str, identifier: str,
                 access_key_id: str | None = None, secret_access_key: str | None = None,
                 session_token: str | None = None) -> dict[str, Any]:
    fn = LIVE_DISPATCH.get(resource_type)
    if fn is None:
        return {"status": "unknown", "summary": "unsupported resource type", "metrics": {}, "details": {}}
    session = _session(mode, profile_name, region, access_key_id, secret_access_key, session_token)
    return fn(session, identifier)
