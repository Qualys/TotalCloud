import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import type { Filters, ResourceControlHit, ResourceRow, ResourceStats, Severity } from '../types'
import { SEVERITIES, cloudClass, downloadCsv, sevRank, sevVar } from '../util'
import { SevBadge } from './ControlsView'
import { Th, sortRows, useSortState } from './sortable'
import { ColumnPicker, type ColumnDef, useColumns } from './columns'
import { Pagination, usePagination } from './pagination'
import { ExportXlsx } from './ExportXlsx'
import { TagsCell, TagChips } from './TagsCell'
import { RemediationCell, remediationFor, useRemediationMap } from './Remediation'

const RES_COLS: ColumnDef[] = [
  { key: 'resource', label: 'Resource', required: true },
  { key: 'account', label: 'Account ID', default: true },
  { key: 'alias', label: 'Account alias', default: true },
  { key: 'type', label: 'Type', default: true },
  { key: 'region', label: 'Region', default: true },
  { key: 'cloud', label: 'Cloud' },
  { key: 'result', label: 'Result', default: true },
  { key: 'status', label: 'Status', default: true },
  { key: 'topsev', label: 'Top severity', default: true },
  { key: 'failing', label: 'Failing controls', default: true },
  { key: 'mix', label: 'Severity mix' },
  { key: 'first', label: 'First evaluated' },
  { key: 'last', label: 'Last evaluated' },
  { key: 'fixed', label: 'Date fixed' },
  { key: 'reopened', label: 'Date reopened' },
  { key: 'evidence', label: 'Evidence', default: true },
  { key: 'tags', label: 'Cloud tags' },     // provider tags — off by default (often empty)
  { key: 'qtags', label: 'Qualys tags' },   // Qualys asset tags — separate source, kept separate
  { key: 'rem', label: 'Remediation' },     // manual fix inline — pick it in Columns
]

/** A resource fails many controls; the inline cell shows the most-severe one's fix (the Excel
 *  export carries every failing control's steps). */
function resourceRemediation(map: Record<string, string>, r: ResourceRow): string {
  const text = r.top_control_id ? remediationFor(map, r.csp, r.top_control_id) : ''
  if (!text) return ''
  const extra = r.failing_controls > 1 ? ` (+${r.failing_controls - 1} more failing controls)` : ''
  return `[${r.top_control_id}] ${text}${extra}`
}

const RES_ACCESSORS: Record<string, (r: ResourceRow) => string | number> = {
  resource: (r) => r.resource_id,
  account: (r) => r.account,
  alias: (r) => r.account_name || '',
  type: (r) => r.resource_type || '',
  region: (r) => r.region || '',
  cloud: (r) => r.csp,
  result: (r) => r.result,
  status: (r) => r.status,
  topsev: (r) => sevRank(r.top_severity || ''),
  failing: (r) => r.failing_controls,
  first: (r) => r.first_seen || '',
  last: (r) => r.last_seen || '',
  fixed: (r) => r.date_fixed || '',
  reopened: (r) => r.date_reopen || '',
  tags: (r) => r.tags || '',
  qtags: (r) => r.qualys_tags || '',
}

export function ResourceView({ rows, stats, loading, error, filters, onInteracting }: {
  rows: ResourceRow[]; stats: ResourceStats; loading: boolean; error: string | null; filters: Filters
  onInteracting?: (v: boolean) => void
}) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [drill, setDrill] = useState<Record<string, ResourceControlHit[] | 'loading' | 'error'>>({})
  const { sort, onSort } = useSortState({ key: 'failing', dir: 'desc' })
  const cols = useColumns('qpd-resource-cols', RES_COLS)
  const remMap = useRemediationMap()
  const COLS = cols.count
  useEffect(() => { onInteracting?.(open.size > 0) }, [open, onInteracting])
  const sorted = sortRows(rows, sort, RES_ACCESSORS)
  const pg = usePagination(sorted, `${sort.key}:${sort.dir}`)

  const toggle = async (r: ResourceRow) => {
    const next = new Set(open)
    if (next.has(r.uid)) { next.delete(r.uid); setOpen(next); return }
    next.add(r.uid); setOpen(next)
    if (!drill[r.uid]) {
      setDrill((d) => ({ ...d, [r.uid]: 'loading' }))
      try {
        const res = await api.resourceControls(r, filters.as_of)
        setDrill((d) => ({ ...d, [r.uid]: res.controls }))
      } catch {
        setDrill((d) => ({ ...d, [r.uid]: 'error' }))
      }
    }
  }

  const exportCsv = () => {
    const header = ['Resource ID', 'Account', 'Account name', 'Type', 'Region', 'Cloud', 'Result', 'Status', 'Top severity',
      'Failing controls', 'Passing controls', 'First evaluated', 'Last evaluated', 'Date fixed', 'Date reopened', 'Evidence', 'Cloud tags', 'Qualys tags', 'Manual remediation']
    const data = rows.map((r) => [
      r.resource_id, r.account, r.account_name || '', r.resource_type || '', r.region || '', r.csp,
      r.result, r.status, r.top_severity || '', r.failing_controls, r.passing_controls,
      r.first_seen || '', r.last_seen || '', r.date_fixed || '', r.date_reopen || '',
      r.evidence_summary || '', r.tags || '', r.qualys_tags || '', resourceRemediation(remMap, r),
    ])
    downloadCsv('qualys-resources.csv', [header, ...data])
  }

  if (loading && !rows.length) return <div className="empty"><span className="spinner" /> Loading resources…</div>
  if (error && !rows.length) return <div className="empty">Could not load resources: {error}</div>

  return (
    <div>
      <div className="stat-row">
        <Stat k="Resources with failures" v={stats.failing_resources} tone="fail"
          hint="Distinct cloud resources that fail at least one CSPM control in this snapshot." />
        <Stat k="Passing resources" v={stats.passing_resources} tone="ok"
          hint="Distinct resources that pass every CSPM control they were evaluated against." />
        <Stat k="New (last 30d)" v={stats.new_30d} tone="fail"
          hint="Resources Qualys first started detecting as failing within the last 30 days (from each finding's firstEvaluated date)." />
        <Stat k="Reopened" v={stats.reopened} tone="fail"
          hint="Resources that had previously PASSED (or were fixed) and are failing again — Qualys stamps a reopen date on the finding." />
        <Stat k="Recently fixed (30d)" v={stats.fixed_30d} tone="ok"
          hint="Findings remediated in the last 30 days — the resource now PASSES (from the finding's dateFixed). Shown for lifecycle context; these are not in the failing list." />
      </div>

      <div className="toolbar" style={{ justifyContent: 'flex-end' }}>
        <span style={{ display: 'flex', gap: 8 }}>
          <ColumnPicker cols={cols} />
          <button className="btn ghost" onClick={exportCsv}>⭳ Export CSV</button>
          <ExportXlsx view="resources" filters={filters} />
        </span>
      </div>

      {!rows.length ? (
        <div className="empty">No resources match the current filters.</div>
      ) : (
        <>
        <Pagination page={pg.page} totalPages={pg.totalPages} total={pg.total} size={pg.size} setSize={pg.setSize} onPage={pg.setPage} top />
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                {cols.has('resource') && <Th label="Resource" col="resource" sort={sort} onSort={onSort} style={{ width: 280, minWidth: 280, maxWidth: 280 }} />}
                {cols.has('account') && <Th label="Account ID" col="account" sort={sort} onSort={onSort} />}
                {cols.has('alias') && <Th label="Account alias" col="alias" sort={sort} onSort={onSort} />}
                {cols.has('type') && <Th label="Type" col="type" sort={sort} onSort={onSort} />}
                {cols.has('region') && <Th label="Region" col="region" sort={sort} onSort={onSort} />}
                {cols.has('cloud') && <Th label="Cloud" col="cloud" sort={sort} onSort={onSort} />}
                {cols.has('result') && <Th label="Result" col="result" sort={sort} onSort={onSort} />}
                {cols.has('status') && <Th label="Status" col="status" sort={sort} onSort={onSort} />}
                {cols.has('topsev') && <Th label="Top severity" col="topsev" sort={sort} onSort={onSort} />}
                {cols.has('failing') && <Th label="Failing" col="failing" sort={sort} onSort={onSort} align="right" />}
                {cols.has('mix') && <th style={{ minWidth: 130 }}>Severity mix</th>}
                {cols.has('first') && <Th label="First evaluated" col="first" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('last') && <Th label="Last evaluated" col="last" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('fixed') && <Th label="Date fixed" col="fixed" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('reopened') && <Th label="Date reopened" col="reopened" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('evidence') && <th style={{ minWidth: 200 }}>Evidence</th>}
                {cols.has('tags') && <Th label="Cloud tags" col="tags" sort={sort} onSort={onSort} />}
                {cols.has('qtags') && <Th label="Qualys tags" col="qtags" sort={sort} onSort={onSort} />}
                {cols.has('rem') && <th style={{ minWidth: 280 }}>Remediation</th>}
              </tr>
            </thead>
            <tbody>
              {pg.pageRows.map((r) => {
                const isOpen = open.has(r.uid)
                return (
                  <Fragment key={r.uid}>
                    <tr className={`expandable ${isOpen ? 'is-open' : ''}`} onClick={() => toggle(r)}
                      style={{ '--rs': r.result === 'FAIL' ? 'var(--sev-high)' : 'var(--ok)' } as React.CSSProperties}>
                      {cols.has('resource') && (
                        <td style={{ width: 280, maxWidth: 280 }}>
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <span className={`chev ${isOpen ? 'open' : ''}`} style={{ marginTop: 1 }}>▸</span>
                            <span className="mono name clamp2" style={{ wordBreak: 'break-all' }} title={r.resource_id}>{r.resource_id}</span>
                          </div>
                        </td>
                      )}
                      {cols.has('account') && <td className="mono muted nowrap">{r.account}</td>}
                      {cols.has('alias') && <td className="muted nowrap">{r.account_name || '—'}</td>}
                      {cols.has('type') && <td><span className="csp-badge">{r.resource_type || '—'}</span></td>}
                      {cols.has('region') && <td className="muted nowrap">{r.region || '—'}</td>}
                      {cols.has('cloud') && <td><span className={`csp-badge ${cloudClass(r.csp)}`}>{r.csp === 'KUBERNETES' ? 'K8S' : r.csp}</span></td>}
                      {cols.has('result') && <td><span className={`badge ${r.result === 'FAIL' ? 'sev-HIGH' : 'result-pass'}`}>{r.result === 'FAIL' ? 'Fail' : 'Pass'}</span></td>}
                      {cols.has('status') && <td><StatusBadge s={r.status} /></td>}
                      {cols.has('topsev') && <td>{r.top_severity ? <SevBadge s={r.top_severity} /> : <span className="badge sev-INFORMATIONAL">Pass</span>}</td>}
                      {cols.has('failing') && <td className="right"><span className="pill-count">{r.failing_controls}</span></td>}
                      {cols.has('mix') && <td><SeverityMix mix={r.severity_mix} /></td>}
                      {cols.has('first') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.first_seen || '—'}</td>}
                      {cols.has('last') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.last_seen || '—'}</td>}
                      {cols.has('fixed') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.date_fixed || '—'}</td>}
                      {cols.has('reopened') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.date_reopen || '—'}</td>}
                      {cols.has('evidence') && (
                        <td className="evidence" style={{ maxWidth: 280 }} title={r.evidence_summary || ''}>
                          <div className="clamp1">{r.evidence_summary || '—'}</div>
                        </td>
                      )}
                      {cols.has('tags') && <TagsCell tags={r.tags} />}
                      {cols.has('qtags') && <TagsCell tags={r.qualys_tags} kind="qualys" />}
                      {cols.has('rem') && <RemediationCell text={resourceRemediation(remMap, r)} />}
                    </tr>
                    {isOpen && (
                      <tr className="expand-panel">
                        <td colSpan={COLS} style={{ padding: 0 }}>
                          <div style={{ padding: '10px 14px 14px 40px' }}>
                            <div className="section-title">
                              Controls · <span style={{ color: 'var(--sev-high)' }}>{r.failing_controls} failing</span> · <span style={{ color: 'var(--ok)' }}>{r.passing_controls} passing</span>{r.services.length ? ` · ${r.services.join(', ')}` : ''} · last seen {r.last_seen || '—'}
                            </div>
                            <ResourceDrill state={drill[r.uid]} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
        </>
      )}
      <Pagination page={pg.page} totalPages={pg.totalPages} total={pg.total} size={pg.size} setSize={pg.setSize} onPage={pg.setPage} />
    </div>
  )
}

function ResourceDrill({ state }: { state: ResourceControlHit[] | 'loading' | 'error' | undefined }) {
  if (state === 'loading' || state === undefined) return <div className="subtle"><span className="spinner" /> Loading controls…</div>
  if (state === 'error') return <div className="subtle">Could not load controls for this resource.</div>
  if (!state.length) return <div className="subtle">No control detail loaded (data streams in during a refresh).</div>
  return (
    <>
    <TagChips tags={state[0]?.tags || ''} qualysTags={state[0]?.qualys_tags || ''} />
    <table>
      <thead><tr><th>CID</th><th>Control</th><th>Result</th><th>Severity</th><th>Lifecycle</th><th>Evidence</th></tr></thead>
      <tbody>
        {state.map((c) => {
          const fail = (c.result || 'FAIL') === 'FAIL'
          return (
            <Fragment key={c.control_id}>
              <tr>
                <td className="mono nowrap">CID-{c.control_id}</td>
                <td>{c.control_name}</td>
                <td><span className={`badge ${fail ? 'sev-HIGH' : 'result-pass'}`}>{fail ? 'Fail' : 'Pass'}</span></td>
                <td><SevBadge s={c.criticality} /></td>
                <td className="nowrap">
                  {c.is_new && <span className="badge sev-HIGH" style={{ marginRight: 4 }}>NEW</span>}
                  {c.is_reopened && <span className="badge sev-MEDIUM">REOPENED</span>}
                  {!c.is_new && !c.is_reopened && <span className="subtle" style={{ fontSize: 11 }}>existing</span>}
                </td>
                <td className="evidence">
                  {c.evidence.length
                    ? c.evidence.slice(0, 4).map((e, i) => (<div key={i}>{e.settingName}: {e.actualValue}</div>))
                    : <span className="subtle">—</span>}
                </td>
              </tr>
            </Fragment>
          )
        })}
      </tbody>
    </table>
    </>
  )
}

function StatusBadge({ s }: { s: string }) {
  const cls = s === 'NEW' ? 'sev-HIGH badge-new'
    : s === 'REOPENED' ? 'sev-MEDIUM'
    : s === 'FIXED' ? 'badge-fixed'
    : 'sev-INFORMATIONAL'
  const label = s === 'EXISTING' ? 'Existing' : s[0] + s.slice(1).toLowerCase()
  return <span className={`badge ${cls}`}>{label}</span>
}

function SeverityMix({ mix }: { mix: Record<Severity, number> }) {
  const total = SEVERITIES.reduce((s, k) => s + (mix[k] || 0), 0) || 1
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="mix-bar" title={SEVERITIES.map((s) => `${s}: ${mix[s] || 0}`).join('  ')}>
        {SEVERITIES.map((s) => {
          const n = mix[s] || 0
          if (!n) return null
          return <div key={s} className="mix-seg" style={{ width: `${(n / total) * 100}%`, background: sevVar(s) }} />
        })}
      </div>
      <span className="subtle" style={{ fontSize: 11 }}>{total}</span>
    </div>
  )
}

function Stat({ k, v, tone, hint }: { k: string; v: number; tone?: 'ok' | 'fail'; hint?: string }) {
  const color = tone === 'fail' ? 'var(--sev-high)' : tone === 'ok' ? 'var(--ok)' : 'var(--fg)'
  const toneCls = tone === 'fail' ? 'tone-fail' : tone === 'ok' ? 'tone-ok' : ''
  return (
    <div className={`stat card ${toneCls}`} title={hint}>
      <div className="k">{k}{hint && <span className="info-dot" title={hint}>ⓘ</span>}</div>
      <div className="v" style={{ color }}>{v.toLocaleString()}</div>
    </div>
  )
}
