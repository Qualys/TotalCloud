import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import type { Evidence, FindingRow, Filters } from '../types'
import { accountLabel, downloadCsv, sevRank, sevVar } from '../util'
import { SevBadge } from './ControlsView'
import { Th, sortRows, useSortState } from './sortable'
import { ColumnPicker, type ColumnDef, useColumns } from './columns'
import { Pagination, usePagination } from './pagination'
import { ExportXlsx } from './ExportXlsx'
import { TagsCell } from './TagsCell'
import { RemediationCell, remediationFor, useRemediationMap } from './Remediation'

const FIND_COLS: ColumnDef[] = [
  { key: 'cid', label: 'CID', required: true },
  { key: 'control', label: 'Control', default: true },
  { key: 'severity', label: 'Severity', default: true },
  { key: 'service', label: 'Service', default: true },
  { key: 'resource', label: 'Resource', default: true },
  { key: 'type', label: 'Type', default: true },
  { key: 'region', label: 'Region', default: true },
  { key: 'account', label: 'Account ID', default: true },
  { key: 'alias', label: 'Account alias', default: true },
  { key: 'result', label: 'Result' },
  { key: 'status', label: 'Status', default: true },
  { key: 'first', label: 'First evaluated' },
  { key: 'last', label: 'Last evaluated' },
  { key: 'fixed', label: 'Fixed date' },    // when Qualys recorded remediation — pick it to track FIXED items
  { key: 'evidence', label: 'Evidence', default: true },
  { key: 'tags', label: 'Cloud tags' },     // provider tags — off by default (often empty)
  { key: 'qtags', label: 'Qualys tags' },   // Qualys asset tags — separate source, kept separate
  { key: 'rem', label: 'Remediation' },     // manual fix inline — pick it in Columns
]

const cidNum = (id: string) => { const n = Number(id); return Number.isFinite(n) ? n : id }
const FIND_ACCESSORS: Record<string, (r: FindingRow) => string | number> = {
  cid: (r) => cidNum(r.control_id),
  control: (r) => r.control_name,
  severity: (r) => sevRank(r.criticality),
  service: (r) => r.service || '',
  resource: (r) => r.resource_id,
  type: (r) => r.resource_type || '',
  region: (r) => r.region || '',
  account: (r) => r.account,
  alias: (r) => r.account_name || '',
  result: (r) => r.result,
  status: (r) => r.status,
  first: (r) => r.first_evaluated || '',
  last: (r) => r.last_evaluated || '',
  fixed: (r) => r.date_fixed || '',
  tags: (r) => r.tags || '',
  qtags: (r) => r.qualys_tags || '',
}

export function FindingsView({ rows, loading, error, filters, onInteracting }: {
  rows: FindingRow[]; loading: boolean; error: string | null; filters: Filters
  onInteracting?: (v: boolean) => void
}) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [drill, setDrill] = useState<Record<string, Evidence[] | 'loading' | 'error'>>({})
  const { sort, onSort } = useSortState({ key: 'cid', dir: 'asc' })
  const cols = useColumns('qpd-findings-cols', FIND_COLS)
  const remMap = useRemediationMap()
  const COLS = cols.count
  useEffect(() => { onInteracting?.(open.size > 0) }, [open, onInteracting])
  const sorted = sortRows(rows, sort, FIND_ACCESSORS)
  const pg = usePagination(sorted, `${sort.key}:${sort.dir}`)

  const toggle = async (r: FindingRow) => {
    const next = new Set(open)
    if (next.has(r.uid)) { next.delete(r.uid); setOpen(next); return }
    next.add(r.uid); setOpen(next)
    if (!drill[r.uid]) {
      setDrill((d) => ({ ...d, [r.uid]: 'loading' }))
      try {
        const res = await api.findingEvidence(r, filters.as_of)
        setDrill((d) => ({ ...d, [r.uid]: res.evidence }))
      } catch {
        setDrill((d) => ({ ...d, [r.uid]: 'error' }))
      }
    }
  }

  const exportCsv = () => {
    const header = ['CID', 'Control', 'Severity', 'Service', 'Resource ID', 'Type', 'Region', 'Account', 'Account name',
      'Result', 'Status', 'First evaluated', 'Last evaluated', 'Fixed date', 'Evidence (summary)', 'Cloud tags', 'Qualys tags', 'Manual remediation']
    const data = sorted.map((r) => [
      r.control_id, r.control_name, r.criticality, r.service || '', r.resource_id, r.resource_type || '', r.region || '',
      r.account, r.account_name || '', r.result, r.status, r.first_evaluated || '', r.last_evaluated || '', r.date_fixed || '', r.evidence_summary || '',
      r.tags || '', r.qualys_tags || '', remediationFor(remMap, r.csp, r.control_id),
    ])
    downloadCsv('qualys-findings.csv', [header, ...data])
  }

  if (loading && !rows.length) return <div className="empty"><span className="spinner" /> Loading findings…</div>
  if (error && !rows.length) return <div className="empty">Could not load findings: {error}</div>

  return (
    <div>
      <div className="toolbar" style={{ justifyContent: 'flex-end' }}>
        <span style={{ display: 'flex', gap: 8 }}>
          <ColumnPicker cols={cols} />
          <button className="btn ghost" onClick={exportCsv}>⭳ Export CSV</button>
          <ExportXlsx view="findings" filters={filters} />
        </span>
      </div>

      {!rows.length ? (
        <div className="empty">No findings match the current filters.</div>
      ) : (
        <>
        <Pagination page={pg.page} totalPages={pg.totalPages} total={pg.total} size={pg.size} setSize={pg.setSize} onPage={pg.setPage} top />
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                {cols.has('cid') && <Th label="CID" col="cid" sort={sort} onSort={onSort} />}
                {cols.has('control') && <Th label="Control" col="control" sort={sort} onSort={onSort} />}
                {cols.has('severity') && <Th label="Severity" col="severity" sort={sort} onSort={onSort} />}
                {cols.has('service') && <Th label="Service" col="service" sort={sort} onSort={onSort} />}
                {cols.has('resource') && <Th label="Resource" col="resource" sort={sort} onSort={onSort} style={{ minWidth: 200 }} />}
                {cols.has('type') && <Th label="Type" col="type" sort={sort} onSort={onSort} />}
                {cols.has('region') && <Th label="Region" col="region" sort={sort} onSort={onSort} />}
                {cols.has('account') && <Th label="Account ID" col="account" sort={sort} onSort={onSort} />}
                {cols.has('alias') && <Th label="Account alias" col="alias" sort={sort} onSort={onSort} />}
                {cols.has('result') && <Th label="Result" col="result" sort={sort} onSort={onSort} />}
                {cols.has('status') && <Th label="Status" col="status" sort={sort} onSort={onSort} />}
                {cols.has('first') && <Th label="First evaluated" col="first" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('last') && <Th label="Last evaluated" col="last" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('fixed') && <Th label="Fixed date" col="fixed" sort={sort} onSort={onSort} style={{ whiteSpace: 'nowrap' }} />}
                {cols.has('evidence') && <th style={{ minWidth: 220 }}>Evidence</th>}
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
                      style={{ '--rs': sevVar(r.criticality) } as React.CSSProperties}>
                      {cols.has('cid') && (
                        <td className="nowrap">
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span className={`chev ${isOpen ? 'open' : ''}`}>▸</span>
                            <span className="mono cid-link">CID-{r.control_id}</span>
                          </div>
                        </td>
                      )}
                      {cols.has('control') && <td className="name" style={{ minWidth: 260 }}>{r.control_name}</td>}
                      {cols.has('severity') && <td><SevBadge s={r.criticality} /></td>}
                      {cols.has('service') && <td className="muted">{r.service || '—'}</td>}
                      {cols.has('resource') && <td><span className="mono name" style={{ wordBreak: 'break-all' }} title={r.resource_id}>{r.resource_id}</span></td>}
                      {cols.has('type') && <td><span className="csp-badge">{r.resource_type || '—'}</span></td>}
                      {cols.has('region') && <td className="muted nowrap">{r.region || '—'}</td>}
                      {cols.has('account') && <td className="mono muted nowrap">{r.account}</td>}
                      {cols.has('alias') && <td className="muted nowrap">{r.account_name || '—'}</td>}
                      {cols.has('result') && <td><span className={`badge ${r.result === 'FAIL' ? 'sev-HIGH' : 'result-pass'}`}>{r.result === 'FAIL' ? 'Fail' : 'Pass'}</span></td>}
                      {cols.has('status') && <td><StatusBadge s={r.status} /></td>}
                      {cols.has('first') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.first_evaluated?.slice(0, 10) || '—'}</td>}
                      {cols.has('last') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.last_evaluated?.slice(0, 10) || '—'}</td>}
                      {cols.has('fixed') && <td className="subtle nowrap" style={{ fontSize: 12 }}>{r.date_fixed?.slice(0, 10) || '—'}</td>}
                      {cols.has('evidence') && (
                        <td className="evidence" style={{ maxWidth: 300 }} title={r.evidence_summary || ''}>
                          <div className="clamp1">{r.evidence_summary || '—'}</div>
                        </td>
                      )}
                      {cols.has('tags') && <TagsCell tags={r.tags} />}
                      {cols.has('qtags') && <TagsCell tags={r.qualys_tags} kind="qualys" />}
                      {cols.has('rem') && <RemediationCell text={remediationFor(remMap, r.csp, r.control_id)} />}
                    </tr>
                    {isOpen && (
                      <tr className="expand-panel">
                        <td colSpan={COLS} style={{ padding: 0 }}>
                          <div style={{ padding: '10px 14px 14px 40px' }}>
                            <div className="section-title">
                              CID-{r.control_id} · {r.control_name}{r.policies.length ? ` · ${r.policies.slice(0, 4).join(', ')}` : ''}
                            </div>
                            <EvidenceDrill state={drill[r.uid]} account={accountLabel(r.account, r.account_name)} />
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

function EvidenceDrill({ state, account }: { state: Evidence[] | 'loading' | 'error' | undefined; account: string }) {
  if (state === 'loading' || state === undefined) return <div className="subtle"><span className="spinner" /> Loading evidence…</div>
  if (state === 'error') return <div className="subtle">Could not load evidence.</div>
  if (!state.length) return <div className="subtle">No evidence recorded for this finding ({account}).</div>
  return (
    <table>
      <thead><tr><th>Setting</th><th>Actual value</th></tr></thead>
      <tbody>
        {state.map((e, i) => (
          <tr key={i}><td className="muted">{e.settingName}</td><td className="mono">{e.actualValue}</td></tr>
        ))}
      </tbody>
    </table>
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
