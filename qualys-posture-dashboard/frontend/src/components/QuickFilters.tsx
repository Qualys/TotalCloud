import { useState } from 'react'
import type { ControlRow, Facets, FindingRow, Filters, ResourceRow, Status } from '../types'
import { SEVERITIES, accountLabel } from '../util'

type View = 'controls' | 'resources' | 'findings'
interface Item { value: string; label: string; count: number }

interface Props {
  view: View
  filters: Filters
  onFilters: (f: Filters) => void
  facets: Facets | null
  status: Status
  controls: ControlRow[]
  resources: ResourceRow[]
  findings: FindingRow[]
  findingStatusCounts?: Record<string, number> | null
}

/** Count helper — how many loaded rows match a given facet value. */
function tally<T>(rows: T[], pick: (r: T) => string | string[] | null | undefined): Map<string, number> {
  const m = new Map<string, number>()
  for (const r of rows) {
    const v = pick(r)
    const vals = Array.isArray(v) ? v : v == null ? [] : [v]
    for (const x of vals) m.set(x, (m.get(x) || 0) + 1)
  }
  return m
}

export function QuickFilters({ view, filters, onFilters, facets, status, controls, resources, findings, findingStatusCounts }: Props) {
  const set = (patch: Partial<Filters>) => onFilters({ ...filters, ...patch })

  // Counts come from the currently-loaded rows for the active view (they react to other filters).
  const isC = view === 'controls', isR = view === 'resources', isF = view === 'findings'
  const cloudCounts = isC ? tally(controls, (r) => r.csp) : isR ? tally(resources, (r) => r.csp) : tally(findings, (r) => r.csp)
  const sevCounts = isC ? tally(controls, (r) => r.criticality) : isR ? tally(resources, (r) => r.top_severity) : tally(findings, (r) => r.criticality)
  const svcCounts = isC ? tally(controls, (r) => r.service) : isR ? tally(resources, (r) => r.services) : tally(findings, (r) => r.service)
  const policyCounts = isC ? tally(controls, (r) => r.policies) : isR ? tally(resources, (r) => r.policies) : tally(findings, (r) => r.policies)
  const acctCounts = isC ? tally(controls, () => null) : isR ? tally(resources, (r) => r.account) : tally(findings, (r) => r.account)
  const rtypeCounts = isF ? tally(findings, (r) => r.resource_type) : tally(resources, (r) => r.resource_type)
  const regionCounts = isF ? tally(findings, (r) => r.region) : tally(resources, (r) => r.region)
  // Findings: use the server-computed lifecycle totals (whole facet set) so FIXED — never present in
  // the default fail-only rows — still shows its true count. Resources: tally the loaded rows.
  const statusCounts = isF
    ? new Map<string, number>(Object.entries(findingStatusCounts || {}))
    : tally(resources, (r) => r.status)
  const resultCounts = isF ? tally(findings, (r) => r.result.toLowerCase()) : tally(resources, (r) => r.result.toLowerCase())

  const cloudsPresent = Array.from(new Set(status.accounts.map((a) => a.csp)))
  const accountsForCloud = status.accounts.filter((a) => !filters.cloud || a.csp === filters.cloud)

  const mk = (values: string[], counts: Map<string, number>, label?: (v: string) => string): Item[] =>
    values.map((v) => ({ value: v, label: label ? label(v) : v, count: counts.get(v) || 0 }))

  const activeCount = (['cloud', 'account', 'severity', 'service', 'policy', 'rtype', 'region', 'status', 'result'] as (keyof Filters)[])
    .filter((k) => filters[k]).length
  const clearAll = () => onFilters({ ...filters, cloud: '', account: '', severity: '', service: '', policy: '', rtype: '', region: '', status: '', result: '' })

  return (
    <aside className="qf card">
      <div className="qf-head">
        <span>Quick Filters</span>
        {activeCount > 0 && <button className="qf-clear" onClick={clearAll}>Clear all ({activeCount})</button>}
      </div>

      <FacetGroup
        title="Cloud" selected={filters.cloud}
        items={mk(cloudsPresent, cloudCounts, (c) => (c === 'KUBERNETES' ? 'Kubernetes' : c))}
        onSelect={(v) => set({ cloud: v, account: '' })}
      />

      <FacetGroup
        title="Severity" selected={filters.severity}
        items={mk(SEVERITIES, sevCounts, (s) => s[0] + s.slice(1).toLowerCase())}
        tone="sev" onSelect={(v) => set({ severity: v })}
      />

      {view !== 'controls' && (
        <FacetGroup
          title="Result" selected={filters.result}
          items={mk(['fail', 'pass'], resultCounts, (v) => (v === 'fail' ? 'Failing' : 'Passing'))}
          onSelect={(v) => set({ result: v })}
        />
      )}

      {view !== 'controls' && (
        <FacetGroup
          title="Status" selected={filters.status}
          items={mk(['NEW', 'EXISTING', 'FIXED', 'REOPENED'], statusCounts, (s) => s[0] + s.slice(1).toLowerCase())}
          onSelect={(v) => set({ status: v })}
          keepAll={isF}
        />
      )}

      <FacetGroup
        title="Account" selected={filters.account} max={6} keepAll={view === 'controls'}
        items={accountsForCloud.map((a) => ({
          value: a.account, label: accountLabel(a.account, a.name), count: acctCounts.get(a.account) || 0,
        }))}
        onSelect={(v) => set({ account: v })}
      />

      <FacetGroup
        title="Service" selected={filters.service} max={8}
        items={mk(facets?.services || [], svcCounts)}
        onSelect={(v) => set({ service: v })}
      />

      <FacetGroup
        title="Policy" selected={filters.policy} max={8}
        items={mk(facets?.policies || [], policyCounts)}
        onSelect={(v) => set({ policy: v })}
      />

      {view !== 'controls' && (
        <FacetGroup
          title="Resource type" selected={filters.rtype} max={8}
          items={mk(facets?.resource_types || [], rtypeCounts)}
          onSelect={(v) => set({ rtype: v })}
        />
      )}

      {view !== 'controls' && (
        <FacetGroup
          title="Region" selected={filters.region} max={8}
          items={mk(facets?.regions || [], regionCounts)}
          onSelect={(v) => set({ region: v })}
        />
      )}
    </aside>
  )
}

function FacetGroup({ title, items, selected, onSelect, max = 6, tone, keepAll }: {
  title: string
  items: Item[]
  selected: string
  onSelect: (v: string) => void
  max?: number
  tone?: 'sev'
  keepAll?: boolean   // show every value even with a 0 count (e.g. Account on the Controls view)
}) {
  const [expanded, setExpanded] = useState(false)
  // Hide zero-count values (unless selected) so the group stays tight — unless keepAll. Sort by count desc.
  const visible = (keepAll ? items : items.filter((i) => i.count > 0 || i.value === selected))
    .sort((a, b) => b.count - a.count)
  if (!visible.length) return null
  const shown = expanded ? visible : visible.slice(0, max)
  const hidden = visible.length - shown.length
  const maxCount = Math.max(1, ...visible.map((i) => i.count))

  return (
    <div className="qf-group">
      <div className="qf-title">{title}{selected && <span className="gdot" title="Filter active in this group" />}</div>
      <ul className="qf-list">
        {shown.map((i) => {
          const active = i.value === selected
          return (
            <li key={i.value}>
              <button
                className={`qf-item ${active ? 'active' : ''}`}
                onClick={() => onSelect(active ? '' : i.value)}
                title={i.label}
              >
                {!active && i.count > 0 && <span className="qf-bar" style={{ width: `${(i.count / maxCount) * 100}%` }} />}
                {tone === 'sev' && <span className={`sev-dot sev-${i.value}`} />}
                <span className="qf-label">{i.label}</span>
                {i.count > 0 && <span className="qf-count">{i.count.toLocaleString()}</span>}
              </button>
            </li>
          )
        })}
      </ul>
      {hidden > 0 && (
        <button className="qf-more" onClick={() => setExpanded(true)}>+{hidden} more</button>
      )}
      {expanded && visible.length > max && (
        <button className="qf-more" onClick={() => setExpanded(false)}>show less</button>
      )}
    </div>
  )
}
