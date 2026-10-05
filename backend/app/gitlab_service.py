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


def _api_get(source: GitLabSource, path: str, params: dict[str, Any] | None = None,
             timeout: int = 20) -> Any:
    """Call a GitLab v4 API endpoint (``path`` is relative to the project) and
    return the parsed JSON. Raises on network/HTTP/parse errors."""
    base = source.base_url.rstrip("/")
    project = urllib.parse.quote(str(source.project), safe="")
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{base}/api/v4/projects/{project}/{path.lstrip('/')}{query}"
    req = urllib.request.Request(url, method="GET")
    if source.token:
        req.add_header("PRIVATE-TOKEN", source.token)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-configured host
        return json.loads(resp.read().decode("utf-8"))


def _sha_from_tag(image_tag: str | None) -> str | None:
    """Extract a git-sha-looking token (7-40 hex chars) from an image tag."""
    import re

    if not image_tag:
        return None
    for part in re.split(r"[^0-9a-fA-F]+", image_tag):
        if 7 <= len(part) <= 40:
            return part
    return None


def find_pipeline_for_image(source: GitLabSource, image_tag: str | None,
                            commit_sha: str | None = None) -> dict[str, Any]:
    """Best-effort correlation of a deployed image back to the successful GitLab
    pipeline that built it. Matches on an explicit commit SHA when available,
    otherwise on a SHA-looking token embedded in the image tag, and finally
    falls back to the latest successful pipeline on the configured ref.

    Never raises: returns ``{"found": False, "error": ...}`` on failure."""
    base = source.base_url.rstrip("/")
    try:
        sha = commit_sha or _sha_from_tag(image_tag)
        pipelines: list[dict[str, Any]] = []
        if sha:
            pipelines = _api_get(source, "pipelines", {"sha": sha, "per_page": 1})
        if not pipelines:
            pipelines = _api_get(
                source,
                "pipelines",
                {"ref": source.ref, "status": "success", "per_page": 1},
            )
        if not pipelines:
            return {"found": False, "error": "no matching pipeline"}
        p = pipelines[0]
        pid = p.get("id")
        detail = _api_get(source, f"pipelines/{pid}") if pid else {}
        full_sha = detail.get("sha") or p.get("sha")
        return {
            "found": True,
            "pipeline_id": pid,
            "pipeline_url": p.get("web_url"),
            "pipeline_status": p.get("status"),
            "created_at": p.get("created_at"),
            "image_tag": image_tag,
            "commit_id": full_sha,
            "commit_url": f"{base}/-/commit/{full_sha}" if full_sha else None,
            "ref": p.get("ref"),
        }
    except Exception as exc:  # noqa: BLE001 - correlation is best-effort
        return {"found": False, "error": f"{type(exc).__name__}: {exc}"}


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
