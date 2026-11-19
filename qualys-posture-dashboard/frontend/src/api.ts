import type { ControlDrillResult, ControlRow, Facets, FindingRow, Filters, Remediation, ResourceControlsResult, ResourceRow, ResourceStats, Schedule, Status, TrendPoint } from './types'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) throw new Error((await safeDetail(r)) || `Request failed (${r.status})`)
  return r.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) throw new Error((await safeDetail(r)) || `Request failed (${r.status})`)
  return r.json()
}

async function safeDetail(r: Response): Promise<string | null> {
  try {
    const j = await r.json()
    return (j && (j.detail || j.message)) || null
  } catch {
    return null
  }
}

/** Serialize the subset of filters an endpoint understands. Keys map 1:1 to backend query params. */
const qs = (f: Partial<Filters>, keys: (keyof Filters)[]): string => {
  const p = new URLSearchParams()
  for (const k of keys) {
    const v = f[k]
    if (v) p.set(k, v)
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

const CONTROL_KEYS: (keyof Filters)[] = ['cloud', 'account', 'severity', 'service', 'policy', 'q', 'as_of']
const RESOURCE_KEYS: (keyof Filters)[] = ['cloud', 'account', 'severity', 'service', 'policy', 'rtype', 'region', 'status', 'result', 'q', 'as_of']
const FINDING_KEYS: (keyof Filters)[] = ['cloud', 'account', 'severity', 'service', 'policy', 'rtype', 'region', 'status', 'result', 'q', 'as_of']

const EXPORT_KEYS: Record<ExportView, (keyof Filters)[]> = {
  controls: CONTROL_KEYS,
  resources: RESOURCE_KEYS,
  findings: FINDING_KEYS,
}

export type ExportView = 'controls' | 'resources' | 'findings'

/** URL of the server-rendered .xlsx for a view under the current filters (adds a Manual
 *  remediation column that the client-side CSV can't carry — remediation is joined server-side). */
export function exportXlsxUrl(view: ExportView, f: Partial<Filters>): string {
  const q = qs(f, EXPORT_KEYS[view])
  return `/api/export.xlsx${q ? `${q}&` : '?'}view=${view}`
}

export const api = {
  status: () => get<Status>('/api/status'),
  facets: (f: Partial<Filters> = {}) => get<Facets>(`/api/facets${qs(f, ['cloud', 'as_of'])}`),
  saveCreds: (b: { gateway_url: string; username: string; password: string }) =>
    post<{ ok: boolean; gateway: string }>('/api/creds', b),
  sync: () => post<{ ok: boolean; started?: boolean; already_running?: boolean }>('/api/sync'),
  schedule: () => get<Schedule>('/api/schedule'),
  saveSchedule: (s: Schedule) => post<Schedule>('/api/schedule', s),
  syncState: () => get<{ running: boolean; progress: string; error: string | null }>('/api/sync/state'),
  controls: (f: Partial<Filters>) =>
    get<{ latest: string | null; as_of: string | null; controls: ControlRow[] }>(`/api/controls${qs(f, CONTROL_KEYS)}`),
  resources: (f: Partial<Filters>) =>
    get<{ latest: string | null; as_of: string | null; resources: ResourceRow[]; stats: ResourceStats }>(
      `/api/resources${qs(f, RESOURCE_KEYS)}`),
  findings: (f: Partial<Filters>) =>
    get<{ latest: string | null; as_of: string | null; findings: FindingRow[]; total: number
          status_counts?: Record<string, number> | null }>(
      `/api/findings${qs(f, FINDING_KEYS)}`),
  findingEvidence: (r: FindingRow, as_of?: string) => {
    const p = new URLSearchParams({ control: r.control_id, account: r.account, csp: r.csp })
    if (r.resource_type) p.set('resource_type', r.resource_type)
    p.set('resource_id', r.resource_id)
    if (r.region) p.set('region', r.region)
    if (as_of) p.set('as_of', as_of)
    return get<{ evidence: { settingName: string; actualValue: string }[] }>(`/api/finding-evidence?${p.toString()}`)
  },
  controlResources: (control: string, csp: string, f: Partial<Filters> = {}) => {
    const p = new URLSearchParams({ control })
    if (csp) p.set('csp', csp)
    if (f.account) p.set('account', f.account)
    if (f.as_of) p.set('as_of', f.as_of)
    return get<ControlDrillResult>(`/api/control-resources?${p.toString()}`)
  },
  /** {"CSP:cid": manual remediation} for every control — one fetch feeds the inline Remediation
   *  column on all three tables (and their CSV exports). */
  remediationMap: () => get<Record<string, string>>('/api/remediation-map'),
  controlRemediation: (control: string, csp: string) =>
    get<Remediation>(`/api/control-remediation?control=${encodeURIComponent(control)}&csp=${encodeURIComponent(csp)}`),
  resourceControls: (r: { account: string; csp: string; resource_type: string | null; resource_id: string; region: string | null }, as_of?: string) => {
    const p = new URLSearchParams({ account: r.account, csp: r.csp })
    if (r.resource_type) p.set('resource_type', r.resource_type)
    p.set('resource_id', r.resource_id)
    if (r.region) p.set('region', r.region)
    if (as_of) p.set('as_of', as_of)
    return get<ResourceControlsResult>(`/api/resource-controls?${p.toString()}`)
  },
  trend: (f: { cloud?: string; account?: string; severity?: string; service?: string; policy?: string; days?: number }) => {
    const p = new URLSearchParams()
    for (const k of ['cloud', 'account', 'severity', 'service', 'policy'] as const) if (f[k]) p.set(k, f[k]!)
    if (f.days) p.set('days', String(f.days))
    const s = p.toString()
    return get<{ trend: TrendPoint[] }>(`/api/trend${s ? `?${s}` : ''}`)
  },
}
