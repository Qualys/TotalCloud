"""
Azure client — discovers tenant, management groups, and subscriptions.
Supports both Azure Government and Azure Commercial clouds, selected via is_gov_cloud.
"""

import logging
from typing import Optional

from azure.identity import ClientSecretCredential, AzureAuthorityHosts
from azure.mgmt.managementgroups import ManagementGroupsAPI
from azure.mgmt.subscription import SubscriptionClient
from azure.core.exceptions import HttpResponseError

log = logging.getLogger(__name__)

_GOV_ARM        = "https://management.usgovcloudapi.net"
_GOV_AUTH       = AzureAuthorityHosts.AZURE_GOVERNMENT   # login.microsoftonline.us

_COMMERCIAL_ARM  = "https://management.azure.com"
_COMMERCIAL_AUTH = AzureAuthorityHosts.AZURE_PUBLIC_CLOUD  # login.microsoftonline.com


def _endpoints(is_gov_cloud: bool) -> tuple[str, str]:
    """Return (arm_endpoint, authority_host) for the chosen cloud."""
    if is_gov_cloud:
        return _GOV_ARM, _GOV_AUTH
    return _COMMERCIAL_ARM, _COMMERCIAL_AUTH


def build_credential(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    is_gov_cloud: bool = True,
) -> ClientSecretCredential:
    _, authority = _endpoints(is_gov_cloud)
    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        authority=authority,
    )


def get_tenant_info(credential: ClientSecretCredential, tenant_id: str, is_gov_cloud: bool = True) -> dict:
    arm, _ = _endpoints(is_gov_cloud)
    return {
        "tenantId":    tenant_id,
        "cloud":       "AzureUSGovernment" if is_gov_cloud else "AzureCommercial",
        "armEndpoint": arm,
    }


def _mg_client(credential: ClientSecretCredential, is_gov_cloud: bool = True) -> ManagementGroupsAPI:
    arm, _ = _endpoints(is_gov_cloud)
    return ManagementGroupsAPI(
        credential,
        base_url=arm,
        credential_scopes=[f"{arm}/.default"],
    )


def list_management_groups(
    credential: ClientSecretCredential,
    is_gov_cloud: bool = True,
) -> list[dict]:
    """Return all management groups the SP can see as a flat list."""
    groups = []
    try:
        for mg in _mg_client(credential, is_gov_cloud).management_groups.list():
            groups.append({
                "id":          mg.id,
                "name":        mg.name,
                "displayName": mg.display_name,
                "type":        mg.type,
                "parentName":  None,
            })
    except HttpResponseError as exc:
        log.warning("Management Groups API error: %s", exc)
    return groups


def get_mg_hierarchy(
    credential: ClientSecretCredential,
    mg_name: str,
    depth: int = 0,
    is_gov_cloud: bool = True,
) -> dict:
    """
    Recursively fetch the management group tree rooted at mg_name.
    Returns a dict with keys: name, displayName, children, depth.
    """
    client = _mg_client(credential, is_gov_cloud)
    try:
        detail = client.management_groups.get(
            group_id=mg_name,
            expand="children",
            recurse=True,
        )
    except HttpResponseError as exc:
        log.warning("Could not fetch MG details for %s: %s", mg_name, exc)
        return {"name": mg_name, "displayName": mg_name, "children": [], "depth": depth}

    def _walk(node, d: int) -> dict:
        children = []
        for child in (getattr(node, "children", None) or []):
            child_type = getattr(child, "type", "")
            if "managementGroups" in child_type:
                children.append(_walk(child, d + 1))
        return {
            "name":        node.name,
            "displayName": getattr(node, "display_name", node.name),
            "children":    children,
            "depth":       d,
        }

    return _walk(detail, depth)


def _collect_mg_names(hierarchy: dict) -> list[str]:
    """Flatten a hierarchy dict into a list of all MG names (including root)."""
    names = [hierarchy["name"]]
    for child in hierarchy.get("children", []):
        names.extend(_collect_mg_names(child))
    return names


def list_subscriptions_in_management_group(
    credential: ClientSecretCredential,
    management_group_name: str,
    is_gov_cloud: bool = True,
) -> list[dict]:
    """Return all subscriptions under the given management group."""
    subscriptions = []
    try:
        for entity in _mg_client(credential, is_gov_cloud).management_group_subscriptions.get_subscriptions_under_management_group(
            group_id=management_group_name
        ):
            subscriptions.append({
                "subscriptionId":      entity.name,
                "displayName":         entity.display_name,
                "managementGroupName": management_group_name,
                "state":               getattr(entity, "state", "Unknown"),
            })
    except (HttpResponseError, AttributeError) as exc:
        log.warning("Could not list subscriptions under MG %s: %s", management_group_name, exc)
    return subscriptions


def list_all_subscriptions(
    credential: ClientSecretCredential,
    is_gov_cloud: bool = True,
) -> list[dict]:
    """Fallback: all subscriptions visible via the Subscriptions API."""
    arm, _ = _endpoints(is_gov_cloud)
    client = SubscriptionClient(
        credential,
        base_url=arm,
        credential_scopes=[f"{arm}/.default"],
    )
    subs = []
    for sub in client.subscriptions.list():
        state = sub.state
        subs.append({
            "subscriptionId":      sub.subscription_id,
            "displayName":         sub.display_name,
            "state":               (state.value if hasattr(state, "value") else str(state)) if state else "Unknown",
            "managementGroupName": None,
        })
    return subs


def discover_subscriptions(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    root_management_group: Optional[str] = None,
    is_gov_cloud: bool = True,
) -> tuple[dict, list[dict], list[dict]]:
    """
    Main discovery entry point. Works for both Azure Government and Commercial.

    If root_management_group is given, fetches that MG's full descendant tree
    (all child/grandchild MGs) and collects subscriptions from every node.

    Returns:
        (tenant_info, management_groups, active_subscriptions)
    """
    credential  = build_credential(tenant_id, client_id, client_secret, is_gov_cloud)
    tenant_info = get_tenant_info(credential, tenant_id, is_gov_cloud)

    cloud_label = "Government" if is_gov_cloud else "Commercial"
    log.info("Cloud         : Azure %s", cloud_label)
    log.info("Listing management groups for tenant %s …", tenant_id)
    all_mgs = list_management_groups(credential, is_gov_cloud)
    log.info("Found %d management group(s)", len(all_mgs))

    subscriptions: list[dict] = []
    seen_ids: set[str] = set()

    if all_mgs:
        if root_management_group:
            log.info("Building MG hierarchy under '%s' …", root_management_group)
            hierarchy = get_mg_hierarchy(credential, root_management_group, is_gov_cloud=is_gov_cloud)
            target_mg_names = _collect_mg_names(hierarchy)
            log.info("Scoping to %d MG(s): %s", len(target_mg_names), target_mg_names)
        else:
            target_mg_names = [mg["name"] for mg in all_mgs]

        for mg_name in target_mg_names:
            log.info("Enumerating subscriptions under management group '%s' …", mg_name)
            for sub in list_subscriptions_in_management_group(credential, mg_name, is_gov_cloud):
                if sub["subscriptionId"] not in seen_ids:
                    subscriptions.append(sub)
                    seen_ids.add(sub["subscriptionId"])

    if not subscriptions:
        log.info("Falling back to subscription-list API …")
        for sub in list_all_subscriptions(credential, is_gov_cloud):
            if sub["subscriptionId"] not in seen_ids:
                subscriptions.append(sub)
                seen_ids.add(sub["subscriptionId"])

    active = [s for s in subscriptions if s.get("state", "").lower() in ("enabled", "active", "unknown")]
    log.info("Discovered %d subscription(s) (%d active)", len(subscriptions), len(active))
    return tenant_info, all_mgs, active
