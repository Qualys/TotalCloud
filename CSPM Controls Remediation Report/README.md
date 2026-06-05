# CSPM Controls Remediation Report

Generate comprehensive HTML reports with remediation steps for Qualys TotalCloud CSPM Controls across AWS, Azure, GCP, and OCI.

## Features

- **Multi-Cloud Support**: AWS, Azure, GCP, and OCI
- **Dynamic API Fetching**: Policies and controls fetched directly from Qualys CloudView API
- **Interactive HTML Report**: Single-page application with tabs for each cloud provider
- **Policy Filtering**: Click on any policy in the sidebar to filter controls
- **Criticality Filtering**: Filter by High, Medium, or Low criticality
- **Dynamic Stats**: Stat widgets update based on active filters
- **Dark Mode**: Toggle with `D` key or click the theme button
- **Search**: Global search with `/` key
- **Export CSV**: Export visible controls to CSV with `E` key
- **Print Support**: Print-friendly styles with `P` key
- **Keyboard Shortcuts**: Quick navigation with keyboard

## Prerequisites

- Python 3.8+
- Qualys Platform credentials (Username & Password)
- Access to Qualys CloudView API

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd cspm-controls-remediation

# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt
```

> **Note:** the script loads its report styles/scripts from the `templates/` directory, which must sit next to `cspm_remediation_report.py`. Cloning the repository takes care of this automatically.

## Usage

### Basic Usage - All Clouds

```bash
python3 cspm_remediation_report.py \
  --platform US1 \
  --csp ALL \
  --policy all \
  --username <your-username> \
  --password '<your-password>' \
  --output-dir reports
```

### Cloud-Specific Reports

**AWS Only:**
```bash
python3 cspm_remediation_report.py \
  --platform US1 \
  --csp AWS \
  --policy all \
  --username <your-username> \
  --password '<your-password>'
```

**Azure Only:**
```bash
python3 cspm_remediation_report.py \
  --platform US1 \
  --csp AZURE \
  --policy all \
  --username <your-username> \
  --password '<your-password>'
```

**GCP Only:**
```bash
python3 cspm_remediation_report.py \
  --platform US1 \
  --csp GCP \
  --policy all \
  --username <your-username> \
  --password '<your-password>'
```

**OCI Only:**
```bash
python3 cspm_remediation_report.py \
  --platform US1 \
  --csp OCI \
  --policy all \
  --username <your-username> \
  --password '<your-password>'
```

### Command Line Arguments

| Argument | Short | Required | Description |
|----------|-------|----------|-------------|
| `--platform` | `-p` | Yes | Qualys platform (US1, US2, US3, US4, GOV1, EU1, EU2, EU3, IN1, CA1, AE1, UK1, AU1, KSA1) |
| `--csp` | `-c` | Yes | Cloud provider: `AWS`, `AZURE`, `GCP`, `OCI`, or `ALL` |
| `--policy` | | No | Policy filter: `all`, `system`, `custom`, or specific policy name |
| `--username` | `-u` | Yes* | Qualys username (*or use config file) |
| `--password` | `-P` | Yes* | Qualys password (*or use config file) |
| `--output-dir` | `-d` | No | Output directory (default: `reports`) |
| `--config` | `-f` | No | Config file path (`.config` or `.json`) |
| `--output` | `-o` | No | Output format: `consolidated`, `separate`, `both` |

### Using Config File

Create a `.config` file:
```
username=your-username
password=your-password
```

Or a `config.json` file:
```json
{
  "username": "your-username",
  "password": "your-password"
}
```

Then run:
```bash
python3 cspm_remediation_report.py \
  --platform US1 \
  --csp ALL \
  --config .config
```

### Using Environment Variables

Credentials can also be supplied via environment variables (useful for CI/automation, and keeps the password out of shell history):

```bash
export QUALYS_USERNAME=your-username
export QUALYS_PASSWORD=your-password
python3 cspm_remediation_report.py --platform US1 --csp ALL --policy all
```

Credential precedence: CLI arguments > config file > environment variables > interactive prompt.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `D` | Toggle dark mode |
| `E` | Export to CSV |
| `P` | Print report |
| `/` | Focus search |
| `1` | Show all controls |
| `2` | Filter high criticality |
| `3` | Filter medium criticality |
| `4` | Filter low criticality |
| `Esc` | Close modal |

## Report Features

### Sidebar Navigation
- Expand/collapse CSP sections
- Click "Show All Controls" to reset filters
- Click on any policy to filter controls by that policy

### Stats Widgets
- Dynamically update based on active filters
- Show total, high, medium, and low counts

### Controls Table
- Sortable columns (click headers)
- Click any row to view full control details
- Includes remediation steps, rationale, and references

### Control Detail Modal
- Full control information
- Manual remediation steps
- CLI/Terraform remediation (where available)
- Copy-to-clipboard functionality

## Supported Platforms

Platform names follow the official [Qualys platform identification](https://www.qualys.com/platform-identification/) page. The CloudView API used by this tool is served from the `qualysguard.*` hosts:

| Platform | URL |
|----------|-----|
| US1 | qualysguard.qualys.com |
| US2 | qualysguard.qg2.apps.qualys.com |
| US3 | qualysguard.qg3.apps.qualys.com |
| US4 | qualysguard.qg4.apps.qualys.com |
| GOV1 | qualysguard.gov1.qualys.us |
| EU1 | qualysguard.qualys.eu |
| EU2 | qualysguard.qg2.apps.qualys.eu |
| EU3 | qualysguard.qg3.apps.qualys.it |
| IN1 | qualysguard.qg1.apps.qualys.in |
| CA1 | qualysguard.qg1.apps.qualys.ca |
| AE1 | qualysguard.qg1.apps.qualys.ae |
| UK1 | qualysguard.qg1.apps.qualys.co.uk |
| AU1 | qualysguard.qg1.apps.qualys.com.au |
| KSA1 | qualysguard.qg1.apps.qualysksa.com |

## Output

Reports are generated in the specified output directory:
```
reports/
└── CSPM_Multi_Cloud_Report_YYYYMMDD_HHMMSS.html
```

For single-cloud reports:
```
reports/
└── CSPM_AWS_Report_YYYYMMDD_HHMMSS.html
```

## Troubleshooting

### Authentication Errors
- Verify username and password are correct
- Ensure your account has CloudView API access
- Check if the platform URL is correct for your subscription

### No Controls Found
- Verify you have CSPM policies configured in your Qualys subscription
- Check if the specified CSP has any policies assigned

### Connection Errors
- Check network connectivity to Qualys API
- Verify firewall rules allow HTTPS connections to Qualys endpoints
