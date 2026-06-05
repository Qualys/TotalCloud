#!/usr/bin/env python3
"""
Qualys TotalCloud CSPM Remediation Report Generator

A unified script to download and generate HTML reports for TotalCloud CSPM Controls
using Qualys CloudView APIs.

Usage:
    python3 cspm_remediation_report.py --platform US2 --csp AWS --output consolidated
    python3 cspm_remediation_report.py --platform EU1 --csp ALL --output separate --config config.json
    python3 cspm_remediation_report.py --platform US2 --csp AZURE --policy "CIS Microsoft Azure Foundations Benchmark"

License:
    THIS SCRIPT IS PROVIDED TO YOU "AS IS." TO THE EXTENT PERMITTED BY LAW, QUALYS HEREBY
    DISCLAIMS ALL WARRANTIES AND LIABILITY FOR THE PROVISION OR USE OF THIS SCRIPT.
"""

import argparse
import base64
import configparser
import datetime
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Union
from getpass import getpass

try:
    import requests
except ImportError:
    print("ERROR: 'requests' module not found. Install with: pip install requests")
    sys.exit(1)

# Version
VERSION = "2.0.0"

# Platform URL mapping
# Platform names follow https://www.qualys.com/platform-identification/
# CloudView APIs are served from the qualysguard.* hosts (the official
# qualysapi.* "API Server" hosts return 404 for /cloudview-api).
PLATFORM_URLS = {
    "US1": "https://qualysguard.qualys.com",
    "US2": "https://qualysguard.qg2.apps.qualys.com",
    "US3": "https://qualysguard.qg3.apps.qualys.com",
    "US4": "https://qualysguard.qg4.apps.qualys.com",
    "GOV1": "https://qualysguard.gov1.qualys.us",        # inferred, untested
    "EU1": "https://qualysguard.qualys.eu",
    "EU2": "https://qualysguard.qg2.apps.qualys.eu",
    "EU3": "https://qualysguard.qg3.apps.qualys.it",     # inferred, untested
    "IN1": "https://qualysguard.qg1.apps.qualys.in",
    "CA1": "https://qualysguard.qg1.apps.qualys.ca",
    "AE1": "https://qualysguard.qg1.apps.qualys.ae",
    "UK1": "https://qualysguard.qg1.apps.qualys.co.uk",
    "AU1": "https://qualysguard.qg1.apps.qualys.com.au",
    "KSA1": "https://qualysguard.qg1.apps.qualysksa.com",  # inferred, untested
    "IN": "https://qualysguard.qg1.apps.qualys.in",      # deprecated alias for IN1
}

# Supported CSPs
SUPPORTED_CSPS = ["AWS", "AZURE", "GCP", "OCI"]

# Directory holding static report assets (CSS/JS), kept next to this script
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def load_template(name: str) -> str:
    """Load a static template asset (CSS/JS) from the templates/ directory."""
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Note: System-defined policies are now fetched dynamically from the API
# based on the 'isSystemDefined' or similar field in the policy response


# =============================================================================
# Logging Functions
# =============================================================================

def log_info(message: str) -> None:
    """Log info message."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[INFO] {timestamp} - {message}")


def log_error(message: str) -> None:
    """Log error message."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[ERROR] {timestamp} - {message}")


def log_success(message: str) -> None:
    """Log success message."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[SUCCESS] {timestamp} - {message}")


def log_warn(message: str) -> None:
    """Log warning message."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[WARNING] {timestamp} - {message}")


# =============================================================================
# Authentication
# =============================================================================

def get_auth_header(username: str, password: str) -> Dict[str, str]:
    """Generate Basic Auth header."""
    auth = f"{username}:{password}"
    b64_auth = base64.b64encode(auth.encode()).decode("utf-8")
    return {"Authorization": f"Basic {b64_auth}"}


def load_credentials(config_file: Optional[str] = None, 
                     username: Optional[str] = None, 
                     password: Optional[str] = None) -> Tuple[str, str]:
    """Load credentials from CLI args, config file, environment, or prompt."""

    # Priority: CLI args > config file > environment variables > prompt
    if username and password:
        return username, password

    if config_file and os.path.exists(config_file):
        if config_file.endswith('.json'):
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('username', ''), config.get('password', '')
        else:
            config = configparser.ConfigParser()
            config.read(config_file)
            return config.get('creds', 'username', fallback=''), config.get('creds', 'password', fallback='')

    env_username = os.environ.get('QUALYS_USERNAME')
    env_password = os.environ.get('QUALYS_PASSWORD')
    if env_username and env_password:
        log_info("Using credentials from QUALYS_USERNAME/QUALYS_PASSWORD environment variables.")
        return env_username, env_password

    # Prompt for credentials
    log_info("Credentials not provided. Please enter manually.")
    username = input("Username: ")
    password = getpass("Password: ")
    return username, password


# =============================================================================
# API Functions
# =============================================================================

def api_request(url: str, headers: Dict[str, str], method: str = "GET",
                retries: int = 3, timeout: int = 60) -> requests.Response:
    """Make API request with retry logic and exponential backoff.

    Retries on timeouts, connection errors, HTTP 429 and 5xx responses.
    """
    response = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.request(method, url, headers=headers, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                log_warn(f"API returned status {response.status_code} (attempt {attempt}/{retries})")
            else:
                return response
        except requests.exceptions.Timeout:
            log_warn(f"Request timeout (attempt {attempt}/{retries})")
        except requests.exceptions.ConnectionError as e:
            log_warn(f"Connection error (attempt {attempt}/{retries}): {e}")
        except requests.exceptions.RequestException as e:
            log_error(f"Request failed: {e}")
            raise
        if attempt < retries:
            wait = 2 ** attempt
            log_info(f"Retrying in {wait}s...")
            time.sleep(wait)

    if response is not None:
        # Exhausted retries on a retryable HTTP status; let the caller see it
        return response
    raise requests.exceptions.RequestException(f"Failed after {retries} attempts")


def fetch_controls_paginated(platform_url: str, headers: Dict[str, str],
                             filter_expr: str, page_size: int) -> Optional[Dict]:
    """Fetch all controls matching a filter, paging until exhausted.

    Increments pageNo on the original (filtered) URL rather than following the
    API's warning.url, which drops the filter parameter. Continues while a page
    comes back full or the API warns that more records exist.
    """
    all_controls: List[Dict] = []
    page_no = 0
    while True:
        url = (f"{platform_url}/cloudview-api/rest/v1/controls/metadata/list"
               f"?filter={filter_expr}&pageNo={page_no}&pageSize={page_size}")
        response = api_request(url, headers)

        if response.status_code != 200:
            log_error(f"API returned status {response.status_code}: {response.text}")
            return None

        data = response.json()
        if "errorCode" in data or "error" in data:
            log_error(f"API error: {data}")
            return None

        controls = data.get('control', [])
        all_controls.extend(controls)

        if len(controls) < page_size and "warning" not in data:
            break
        if not controls:
            break
        page_no += 1

    return {"control": all_controls}


def get_controls_metadata(platform_url: str, headers: Dict[str, str],
                          csp: str, page_size: int = 1000) -> Optional[Dict]:
    """Fetch controls metadata for a CSP."""
    log_info(f"Fetching controls metadata for {csp}...")
    data = fetch_controls_paginated(platform_url, headers,
                                    f"provider%3A{csp}", page_size)
    if data is None:
        return None

    control_count = len(data.get('control', []))
    log_success(f"Retrieved {control_count} controls for {csp}")
    return data


def get_policies(platform_url: str, headers: Dict[str, str], csp: str) -> Optional[Dict]:
    """Fetch policies for a CSP dynamically from the API."""
    url = f"{platform_url}/cloudview-api/rest/v1/reports/policies?cloudType={csp}"
    
    log_info(f"Fetching policies for {csp} from API...")
    response = api_request(url, headers)
    
    if response.status_code != 200:
        log_error(f"API returned status {response.status_code}: {response.text}")
        return None
    
    data = response.json()
    if isinstance(data, dict) and ("errorCode" in data or "error" in data):
        log_error(f"API error: {data}")
        return None
    
    # Dynamically categorize policies from API response
    system_policies = []
    custom_policies = []
    all_policies = []
    
    if isinstance(data, list):
        for policy in data:
            title = policy.get('title', '')
            if not title:
                continue
            
            all_policies.append(title)
            
            # Check if policy is system-defined based on API fields
            # Common indicators: 'isSystemDefined', 'type', 'source', or naming patterns
            is_system = policy.get('isSystemDefined', False)
            policy_type = policy.get('type', '').lower()
            
            # Also check naming patterns for system policies
            system_patterns = [
                'Best Practices Policy',
                'CIS ',
                'NIST ',
                'SOC ',
                'PCI ',
                'HIPAA',
                'ISO ',
                'GDPR',
                'FedRAMP'
            ]
            
            is_system_by_name = any(pattern in title for pattern in system_patterns)
            
            if is_system or policy_type == 'system' or is_system_by_name:
                system_policies.append(title)
            else:
                custom_policies.append(title)
    
    log_success(f"Found {len(system_policies)} system policies and {len(custom_policies)} custom policies for {csp}")
    log_info(f"System policies: {', '.join(system_policies[:3])}{'...' if len(system_policies) > 3 else ''}")
    
    return {
        "system_defined": system_policies,
        "custom": custom_policies,
        "all": all_policies
    }


def get_policy_controls(platform_url: str, headers: Dict[str, str],
                        policy_name: str, page_size: int = 100) -> Optional[Dict]:
    """Fetch controls for a specific policy."""
    # URL encode the policy name
    encoded_policy = requests.utils.quote(policy_name)

    log_info(f"Fetching controls for policy: {policy_name}...")
    data = fetch_controls_paginated(platform_url, headers,
                                    f"policy.name%3A{encoded_policy}", page_size)
    if data is None:
        return None

    control_count = len(data.get('control', []))
    log_success(f"Retrieved {control_count} controls for policy: {policy_name}")
    return data


# =============================================================================
# HTML Generation
# =============================================================================

def get_html_header(title: str) -> str:
    """Generate HTML header with modern styling."""
    css = load_template('consolidated_report.css')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
{css}
    </style>
</head>
<body>
<div class="container">
'''


def get_html_footer() -> str:
    """Generate HTML footer."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f'''
    <a href="#top" class="back-to-top" title="Back to top">↑</a>
    <div class="footer">
        <div class="logo">Qualys CSPM</div>
        <p>Report generated by Qualys CSPM Remediation Report Generator v{VERSION}</p>
        <p>Generated at: {timestamp}</p>
    </div>
</div>
</body>
</html>
'''


def format_field_name(field: str) -> str:
    """Convert camelCase to Title Case."""
    result = []
    for i, char in enumerate(field):
        if char.isupper() and i > 0:
            result.append(' ')
        result.append(char)
    return ''.join(result).title()


def format_evaluation(evaluation: Dict) -> str:
    """Format evaluation dict as HTML list."""
    if not evaluation:
        return "N/A"
    
    items = []
    for key, value in evaluation.items():
        if value:
            items.append(f"<li><strong>{key}:</strong> {value}</li>")
    
    if items:
        return f"<ul>{''.join(items)}</ul>"
    return "N/A"


def generate_control_html(control: Dict) -> str:
    """Generate HTML for a single control."""
    cid = control.get('cid', 'N/A')
    name = control.get('controlName', 'Unknown Control')
    criticality = control.get('criticality', 'N/A')
    control_type = control.get('controlType', 'N/A')
    provider = control.get('provider', 'N/A')
    resource_type = control.get('resourceType', 'N/A')
    service = control.get('service', 'N/A')
    category = control.get('category', 'N/A')
    rationale = control.get('rationale', '')
    manual_remediation = control.get('manualRemediation', '')
    build_remediation = control.get('buildTimeRemediation', '')
    cli_remediation = control.get('cliRemediation', '')
    
    # Criticality badge class
    crit_class = f"badge-{criticality.lower()}" if criticality else "badge-medium"
    
    html = f'''
    <div class="control" id="cid-{cid}">
        <div class="control-header">
            <h3>{name}</h3>
            <span class="cid-badge">CID-{cid}</span>
        </div>
        <div class="control-body">
            <div class="control-grid">
                <div class="field">
                    <div class="field-label">Control ID</div>
                    <div class="field-value">{cid}</div>
                </div>
                <div class="field">
                    <div class="field-label">Criticality</div>
                    <div class="field-value criticality-{criticality}">{criticality}</div>
                </div>
                <div class="field">
                    <div class="field-label">Control Type</div>
                    <div class="field-value">{control_type}</div>
                </div>
                <div class="field">
                    <div class="field-label">Cloud Provider</div>
                    <div class="field-value">{provider}</div>
                </div>
                <div class="field">
                    <div class="field-label">Resource Type</div>
                    <div class="field-value">{resource_type}</div>
                </div>
                <div class="field">
                    <div class="field-label">Service</div>
                    <div class="field-value">{service}</div>
                </div>
                <div class="field">
                    <div class="field-label">Category</div>
                    <div class="field-value">{category}</div>
                </div>
            </div>
    '''
    
    # Add rationale if present
    if rationale:
        html += f'''
            <div class="field" style="margin-top: 20px; grid-column: 1 / -1;">
                <div class="field-label">Rationale</div>
                <div class="field-value">{rationale}</div>
            </div>
        '''
    
    # Add remediation sections
    if manual_remediation or build_remediation or cli_remediation:
        html += '<div style="margin-top: 20px;">'
        
        if manual_remediation:
            html += f'''
            <div class="remediation-section">
                <h4>Manual Remediation</h4>
                <div class="content">{manual_remediation}</div>
            </div>
            '''
        
        if cli_remediation:
            html += f'''
            <div class="remediation-section" style="margin-top: 15px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-color: #93c5fd;">
                <h4 style="color: #1e40af;">CLI Remediation</h4>
                <div class="content" style="color: #1d4ed8; font-family: monospace; white-space: pre-wrap;">{cli_remediation}</div>
            </div>
            '''
        
        if build_remediation:
            html += f'''
            <div class="remediation-section" style="margin-top: 15px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-color: #fcd34d;">
                <h4 style="color: #92400e;">Build-Time Remediation</h4>
                <div class="content" style="color: #b45309;">{build_remediation}</div>
            </div>
            '''
        
        html += '</div>'
    
    html += '''
        </div>
    </div>
    '''
    
    return html


def generate_consolidated_html(controls_data: Dict, csp: str, output_dir: str, 
                               policy_name: Optional[str] = None) -> str:
    """Generate a single HTML file with all controls."""
    controls = controls_data.get('control', [])
    
    if not controls:
        log_warn(f"No controls found for {csp}")
        return ""
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if policy_name:
        filename = f"{csp}_{policy_name.replace(' ', '_')}_{timestamp}.html"
        title = f"{csp} - {policy_name} - CSPM Controls"
    else:
        filename = f"{csp}_All_Controls_{timestamp}.html"
        title = f"{csp} - All CSPM Controls"
    
    filepath = os.path.join(output_dir, filename)
    
    # Count criticality levels
    high_count = sum(1 for c in controls if c.get('criticality', '').upper() == 'HIGH')
    medium_count = sum(1 for c in controls if c.get('criticality', '').upper() == 'MEDIUM')
    low_count = sum(1 for c in controls if c.get('criticality', '').upper() == 'LOW')
    
    # Build HTML
    html = get_html_header(title)
    
    # Header section
    html += f'''
    <div class="header" id="top">
        <h1>Qualys CloudView CSPM Controls</h1>
        <p class="subtitle">{csp} Security Controls & Remediation Guide</p>
        <div class="meta">
            <div class="meta-item">
                <strong>Cloud Provider</strong>
                <span>{csp}</span>
            </div>
            <div class="meta-item">
                <strong>Total Controls</strong>
                <span>{len(controls)}</span>
            </div>
            {f'<div class="meta-item"><strong>Policy</strong><span>{policy_name}</span></div>' if policy_name else ''}
            <div class="meta-item">
                <strong>Generated</strong>
                <span>{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
            </div>
        </div>
    </div>
    '''
    
    # Stats section
    html += f'''
    <div class="stats">
        <div class="stat-card">
            <div class="number">{len(controls)}</div>
            <div class="label">Total Controls</div>
        </div>
        <div class="stat-card high">
            <div class="number">{high_count}</div>
            <div class="label">High Criticality</div>
        </div>
        <div class="stat-card medium">
            <div class="number">{medium_count}</div>
            <div class="label">Medium Criticality</div>
        </div>
        <div class="stat-card low">
            <div class="number">{low_count}</div>
            <div class="label">Low Criticality</div>
        </div>
    </div>
    '''
    
    # Search box
    html += '''
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 Search controls by name, CID, or keyword..." onkeyup="filterControls()">
    </div>
    <script>
    function filterControls() {
        const input = document.getElementById('searchInput').value.toLowerCase();
        const controls = document.querySelectorAll('.control');
        const indexItems = document.querySelectorAll('.index-item');
        
        controls.forEach(control => {
            const text = control.textContent.toLowerCase();
            control.style.display = text.includes(input) ? 'block' : 'none';
        });
        
        indexItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(input) ? 'flex' : 'none';
        });
    }
    </script>
    '''
    
    # Index section
    html += '''
    <div class="index">
        <h2>Control Index</h2>
        <div class="index-grid">
    '''
    
    for control in controls:
        cid = control.get('cid', 'N/A')
        name = control.get('controlName', 'Unknown')
        criticality = control.get('criticality', 'N/A')
        crit_lower = criticality.lower() if criticality else 'medium'
        html += f'''<a href="#cid-{cid}" class="index-item">
            <span class="cid">CID-{cid}</span>
            <span class="name">{name}</span>
            <span class="badge badge-{crit_lower}">{criticality}</span>
        </a>
        '''
    
    html += '''
        </div>
    </div>
    '''
    
    # Controls section
    log_info(f"Generating HTML for {len(controls)} controls...")
    for i, control in enumerate(controls):
        html += generate_control_html(control)
        # Progress indicator
        if (i + 1) % 50 == 0:
            log_info(f"Processed {i + 1}/{len(controls)} controls...")
    
    html += get_html_footer()
    
    # Write file
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    log_success(f"Generated: {filepath}")
    return filepath


def generate_separate_html(controls_data: Dict, csp: str, output_dir: str) -> List[str]:
    """Generate separate HTML files for each control."""
    controls = controls_data.get('control', [])
    
    if not controls:
        log_warn(f"No controls found for {csp}")
        return []
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csp_dir = os.path.join(output_dir, csp, "controls")
    os.makedirs(csp_dir, exist_ok=True)
    
    generated_files = []
    
    log_info(f"Generating {len(controls)} separate HTML files for {csp}...")
    
    for i, control in enumerate(controls):
        cid = control.get('cid', 'N/A')
        name = control.get('controlName', 'Unknown')
        
        filename = f"CID_{cid}_{timestamp}.html"
        filepath = os.path.join(csp_dir, filename)
        
        title = f"CID-{cid}: {name}"
        
        html = get_html_header(title)
        html += f'''
        <div class="header">
            <h1>Qualys CloudView CSPM Control</h1>
            <div class="meta">
                <p>Cloud Provider: {csp}</p>
                <p>Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
        </div>
        '''
        html += generate_control_html(control)
        html += get_html_footer()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        generated_files.append(filepath)
        
        # Progress indicator
        if (i + 1) % 50 == 0:
            log_info(f"Generated {i + 1}/{len(controls)} files...")
    
    log_success(f"Generated {len(generated_files)} files in {csp_dir}")
    return generated_files


# =============================================================================
# Main Functions
# =============================================================================

def process_all_controls(platform_url: str, headers: Dict[str, str], 
                         csps: List[str], output_type: str, output_dir: str) -> bool:
    """Process all controls for given CSPs."""
    fetch_ok = True
    any_data = False
    for csp in csps:
        controls_data = get_controls_metadata(platform_url, headers, csp)

        if not controls_data:
            log_error(f"Failed to fetch controls for {csp}")
            fetch_ok = False
            continue
        any_data = True

        # Save raw JSON response
        json_dir = os.path.join(output_dir, "json")
        os.makedirs(json_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = os.path.join(json_dir, f"{csp}_controls_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(controls_data, f, indent=2)
        log_info(f"Saved JSON: {json_file}")
        
        # Generate HTML
        if output_type == "consolidated":
            generate_consolidated_html(controls_data, csp, output_dir)
        elif output_type == "separate":
            generate_separate_html(controls_data, csp, output_dir)
        else:
            # Both
            generate_consolidated_html(controls_data, csp, output_dir)
            generate_separate_html(controls_data, csp, output_dir)

    if not fetch_ok and any_data:
        log_warn("Reports were written, but some API fetches failed; data may be incomplete.")
    return any_data and fetch_ok


def generate_multi_csp_report(platform_url: str, headers: Dict[str, str],
                              csps: List[str], policy_filter: str,
                              output_dir: str) -> Tuple[Optional[str], bool]:
    """Generate a single HTML with all CSPs, policies, and controls with tabbed navigation.

    Returns (filepath, fetch_ok). filepath is None when no data could be
    fetched at all; fetch_ok is False when any fetch failed.
    """

    log_info(f"Building multi-CSP report for {', '.join(csps)}...")

    # Fetch all data for all CSPs
    all_csp_data = {}  # {csp: {policy_name: [controls]}}
    all_controls_by_csp = {}  # {csp: [all_controls]} for "All Controls" tab
    fetch_ok = True

    for csp in csps:
        policies_data = get_policies(platform_url, headers, csp)
        if not policies_data:
            log_error(f"Failed to fetch policies for {csp}")
            fetch_ok = False
            continue

        # Determine which policies to process
        if policy_filter == "all":
            policies_to_process = policies_data['all']
        elif policy_filter == "system":
            policies_to_process = policies_data['system_defined']
        elif policy_filter == "custom":
            policies_to_process = policies_data['custom']
        else:
            policies_to_process = [policy_filter]

        all_csp_data[csp] = {}
        all_controls_by_csp[csp] = []

        # Also fetch all controls for "All Controls" tab
        all_controls_data = get_controls_metadata(platform_url, headers, csp)
        if all_controls_data:
            all_controls_by_csp[csp] = all_controls_data.get('control', [])
        else:
            fetch_ok = False

        for policy_name in policies_to_process:
            controls_data = get_policy_controls(platform_url, headers, policy_name)
            if controls_data:
                controls = controls_data.get('control', [])
                all_csp_data[csp][policy_name] = controls
            else:
                fetch_ok = False

    if not any(all_csp_data.values()) and not any(all_controls_by_csp.values()):
        log_error("No data could be fetched from the API; skipping report generation.")
        return None, False

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"CSPM_Multi_Cloud_Report_{timestamp}.html"
    filepath = os.path.join(output_dir, filename)
    
    # Calculate stats
    total_policies = sum(len(policies) for policies in all_csp_data.values())
    total_controls = sum(len(controls) for csp_data in all_csp_data.values() for controls in csp_data.values())
    
    # Build HTML
    multi_csp_css = load_template('multi_csp_report.css')
    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CSPM Multi-Cloud Controls Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
{multi_csp_css}
    </style>
</head>
<body>
    <!-- Top Navigation -->
    <nav class="top-nav">
        <div class="logo">
            <span>📋</span>
            <span>Qualys CSPM Controls</span>
        </div>
        <div class="search">
            <input type="text" id="globalSearch" placeholder="Search controls... (Press / to focus)" onkeyup="globalFilter()">
        </div>
        <div class="top-nav-actions">
            <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark mode (D)">
                <span id="themeIcon">🌙</span>
                <span>Dark</span>
                <span class="kbd">D</span>
            </button>
            <button class="export-btn" onclick="exportCSV()" title="Export to CSV (E)">
                📥 Export CSV
                <span class="kbd">E</span>
            </button>
            <button class="export-btn" onclick="window.print()" title="Print report (P)">
                🖨️ Print
                <span class="kbd">P</span>
            </button>
        </div>
    </nav>
    
    <!-- CSP Tabs -->
    <div class="csp-tabs">
        <div class="csp-tab active" data-csp="all" onclick="switchCSP('all')">
            <span>🌐 All Clouds</span>
            <span class="count">{sum(len(c) for c in all_controls_by_csp.values())}</span>
        </div>
'''
    
    # Add CSP tabs
    for csp in csps:
        if csp in all_controls_by_csp:
            csp_lower = csp.lower()
            icon = "☁️" if csp == "AWS" else "🔷" if csp == "AZURE" else "🔶" if csp == "GCP" else "🔴"
            html += f'''
        <div class="csp-tab {csp_lower}" data-csp="{csp}" onclick="switchCSP('{csp}')">
            <span>{icon} {csp}</span>
            <span class="count">{len(all_controls_by_csp.get(csp, []))}</span>
        </div>
'''
    
    html += '''
    </div>
    
    <div class="main-layout">
        <!-- Sidebar -->
        <aside class="sidebar" id="sidebar">
'''
    
    # Add sidebar sections for each CSP
    for csp in csps:
        if csp not in all_csp_data:
            continue
        csp_lower = csp.lower()
        html += f'''
            <div class="sidebar-section expanded" data-csp="{csp}">
                <div class="sidebar-section-header" onclick="toggleSection(this)">
                    <span>📁 {csp} Policies</span>
                    <span style="margin-left:auto; font-size:0.8rem; color:var(--gray-400);">{len(all_csp_data[csp])} policies</span>
                </div>
                <div class="policy-item" data-csp="{csp}">
                    <div class="policy-header show-all" onclick="showAllControls('{csp}')" style="background: var(--gray-200); font-weight: 600;">
                        <span class="name">📋 Show All Controls</span>
                        <span class="count">{len(all_controls_by_csp.get(csp, []))}</span>
                    </div>
                </div>
'''
        for policy_name, controls in all_csp_data[csp].items():
            policy_id = f"{csp}_{policy_name}".replace(' ', '_').replace("'", "").replace('"', '').replace('~', '').replace('!', '').replace('@', '').replace('#', '').replace('$', '')
            html += f'''
                <div class="policy-item" data-csp="{csp}">
                    <div class="policy-header" data-policy="{policy_id}" onclick="showPolicyControls('{csp}', '{policy_id}')">
                        <span class="name">{policy_name}</span>
                        <span class="count">{len(controls)}</span>
                    </div>
                </div>
'''
        html += '''
            </div>
'''
    
    html += '''
        </aside>
        
        <!-- Content Area -->
        <main class="content">
'''
    
    # Add "All Controls" panel
    html += f'''
            <div class="content-panel active" id="panel-all">
                <h2 style="margin-bottom:20px;">All Cloud Controls</h2>
                <div class="stats">
'''
    for csp in csps:
        if csp in all_controls_by_csp:
            csp_lower = csp.lower()
            html += f'''
                    <div class="stat-card {csp_lower}">
                        <div class="number">{len(all_controls_by_csp[csp])}</div>
                        <div class="label">{csp} Controls</div>
                    </div>
'''
    
    # Add criticality stats
    all_high = sum(1 for csp_controls in all_controls_by_csp.values() for c in csp_controls if c.get('criticality', '').upper() == 'HIGH')
    all_medium = sum(1 for csp_controls in all_controls_by_csp.values() for c in csp_controls if c.get('criticality', '').upper() == 'MEDIUM')
    all_low = sum(1 for csp_controls in all_controls_by_csp.values() for c in csp_controls if c.get('criticality', '').upper() == 'LOW')
    
    total_all = all_high + all_medium + all_low
    high_pct = (all_high / total_all * 100) if total_all > 0 else 0
    medium_pct = (all_medium / total_all * 100) if total_all > 0 else 0
    low_pct = (all_low / total_all * 100) if total_all > 0 else 0
    
    html += f'''
                    <div class="stat-card high">
                        <div class="number">{all_high}</div>
                        <div class="label">High</div>
                    </div>
                    <div class="stat-card medium">
                        <div class="number">{all_medium}</div>
                        <div class="label">Medium</div>
                    </div>
                    <div class="stat-card low">
                        <div class="number">{all_low}</div>
                        <div class="label">Low</div>
                    </div>
                </div>
                
                <!-- Progress Chart -->
                <div class="progress-chart" title="Criticality Distribution">
                    <div class="progress-segment high" style="width: {high_pct:.1f}%"></div>
                    <div class="progress-segment medium" style="width: {medium_pct:.1f}%"></div>
                    <div class="progress-segment low" style="width: {low_pct:.1f}%"></div>
                </div>
                
                <!-- Filter Pills -->
                <div class="filter-pills" style="margin-top: 20px;">
                    <button class="filter-pill active" onclick="filterByCriticality('all')" data-filter="all">
                        All <span class="count">{total_all}</span>
                    </button>
                    <button class="filter-pill" onclick="filterByCriticality('high')" data-filter="high">
                        🔴 High <span class="count">{all_high}</span>
                    </button>
                    <button class="filter-pill" onclick="filterByCriticality('medium')" data-filter="medium">
                        🟡 Medium <span class="count">{all_medium}</span>
                    </button>
                    <button class="filter-pill" onclick="filterByCriticality('low')" data-filter="low">
                        🟢 Low <span class="count">{all_low}</span>
                    </button>
                </div>
                
                <div class="controls-table">
                    <table id="controlsTable">
                        <thead>
                            <tr>
                                <th onclick="sortTable(0)">CID <span class="sort-indicator">↕</span></th>
                                <th onclick="sortTable(1)">Control Name <span class="sort-indicator">↕</span></th>
                                <th onclick="sortTable(2)">CSP <span class="sort-indicator">↕</span></th>
                                <th onclick="sortTable(3)">Service <span class="sort-indicator">↕</span></th>
                                <th onclick="sortTable(4)">Resource Type <span class="sort-indicator">↕</span></th>
                                <th onclick="sortTable(5)">Criticality <span class="sort-indicator">↕</span></th>
                            </tr>
                        </thead>
                        <tbody>
'''
    
    # Add all controls to table
    for csp in csps:
        if csp not in all_controls_by_csp:
            continue
        csp_lower = csp.lower()
        for control in all_controls_by_csp[csp]:
            cid = control.get('cid', 'N/A')
            name = control.get('controlName', 'Unknown')[:60]
            service = control.get('serviceType', 'N/A')
            resource = control.get('resourceType', 'N/A')
            criticality = control.get('criticality', 'N/A')
            crit_lower = criticality.lower() if criticality else 'medium'
            
            html += f'''
                            <tr onclick="showControlDetail('{csp}', '{cid}')" data-csp="{csp}" data-criticality="{crit_lower}">
                                <td class="cid">CID-{cid}</td>
                                <td>{name}</td>
                                <td><span class="badge badge-{csp_lower}">{csp}</span></td>
                                <td>{service}</td>
                                <td>{resource}</td>
                                <td><span class="badge badge-{crit_lower}">{criticality}</span></td>
                            </tr>
'''
    
    html += '''
                        </tbody>
                    </table>
                </div>
            </div>
'''
    
    # Add CSP-specific panels
    for csp in csps:
        if csp not in all_controls_by_csp:
            continue
        csp_lower = csp.lower()
        csp_high = sum(1 for c in all_controls_by_csp[csp] if c.get('criticality', '').upper() == 'HIGH')
        csp_medium = sum(1 for c in all_controls_by_csp[csp] if c.get('criticality', '').upper() == 'MEDIUM')
        csp_low = sum(1 for c in all_controls_by_csp[csp] if c.get('criticality', '').upper() == 'LOW')
        
        html += f'''
            <div class="content-panel" id="panel-{csp}">
                <h2 style="margin-bottom:20px;">{csp} Controls</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="number">{len(all_controls_by_csp[csp])}</div>
                        <div class="label">Total Controls</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{len(all_csp_data.get(csp, dict()))}</div>
                        <div class="label">Policies</div>
                    </div>
                    <div class="stat-card high">
                        <div class="number">{csp_high}</div>
                        <div class="label">High</div>
                    </div>
                    <div class="stat-card medium">
                        <div class="number">{csp_medium}</div>
                        <div class="label">Medium</div>
                    </div>
                    <div class="stat-card low">
                        <div class="number">{csp_low}</div>
                        <div class="label">Low</div>
                    </div>
                </div>
                
                <!-- Filter Pills for {csp} -->
                <div class="filter-pills" style="margin-top: 20px;">
                    <button class="filter-pill active" onclick="filterByCriticality('all')" data-filter="all">
                        All <span class="count">{len(all_controls_by_csp[csp])}</span>
                    </button>
                    <button class="filter-pill" onclick="filterByCriticality('high')" data-filter="high">
                        🔴 High <span class="count">{csp_high}</span>
                    </button>
                    <button class="filter-pill" onclick="filterByCriticality('medium')" data-filter="medium">
                        🟡 Medium <span class="count">{csp_medium}</span>
                    </button>
                    <button class="filter-pill" onclick="filterByCriticality('low')" data-filter="low">
                        🟢 Low <span class="count">{csp_low}</span>
                    </button>
                </div>
                
                <div class="controls-table">
                    <table>
                        <thead>
                            <tr>
                                <th>CID</th>
                                <th>Control Name</th>
                                <th>Service</th>
                                <th>Resource Type</th>
                                <th>Control Type</th>
                                <th>Criticality</th>
                            </tr>
                        </thead>
                        <tbody>
'''
        for control in all_controls_by_csp[csp]:
            cid = control.get('cid', 'N/A')
            name = control.get('controlName', 'Unknown')[:60]
            service = control.get('serviceType', 'N/A')
            resource = control.get('resourceType', 'N/A')
            control_type = control.get('controlType', 'N/A')
            criticality = control.get('criticality', 'N/A')
            crit_lower = criticality.lower() if criticality else 'medium'
            
            html += f'''
                            <tr onclick="showControlDetail('{csp}', '{cid}')" data-criticality="{crit_lower}">
                                <td class="cid">CID-{cid}</td>
                                <td>{name}</td>
                                <td>{service}</td>
                                <td>{resource}</td>
                                <td>{control_type}</td>
                                <td><span class="badge badge-{crit_lower}">{criticality}</span></td>
                            </tr>
'''
        html += '''
                        </tbody>
                    </table>
                </div>
            </div>
'''
    
    html += '''
        </main>
    </div>
    
    <!-- Control Detail Modal -->
    <div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <button class="modal-close" onclick="closeModal()">&times;</button>
                <h2 id="modalTitle">Control Details</h2>
                <div class="meta" id="modalMeta"></div>
            </div>
            <div class="modal-body" id="modalBody"></div>
        </div>
    </div>
    
    <script>
        // Store all control data
        const controlsData = {
'''
    
    # Add control data as JSON
    for csp in csps:
        if csp not in all_controls_by_csp:
            continue
        html += f'            "{csp}": {{\n'
        for control in all_controls_by_csp[csp]:
            cid = control.get('cid', 'N/A')
            # Escape special characters in JSON
            control_json = json.dumps(control).replace('</script>', '<\\/script>')
            html += f'                "{cid}": {control_json},\n'
        html += '            },\n'
    
    html += load_template('multi_csp_report.js')
    
    # Write file
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    log_success(f"Generated multi-CSP report: {filepath}")
    return filepath, fetch_ok


def process_policy_controls(platform_url: str, headers: Dict[str, str],
                            csps: List[str], policy_filter: str,
                            output_dir: str) -> bool:
    """Process controls for specific policies - generates single multi-CSP HTML."""
    # Generate single multi-CSP report with all policies and controls
    filepath, fetch_ok = generate_multi_csp_report(platform_url, headers, csps,
                                                   policy_filter, output_dir)
    if filepath and not fetch_ok:
        log_warn("Report was written, but some API fetches failed; data may be incomplete.")
    return filepath is not None and fetch_ok


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Qualys TotalCloud CSPM Remediation Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --platform US2 --csp AWS
  %(prog)s --platform EU1 --csp ALL --output separate
  %(prog)s --platform US2 --csp AZURE --policy system
  %(prog)s --platform US2 --csp GCP --policy "CIS Google Cloud Platform Foundation Benchmark"
  %(prog)s --platform US2 --csp AWS --config config.json
        """
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    
    parser.add_argument('--platform', '-p', required=True, 
                        choices=list(PLATFORM_URLS.keys()),
                        help='Qualys platform (e.g., US1, US2, EU1)')
    
    parser.add_argument('--csp', '-c', required=True,
                        help='Cloud provider: AWS, AZURE, GCP, or ALL')
    
    parser.add_argument('--output', '-o', default='consolidated',
                        choices=['consolidated', 'separate', 'both'],
                        help='Output format (default: consolidated)')
    
    parser.add_argument('--policy', 
                        help='Policy filter: all, system, custom, or specific policy name')
    
    parser.add_argument('--config', '-f',
                        help='Config file path (.config or .json)')
    
    parser.add_argument('--username', '-u',
                        help='Qualys username')
    
    parser.add_argument('--password', '-P',
                        help='Qualys password')
    
    parser.add_argument('--output-dir', '-d', default='reports',
                        help='Output directory (default: reports)')
    
    args = parser.parse_args()
    
    # Banner
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  Qualys TotalCloud CSPM Remediation Report Generator v{VERSION}     ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    # Validate CSP
    csp_input = args.csp.upper()
    if csp_input == "ALL":
        csps = SUPPORTED_CSPS
    else:
        csps = [c.strip().upper() for c in csp_input.split(',')]
        for csp in csps:
            if csp not in SUPPORTED_CSPS:
                log_error(f"Invalid CSP: {csp}. Supported: {SUPPORTED_CSPS}")
                sys.exit(1)
    
    # Get platform URL
    platform_url = PLATFORM_URLS[args.platform]
    log_info(f"Platform: {args.platform} ({platform_url})")
    log_info(f"CSP(s): {', '.join(csps)}")
    log_info(f"Output: {args.output}")
    
    # Load credentials
    username, password = load_credentials(args.config, args.username, args.password)
    
    if not username or not password:
        log_error("Credentials are required.")
        sys.exit(1)
    
    headers = get_auth_header(username, password)
    
    # Create output directory
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    # Process based on mode
    if args.policy:
        success = process_policy_controls(platform_url, headers, csps, 
                                          args.policy, output_dir)
    else:
        success = process_all_controls(platform_url, headers, csps, 
                                       args.output, output_dir)
    
    if success:
        log_success("Report generation complete!")
        log_info(f"Output directory: {os.path.abspath(output_dir)}")
    else:
        log_error("Report generation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
