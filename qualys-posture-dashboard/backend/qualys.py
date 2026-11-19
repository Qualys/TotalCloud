"""Standalone Qualys CloudView (CSPM/KSPM) client.

Self-contained — NO imports from the totalcloud-demo-lab. Auth + endpoints adapted from that
project's proven `lib/cspm_report.py`, then CORRECTED against LIVE CloudView responses captured
from a live Qualys pod. Key live facts baked in here:

- Responses are **Spring-paged** ({content, totalPages, last, number, size, totalElements}) — we
  loop pages until `last == true`.
- The resources response has **NO `arn`** field. A resource's identity is
  `(accountId, resourceType, resourceId, region)`; `resourceId` is a NATIVE id/name (IAM user
  name, S3 bucket, instance id, …) and `region` may be null (e.g. IAM_PASSWORD).
- Each resource carries `evaluationDates` (firstEvaluated / lastEvaluated / dateFixed / dateReopen
  / prevResult) — Qualys's own per-finding lifecycle, which we use for NEW / FIXED / REOPENED.

Auth: POST <gateway>/auth (form username/password/token=true) → JWT; Bearer on all subsequent calls.

Endpoints (all GET unless noted):
- Mint JWT:       POST <gw>/auth
- Accounts:       <gw>/cloudview-api/rest/v1/<csp>/connectors?pageSize=50&pageNo=N  → awsAccountId/subscriptionId/projectId
- CSPM controls:  <gw>/cloudview-api/rest/v1/controls/metadata/list?filter=provider%3A<CSP>&pageNo=N&pageSize=1000
- CSPM posture:   <gw>/cloudview-api/rest/v1/<csp>/evaluations/<accountId>?pageSize=300&pageNo=N
- CSPM resources: <gw>/cloudview-api/rest/v1/<csp>/evaluations/<accountId>/resources/<controlId>?pageSize=50&pageNo=N
- KSPM posture:   <gw>/csapi/v1.3/k8s_postures/list?pageSize=300&pageNumber=N
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("qualys")

CSPS = ["AWS", "AZURE", "GCP"]
KUBERNETES = "KUBERNETES"
_CONN_ACCOUNT_FIELD = {"AWS": "awsAccountId", "AZURE": "subscriptionId", "GCP": "projectId"}

_POD_GATEWAY = {
    "US1": "https://gateway.qg1.apps.qualys.com",
    "US2": "https://gateway.qg2.apps.qualys.com",
    "US3": "https://gateway.qg3.apps.qualys.com",
    "US4": "https://gateway.qg4.apps.qualys.com",
    "EU1": "https://gateway.qg1.apps.qualys.eu",
    "EU2": "https://gateway.qg2.apps.qualys.eu",
    "IN1": "https://gateway.qg1.apps.qualysksa.com",
    "CA1": "https://gateway.qg1.apps.qualys.ca",
    "UK1": "https://gateway.qg1.apps.qualys.co.uk",
    "AU1": "https://gateway.qg1.apps.qualys.com.au",
}
_INTERNAL_TLS_DOMAINS = (".qualys.com", ".totalcloud.network")

_MAX_PAGES = 500  # safety ceiling for any paged loop


class QualysError(RuntimeError):
    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


def _ssl_ctx(url: str):
    """SSL context. ENG/QA pods serve self-signed certs → drop verification only for a qualys-owned
    `.eng.` host / *.qualys.dev, or when QPD_INSECURE_SSL is set. Commercial pods keep full
    verification (returns None → urllib's default verifying context)."""
    host = (urlparse(url).hostname or "").lower()
    insecure = os.environ.get("QPD_INSECURE_SSL", "").strip().lower() in ("1", "true", "yes")
    eng_pod = ".eng." in f".{host}" and host.endswith(_INTERNAL_TLS_DOMAINS)
    if insecure or eng_pod or host.endswith(".qualys.dev"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def resolve_gateway(gateway_or_pod: str) -> str:
    """Normalize the customer's input into a gateway base URL (scheme://host). The gateway host
    VARIES by pod — we take it from their input, or map a POD short-code."""
    s = (gateway_or_pod or "").strip()
    if not s:
        return ""
    up = s.upper()
    if up in _POD_GATEWAY:
        return _POD_GATEWAY[up]
    if not s.startswith("http"):
        s = "https://" + s
    u = urlparse(s)
    if u.scheme and u.netloc:
        host = u.netloc.replace("qualysapi.", "gateway.").replace("qualysguard.", "gateway.")
        return f"{u.scheme}://{host}"
    return s.rstrip("/")


# ── HTTP ─────────────────────────────────────────────────────────────────────
def _get(gw: str, jwt: str, path: str, timeout: int = 45) -> object:
    req = urllib.request.Request(
        f"{gw}{path}", headers={"Authorization": "Bearer " + jwt, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx(gw)) as r:
        raw = r.read().decode()
    return json.loads(raw) if raw.strip() else {}


def _get_paged(gw: str, jwt: str, base_path: str, page_size: int = 300,
               page_param: str = "pageNo", content_key: str = "content") -> List[Dict]:
    """Walk a Spring-paged endpoint (content/totalPages/last/number) and return all items.
    Stops when `last is True`, when number+1 >= totalPages, or when a page is empty."""
    items: List[Dict] = []
    page = 0
    while page < _MAX_PAGES:
        sep = "&" if "?" in base_path else "?"
        path = f"{base_path}{sep}pageSize={page_size}&{page_param}={page}"
        data = _get(gw, jwt, path)
        if isinstance(data, list):
            items.extend(data)
            break
        if not isinstance(data, dict):
            break
        content = data.get(content_key)
        if content is None:
            content = data.get("content") or data.get("data") or []
        items.extend(content)
        last = data.get("last")
        total_pages = data.get("totalPages")
        number = data.get("number", page)
        if last is True:
            break
        if total_pages is not None and (number + 1) >= total_pages:
            break
        if not content:
            break
        page += 1
    return items


def mint_jwt(gateway_or_pod: str, username: str, password: str) -> Tuple[str, str]:
    """(gateway_base, jwt). Raises QualysError with a human message. NEVER logs the password."""
    gw = resolve_gateway(gateway_or_pod)
    if not gw:
        raise QualysError("No gateway URL / POD provided.")
    data = urllib.parse.urlencode({"username": username, "password": password, "token": "true"}).encode()
    req = urllib.request.Request(
        f"{gw}/auth", data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx(gw)) as r:
            jwt = r.read().decode().strip()
        if not jwt:
            raise QualysError("Gateway returned an empty token.")
        return gw, jwt
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise QualysError("Authentication failed (401) — check the Qualys username/password.", 401)
        raise QualysError(f"Qualys gateway error ({e.code}) — try again shortly.", e.code) from None
    except urllib.error.URLError as e:
        raise QualysError(f"Could not reach the Qualys gateway at {gw}: {e.reason}", 0) from None


# ── accounts (paged connectors) ──────────────────────────────────────────────
def list_accounts(gw: str, jwt: str, csp: str) -> List[Dict[str, str]]:
    field = _CONN_ACCOUNT_FIELD.get(csp.upper())
    if not field:
        return []
    try:
        rows = _get_paged(gw, jwt, f"/cloudview-api/rest/v1/{csp.lower()}/connectors", page_size=50)
    except Exception as e:  # noqa: BLE001
        logger.warning("connector list failed (%s): %s — skipping", csp, e)
        return []
    out: Dict[str, str] = {}
    for c in rows:
        acct = c.get(field)
        if acct and str(acct) not in out:
            out[str(acct)] = c.get("name") or str(acct)
    return [{"id": k, "name": v, "csp": csp.upper()} for k, v in out.items()]


def enumerate_accounts(gw: str, jwt: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for csp in CSPS:
        accounts.extend(list_accounts(gw, jwt, csp))
    return accounts


# ── CSPM controls (paged) ────────────────────────────────────────────────────
def fetch_cspm_controls(gw: str, jwt: str, csp: str) -> List[Dict]:
    """Control catalog for a provider. Uses the `control` content key. A CSP whose controls
    endpoint 500s (seen on some AZURE/GCP profiles) returns [] instead of aborting."""
    try:
        return _get_paged(gw, jwt, f"/cloudview-api/rest/v1/controls/metadata/list?filter=provider%3A{csp.upper()}",
                          page_size=1000, content_key="control")
    except Exception as e:  # noqa: BLE001
        logger.warning("CSPM controls fetch error (%s): %s — skipping csp", csp, e)
        return []


def cspm_control_index(gw: str, jwt: str, csp: str) -> Dict[str, Dict]:
    idx: Dict[str, Dict] = {}
    for c in fetch_cspm_controls(gw, jwt, csp):
        cid = str(c.get("cid") or c.get("controlId") or "")
        if not cid:
            continue
        idx[cid] = {
            "control_name": c.get("controlName", ""),
            "criticality": (c.get("criticality") or "MEDIUM").upper(),
            "service": c.get("serviceType") or c.get("service") or "",
            "resource_type": c.get("resourceType", ""),
            "policies": c.get("policyNames") or [],
            # Remediation guidance (same control-metadata response — no extra API call).
            "manual_remediation": c.get("manualRemediation", ""),
            "cli_remediation": c.get("cliRemediation", ""),
            "buildtime_remediation": c.get("buildTimeRemediation", ""),
            "rationale": c.get("rationale", ""),
            "specification": c.get("specification", ""),
            "references": c.get("references", ""),
        }
    return idx


# ── CSPM posture + resources (paged) ─────────────────────────────────────────
def cspm_posture(gw: str, jwt: str, csp: str, account_id: str) -> List[Dict]:
    return _get_paged(gw, jwt, f"/cloudview-api/rest/v1/{csp.lower()}/evaluations/{account_id}", page_size=300)


def cspm_posture_resources(gw: str, jwt: str, csp: str, account_id: str, control_id: str) -> List[Dict]:
    return _get_paged(
        gw, jwt,
        f"/cloudview-api/rest/v1/{csp.lower()}/evaluations/{account_id}/resources/{control_id}",
        page_size=50)


# ── resource inventory (Qualys tags) ─────────────────────────────────────────
# Qualys's OWN asset tags live on the resource-INVENTORY API, not on the evaluations response
# (which carries only the provider's `cloudTags`). One paged call per resource type covers every
# account, so this is a per-CSP pass rather than a per-account one.
_INVENTORY_CLOUD = {"AWS": "AWS", "AZURE": "Azure", "GCP": "GCP"}


def resource_inventory_tags(gw: str, jwt: str, csp: str, resource_type: str) -> Dict[tuple, Dict]:
    """{(accountId, resourceId): {"qualys": [names], "cloud": [{key, value}, …]}} for one type.

    The key includes the ACCOUNT because this endpoint spans every account and some resource ids
    are only unique within one — IAM user/role/policy ids are bare names (`OktaSSO`), so keying on
    the id alone would stamp one account's tags onto another account's identically-named resource.

    BOTH tag kinds come back in the same response, so this one call serves two purposes:
      * Qualys asset tags — available nowhere else.
      * Cloud tags — a FALLBACK for resource types the evaluations response omits `cloudTags` for
        entirely (CloudFront, IAM users…). The two sources are complementary: inventory has tags
        for types evaluations skips, and is null for some types evaluations does cover.
    Types with no inventory endpoint return {} (Qualys answers 400) rather than aborting the sweep."""
    cloud = _INVENTORY_CLOUD.get(csp.upper())
    if not cloud or not resource_type:
        return {}
    try:
        rows = _get_paged(gw, jwt, f"/cloudview-api/rest/v1/resource/{resource_type}/{cloud}",
                          page_size=500)
    except Exception as e:  # noqa: BLE001
        logger.info("inventory fetch skipped %s/%s: %s", csp, resource_type, e)
        return {}
    out: Dict[tuple, Dict] = {}
    for r in rows:
        rid = str(r.get("resourceId") or r.get("cloudResourceId") or "")
        acct = str(r.get("cloudAccountId") or r.get("accountId") or "")
        if not rid or not acct:
            continue
        names = [str(t.get("tagName")) for t in (r.get("qualysTags") or []) if t.get("tagName")]
        cloud = [{"key": t.get("key"), "value": t.get("value")}
                 for t in (r.get("tags") or []) if t.get("key")]
        if names or cloud:
            out[(acct, rid)] = {"qualys": names, "cloud": cloud}
    return out


# ── KSPM posture + resources ─────────────────────────────────────────────────
def kspm_posture(gw: str, jwt: str) -> List[Dict]:
    try:
        rows = _get_paged(gw, jwt, "/csapi/v1.3/k8s_postures/list", page_size=300,
                          page_param="pageNumber", content_key="data")
    except Exception as e:  # noqa: BLE001
        logger.warning("KSPM posture fetch failed: %s — skipping", e)
        return []
    out = []
    for item in rows:
        passed = item.get("passControls", 0) or 0
        failed = item.get("failedControls", 0) or 0
        out.append({
            "controlId": str(item.get("cid", "")), "controlName": item.get("controlName", ""),
            "criticality": (item.get("criticality") or "MEDIUM").upper(), "service": "Kubernetes",
            "passedResources": passed, "failedResources": failed,
            "passWithExceptionResources": 0,
            "result": "FAIL" if failed else "PASS",
        })
    return out


def kspm_posture_resources(gw: str, jwt: str, control_id: str) -> List[Dict]:
    try:
        rows = _get_paged(gw, jwt, f"/csapi/v1.3/k8s_postures/count?filter=cid:{control_id}",
                          page_size=100, content_key="data")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for res in rows:
        out.append({
            "resourceId": res.get("resourceId") or res.get("resourceName", ""),
            "resourceType": res.get("resourceType", ""),
            "region": res.get("clusterName", ""), "accountId": res.get("accountId", ""),
            "result": (res.get("status") or "").upper() or "FAIL",
            "evidences": [
                {"settingName": "Resource Type", "actualValue": res.get("resourceType", "")},
                {"settingName": "Cluster", "actualValue": res.get("clusterName", "")},
                {"settingName": "Status", "actualValue": res.get("status", "")},
            ],
            "evaluationDates": {"firstEvaluated": res.get("firstEvaluated"),
                                "lastEvaluated": res.get("lastEvaluated")},
        })
    return out


# ── field parsers (against the LIVE shapes) ──────────────────────────────────
def parse_posture_eval(ev: Dict) -> Dict:
    """One CSPM/KSPM evaluation → normalized dict. Live fields: controlName, criticality, service,
    result, controlId, passedResources, failedResources, passWithExceptionResources."""
    passed = int(ev.get("passedResources", ev.get("passed", 0)) or 0)
    failed = int(ev.get("failedResources", ev.get("failed", 0)) or 0)
    exceptions = int(ev.get("passWithExceptionResources", 0) or 0)
    return {
        "control_id": str(ev.get("controlId") or ev.get("cid") or ""),
        "control_name": ev.get("controlName", ""),
        "criticality": (ev.get("criticality") or "MEDIUM").upper(),
        "service": ev.get("service", ""),
        "result": (ev.get("result") or "").upper(),
        "passed": passed, "failed": failed, "exceptions": exceptions,
        "total": passed + failed + exceptions,
    }


def parse_resource(res: Dict) -> Dict:
    """One CSPM/KSPM resource → normalized dict. NO arn — identity is
    (accountId, resourceType, resourceId, region). Region may be '' (e.g. IAM_PASSWORD).
    Captures Qualys's own lifecycle dates for NEW / FIXED / REOPENED."""
    ed = res.get("evaluationDates") or {}
    region = res.get("region")
    return {
        "resource_id": str(res.get("resourceId") or res.get("resourceName") or res.get("id") or ""),
        "resource_type": res.get("resourceType") or res.get("type") or "",
        "region": region if region else "",   # store '' not None so the PK is reliable in SQLite
        "account_id": str(res.get("accountId") or ""),
        "result": (res.get("result") or "").upper(),
        "evidences": res.get("evidences") or res.get("evidence") or [],
        # Cloud-provider resource tags. AWS returns these as `cloudTags`: [{key, value}, …].
        # Absent on providers/resource types that don't report them → [].
        "tags": res.get("cloudTags") or res.get("tags") or [],
        "first_evaluated": ed.get("firstEvaluated"),
        "last_evaluated": ed.get("lastEvaluated"),
        "date_fixed": ed.get("dateFixed"),
        "date_reopen": ed.get("dateReopen"),
        "prev_result": ed.get("prevResult"),
    }
