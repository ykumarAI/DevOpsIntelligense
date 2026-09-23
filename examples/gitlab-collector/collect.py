#!/usr/bin/env python3
"""Read-only AWS collector that emits the normalized devops-report.json the
DevOps Intelligence dashboard understands.

Runs inside a GitLab CI job using the pipeline's OIDC/assume-role credentials —
so it works for UAT/Prod without any personal AWS access. All calls are
Describe*/List*/Get* only; nothing is modified.

Output schema (devops-report.json):
{
  "environment": "UAT",
  "generated_at": "2026-09-23T10:32:00Z",
  "resources": [
    {"type": "ec2", "identifier": "i-0abc", "display_name": "...",
     "status": "healthy|warning|critical|unknown", "summary": "...",
     "metrics": {...}, "details": {...}}
  ]
}

Configure via env vars:
  COLLECT_ENVIRONMENT   label for the environment (e.g. UAT)
  AWS_DEFAULT_REGION    region to inspect
  AWS_ROLE_ARN          read-only role to assume via GitLab OIDC (optional)
  GITLAB_OIDC_TOKEN     OIDC token injected by the CI job (optional)
  COLLECT_OUTPUT        output filename (default devops-report.json)
  COLLECT_MAX           max items per service to include (default 25)
"""
from __future__ import annotations

import datetime as dt
import json
import os

import boto3

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
ENVIRONMENT = os.getenv("COLLECT_ENVIRONMENT") or os.getenv("CI_ENVIRONMENT_NAME") or "unknown"
MAX = int(os.getenv("COLLECT_MAX", "25"))
OUTPUT = os.getenv("COLLECT_OUTPUT", "devops-report.json")


def build_session() -> "boto3.Session":
    """Assume the environment's read-only role via GitLab OIDC when configured,
    otherwise fall back to the job's default credentials/region."""
    role_arn = os.getenv("AWS_ROLE_ARN")
    token = os.getenv("GITLAB_OIDC_TOKEN")
    if role_arn and token:
        sts = boto3.client("sts", region_name=REGION)
        creds = sts.assume_role_with_web_identity(
            RoleArn=role_arn,
            RoleSessionName=f"gitlab-devops-collect-{os.getenv('CI_JOB_ID', 'local')}",
            WebIdentityToken=token,
            DurationSeconds=3600,
        )["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=REGION,
        )
    return boto3.Session(region_name=REGION)


session = build_session()


def _worst(*statuses: str) -> str:
    order = {"critical": 0, "warning": 1, "unknown": 2, "healthy": 3}
    return min(statuses, key=lambda s: order.get(s, 2))


def collect_ec2() -> list[dict]:
    out: list[dict] = []
    ec2 = session.client("ec2")
    try:
        reservations = ec2.describe_instances().get("Reservations", [])
    except Exception as exc:  # noqa: BLE001
        return [_err("ec2", "describe_instances", exc)]
    for res in reservations:
        for inst in res.get("Instances", []):
            if len(out) >= MAX:
                return out
            state = inst["State"]["Name"]
            name = next(
                (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                inst["InstanceId"],
            )
            status = "healthy" if state == "running" else "warning"
            out.append({
                "type": "ec2",
                "identifier": inst["InstanceId"],
                "display_name": name,
                "status": status,
                "summary": f"{state} · {inst.get('InstanceType', '')}",
                "metrics": {},
                "details": {
                    "state": state,
                    "instance_type": inst.get("InstanceType"),
                    "availability_zone": inst.get("Placement", {}).get("AvailabilityZone"),
                    "private_ip": inst.get("PrivateIpAddress"),
                },
            })
    return out


def collect_ecs() -> list[dict]:
    out: list[dict] = []
    ecs = session.client("ecs")
    try:
        clusters = ecs.list_clusters().get("clusterArns", [])
    except Exception as exc:  # noqa: BLE001
        return [_err("ecs", "list_clusters", exc)]
    for cluster in clusters:
        svc_arns = ecs.list_services(cluster=cluster).get("serviceArns", [])
        for i in range(0, len(svc_arns), 10):
            chunk = svc_arns[i : i + 10]
            if not chunk:
                continue
            for svc in ecs.describe_services(cluster=cluster, services=chunk).get("services", []):
                if len(out) >= MAX:
                    return out
                desired = svc.get("desiredCount", 0)
                running = svc.get("runningCount", 0)
                status = "healthy" if running == desired and desired > 0 else (
                    "critical" if running == 0 else "warning"
                )
                out.append({
                    "type": "ecs",
                    "identifier": f"{cluster.split('/')[-1]}/{svc['serviceName']}",
                    "display_name": svc["serviceName"],
                    "status": status,
                    "summary": f"{running}/{desired} tasks running",
                    "metrics": {"desired_count": desired, "running_count": running,
                                "pending_count": svc.get("pendingCount", 0)},
                    "details": {"launch_type": svc.get("launchType"),
                                "task_definition": svc.get("taskDefinition", "").split("/")[-1]},
                })
    return out


def collect_ecr() -> list[dict]:
    out: list[dict] = []
    ecr = session.client("ecr")
    try:
        repos = ecr.describe_repositories().get("repositories", [])
    except Exception as exc:  # noqa: BLE001
        return [_err("ecr", "describe_repositories", exc)]
    for repo in repos[:MAX]:
        name = repo["repositoryName"]
        try:
            images = ecr.describe_images(repositoryName=name).get("imageDetails", [])
        except Exception:  # noqa: BLE001
            images = []
        out.append({
            "type": "ecr",
            "identifier": name,
            "display_name": name,
            "status": "healthy" if images else "warning",
            "summary": f"{len(images)} images",
            "metrics": {"image_count": len(images)},
            "details": {"scan_on_push": repo.get("imageScanningConfiguration", {}).get("scanOnPush")},
        })
    return out


def collect_eks() -> list[dict]:
    out: list[dict] = []
    eks = session.client("eks")
    try:
        names = eks.list_clusters().get("clusters", [])
    except Exception as exc:  # noqa: BLE001
        return [_err("eks", "list_clusters", exc)]
    for name in names[:MAX]:
        cl = eks.describe_cluster(name=name).get("cluster", {})
        state = cl.get("status", "UNKNOWN")
        status = "healthy" if state == "ACTIVE" else ("warning" if state == "UPDATING" else "critical")
        out.append({
            "type": "eks",
            "identifier": name,
            "display_name": name,
            "status": status,
            "summary": f"cluster {state}",
            "metrics": {},
            "details": {"version": cl.get("version"), "status": state},
        })
    return out


def collect_s3() -> list[dict]:
    out: list[dict] = []
    s3 = session.client("s3")
    try:
        buckets = s3.list_buckets().get("Buckets", [])
    except Exception as exc:  # noqa: BLE001
        return [_err("s3", "list_buckets", exc)]
    for b in buckets[:MAX]:
        name = b["Name"]
        public, encrypted = False, True
        try:
            cfg = s3.get_public_access_block(Bucket=name).get("PublicAccessBlockConfiguration", {})
            public = not all(cfg.values()) if cfg else True
        except Exception:  # noqa: BLE001
            public = True
        try:
            s3.get_bucket_encryption(Bucket=name)
        except Exception:  # noqa: BLE001
            encrypted = False
        status = "critical" if public else ("warning" if not encrypted else "healthy")
        out.append({
            "type": "s3",
            "identifier": name,
            "display_name": name,
            "status": status,
            "summary": "public" if public else "private",
            "metrics": {},
            "details": {"public_access": public, "encrypted": encrypted},
        })
    return out


def collect_cloudwatch() -> list[dict]:
    out: list[dict] = []
    cw = session.client("cloudwatch")
    try:
        alarms = cw.describe_alarms(StateValue="ALARM").get("MetricAlarms", [])
    except Exception as exc:  # noqa: BLE001
        return [_err("cloudwatch", "describe_alarms", exc)]
    for a in alarms[:MAX]:
        out.append({
            "type": "cloudwatch",
            "identifier": a["AlarmName"],
            "display_name": a["AlarmName"],
            "status": "critical",
            "summary": "alarm state: ALARM",
            "metrics": {},
            "details": {"metric": a.get("MetricName"), "threshold": a.get("Threshold")},
        })
    return out


def _err(rtype: str, op: str, exc: Exception) -> dict:
    return {
        "type": rtype,
        "identifier": f"{rtype}:{op}",
        "display_name": f"{rtype} collection failed",
        "status": "unknown",
        "summary": f"{op} error",
        "metrics": {},
        "details": {"error": f"{type(exc).__name__}: {exc}"},
    }


def main() -> None:
    resources: list[dict] = []
    for fn in (collect_ec2, collect_ecs, collect_ecr, collect_eks, collect_s3, collect_cloudwatch):
        resources.extend(fn())

    report = {
        "environment": ENVIRONMENT,
        "region": REGION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "resources": resources,
    }
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"Wrote {OUTPUT} with {len(resources)} resources for {ENVIRONMENT}")


if __name__ == "__main__":
    main()
