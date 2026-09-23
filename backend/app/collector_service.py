"""Service layer that turns a MonitoredResource into a normalized ResourceStatus.

Chooses between synthetic (mock) data and live boto3 calls based on the owning
account's mode, and never raises: any failure is captured as an `error` field.
"""
from __future__ import annotations

from datetime import datetime

from .aws import mock
from .aws.collectors import collect_live
from .models import AwsAccount, MonitoredResource
from .schemas import ResourceStatus


def collect_resource(resource: MonitoredResource, account: AwsAccount) -> ResourceStatus:
    region = resource.region or account.region
    base = ResourceStatus(
        resource_id=resource.id,
        account_id=account.id,
        account_name=account.name,
        resource_type=resource.resource_type,
        identifier=resource.identifier,
        display_name=resource.display_name,
        region=region,
        group_name=resource.group_name,
        collected_at=datetime.utcnow(),
    )

    if not resource.enabled:
        base.status = "unknown"
        base.summary = "monitoring disabled"
        base.source = "mock"
        return base

    if account.mode == "mock":
        data = mock.get_mock(resource.resource_type, resource.identifier)
        base.source = "mock"
    else:
        try:
            data = collect_live(
                account.mode,
                account.profile_name,
                region,
                resource.resource_type,
                resource.identifier,
                account.access_key_id,
                account.secret_access_key,
                account.session_token,
            )
            base.source = "aws"
        except Exception as exc:  # noqa: BLE001 - surface any AWS failure gracefully
            base.status = "unknown"
            base.summary = "collection failed"
            base.source = "aws"
            base.error = f"{type(exc).__name__}: {exc}"
            return base

    # Health is computed from the full data; display is filtered to the signals
    # the user selected (None = show everything).
    base.status = data.get("status", "unknown")
    base.summary = data.get("summary", "")
    metrics = data.get("metrics", {})
    details = data.get("details", {})
    selected = resource.collect_options
    if selected is not None:
        metrics = {k: v for k, v in metrics.items() if k in selected}
        details = {k: v for k, v in details.items() if k in selected}
    base.metrics = metrics
    base.details = details
    return base
