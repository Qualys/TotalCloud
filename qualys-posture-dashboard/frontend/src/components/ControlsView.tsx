import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import type { ControlDrillResult, ControlRow, Filters, Severity } from '../types'
import { accountLabel, cloudClass, downloadCsv, failPct, pctTone, sevRank, sevVar } from '../util'
import { Sparkline } from './Sparkline'
import { Th, sortRows, useSortState } from './sortable'
import { ColumnPicker, type ColumnDef, useColumns } from './columns'
import { Pagination, usePagination } from './pagination'
import { ExportXlsx } from './ExportXlsx'
import { RemediationCell, remediationFor, useRemediationMap } from './Remediation'
import { TagsCell } from './TagsCell'

const CONTROL_COLS: ColumnDef[] = [
  { key: 'cid', label: 'CID', required: true },
  { key: 'control', label: 'Control', default: true },
  { key: 'cloud', label: 'Cloud', default: true },
  { key: 'severity', label: 'Severity', default: true },
  { key: 'service', label: 'Service', default: true },
  { key: 'passfail', label: 'Pass / Fail', default: true },
  { key: 'passed', label: 'Passed' },
  { key: 'failed', label: 'Failed', default: true },
  { key: 'total', label: 'Total' },
  { key: 'pct', label: '% Fail', default: true },
  { key: 'accounts', label: 'Accts' },
  { key: 'trend', label: '30-day trend' },
]

const cidNum = (id: string) => { const n = Number(id); return Number.isFinite(n) ? n : id }
const CONTROL_ACCESSORS: Record<string, (r: ControlRow) => string | number> = {
  cid: (r) => cidNum(r.control_id),
  control: (r) => r.control_name,
  cloud: (r) => r.csp,
  severity: (r) => sevRank(r.criticality),
  service: (r) => r.service || '',
  passed: (r) => r.passed,
  failed: (r) => r.failed,
  total: (r) => r.total,
  pct: (r) => failPct(r.failed, r.total),
  accounts: (r) => r.accounts,
}

export function ControlsView({ rows, loading, error, filters, onInteracting }: {
  rows: ControlRow[]; loading: boolean; error: string | null; filters: Filters
  onInteracting?: (v: boolean) => void
}) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [drill, setDrill] = useState<Record<string, ControlDrillResult | 'loading' | 'error'>>({})
  const { sort, onSort } = useSortState({ key: 'cid', dir: 'asc' })
  const cols = useColumns('qpd-controls-cols', CONTROL_COLS)
  const remMap = useRemediationMap()
  const COLS = cols.count
  useEffect(() => { onInteracting?.(open.size > 0) }, [open, onInteracting])

  const sorted = sortRows(rows, sort, CONTROL_ACCESSORS)
  const pg = usePagination(sorted, `${sort.key}:${sort.dir}`)
  const totFail = rows.reduce((s, r) => s + r.failed, 0)
  const totPass = rows.reduce((s, r) => s + r.passed, 0)
  const failing = rows.filter((r) => r.failed > 0).length

  const toggle = async (r: ControlRow) => {
    const key = `${r.csp}:${r.control_id}`
    const next = new Set(open)
    if (next.has(key)) { next.delete(key); setOpen(next); return }
    next.add(key); setOpen(next)
    if (!drill[key]) {
      setDrill((d) => ({ ...d, [key]: 'loading' }))
      try {
        const res = await api.controlResources(r.control_id, r.csp, { account: filters.account, as_of: filters.as_of })
        setDrill((d) => ({ ...d, [key]: res }))
      } catch {
        setDrill((d) => ({ ...d, [key]: 'error' }))
      }
    }
  }

  const exportCsv = () => {
    const header = ['Control ID', 'Control', 'Cloud', 'Severity', 'Service', 'Accounts', 'Passed', 'Failed', 'Total', '% Fail',
      'Manual remediation']
    const data = sorted.map((r) => [r.control_id, r.control_name, r.csp, r.criticality, r.service, r.accounts, r.passed, r.failed, r.total, `${failPct(r.failed, r.total)}%`,
      remediationFor(remMap, r.csp, r.control_id)])
    downloadCsv('qualys-controls.csv', [header, ...data])
  }

  if (loading && !rows.length) return <div className="empty"><span className="spinner" /> Loading controls…</div>
  if (error && !rows.length) return <div className="empty">Could not load controls: {error}</div>
  if (!rows.length) return <div className="empty">No controls match the current filters.</div>

  return (
    <div>
      <div className="stat-row">
        <Stat k="Controls evaluated" v={rows.length} />
        <Stat k="Controls with failures" v={failing} tone="fail" />
        <Stat k="Failing checks" v={totFail} tone="fail" hint="Resource×control failures (a resource is counted once per control it fails) — not distinct resources. See the Resources tab for distinct resource counts." />
        <Stat k="Passing checks" v={totPass} tone="ok" hint="Resource×control passes." />
      </div>

      <div className="toolbar" style={{ justifyContent: 'flex-end' }}>
        <span style={{ display: 'flex', gap: 8 }}>
          <ColumnPicker cols={cols} />
          <button className="btn ghost" onClick={exportCsv}>⭳ Export CSV</button>
          <ExportXlsx view="controls" filters={filters} />
        </span>
      </div>

      <Pagination page={pg.page} totalPages={pg.totalPages} total={pg.total} size={pg.size} setSize={pg.setSize} onPage={pg.setPage} top />

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              {cols.has('cid') && <Th label="CID" col="cid" sort={sort} onSort={onSort} />}
              {cols.has('control') && <Th label="Control" col="control" sort={sort} onSort={onSort} />}
              {cols.has('cloud') && <Th label="Cloud" col="cloud" sort={sort} onSort={onSort} />}
              {cols.has('severity') && <Th label="Severity" col="severity" sort={sort} onSort={onSort} />}
              {cols.has('service') && <Th label="Service" col="service" sort={sort} onSort={onSort} />}
              {cols.has('passfail') && <th style={{ minWidth: 180 }}>Pass / Fail</th>}
              {cols.has('passed') && <Th label="Passed" col="passed" sort={sort} onSort={onSort} align="right" />}
              {cols.has('failed') && <Th label="Failed" col="failed" sort={sort} onSort={onSort} align="right" />}
              {cols.has('total') && <Th label="Total" col="total" sort={sort} onSort={onSort} align="right" />}
              {cols.has('pct') && <Th label="% Fail" col="pct" sort={sort} onSort={onSort} align="right" />}
              {cols.has('accounts') && <Th label="Accts" col="accounts" sort={sort} onSort={onSort} align="right" />}
              {cols.has('trend') && <th>30-day trend</th>}
            </tr>
          </thead>
          <tbody>
            {pg.pageRows.map((r) => {
              const pct = failPct(r.failed, r.total)
              const key = `${r.csp}:${r.control_id}`
              const isOpen = open.has(key)
              return (
                <Fragment key={key}>
                  <tr className={`expandable ${isOpen ? 'is-open' : ''}`} onClick={() => toggle(r)}
                    style={{ '--rs': sevVar(r.criticality) } as React.CSSProperties}>
                    {cols.has('cid') && (
                      <td className="nowrap">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span className={`chev ${isOpen ? 'open' : ''}`}>▸</span>
                          <span className="mono cid-link">CID-{r.control_id}</span>
                        </div>
                      </td>
                    )}
                    {cols.has('control') && <td className="name" style={{ minWidth: 280 }}>{r.control_name}</td>}
                    {cols.has('cloud') && <td><span className={`csp-badge ${cloudClass(r.csp)}`}>{r.csp === 'KUBERNETES' ? 'K8S' : r.csp}</span></td>}
                    {cols.has('severity') && <td><SevBadge s={r.criticality} /></td>}
                    {cols.has('service') && <td className="muted">{r.service || '—'}</td>}
                    {cols.has('passfail') && <td><PassFail passed={r.passed} failed={r.failed} /></td>}
                    {cols.has('passed') && <td className="right tnum muted">{r.passed.toLocaleString()}</td>}
                    {cols.has('failed') && <td className="right tnum" style={{ color: 'var(--sev-high)', fontWeight: 700 }}>{r.failed.toLocaleString()}</td>}
                    {cols.has('total') && <td className="right tnum muted">{r.total.toLocaleString()}</td>}
                    {cols.has('pct') && <td className={`right tnum ${pctTone(pct)}`} style={{ fontWeight: 700 }}>{pct}%</td>}
                    {cols.has('accounts') && <td className="right muted">{r.accounts}</td>}
                    {cols.has('trend') && <td><Sparkline values={r.trend.map((t) => t.failed)} /></td>}
                    {cols.has('rem') && <RemediationCell text={remediationFor(remMap, r.csp, r.control_id)} />}
                  </tr>
                  {isOpen && (
                    <tr className="expand-panel">
                      <td colSpan={COLS} style={{ padding: 0 }}>
                        <div style={{ padding: '10px 14px 14px 40px' }}>
                          <ControlDrill state={drill[key]} failed={r.failed} />
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
      <Pagination page={pg.page} totalPages={pg.totalPages} total={pg.total} size={pg.size} setSize={pg.setSize} onPage={pg.setPage} />
    </div>
  )
}

function ControlDrill({ state, failed }: { state: ControlDrillResult | 'loading' | 'error' | undefined; failed: number }) {
  if (state === 'loading' || state === undefined) return <div className="subtle"><span className="spinner" /> Loading failing resources…</div>
  if (state === 'error') return <div className="subtle">Could not load resources for this control.</div>
  if (!state.resources.length) {
    return <div className="subtle">
      No failing-resource detail loaded yet{failed > 0 ? ' — resources stream in during a refresh (the Resources pass runs after Controls).' : '.'}
    </div>
  }
  const capped = state.total > state.resources.length
  return (
    <div>
      <div className="section-title">
        Failing resources ({state.total.toLocaleString()}){capped ? ` · showing first ${state.resources.length}` : ''}
      </div>
      <table>
        <thead>
          <tr><th>Resource</th><th>Type</th><th>Region</th><th>Account</th><th>Status</th><th>Evidence</th><th>Cloud tags</th><th>Qualys tags</th></tr>
        </thead>
        <tbody>
          {state.resources.map((r, i) => (
            <tr key={r.csp + r.account + r.resource_id + r.region + i}>
              <td className="mono" style={{ wordBreak: 'break-all', fontWeight: 600 }}>{r.resource_id}</td>
              <td><span className="csp-badge">{r.resource_type || '—'}</span></td>
              <td className="muted nowrap">{r.region || '—'}</td>
              <td className="muted nowrap" title={r.account}>{accountLabel(r.account, r.account_name)}</td>
              <td className="nowrap">
                {r.is_new && <span className="badge sev-HIGH" style={{ marginRight: 4 }}>NEW</span>}
                {r.is_reopened && <span className="badge sev-MEDIUM">REOPENED</span>}
                {!r.is_new && !r.is_reopened && <span className="subtle" style={{ fontSize: 11 }}>existing</span>}
              </td>
              <td className="evidence">
                {r.evidence.length
                  ? r.evidence.slice(0, 3).map((e, j) => (<div key={j}>{e.settingName}: {e.actualValue}</div>))
                  : <span className="subtle">—</span>}
              </td>
              <TagsCell tags={r.tags} />
              <TagsCell tags={r.qualys_tags} kind="qualys" />
            </tr>
          ))}
        </tbody>
      </table>
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

export function SevBadge({ s }: { s: Severity }) {
  const S = (s || 'MEDIUM').toUpperCase() as Severity
  return <span className={`badge sev-${S}`}>{S[0] + S.slice(1).toLowerCase()}</span>
}

export function PassFail({ passed, failed }: { passed: number; failed: number }) {
  const total = passed + failed || 1
  const pct = (failed / total) * 100
  return (
    <div className="pf">
      <div className="pf-bar" title={`${failed} failing / ${total} evaluated`}>
        <div className="fail" style={{ width: `${pct}%` }} />
      </div>
      <div className="pf-nums nowrap"><span className="f">{failed}</span> <span className="subtle">/ {total}</span></div>
    </div>
  )
}
