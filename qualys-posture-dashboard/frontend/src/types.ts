export type Csp = 'AWS' | 'AZURE' | 'GCP' | 'KUBERNETES'
export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFORMATIONAL'
export type ResourceStatus = 'NEW' | 'REOPENED' | 'EXISTING' | 'FIXED'

export interface AccountRef { account: string; csp: Csp; name?: string | null }

/** The full filter set shared by both views + the quick-filter rail. Empty string = unset. */
export interface Filters {
  cloud: string
  account: string
  severity: string
  service: string
  policy: string    // Qualys policy / compliance framework (e.g. CIS…)
  rtype: string     // resource type (resources view)
  region: string    // resources view
  status: string    // NEW / REOPENED / EXISTING (resources view)
  result: string    // '' (all) | 'fail' | 'pass' (resources view)
  q: string         // free-text search
  as_of: string     // snapshot date (time-travel); '' = latest
}

export const EMPTY_FILTERS: Filters = {
  cloud: '', account: '', severity: '', service: '', policy: '', rtype: '', region: '', status: '', result: '', q: '', as_of: '',
}

export interface Status {
  creds_set: boolean
  gateway_url: string | null
  username: string | null
  last_sync: string | null
  last_sync_accounts: string | null
  demo_mode: boolean
  latest_snapshot: string | null
  accounts: AccountRef[]
  dates: string[]
  syncing: boolean
  sync_progress: string | null
}

export interface Remediation {
  manual: string
  cli: string
  buildtime: string
  rationale: string
  specification: string
  references: string
}

export interface Schedule {
  enabled: boolean
  mode: 'daily' | 'interval'
  time: string   // HH:MM (daily mode)
  hours: number  // interval mode
}

export interface Facets {
  dates: string[]
  services: string[]
  resource_types: string[]
  regions: string[]
  policies: string[]
  accounts: AccountRef[]
}

export interface TrendPoint { date: string; passed: number; failed: number }

export interface ControlRow {
  control_id: string
  csp: Csp
  control_name: string
  criticality: Severity
  service: string
  passed: number
  failed: number
  total: number
  accounts: number
  policies: string[]
  trend: { date: string; failed: number; passed: number }[]
}

export interface Evidence { settingName: string; actualValue: string }

export interface ResourceControlHit {
  control_id: string
  control_name: string
  criticality: Severity
  result?: 'PASS' | 'FAIL'
  evidence: Evidence[]
  first_evaluated: string | null
  last_evaluated: string | null
  date_reopen: string | null
  prev_result: string | null
  is_new: boolean
  is_reopened: boolean
  tags: string        // CLOUD provider resource tags, "key=value; key=value" ('' when untagged)
  qualys_tags: string // QUALYS asset tag names, "name; name" — a different source, kept separate
}

export interface ResourceRow {
  uid: string
  resource_id: string
  resource_type: string | null
  region: string | null
  csp: Csp
  account: string
  account_name: string | null
  severity_mix: Record<Severity, number>
  services: string[]
  policies: string[]
  first_seen: string | null
  last_seen: string | null
  date_fixed: string | null
  date_reopen: string | null
  is_new: boolean
  is_reopened: boolean
  top_severity: Severity | null
  result: 'PASS' | 'FAIL'
  failing_controls: number
  passing_controls: number
  total_controls: number
  status: ResourceStatus
  evidence_summary: string | null
  top_control_id: string | null    // most-severe failing control — drives the inline Remediation cell
  top_control_name: string | null
  tags: string        // CLOUD provider resource tags, "key=value; key=value" ('' when untagged)
  qualys_tags: string // QUALYS asset tag names, "name; name" — a different source, kept separate
}

export interface ResourceStats {
  failing_resources: number
  passing_resources: number
  total_resources: number
  new_30d: number
  reopened: number
  fixed_30d: number
}

/** Flat finding — one (control × resource) evaluation row (the "Findings" / plan view). */
export interface FindingRow {
  uid: string
  control_id: string
  control_name: string
  criticality: Severity
  service: string
  policies: string[]
  resource_id: string
  resource_type: string | null
  region: string | null
  csp: Csp
  account: string
  account_name: string | null
  result: 'PASS' | 'FAIL'
  status: ResourceStatus
  first_evaluated: string | null
  last_evaluated: string | null
  date_fixed: string | null    // when Qualys recorded the finding as remediated (drives FIXED status)
  date_reopen: string | null   // when a previously-fixed finding was detected failing again
  evidence_summary: string | null
  tags: string        // CLOUD provider resource tags, "key=value; key=value" ('' when untagged)
  qualys_tags: string // QUALYS asset tag names, "name; name" — a different source, kept separate
}

export interface ControlDrillRow {
  resource_id: string
  resource_type: string | null
  region: string | null
  csp: Csp
  account: string
  account_name: string | null
  criticality: Severity
  first_evaluated: string | null
  last_evaluated: string | null
  is_new: boolean
  is_reopened: boolean
  evidence: Evidence[]
  tags: string        // CLOUD provider resource tags, "key=value; key=value" ('' when untagged)
  qualys_tags: string // QUALYS asset tag names, "name; name" — a different source, kept separate
}

export interface ControlDrillResult {
  resources: ControlDrillRow[]
  total: number
  control_name: string | null
}

/** Lazy-loaded failing controls for one resource (Resource-view drawer). */
export interface ResourceControlsResult {
  controls: ResourceControlHit[]
}
