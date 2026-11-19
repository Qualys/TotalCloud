import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Schedule, Status } from '../types'
import { PODS, CUSTOM } from './Setup'

/** Update the Qualys credentials / connected platform without leaving the dashboard. On save it
 *  re-validates (mint JWT), persists (encrypted), and kicks off a fresh sync. */
export function SettingsModal({ status, onClose, onSaved }: {
  status: Status; onClose: () => void; onSaved: () => void
}) {
  const known = PODS.find((p) => p.url === status.gateway_url)
  const [pod, setPod] = useState(known ? known.url : status.gateway_url ? CUSTOM : '')
  const [customUrl, setCustomUrl] = useState(known ? '' : status.gateway_url || '')
  const [username, setUsername] = useState(status.username || '')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Auto-refresh schedule (saved independently of credentials — no password needed).
  const [sched, setSched] = useState<Schedule>({ enabled: false, mode: 'daily', time: '06:00', hours: 6 })
  const [schedMsg, setSchedMsg] = useState<string | null>(null)
  const [schedBusy, setSchedBusy] = useState(false)
  useEffect(() => { api.schedule().then(setSched).catch(() => {}) }, [])
  const saveSchedule = async () => {
    setSchedBusy(true); setSchedMsg(null)
    try { await api.saveSchedule(sched); setSchedMsg('Schedule saved.') }
    catch (e) { setSchedMsg(e instanceof Error ? e.message : 'Could not save schedule.') }
    finally { setSchedBusy(false) }
  }

  const gateway = pod === CUSTOM ? customUrl.trim() : pod

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!gateway) { setError('Select your Qualys platform (or enter a custom gateway URL).'); return }
    if (!password) { setError('Enter the password to re-validate and save.'); return }
    setBusy(true); setError(null)
    try {
      await api.saveCreds({ gateway_url: gateway, username: username.trim(), password })
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate credentials')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-scrim" onMouseDown={onClose}>
      <form className="modal card" onMouseDown={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="modal-head">
          <span>Qualys credentials</span>
          <button type="button" className="btn ghost" onClick={onClose} title="Close">✕</button>
        </div>

        <p className="hint" style={{ margin: '0 0 14px' }}>
          Update the connected platform or credentials. Saving re-validates and pulls a fresh snapshot.
          Stored encrypted on this machine only.
        </p>

        {error && <div className="error-box">{error}</div>}

        <div className="setup-field">
          <label htmlFor="s-pod">Qualys platform</label>
          <select id="s-pod" value={pod} onChange={(e) => setPod(e.target.value)} required>
            <option value="" disabled>Select your Qualys platform…</option>
            {PODS.map((p) => <option key={p.url} value={p.url}>{p.label} — {p.url.replace('https://', '')}</option>)}
            <option value={CUSTOM}>Custom gateway URL…</option>
          </select>
          {pod === CUSTOM && (
            <input type="text" placeholder="https://gateway.<pod>.apps.qualys.com" value={customUrl}
              onChange={(e) => setCustomUrl(e.target.value)} required style={{ marginTop: 8 }} />
          )}
        </div>

        <div className="setup-field">
          <label htmlFor="s-user">Username</label>
          <input id="s-user" type="text" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>

        <div className="setup-field">
          <label htmlFor="s-pw">Password</label>
          <input id="s-pw" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} placeholder="Re-enter to save" required />
          <span className="hint">The stored password is never shown — re-enter it to re-validate and save.</span>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 6 }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? <><span className="spinner" /> Validating…</> : 'Save & refresh'}
          </button>
        </div>

        <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '18px 0 14px' }} />

        <div className="modal-head" style={{ fontSize: 14, marginBottom: 8 }}>Automatic refresh</div>
        <label className="sched-row">
          <input type="checkbox" checked={sched.enabled} onChange={(e) => setSched({ ...sched, enabled: e.target.checked })} />
          <span>Refresh automatically on a schedule</span>
        </label>
        {sched.enabled && (
          <div className="sched-body">
            <label className="sched-row">
              <input type="radio" name="sched-mode" checked={sched.mode === 'daily'} onChange={() => setSched({ ...sched, mode: 'daily' })} />
              <span>Every day at</span>
              <input type="time" value={sched.time} onChange={(e) => setSched({ ...sched, time: e.target.value })}
                disabled={sched.mode !== 'daily'} style={{ minWidth: 0, width: 110 }} />
            </label>
            <label className="sched-row">
              <input type="radio" name="sched-mode" checked={sched.mode === 'interval'} onChange={() => setSched({ ...sched, mode: 'interval' })} />
              <span>Every</span>
              <input type="number" min={1} max={168} value={sched.hours}
                onChange={(e) => setSched({ ...sched, hours: Math.max(1, Number(e.target.value) || 1) })}
                disabled={sched.mode !== 'interval'} style={{ minWidth: 0, width: 70 }} />
              <span>hours</span>
            </label>
          </div>
        )}
        <span className="hint" style={{ display: 'block', marginTop: 4 }}>
          Runs inside the app while it's open/running — no OS cron needed. Requires stored credentials.
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end', marginTop: 8 }}>
          {schedMsg && <span className="subtle" style={{ fontSize: 12 }}>{schedMsg}</span>}
          <button type="button" className="btn" onClick={saveSchedule} disabled={schedBusy}>
            {schedBusy ? <><span className="spinner" /> Saving…</> : 'Save schedule'}
          </button>
        </div>
      </form>
    </div>
  )
}
