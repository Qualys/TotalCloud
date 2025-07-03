## Draft
# Deploying Qualys Cloud Agent on Azure VMs and VM Scale Sets Using Azure Policy

This guide provides step-by-step instructions to deploy the **Qualys Cloud Agent** on Azure Linux and Windows VMs and VM Scale Sets automatically using Azure Policy with remediation.

---

## Table of Contents
- [Prerequisites](#prerequisites)  
- [Policy JSON Files](#policy-json-files)  
- [Step 1: Create the Azure Policy](#step-1-create-the-azure-policy)  
- [Step 2: Assign the Policy](#step-2-assign-the-policy)  
- [Step 3: Trigger Compliance Scan](#step-3-trigger-compliance-scan)  
- [Step 4: Create Remediation Task](#step-4-create-remediation-task)  
- [Step 5: Verify Deployment](#step-5-verify-deployment)  
- [Notes and Troubleshooting](#notes-and-troubleshooting)  

---

## Prerequisites

- Azure subscription with permission to create policy definitions and assignments.  
- Existing Azure VMs or VM Scale Sets running supported OS (Linux or Windows).  
- Qualys License Code.  
- Azure CLI installed (optional).  
- Access to Azure Portal.  

---

## Policy JSON Files

Use the following JSON files for the policies (Linux VM, Linux VMSS, Windows VM, Windows VMSS):

| Policy Name                 | Description                    | File Name                  |
|-----------------------------|-------------------------------|----------------------------|
| Linux VM Extension Policy    | Auto-deploy Qualys agent to Linux VMs    | `qualys-linux-vm-policy.json`    |
| Linux VM Scale Set Policy    | Auto-deploy Qualys agent to Linux VMSS   | `qualys-linux-vmss-policy.json`  |
| Windows VM Extension Policy  | Auto-deploy Qualys agent to Windows VMs  | `qualys-windows-vm-policy.json`  |
| Windows VM Scale Set Policy  | Auto-deploy Qualys agent to Windows VMSS | `qualys-windows-vmss-policy.json`|

*(Attach or link the actual JSON files you generated earlier here)*

---

## Step 1: Create the Azure Policy

### CLI Method

Run the following commands for each JSON policy file:

```bash
az policy definition create --name "QualysLinuxVM" \
  --display-name "Autodeploy Qualys Agent for Linux VMs" \
  --description "Deploy Qualys Cloud Agent to Linux VMs" \
  --rules @qualys-linux-vm-policy.json \
  --mode All

az policy definition create --name "QualysLinuxVMSS" \
  --display-name "Autodeploy Qualys Agent for Linux VM Scale Sets" \
  --description "Deploy Qualys Cloud Agent to Linux VMSS" \
  --rules @qualys-linux-vmss-policy.json \
  --mode All

az policy definition create --name "QualysWindowsVM" \
  --display-name "Autodeploy Qualys Agent for Windows VMs" \
  --description "Deploy Qualys Cloud Agent to Windows VMs" \
  --rules @qualys-windows-vm-policy.json \
  --mode All

az policy definition create --name "QualysWindowsVMSS" \
  --display-name "Autodeploy Qualys Agent for Windows VM Scale Sets" \
  --description "Deploy Qualys Cloud Agent to Windows VMSS" \
  --rules @qualys-windows-vmss-policy.json \
  --mode All
```

### Azure Portal UI Method

1. Sign in to the Azure Portal.

2. Search for **Policy** and select it.

3. On the left pane, select **Definitions**.

4. Click **+ Policy definition** at the top.

5. Fill in the form:
   - **Name**: e.g., `QualysLinuxVM`
   - **Description**: e.g., `Autodeploy Qualys Agent for Linux VMs`
   - **Category**: Create or select an existing category.
   - **Policy Rule**: Upload the corresponding JSON file (e.g., `qualys-linux-vm-policy.json`).
   - **Mode**: Select `All`.

6. Click **Save**.

7. Repeat these steps for each of the four policies.

---

## Step 2: Assign the Policy

### CLI Method

Assign the policy to a subscription or resource group, providing required parameters:

```bash
az policy assignment create --name "QualysLinuxVMAssignment" \
  --policy "QualysLinuxVM" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>" \
  --params '{
    "licensecode": {
      "value": "<your-qualys-license-code>"
    },
    "excludetagname": {
      "value": "noqualysagent"
    },
    "excludetagvalue": {
      "value": "true"
    },
    "effect": {
      "value": "DeployIfNotExists"
    }
  }'

```
Repeat similarly for Windows and VM Scale Set policies by changing the policy name.

### Azure Portal UI Method

1. Go to **Azure Portal > Policy > Assignments**.

2. Click **Assign Policy**.

3. Select the **Scope** (subscription or resource group).

4. Under **Basics**, pick your policy (e.g., `QualysLinuxVM`).

5. Under Parameters, enter:
   - `licensecode`: your Qualys license code
   - `excludetagname`: default is `noqualysagent`
   - `excludetagvalue`: default is `true`
   - `effect`: select `DeployIfNotExists`

Review and click **Assign**.

---

## Step 3: Trigger Compliance Scan
Azure Policy evaluates compliance every ~24 hours by default. To force immediate compliance evaluation:

### CLI Method

```bash az policy state trigger-scan --resource-group <resource-group> ```

Or for entire subscription:

```bash az policy state trigger-scan ```

### Azure Portal UI Method
1. Navigate to Azure Portal > Policy > Compliance.

2. Select your policy assignment.

3. Click the Scan button at the top.

---
## Step 4: Create Remediation Task
Once non-compliant resources are identified, remediate:

### CLI Method
```bash az policy remediation create --name "QualysRemediation" --policy-assignment <policy-assignment-id> ```

### Azure Portal UI Method
1. Under Policy > Compliance, open the policy assignment.

2. Scroll to Non-compliant resources.

3. Click Create remediation task.

4. Review and confirm parameters.

5. Click Remediate.

---
## Step 5: Verify Deployment

1. Go to the Azure Portal and open the VM or VM Scale Set.

2. Select Extensions + applications.

3. Confirm QualysAgent (Windows) or QualysAgentLinux (Linux) extension is installed and in Succeeded state.

4. Add screenshot showing successful extension install.

5. Confirm the agent reports properly in the Qualys portal.

---
## Notes and Troubleshooting
Use tag noqualysagent=true to exclude specific VMs from deployment.

Qualys Azure VM extension currently supports only x86_64 (Intel/AMD64) VMs; ARM64 VMs are unsupported and deployment will fail.

Check logs in /var/log/azure on Linux or Event Viewer on Windows for extension errors.

Monitor compliance and remediation status via Azure Portal Policy blade.

---


