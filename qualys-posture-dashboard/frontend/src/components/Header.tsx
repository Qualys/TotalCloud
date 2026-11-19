import { useEffect, useRef, useState } from 'react'
import type { Filters, Status } from '../types'
import { relTime } from '../util'
import { ThemeToggle } from './ThemeToggle'

type View = 'controls' | 'resources' | 'findings'
interface Props {
  status: Status
  view: View
  onView: (v: View) => void
  onRefresh: () => void
  syncing: boolean
  syncProgress: string | null
  filters: Filters
  onFilters: (f: Filters) => void
  onSettings: () => void
}

export function Header({ status, view, onView, onRefresh, syncing, syncProgress, filters, onFilters, onSettings }: Props) {
  const dates = status.dates || []
  const placeholder = view === 'controls' ? 'Search controls (name or CID)…' : 'Search resources (ID)…'

  // Debounced search: typing updates a local value immediately, but the filter (which triggers a
  // refetch) only fires 300ms after you stop typing — so keystrokes don't each refetch the payload.
  const filtersRef = useRef(filters); filtersRef.current = filters
  const [qLocal, setQLocal] = useState(filters.q)
  useEffect(() => { setQLocal(filters.q) }, [filters.q])
  useEffect(() => {
    const t = setTimeout(() => {
      if (qLocal !== filtersRef.current.q) onFilters({ ...filtersRef.current, q: qLocal })
    }, 300)
    return () => clearTimeout(t)
  }, [qLocal, onFilters])

  return (
    <div className="topbar">
      <div className="topbar-row">
        <div className="brand">
          <span className="dot" />
          <span>Qualys Posture Dashboard<span className="brand-sub">CloudView · CSPM</span></span>
        </div>

        <div className="tabs" role="tablist">
          <button className={`tab ${view === 'controls' ? 'active' : ''}`} onClick={() => onView('controls')} role="tab" aria-selected={view === 'controls'}>Controls</button>
          <button className={`tab ${view === 'resources' ? 'active' : ''}`} onClick={() => onView('resources')} role="tab" aria-selected={view === 'resources'}>Resources</button>
          <button className={`tab ${view === 'findings' ? 'active' : ''}`} onClick={() => onView('findings')} role="tab" aria-selected={view === 'findings'}>Findings</button>
        </div>

        <div className="spacer" />

        <div className="search-box">
          <span className="search-ico">⌕</span>
          <input type="text" value={qLocal} placeholder={placeholder} onChange={(e) => setQLocal(e.target.value)} />
          {qLocal && <button className="search-clear" onClick={() => { setQLocal(''); onFilters({ ...filters, q: '' }) }} title="Clear search">✕</button>}
        </div>

        <label className="field inline">As of
          <select value={filters.as_of} onChange={(e) => onFilters({ ...filters, as_of: e.target.value })} title="Time-travel to an earlier snapshot">
            <option value="">Latest{status.latest_snapshot ? ` (${status.latest_snapshot})` : ''}</option>
            {dates.filter((d) => d !== status.latest_snapshot).map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>

        <ThemeToggle />

        <button className="btn ghost theme-toggle" onClick={onSettings} title="Qualys credentials / settings" aria-label="Settings">⚙</button>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
          <button className="btn primary" onClick={onRefresh} disabled={syncing || status.demo_mode}
            title={status.demo_mode ? 'Refresh is disabled in demo mode' : 'Pull the latest posture from Qualys'}>
            {syncing ? <><span className="spinner" /> Refreshing…</> : <>↻ Refresh</>}
          </button>
          <span className="sync-meta">
            {status.demo_mode ? 'Demo data — Refresh disabled'
              : syncing ? (syncProgress || 'working…')
              : <>Last refreshed {relTime(status.last_sync)}</>}
          </span>
        </div>
      </div>
    </div>
  )
}
