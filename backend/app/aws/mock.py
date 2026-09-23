"""Deterministic synthetic data used when an account runs in `mock` mode.

Values are seeded from the resource identifier so a given resource always looks
consistent between refreshes, while different resources look different.
"""
from __future__ import annotations

import hashlib
from typing import Any


def _seed(identifier: str) -> int:
    return int(hashlib.sha256(identifier.encode()).hexdigest(), 16)


def _pick(identifier: str, options: list[Any], salt: str = "") -> Any:
    return options[_seed(identifier + salt) % len(options)]


def _num(identifier: str, low: int, high: int, salt: str = "") -> int:
    span = high - low + 1
    return low + (_seed(identifier + salt) % span)


def _status_from_metric(value: float, warn: float, crit: float) -> str:
    if value >= crit:
        return "critical"
    if value >= warn:
        return "warning"
    return "healthy"


def mock_ec2(identifier: str) -> dict[str, Any]:
    cpu = _num(identifier, 3, 97, "cpu")
    disk = _num(identifier, 20, 96, "disk")
    mem = _num(identifier, 25, 95, "mem")
    state = _pick(identifier, ["running", "running", "running", "stopped"], "state")
    status = "unknown"
    if state == "running":
        status = _status_from_metric(max(cpu, disk, mem), 75, 90)
    summary = f"{state} · cpu {cpu}% · disk {disk}% · mem {mem}%"
    return {
        "status": status if state == "running" else "warning",
        "summary": summary,
        "metrics": {"cpu_percent": cpu, "disk_percent": disk, "memory_percent": mem},
        "details": {
            "instance_id": identifier,
            "state": state,
            "instance_type": _pick(
                identifier, ["t3.medium", "m5.large", "c5.xlarge", "t3.small"], "type"
            ),
            "availability_zone": _pick(
                identifier, ["us-east-1a", "us-east-1b", "us-east-1c"], "az"
            ),
            "private_ip": f"10.0.{_num(identifier,0,255,'ip1')}.{_num(identifier,1,254,'ip2')}",
            "launch_days_ago": _num(identifier, 5, 720, "age"),
        },
    }


def mock_ecs(identifier: str) -> dict[str, Any]:
    desired = _num(identifier, 2, 8, "desired")
    running = max(0, desired - _pick(identifier, [0, 0, 0, 1, 2], "gap"))
    status = "healthy" if running == desired else ("critical" if running == 0 else "warning")
    return {
        "status": status,
        "summary": f"{running}/{desired} tasks running",
        "metrics": {
            "desired_count": desired,
            "running_count": running,
            "pending_count": max(0, desired - running),
        },
        "details": {
            "service": identifier,
            "launch_type": _pick(identifier, ["FARGATE", "EC2"], "lt"),
            "deployment_status": _pick(
                identifier, ["PRIMARY", "PRIMARY", "IN_PROGRESS"], "dep"
            ),
            "task_definition": f"{identifier}:{_num(identifier, 3, 88, 'td')}",
        },
    }


def mock_ecr(identifier: str) -> dict[str, Any]:
    image_count = _num(identifier, 4, 120, "imgs")
    days_since_push = _num(identifier, 0, 200, "push")
    near_expiry = _num(identifier, 0, 10, "exp")
    status = "healthy"
    if near_expiry >= 6:
        status = "critical"
    elif days_since_push > 120 or near_expiry >= 3:
        status = "warning"
    return {
        "status": status,
        "summary": f"{image_count} images · {near_expiry} near lifecycle expiry",
        "metrics": {
            "image_count": image_count,
            "images_near_expiry": near_expiry,
            "days_since_last_push": days_since_push,
        },
        "details": {
            "repository": identifier,
            "scan_on_push": _pick(identifier, [True, False], "scan"),
            "latest_tag": _pick(
                identifier, ["latest", "v1.2.3", "main-abc123", "release-2.4"], "tag"
            ),
            "critical_vulnerabilities": _num(identifier, 0, 7, "vuln"),
        },
    }


def mock_eks(identifier: str) -> dict[str, Any]:
    nodes = _num(identifier, 2, 12, "nodes")
    unhealthy = _pick(identifier, [0, 0, 0, 1, 2], "unh")
    status = "healthy" if unhealthy == 0 else ("critical" if unhealthy >= 2 else "warning")
    return {
        "status": status,
        "summary": f"{nodes} nodes · {unhealthy} not-ready",
        "metrics": {
            "node_count": nodes,
            "unhealthy_nodes": unhealthy,
            "pending_pods": _num(identifier, 0, 5, "pend"),
        },
        "details": {
            "cluster": identifier,
            "version": _pick(identifier, ["1.28", "1.29", "1.30"], "ver"),
            "status": _pick(identifier, ["ACTIVE", "ACTIVE", "UPDATING"], "cs"),
            "crashloop_pods": _num(identifier, 0, 4, "cl"),
        },
    }


def mock_s3(identifier: str) -> dict[str, Any]:
    size_gb = _num(identifier, 1, 4000, "size")
    public = _pick(identifier, [False, False, False, True], "pub")
    encrypted = _pick(identifier, [True, True, True, False], "enc")
    status = "healthy"
    if public:
        status = "critical"
    elif not encrypted:
        status = "warning"
    return {
        "status": status,
        "summary": f"{size_gb} GB · {'public' if public else 'private'}",
        "metrics": {"size_gb": size_gb, "object_count": _num(identifier, 10, 500000, "obj")},
        "details": {
            "bucket": identifier,
            "public_access": public,
            "encrypted": encrypted,
            "versioning": _pick(identifier, ["Enabled", "Suspended", "Disabled"], "ver"),
        },
    }


def mock_cloudwatch(identifier: str) -> dict[str, Any]:
    state = _pick(identifier, ["OK", "OK", "OK", "ALARM", "INSUFFICIENT_DATA"], "st")
    status = {"OK": "healthy", "ALARM": "critical", "INSUFFICIENT_DATA": "unknown"}[state]
    return {
        "status": status,
        "summary": f"alarm state: {state}",
        "metrics": {"breaches_24h": _num(identifier, 0, 12, "br")},
        "details": {
            "alarm_name": identifier,
            "state": state,
            "metric": _pick(
                identifier, ["CPUUtilization", "MemoryUtilization", "5XXError", "Latency"], "m"
            ),
            "threshold": _num(identifier, 50, 95, "th"),
        },
    }


MOCK_DISPATCH = {
    "ec2": mock_ec2,
    "ecs": mock_ecs,
    "ecr": mock_ecr,
    "eks": mock_eks,
    "s3": mock_s3,
    "cloudwatch": mock_cloudwatch,
}


def get_mock(resource_type: str, identifier: str) -> dict[str, Any]:
    fn = MOCK_DISPATCH.get(resource_type)
    if fn is None:
        return {
            "status": "unknown",
            "summary": "unsupported resource type",
            "metrics": {},
            "details": {},
        }
    return fn(identifier)
