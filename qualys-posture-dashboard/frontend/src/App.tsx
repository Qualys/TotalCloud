import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { EMPTY_FILTERS, type ControlRow, type Facets, type FindingRow, type Filters, type ResourceRow, type ResourceStats, type Status, type TrendPoint } from './types'
import { Setup } from './components/Setup'
import { Header } from './components/Header'
import { HeroBand } from './components/HeroBand'
import { ActiveFilterChips } from './components/ActiveFilterChips'
import { QuickFilters } from './components/QuickFilters'
import { ControlsView } from './components/ControlsView'
import { ResourceView } from './components/ResourceView'
import { FindingsView } from './components/FindingsView'
import { SettingsModal } from './components/SettingsModal'

type View = 'controls' | 'resources' | 'findings'

const EMPTY_STATS: ResourceStats = { failing_resources: 0, passing_resources: 0, total_resources: 0, new_30d: 0, reopened: 0, fixed_30d: 0 }

export default function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)
  const [view, setView] = useState<View>('controls')
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [facets, setFacets] = useState<Facets | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const [controls, setControls] = useState<ControlRow[]>([])
  const [resources, setResources] = useState<ResourceRow[]>([])
  const [rstats, setRstats] = useState<ResourceStats>(EMPTY_STATS)
  const [findings, setFindings] = useState<FindingRow[]>([])
  // Lifecycle totals for the whole facet set (server-computed), so the Status rail can show FIXED
  // and the others at their true counts even though the default list loads only failing rows.
  const [findingStatusCounts, setFindingStatusCounts] = useState<Record<string, number> | null>(null)
  const [dataLoading, setDataLoading] = useState(true)
  const [dataErr, setDataErr] = useState<string | null>(null)
  const [interacting, setInteracting] = useState(false)   // a row/drill-down is expanded
  const [settingsOpen, setSettingsOpen] = useState(false)
  const pollRef = useRef<number | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const s = await api.status(); setStatus(s); setBootError(null); return s
    } catch (e) {
      setBootError(e instanceof Error ? e.message : 'Cannot reach the backend'); return null
    }
  }, [])

  const loadTrend = useCallback(async () => {
    try {
      setTrend((await api.trend({
        cloud: filters.cloud, account: filters.account, severity: filters.severity,
        service: filters.service, policy: filters.policy,
      })).trend)
    } catch { /* ignore */ }
  }, [filters.cloud, filters.account, filters.severity, filters.service, filters.policy])

  const loadFacets = useCallback(async () => {
    try { setFacets(await api.facets({ cloud: filters.cloud, as_of: filters.as_of })) } catch { /* ignore */ }
  }, [filters.cloud, filters.as_of])

  const hasData = !!status?.creds_set || !!status?.demo_mode

  // Fetch the active view's rows whenever the filters/view/refresh change.
  const loadData = useCallback(async () => {
    setDataLoading(true); setDataErr(null)
    try {
      if (view === 'controls') {
        setControls((await api.controls(filters)).controls)
      } else if (view === 'resources') {
        const r = await api.resources(filters)
        setResources(r.resources); setRstats(r.stats || EMPTY_STATS)
      } else {
        const fr = await api.findings(filters)
        setFindings(fr.findings); setFindingStatusCounts(fr.status_counts || null)
      }
    } catch (e) {
      setDataErr(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setDataLoading(false)
    }
  }, [view, filters])

  useEffect(() => { loadStatus() }, [loadStatus])
  // Refetch on filter/view change or a refresh tick — but while a sync is streaming, DON'T yank the
  // table out from under an expanded row (it would reorder + collapse it). Resume once collapsed.
  useEffect(() => {
    if (!hasData) return
    if (status?.syncing && interacting) return
    loadData(); loadFacets()
  }, [hasData, loadData, loadFacets, reloadKey, status?.syncing, interacting])
  useEffect(() => { if (hasData) loadTrend() }, [hasData, status?.last_sync, loadTrend])

  // Poll while a sync runs; refetch data/facets/trend every tick so partial data streams in live.
  useEffect(() => {
    if (status?.syncing) {
      if (pollRef.current == null) {
        pollRef.current = window.setInterval(async () => {
          const s = await loadStatus()
          setReloadKey((k) => k + 1)
          loadTrend()
          if (s && !s.syncing && pollRef.current != null) { clearInterval(pollRef.current); pollRef.current = null }
        }, 1500)
      }
    }
    return () => {
      if (pollRef.current != null && !status?.syncing) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [status?.syncing, loadStatus, loadTrend])

  const onRefresh = useCallback(async () => {
    try { await api.sync(); await loadStatus() }
    catch (e) { alert(e instanceof Error ? e.message : 'Refresh failed') }
  }, [loadStatus])

  if (bootError && !status) {
    return <div className="empty" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>Backend unreachable: {bootError}</div>
  }
  if (!status) return <div className="empty" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><span className="spinner" /></div>
  if (!status.creds_set && !status.demo_mode) return <Setup onDone={() => loadStatus()} />

  const clearAll = () => setFilters({ ...EMPTY_FILTERS, as_of: filters.as_of })

  return (
    <div className="app">
      {status.syncing && <div className="syncbar" />}
      <Header
        status={status} view={view} onView={setView} onRefresh={onRefresh}
        syncing={!!status.syncing} syncProgress={status.sync_progress}
        filters={filters} onFilters={setFilters} onSettings={() => setSettingsOpen(true)}
      />

      {settingsOpen && (
        <SettingsModal
          status={status}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => { setSettingsOpen(false); loadStatus() }}
        />
      )}

      {status.demo_mode && (
        <div className="demo-banner">● Demo mode — showing synthetic sample data. Real posture appears after you connect live Qualys credentials and Refresh.</div>
      )}

      {!status.latest_snapshot && !status.syncing ? (
        <div className="empty">No snapshot yet. Click <b>Refresh</b> to pull your first posture snapshot from Qualys.</div>
      ) : (
        <>
          {view !== 'findings' && (
            <HeroBand view={view} controls={controls} resources={resources} rstats={rstats} trend={trend} />
          )}
          <ActiveFilterChips filters={filters} onFilters={setFilters} onClear={clearAll} />
          <div className="layout">
            <QuickFilters
              view={view} filters={filters} onFilters={setFilters} facets={facets}
              status={status} controls={controls} resources={resources} findings={findings}
              findingStatusCounts={findingStatusCounts}
            />
            <main className="content">
              {view === 'controls'
                ? <ControlsView rows={controls} loading={dataLoading} error={dataErr} filters={filters} onInteracting={setInteracting} />
                : view === 'resources'
                ? <ResourceView rows={resources} stats={rstats} loading={dataLoading} error={dataErr} filters={filters} onInteracting={setInteracting} />
                : <FindingsView rows={findings} loading={dataLoading} error={dataErr} filters={filters} onInteracting={setInteracting} />}
            </main>
          </div>
        </>
      )}
    </div>
  )
}
