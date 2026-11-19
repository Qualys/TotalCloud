"""Generate the demo fixture set in the EXACT live CloudView response shapes.

Run:  python _generate.py    (writes the *.json files next to this script)

These fixtures mirror the real responses captured from pod a live Qualys pod (account 100000000002):
Spring-paged envelopes, posture evals with passed/failedResources, and resources with NO arn but
with `resourceType`/`resourceId`/`region` (region null for IAM_PASSWORD) and an `evaluationDates`
block (firstEvaluated/lastEvaluated/dateFixed/dateReopen/prevResult) driving NEW/FIXED/REOPENED.

seed.py consumes these through the SAME qualys.parse_* helpers used on the live path, so the demo
exercises the real parsing/pagination logic.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 7, 24, 10, 0, 0, tzinfo=timezone.utc)


def iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def spring(content, page_size, page=0):
    return {
        "content": content,
        "pageable": {"pageNumber": page, "pageSize": page_size, "offset": page * page_size,
                     "paged": True, "unpaged": False},
        "totalPages": 1, "totalElements": len(content), "last": True, "first": True,
        "number": page, "size": page_size, "numberOfElements": len(content), "empty": not content,
    }


# ── connectors (accounts) ────────────────────────────────────────────────────
AWS_ACCOUNTS = ["100000000002", "100000000003", "100000000001"]
AZURE_SUBS = ["a1b2c3d4-5e6f-7788-99aa-bbccddeeff00"]
GCP_PROJECTS = ["demo-gcp-project-8821"]


def connector(csp, acct, i):
    field = {"AWS": "awsAccountId", "AZURE": "subscriptionId", "GCP": "projectId"}[csp]
    return {"connectorId": f"conn-{csp.lower()}-{i}", "name": f"{csp.lower()}-connector-{i}",
            field: acct, "state": "SUCCESS", "provider": csp}


def write_connectors():
    (HERE / "connectors_aws.json").write_text(json.dumps(
        spring([connector("AWS", a, i) for i, a in enumerate(AWS_ACCOUNTS)], 50), indent=2))
    (HERE / "connectors_azure.json").write_text(json.dumps(
        spring([connector("AZURE", a, i) for i, a in enumerate(AZURE_SUBS)], 50), indent=2))
    (HERE / "connectors_gcp.json").write_text(json.dumps(
        spring([connector("GCP", a, i) for i, a in enumerate(GCP_PROJECTS)], 50), indent=2))


# ── controls catalog + posture + resources ───────────────────────────────────
# (cid, name, criticality, service, resourceType, base_total, base_failed)
AWS_CONTROLS = [
    ("1", "Ensure IAM users have MFA enabled", "HIGH", "IAM", "IAM_USER", 24, 5),
    ("2", "Ensure IAM password policy requires minimum length of 14", "MEDIUM", "IAM", "IAM_PASSWORD", 1, 1),
    ("3", "Ensure S3 buckets are not publicly readable", "CRITICAL", "S3", "S3_BUCKET", 18, 4),
    ("4", "Ensure security groups do not allow 0.0.0.0/0 to port 22", "HIGH", "EC2", "SECURITY_GROUP", 40, 9),
    ("5", "Ensure EBS volumes are encrypted", "MEDIUM", "EC2", "EBS_VOLUME", 55, 12),
    ("6", "Ensure CloudTrail is enabled in all regions", "HIGH", "CLOUDTRAIL", "CLOUDTRAIL", 3, 1),
    ("7", "Ensure RDS instances are encrypted at rest", "MEDIUM", "RDS", "RDS_INSTANCE", 12, 3),
]
AZURE_CONTROLS = [
    ("101", "Ensure storage accounts disallow public blob access", "HIGH", "Storage", "STORAGE_ACCOUNT", 20, 6),
    ("102", "Ensure NSGs restrict RDP from the internet", "HIGH", "Network", "NSG", 26, 7),
    ("103", "Ensure SQL servers have auditing enabled", "MEDIUM", "SQL", "SQL_SERVER", 8, 2),
]
GCP_CONTROLS = [
    ("201", "Ensure Cloud Storage buckets are not public", "CRITICAL", "Storage", "GCS_BUCKET", 14, 3),
    ("202", "Ensure default network is deleted", "MEDIUM", "VPC", "NETWORK", 4, 2),
]

_RESOURCE_NAMES = {
    "IAM_USER": ["aman_temp_sme", "svc-backup", "jenkins-ci", "dev-readonly", "ops-admin"],
    "IAM_PASSWORD": ["{account}"],
    "S3_BUCKET": ["prod-logs-archive", "customer-uploads-public", "tf-state-backend", "cf-assets"],
    "SECURITY_GROUP": ["sg-0a1b2c3d4e", "sg-1122334455", "sg-9988776655", "sg-abc0123def"],
    "EBS_VOLUME": ["vol-0f1e2d3c4b", "vol-5a6b7c8d9e", "vol-aa11bb22cc"],
    "CLOUDTRAIL": ["management-events"],
    "RDS_INSTANCE": ["orders-prod", "analytics-replica"],
    "STORAGE_ACCOUNT": ["stprodlogs01", "stpublicassets", "sttfstate"],
    "NSG": ["nsg-web-tier", "nsg-db-tier"],
    "SQL_SERVER": ["sql-orders-prod"],
    "GCS_BUCKET": ["gcs-public-reports", "gcs-tf-state"],
    "NETWORK": ["default", "legacy-vpc"],
}
_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "eastus", "us-central1"]


# Remediation prose is hand-written, NOT generated — carry it over from the existing fixture so a
# regeneration can never wipe it (it is what the demo's Remediation column shows).
_REMEDIATION_KEYS = ("manualRemediation", "cliRemediation", "buildTimeRemediation",
                     "rationale", "specification", "references")


def _existing_remediation(csp):
    """{cid: {remediation fields}} from the controls fixture already on disk, if any."""
    path = HERE / f"controls_{csp.lower()}.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text()).get("control") or []
    except (ValueError, OSError):
        return {}
    return {str(r.get("cid")): {k: r[k] for k in _REMEDIATION_KEYS if r.get(k)} for r in rows}


def controls_response(controls, csp="AWS"):
    keep = _existing_remediation(csp)
    return {"control": [{"cid": c[0], "controlName": c[1], "criticality": c[2],
                          "serviceType": c[3], "resourceType": c[4], "provider": "AWS",
                          "controlType": "System Defined", **keep.get(str(c[0]), {})}
                        for c in controls],
            "count": len(controls)}


def posture_evals(controls):
    out = []
    for cid, name, crit, service, _rtype, total, failed in controls:
        out.append({"controlId": cid, "controlName": name, "policyNames": ["CIS Benchmark"],
                    "criticality": crit, "service": service, "result": "FAIL" if failed else "PASS",
                    "passedResources": total - failed, "failedResources": failed,
                    "passWithExceptionResources": 0})
    return out


# Provider tags, mirroring what Qualys actually returns: some resource types are never collected
# (empty list), and among collected types only some resources are tagged.
_UNTAGGED_TYPES = {"IAM_PASSWORD", "CLOUDTRAIL", "CLOUD_WATCH_LOGGROUP"}
_TAG_SETS = [
    [{"key": "Owner", "value": "platform-team"}, {"key": "Environment", "value": "prod"},
     {"key": "CostCenter", "value": "CC-4412"}],
    [{"key": "Owner", "value": "data-eng"}, {"key": "Environment", "value": "staging"}],
    [{"key": "aws:cloudformation:stack-name", "value": "demo-stack"},
     {"key": "Environment", "value": "dev"}],
]


_QUALYS_TAG_SETS = [
    [{"tagId": "1001", "tagName": "Business Unit:Payments"}],
    [{"tagId": "1002", "tagName": "PCI Scope"}, {"tagId": "1003", "tagName": "Crown Jewel"}],
    [],
]


def _qualys_tags(k):
    """Qualys's own asset tags — a DIFFERENT source from cloud tags, so a different distribution."""
    return _QUALYS_TAG_SETS[k % len(_QUALYS_TAG_SETS)]


def _cloud_tags(rtype, k):
    """Deterministic synthetic tags: untagged types get [], others get tags on ~2 of every 3."""
    if rtype in _UNTAGGED_TYPES or k % 3 == 2:
        return []
    return _TAG_SETS[k % len(_TAG_SETS)]


def resources_for(cid, controls, account, csp):
    ctrl = next(c for c in controls if c[0] == cid)
    _, _name, crit, _service, rtype, _total, failed = ctrl
    names = _RESOURCE_NAMES.get(rtype, [f"{rtype.lower()}-{i}" for i in range(failed)])
    region_pool = ["eastus"] if csp == "AZURE" else ["us-central1"] if csp == "GCP" else _REGIONS
    out = []
    for k in range(failed):
        nm = names[k % len(names)].replace("{account}", account)
        if k > 0 and "{account}" not in _RESOURCE_NAMES.get(rtype, [""])[0]:
            nm = f"{nm}-{k}" if len(names) <= k else nm
        region = None if rtype == "IAM_PASSWORD" else region_pool[k % len(region_pool)]
        # lifecycle mix: k==0 NEW (5d ago), one REOPENED, rest older
        first_ago = 5 if k == 0 else 45 + k
        reopened = (k == 1)
        out.append({
            "resourceId": nm, "region": region, "accountId": account,
            "evaluatedOn": iso(0), "resourceType": rtype, "cloudTags": _cloud_tags(rtype, k), "qualysTags": _qualys_tags(k),
            "connectorId": f"conn-{csp.lower()}-0", "result": "FAIL",
            "evidences": [
                {"settingName": "Control", "actualValue": _name},
                {"settingName": "Current Value", "actualValue": "non-compliant"},
                {"settingName": "Expected", "actualValue": "compliant"},
            ],
            "evaluationDates": {
                "firstEvaluated": iso(first_ago), "lastEvaluated": iso(0),
                "dateReopen": iso(3) if reopened else None, "dateFixed": None,
                "prevResult": "PASS" if k == 0 else "FAIL",
                "sinceLastCurrentState": iso(first_ago),
            },
        })
    # add ONE recently-fixed resource (result PASS + dateFixed within 30d) to exercise fixed_30d
    if failed and rtype not in ("IAM_PASSWORD",):
        fixed_name = f"{names[0].replace('{account}', account)}-remediated"
        out.append({
            "resourceId": fixed_name, "region": region_pool[0], "accountId": account,
            "evaluatedOn": iso(0), "resourceType": rtype, "cloudTags": _cloud_tags(rtype, 0), "qualysTags": _qualys_tags(1),
            "connectorId": f"conn-{csp.lower()}-0", "result": "PASS",
            "evidences": [{"settingName": "Control", "actualValue": _name},
                          {"settingName": "Status", "actualValue": "compliant"}],
            "evaluationDates": {"firstEvaluated": iso(60), "lastEvaluated": iso(0),
                                "dateReopen": None, "dateFixed": iso(4),
                                "prevResult": "FAIL", "sinceLastCurrentState": iso(4)},
        })
    return out


def write_all():
    write_connectors()
    catalogs = {"AWS": AWS_CONTROLS, "AZURE": AZURE_CONTROLS, "GCP": GCP_CONTROLS}
    accounts = {"AWS": AWS_ACCOUNTS, "AZURE": AZURE_SUBS, "GCP": GCP_PROJECTS}
    for csp, controls in catalogs.items():
        (HERE / f"controls_{csp.lower()}.json").write_text(
            json.dumps(controls_response(controls, csp), indent=2))
        for acct in accounts[csp]:
            (HERE / f"posture_{acct}.json").write_text(json.dumps(spring(posture_evals(controls), 300), indent=2))
            for c in controls:
                if c[6] > 0:
                    res = resources_for(c[0], controls, acct, csp)
                    (HERE / f"resources_{acct}_{c[0]}.json").write_text(json.dumps(spring(res, 50), indent=2))
    # a manifest so seed.py knows what's here
    manifest = {"accounts": [{"id": a, "csp": csp} for csp, accts in accounts.items() for a in accts],
                "csps": {csp: [c[0] for c in cs] for csp, cs in catalogs.items()},
                "captured_from": "a live Qualys pod (response shapes only)",
                "note": "Synthetic values, REAL response shapes. No arn field; evaluationDates present."}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("wrote fixtures to", HERE)


if __name__ == "__main__":
    write_all()
