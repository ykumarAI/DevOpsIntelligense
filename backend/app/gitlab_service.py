"""Pull a normalized devops-report.json artifact from a self-managed GitLab
project and map it into ResourceStatus objects.

Uses the GitLab v4 "raw artifact" endpoint so a single JSON file can be fetched
without downloading/unzipping the whole artifact archive:

    GET {base}/api/v4/projects/{id}/jobs/artifacts/{ref}/raw/{path}?job={job}

Auth is a Personal Access Token (read_api) sent via the PRIVATE-TOKEN header.
The dashboard only *reads*; all AWS access happens inside the GitLab pipeline.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from .models import GitLabSource
from .schemas import ResourceStatus

_VALID_STATUS = {"healthy", "warning", "critical", "unknown"}


def _artifact_url(source: GitLabSource) -> str:
    base = source.base_url.rstrip("/")
    project = urllib.parse.quote(str(source.project), safe="")
    ref = urllib.parse.quote(source.ref, safe="")
    path = source.artifact_path.lstrip("/")
    job = urllib.parse.quote(source.job_name, safe="")
    return (
        f"{base}/api/v4/projects/{project}/jobs/artifacts/{ref}/raw/{path}?job={job}"
    )


def fetch_report(source: GitLabSource, timeout: int = 20) -> dict[str, Any]:
    """Fetch and parse the report JSON. Raises on network/HTTP/parse errors."""
    req = urllib.request.Request(_artifact_url(source), method="GET")
    if source.token:
        req.add_header("PRIVATE-TOKEN", source.token)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-configured host
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _normalize_status(value: Any) -> str:
    v = str(value or "").lower()
    return v if v in _VALID_STATUS else "unknown"


def collect_gitlab(source: GitLabSource) -> list[ResourceStatus]:
    """Return one ResourceStatus per resource in the artifact. Never raises:
    on failure returns a single 'unknown' status carrying the error."""
    now = datetime.utcnow()
    # Synthetic negative ids keep GitLab-sourced rows distinct from DB rows.
    base_id = -(source.id * 1000)

    if not source.enabled:
        return []

    try:
        report = fetch_report(source)
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}: {exc.reason}"
        return [_error_status(source, base_id, now, detail)]
    except Exception as exc:  # noqa: BLE001 - surface any failure as a tile
        return [_error_status(source, base_id, now, f"{type(exc).__name__}: {exc}")]

    env = report.get("environment") or source.environment
    resources = report.get("resources") or []
    out: list[ResourceStatus] = []
    for i, r in enumerate(resources):
        out.append(
            ResourceStatus(
                resource_id=base_id - i - 1,
                account_id=base_id,
                account_name=source.name,
                resource_type=str(r.get("type", "unknown")),
                identifier=str(r.get("identifier", "")),
                display_name=r.get("display_name"),
                region=r.get("region") or env,
                status=_normalize_status(r.get("status")),
                summary=str(r.get("summary", "")),
                metrics=r.get("metrics") or {},
                details=r.get("details") or {},
                source="gitlab",
                collected_at=now,
            )
        )
    return out


def _error_status(source: GitLabSource, base_id: int, now: datetime, detail: str) -> ResourceStatus:
    return ResourceStatus(
        resource_id=base_id,
        account_id=base_id,
        account_name=source.name,
        resource_type="gitlab",
        identifier=f"{source.project}@{source.ref}",
        display_name=source.name,
        region=source.environment,
        status="unknown",
        summary="could not fetch GitLab report",
        source="gitlab",
        error=detail,
        collected_at=now,
    )
