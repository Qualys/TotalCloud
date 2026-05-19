# GCP Connectors

Scripts for onboarding GCP projects into Qualys TotalCloud. Three parts — you may need all three or just one depending on where you're starting from:

**[`EnableCloudAPIs/`](EnableCloudAPIs/)** — enables the required Google Cloud APIs across all projects in your organization. If APIs aren't enabled, Qualys can't scan those projects. Run this first.

**[`OrgLevelServiceAccount/`](OrgLevelServiceAccount/)** — creates a GCP service account at the organization level and assigns the IAM roles Qualys needs. This is the account Qualys will use to read your GCP resources. Run this once per organization.

**[`ProjectLevelConnector/`](ProjectLevelConnector/)** — Terraform to configure a project-level connector. Use this if you're connecting individual projects rather than the whole org.

---

Typical flow for an org-wide setup: enable APIs → create service account → configure connector in the Qualys portal using the service account key.

## Author
Yash Jhunjhunwala, Lead SME Cloud Security Solutions
