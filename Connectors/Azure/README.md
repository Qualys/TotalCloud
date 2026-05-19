# Azure Connectors

Four tools depending on what you need:

**[`TenantConnector/`](TenantConnector/)** — if you want full automation. It discovers every subscription in your tenant, creates connectors, handles orphan detection when subscriptions disappear, and can restore disabled connectors. Works for both Azure Commercial and Azure Government. This is the recommended path for most deployments.

**[`SubscriptionConnector/`](SubscriptionConnector/)** — simpler Bash script if you already have a list of subscription IDs and just want to create connectors for them.

**[`Terraform/`](Terraform/)** — Terraform to create the Azure Service Principal with `Reader` permissions. Run this first if you don't already have an SP set up.

**[`UpdateAssetTags/`](UpdateAssetTags/)** — update asset tags on connectors that already exist in Qualys.

---

You'll need a Service Principal with `Reader` role on your tenant (or Management Group root) before any of these tools can connect. See [`Terraform/`](Terraform/) if you haven't done that yet.

## Author
Yash Jhunjhunwala, Lead SME Cloud Security Solutions
