import type { Filters } from '../types'

const LABELS: Partial<Record<keyof Filters, string>> = {
  cloud: 'Cloud', account: 'Account', severity: 'Severity', service: 'Service', policy: 'Policy',
  rtype: 'Type', region: 'Region', status: 'Status', result: 'Result', q: 'Search',
}
const ORDER: (keyof Filters)[] = ['cloud', 'account', 'severity', 'service', 'policy', 'rtype', 'region', 'status', 'result', 'q']

/** Removable chips for the active filters (as_of is shown separately in the header). */
export function ActiveFilterChips({ filters, onFilters, onClear }: {
  filters: Filters; onFilters: (f: Filters) => void; onClear: () => void
}) {
  const active = ORDER.filter((k) => filters[k])
  if (!active.length) return null
  const pretty = (k: keyof Filters, v: string) =>
    k === 'result' ? (v === 'fail' ? 'Failing' : 'Passing')
    : k === 'severity' || k === 'status' ? v[0] + v.slice(1).toLowerCase()
    : v
  return (
    <div className="ctxbar">
      <span className="lead">Filters:</span>
      {active.map((k) => (
        <span key={k} className="chip">
          <b>{LABELS[k]}</b> {pretty(k, filters[k])}
          <span className="x" title="Remove" onClick={() => onFilters({ ...filters, [k]: '' })}>✕</span>
        </span>
      ))}
      <button className="btn ghost" style={{ fontSize: 12 }} onClick={onClear}>Clear all</button>
    </div>
  )
}
