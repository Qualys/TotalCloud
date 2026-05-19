"""
Qualys Connectors API client — creates Azure connectors via the AM module.

Endpoint: POST /qps/rest/3.0/create/am/azureassetdataconnector
Ref: https://docs.qualys.com/en/conn/api/#t=azure_3%2Fcreate_azure_connector_3.0.htm
Auth: HTTP Basic (username:password)
Content-Type: text/xml
"""

import logging
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)

# All Qualys platforms — ref: https://www.qualys.com/platform-identification/
QUALYS_PLATFORMS: dict[str, str] = {
    "US1":  "https://qualysapi.qualys.com",
    "US2":  "https://qualysapi.qg2.apps.qualys.com",
    "US3":  "https://qualysapi.qg3.apps.qualys.com",
    "US4":  "https://qualysapi.qg4.apps.qualys.com",
    "GOV1": "https://qualysapi.gov1.qualys.us",
    "EU1":  "https://qualysapi.qualys.eu",
    "EU2":  "https://qualysapi.qg2.apps.qualys.eu",
    "EU3":  "https://qualysapi.qg3.apps.qualys.it",
    "IN1":  "https://qualysapi.qg1.apps.qualys.in",
    "CA1":  "https://qualysapi.qg1.apps.qualys.ca",
    "AE1":  "https://qualysapi.qg1.apps.qualys.ae",
    "UK1":  "https://qualysapi.qg1.apps.qualys.co.uk",
    "AU1":  "https://qualysapi.qg1.apps.qualys.com.au",
    "KSA1": "https://qualysapi.qg1.apps.qualysksa.com",
}

QUALYS_US2_BASE = QUALYS_PLATFORMS["US2"]  # kept for backwards compat

def resolve_platform_url(platform_or_url: str) -> str:
    """
    Accept either a platform key (e.g. 'CA1') or a full base URL.
    Returns the API base URL, raising ValueError for unknown keys.
    """
    key = platform_or_url.strip().upper()
    if key in QUALYS_PLATFORMS:
        return QUALYS_PLATFORMS[key]
    if platform_or_url.startswith("http"):
        return platform_or_url.rstrip("/")
    valid = ", ".join(QUALYS_PLATFORMS)
    raise ValueError(
        f"Unknown Qualys platform '{platform_or_url}'. "
        f"Valid keys: {valid}  — or pass a full URL."
    )

_CREATE_PATH      = "/qps/rest/3.0/create/am/azureassetdataconnector"
_SEARCH_PATH      = "/qps/rest/3.0/search/am/azureassetdataconnector"
_UPDATE_PATH      = "/qps/rest/3.0/update/am/azureassetdataconnector"
_TAG_SEARCH_PATH  = "/qps/rest/2.0/search/am/tag"
_TAG_CREATE_PATH  = "/qps/rest/2.0/create/am/tag"
_DEFAULT_RUN_FREQUENCY = 1440  # minutes (24 hours)

# App-type → connectorAppInfos modules; activation is controlled separately
APP_TYPE_CONFIG: dict[str, list[str]] = {
    "AI":  ["AI"],
    "CSA": ["AI", "CI", "CSA"],
}

VALID_ACTIVATION_MODULES = ["VM", "CERTVIEW", "SCA", "PC"]

# Qualys connector name max length
_MAX_NAME_LEN = 255


def resolve_connector_name(display_name: Optional[str], subscription_id: str) -> str:
    """Use the subscription alias if present, else azure-sub-<id>. Caps at 255 chars."""
    alias = (display_name or "").strip()
    name = alias if alias else f"azure-sub-{subscription_id}"
    return name[:_MAX_NAME_LEN]


@dataclass
class ConnectorResult:
    subscription_id: str
    subscription_name: str   # display name / alias from Azure
    connector_name: str      # actual name sent to Qualys
    management_group: str
    success: bool
    connector_id: Optional[str] = None
    status: str = ""         # "created" | "skipped" | "failed" | "dry_run"
    note: Optional[str] = None


def _xe(value: str) -> str:
    return (
        value.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;")
    )


def _build_create_xml(
    name: str,
    description: str,
    subscription_id: str,
    directory_id: str,
    application_id: str,
    authentication_key: str,
    is_gov_cloud: bool,
    app_modules: list[str],
    activation_modules: list[str],
    run_frequency: int,
    connector_tag_ids: list[int],
    asset_tag_ids: list[int],
) -> str:
    act_items = "\n".join(
        f"                    <ActivationModule>{m}</ActivationModule>"
        for m in activation_modules
    )

    tags_xml = ""
    if connector_tag_ids:
        tag_items = "\n".join(
            f"                    <TagSimple><id>{tid}</id></TagSimple>"
            for tid in connector_tag_ids
        )
        tags_xml = f"""
            <defaultTags>
                <set>
{tag_items}
                </set>
            </defaultTags>"""

    def _app_list(app_name: str) -> str:
        if asset_tag_ids:
            entries = "\n".join(
                f"""                            <ConnectorAppInfo>
                                <name>{app_name}</name>
                                <identifier>{_xe(subscription_id)}</identifier>
                                <tagId>{tid}</tagId>
                            </ConnectorAppInfo>"""
                for tid in asset_tag_ids
            )
        else:
            entries = f"""                            <ConnectorAppInfo>
                                <name>{app_name}</name>
                                <identifier>{_xe(subscription_id)}</identifier>
                            </ConnectorAppInfo>"""
        return f"""                    <ConnectorAppInfoQList>
                        <set>
{entries}
                        </set>
                    </ConnectorAppInfoQList>"""

    app_lists = "\n".join(_app_list(m) for m in app_modules)

    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<ServiceRequest>
    <data>
        <AzureAssetDataConnector>
            <name>{_xe(name)}</name>
            <description>{_xe(description)}</description>{tags_xml}
            <activation>
                <set>
{act_items}
                </set>
            </activation>
            <disabled>false</disabled>
            <runFrequency>{run_frequency}</runFrequency>
            <isRemediationEnabled>false</isRemediationEnabled>
            <isGovCloudConfigured>{"true" if is_gov_cloud else "false"}</isGovCloudConfigured>
            <authRecord>
                <applicationId>{_xe(application_id)}</applicationId>
                <directoryId>{_xe(directory_id)}</directoryId>
                <subscriptionId>{_xe(subscription_id)}</subscriptionId>
                <authenticationKey>{_xe(authentication_key)}</authenticationKey>
            </authRecord>
            <connectorAppInfos>
                <set>
{app_lists}
                </set>
            </connectorAppInfos>
        </AzureAssetDataConnector>
    </data>
</ServiceRequest>"""


def _parse_response(xml_text: str) -> tuple[bool, Optional[str], Optional[str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return False, None, f"XML parse error: {exc}"

    code = root.findtext("responseCode", "")
    if code == "SUCCESS":
        return True, root.findtext(".//id"), None

    err = (
        root.findtext("responseErrorDetails/errorMessage")
        or root.findtext("responseMessage")
        or "Unknown error"
    )
    return False, None, f"{code}: {err}"


class QualysClient:
    def __init__(self, username: str, password: str, base_url: str = QUALYS_US2_BASE):
        self._auth = HTTPBasicAuth(username, password)
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "text/xml",
            "X-Requested-With": "qualys-azure-gov-connector",
        })

    def _post(self, path: str, body: str, retries: int = 3) -> requests.Response:
        url = f"{self._base}{path}"
        for attempt in range(1, retries + 1):
            resp = self._session.post(url, data=body.encode("utf-8"), auth=self._auth, timeout=60)
            if resp.status_code == 429 and attempt < retries:
                wait = int(resp.headers.get("Retry-After", 30))
                log.warning("Rate-limited, waiting %ds (attempt %d/%d)", wait, attempt, retries)
                time.sleep(wait)
                continue
            return resp
        return resp

    def _paginated_search(
        self,
        path: str,
        item_tag: str,
        filters_xml: str = "",
        page_size: int = 200,
    ) -> list[ET.Element]:
        """
        Fetch all pages from a Qualys search endpoint.
        Qualys paginates via hasMoreRecords / lastId in the response.
        """
        all_items: list[ET.Element] = []
        start_from_id: Optional[str] = None
        page = 1

        while True:
            start_xml = (
                f"        <startFromId>{start_from_id}</startFromId>\n"
                if start_from_id else ""
            )
            body = f"""<?xml version="1.0" encoding="UTF-8" ?>
<ServiceRequest>
    <preferences>
        <limitResults>{page_size}</limitResults>
{start_xml}    </preferences>
{filters_xml}
</ServiceRequest>"""
            resp = self._post(path, body)
            if resp.status_code != 200:
                log.warning("_paginated_search HTTP %d on page %d", resp.status_code, page)
                break
            try:
                root = ET.fromstring(resp.text)
            except ET.ParseError as exc:
                log.warning("_paginated_search XML parse error on page %d: %s", page, exc)
                break
            if root.findtext("responseCode") != "SUCCESS":
                log.warning("_paginated_search non-success on page %d: %s",
                            page, root.findtext("responseCode"))
                break

            items = root.findall(f".//{item_tag}")
            all_items.extend(items)
            log.debug("  page %d: %d item(s) fetched (total so far: %d)", page, len(items), len(all_items))

            has_more = root.findtext("hasMoreRecords", "false").lower() == "true"
            if not has_more:
                break
            start_from_id = root.findtext("lastId")
            if not start_from_id:
                log.warning("_paginated_search: hasMoreRecords=true but no lastId on page %d", page)
                break
            page += 1

        return all_items

    def connector_exists(self, subscription_id: str) -> Optional[str]:
        log.debug("Checking if connector exists for subscription %s", subscription_id)
        body = f"""<?xml version="1.0" encoding="UTF-8" ?>
<ServiceRequest>
    <filters>
        <Criteria field="authRecord.subscriptionId" operator="EQUALS">{_xe(subscription_id)}</Criteria>
    </filters>
</ServiceRequest>"""
        try:
            resp = self._post(_SEARCH_PATH, body)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                if root.findtext("responseCode") == "SUCCESS":
                    cid = root.findtext(".//AzureAssetDataConnector/id")
                    log.debug("  connector_exists → %s", cid or "not found")
                    return cid
            log.debug("  connector_exists HTTP %d for sub %s", resp.status_code, subscription_id)
        except Exception as exc:
            log.debug("connector_exists check failed for %s: %s", subscription_id, exc)
        return None

    def create_connector(
        self,
        connector_name: str,
        subscription_id: str,
        subscription_name: str,
        management_group: str,
        directory_id: str,
        application_id: str,
        authentication_key: str,
        description: str = "",
        is_gov_cloud: bool = True,
        app_type: str = "CSA",
        activation_modules: Optional[list[str]] = None,
        run_frequency: int = _DEFAULT_RUN_FREQUENCY,
        connector_tag_ids: Optional[list[int]] = None,
        asset_tag_ids: Optional[list[int]] = None,
        skip_if_exists: bool = True,
    ) -> ConnectorResult:
        app_modules = APP_TYPE_CONFIG.get(app_type.upper(), APP_TYPE_CONFIG["CSA"])
        activation_modules = activation_modules or []
        log.debug(
            "Connector params — app_type=%s app_modules=%s activation=%s gov=%s freq=%d",
            app_type, app_modules, activation_modules, is_gov_cloud, run_frequency,
        )

        base_result = dict(
            subscription_id=subscription_id,
            subscription_name=subscription_name,
            connector_name=connector_name,
            management_group=management_group,
        )

        if skip_if_exists:
            existing_id = self.connector_exists(subscription_id)
            if existing_id:
                log.info("Already exists for sub %s (id=%s), skipping", subscription_id, existing_id)
                return ConnectorResult(
                    **base_result, success=True,
                    connector_id=existing_id, status="skipped", note="already_exists",
                )

        body = _build_create_xml(
            name=connector_name,
            description=description,
            subscription_id=subscription_id,
            directory_id=directory_id,
            application_id=application_id,
            authentication_key=authentication_key,
            is_gov_cloud=is_gov_cloud,
            app_modules=app_modules,
            activation_modules=activation_modules,
            run_frequency=run_frequency,
            connector_tag_ids=connector_tag_ids or [],
            asset_tag_ids=asset_tag_ids or [],
        )

        log.info("Creating connector '%s' (%s)", connector_name, subscription_id)
        try:
            resp = self._post(_CREATE_PATH, body)
        except requests.RequestException as exc:
            return ConnectorResult(**base_result, success=False, status="failed", note=str(exc))

        log.debug("Response %d: %s", resp.status_code, resp.text[:400])
        success, cid, error = _parse_response(resp.text)

        if success:
            log.info("  ✓ id=%s", cid)
        else:
            log.warning("  ✗ %s: %s", subscription_id, error)

        return ConnectorResult(
            **base_result,
            success=success,
            connector_id=cid,
            status="created" if success else "failed",
            note=error if not success else None,
        )

    def resolve_tag_names(self, tag_names: list[str]) -> list[int]:
        log.info("Resolving %d tag name(s): %s", len(tag_names), tag_names)
        ids = []
        for name in tag_names:
            tag_id = self._find_tag(name)
            if tag_id:
                log.info("  Tag '%s' found: id=%s", name, tag_id)
            else:
                log.info("  Tag '%s' not found — creating …", name)
                tag_id = self._create_tag(name)
                if tag_id:
                    log.info("  Tag '%s' created: id=%s", name, tag_id)
                else:
                    log.warning("  Tag '%s' could not be resolved or created", name)
            if tag_id:
                ids.append(tag_id)
        log.info("Resolved tag IDs: %s", ids)
        return ids

    def _find_tag(self, name: str) -> Optional[int]:
        log.debug("Searching for tag '%s'", name)
        body = f"""<ServiceRequest>
    <filters>
        <Criteria field="name" operator="EQUALS">{_xe(name)}</Criteria>
    </filters>
</ServiceRequest>"""
        try:
            resp = self._session.post(
                f"{self._base}{_TAG_SEARCH_PATH}",
                data=body.encode(), auth=self._auth, timeout=20,
            )
            log.debug("  tag search HTTP %d", resp.status_code)
            root = ET.fromstring(resp.text)
            if root.findtext("responseCode") == "SUCCESS":
                tid = root.findtext(".//Tag/id")
                return int(tid) if tid else None
            log.debug("  tag search response: %s", root.findtext("responseCode"))
        except Exception as exc:
            log.warning("Tag search failed for '%s': %s", name, exc)
        return None

    def _create_tag(self, name: str) -> Optional[int]:
        body = f"""<ServiceRequest>
    <data>
        <Tag>
            <name>{_xe(name)}</name>
        </Tag>
    </data>
</ServiceRequest>"""
        try:
            resp = self._session.post(
                f"{self._base}{_TAG_CREATE_PATH}",
                data=body.encode(), auth=self._auth, timeout=20,
            )
            root = ET.fromstring(resp.text)
            if root.findtext("responseCode") == "SUCCESS":
                tid = root.findtext(".//Tag/id")
                return int(tid) if tid else None
            err = root.findtext("responseErrorDetails/errorMessage", "")
            log.warning("Tag create failed for '%s': %s", name, err)
        except Exception as exc:
            log.warning("Tag create error for '%s': %s", name, exc)
        return None

    def list_all_connectors(self) -> list[dict]:
        """
        Return ALL Azure connectors in Qualys with pagination.
        Fields: id, name, subscriptionId, disabled, connectorState.
        """
        log.info("Fetching all connectors from Qualys (paginated) …")
        try:
            nodes = self._paginated_search(_SEARCH_PATH, "AzureAssetDataConnector")
            connectors = [
                {
                    "id":             node.findtext("id", ""),
                    "name":           node.findtext("name", ""),
                    "subscriptionId": (node.findtext("authRecord/subscriptionId") or ""),
                    "disabled":       node.findtext("disabled", "false").lower() == "true",
                    "connectorState": node.findtext("connectorState", ""),
                }
                for node in nodes
            ]
            log.info("  Total connectors in Qualys: %d", len(connectors))
            return connectors
        except Exception as exc:
            log.warning("list_all_connectors failed: %s", exc)
            return []

    def get_connector_state(self, connector_id: str) -> dict:
        """
        Fetch live state of a single connector by ID.
        Returns a dict with state fields, or an empty dict on failure.
        """
        log.debug("Fetching state for connector id=%s", connector_id)
        body = f"""<?xml version="1.0" encoding="UTF-8" ?>
<ServiceRequest>
    <filters>
        <Criteria field="id" operator="EQUALS">{_xe(connector_id)}</Criteria>
    </filters>
</ServiceRequest>"""
        try:
            resp = self._post(_SEARCH_PATH, body)
            if resp.status_code != 200:
                log.warning("get_connector_state HTTP %d for id=%s", resp.status_code, connector_id)
                return {}
            root = ET.fromstring(resp.text)
            if root.findtext("responseCode") != "SUCCESS":
                log.warning("get_connector_state non-success for id=%s: %s",
                            connector_id, root.findtext("responseCode"))
                return {}
            node = root.find(".//AzureAssetDataConnector")
            if node is None:
                log.warning("get_connector_state: no connector found for id=%s", connector_id)
                return {}
            return {
                "connector_state":       node.findtext("connectorState", ""),
                "last_synced_on":        node.findtext("lastSyncedOn", ""),
                "total_assets_created":  node.findtext("totalAssetsCreated", ""),
                "total_assets_updated":  node.findtext("totalAssetsUpdated", ""),
                "total_assets_deleted":  node.findtext("totalAssetsDeleted", ""),
                "connector_error":       node.findtext("errorDetail", "") or node.findtext("error", ""),
                "disabled":              node.findtext("disabled", "false"),
                "run_frequency":         node.findtext("runFrequency", ""),
            }
        except Exception as exc:
            log.warning("get_connector_state failed for id=%s: %s", connector_id, exc)
            return {}

    def disable_connector(self, connector_id: str) -> tuple[bool, str]:
        """Disable a connector (sets disabled=true). Returns (success, message)."""
        log.info("Disabling connector id=%s", connector_id)
        body = """<?xml version="1.0" encoding="UTF-8" ?>
<ServiceRequest>
    <data>
        <AzureAssetDataConnector>
            <disabled>true</disabled>
        </AzureAssetDataConnector>
    </data>
</ServiceRequest>"""
        try:
            resp = self._post(f"{_UPDATE_PATH}/{connector_id}", body)
            log.debug("  disable HTTP %d", resp.status_code)
            root = ET.fromstring(resp.text)
            if root.findtext("responseCode") == "SUCCESS":
                log.info("  ✓ Connector %s disabled", connector_id)
                return True, "disabled"
            err = root.findtext("responseErrorDetails/errorMessage") or "Unknown error"
            log.warning("  ✗ Failed to disable %s: %s", connector_id, err)
            return False, err
        except Exception as exc:
            log.warning("  ✗ Exception disabling %s: %s", connector_id, exc)
            return False, str(exc)

    def enable_connector(self, connector_id: str) -> tuple[bool, str]:
        """Re-enable a previously disabled connector. Returns (success, message)."""
        log.info("Enabling connector id=%s", connector_id)
        body = """<?xml version="1.0" encoding="UTF-8" ?>
<ServiceRequest>
    <data>
        <AzureAssetDataConnector>
            <disabled>false</disabled>
        </AzureAssetDataConnector>
    </data>
</ServiceRequest>"""
        try:
            resp = self._post(f"{_UPDATE_PATH}/{connector_id}", body)
            log.debug("  enable HTTP %d", resp.status_code)
            root = ET.fromstring(resp.text)
            if root.findtext("responseCode") == "SUCCESS":
                log.info("  ✓ Connector %s enabled", connector_id)
                return True, "enabled"
            err = root.findtext("responseErrorDetails/errorMessage") or "Unknown error"
            log.warning("  ✗ Failed to enable %s: %s", connector_id, err)
            return False, err
        except Exception as exc:
            log.warning("  ✗ Exception enabling %s: %s", connector_id, exc)
            return False, str(exc)

    def disable_orphan_connectors(
        self,
        active_subscription_ids: set[str],
        managed_connector_ids: Optional[set[str]] = None,
    ) -> list[dict]:
        """
        Disable script-managed connectors whose subscriptions are no longer active.
        managed_connector_ids: IDs previously created by this script (from CSV history).
          When provided, only those connectors are considered — all others are ignored.
        Returns list of {id, name, subscriptionId, result, note}.
        """
        all_connectors = self.list_all_connectors()

        if managed_connector_ids:
            before = len(all_connectors)
            all_connectors = [c for c in all_connectors if c["id"] in managed_connector_ids]
            log.info("  Scoped to %d script-managed connector(s) (of %d total in Qualys)",
                     len(all_connectors), before)

        orphans = [
            c for c in all_connectors
            if c["subscriptionId"] not in active_subscription_ids and not c["disabled"]
        ]

        if not orphans:
            log.info("No orphan connectors found.")
            return []

        log.info("Found %d orphan connector(s) to disable.", len(orphans))
        results = []
        for c in orphans:
            log.info("  Disabling [%s] %s (sub=%s) …", c["id"], c["name"], c["subscriptionId"])
            ok, msg = self.disable_connector(c["id"])
            icon = "✓" if ok else "✗"
            log.info("    %s %s", icon, msg)
            results.append({**c, "result": "disabled" if ok else "failed", "note": msg})
        return results

    def create_connectors_bulk(
        self,
        subscriptions: list[dict],
        directory_id: str,
        application_id: str,
        authentication_key: str,
        is_gov_cloud: bool = True,
        app_type: str = "CSA",
        activation_modules: Optional[list[str]] = None,
        run_frequency: int = _DEFAULT_RUN_FREQUENCY,
        connector_tag_ids: Optional[list[int]] = None,
        asset_tag_ids: Optional[list[int]] = None,
        parallel: int = 1,
        delay_between: float = 2.0,
        skip_if_exists: bool = True,
    ) -> list[ConnectorResult]:
        """
        Create connectors for all subscriptions.
        parallel=1 (default) processes them sequentially with delay_between seconds between each.
        parallel=N uses N threads; submissions are still paced at delay_between seconds apart
        to avoid bursting Qualys rate limits.
        """
        log.info(
            "Bulk create — %d subscription(s)  app_type=%s  activation=%s  "
            "freq=%d min  gov=%s  parallel=%d  delay=%.1fs",
            len(subscriptions), app_type, activation_modules or [],
            run_frequency, is_gov_cloud, parallel, delay_between,
        )
        total = len(subscriptions)
        # Pre-allocate result slots so we preserve input order regardless of thread completion order
        results_map: dict[int, ConnectorResult] = {}
        lock = threading.Lock()

        def _do_one(idx: int, sub: dict) -> tuple[int, ConnectorResult]:
            sub_id    = sub["subscriptionId"]
            disp      = sub.get("displayName", "")
            mg        = sub.get("managementGroupName", "")
            conn_name = resolve_connector_name(disp, sub_id)
            desc      = f"Auto-created — subscription {sub_id}"
            if mg:
                desc += f" (MG: {mg})"
            log.info("[%d/%d] %s", idx, total, conn_name)
            result = self.create_connector(
                connector_name=conn_name,
                subscription_id=sub_id,
                subscription_name=disp or sub_id,
                management_group=mg,
                directory_id=directory_id,
                application_id=application_id,
                authentication_key=authentication_key,
                description=desc,
                is_gov_cloud=is_gov_cloud,
                app_type=app_type,
                activation_modules=activation_modules,
                run_frequency=run_frequency,
                connector_tag_ids=connector_tag_ids,
                asset_tag_ids=asset_tag_ids,
                skip_if_exists=skip_if_exists,
            )
            with lock:
                results_map[idx] = result
            return idx, result

        if parallel == 1:
            for idx, sub in enumerate(subscriptions, start=1):
                _do_one(idx, sub)
                if idx < total:
                    time.sleep(delay_between)
        else:
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                futures = []
                for idx, sub in enumerate(subscriptions, start=1):
                    futures.append(executor.submit(_do_one, idx, sub))
                    # Pace submissions to avoid rate limit bursts
                    if idx < total:
                        time.sleep(delay_between)
                # Ensure all futures complete and surface any exceptions
                for f in futures:
                    f.result()

        return [results_map[i] for i in range(1, total + 1)]
