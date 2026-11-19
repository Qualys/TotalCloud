import { useState } from 'react'
import { api } from '../api'

/** Qualys shared-platform API gateway URLs (Gateway host = gateway.<pod>.apps.qualys.<tld>). */
export const PODS: { label: string; url: string }[] = [
  { label: 'US Platform 1 (US1)', url: 'https://gateway.qg1.apps.qualys.com' },
  { label: 'US Platform 2 (US2)', url: 'https://gateway.qg2.apps.qualys.com' },
  { label: 'US Platform 3 (US3)', url: 'https://gateway.qg3.apps.qualys.com' },
  { label: 'US Platform 4 (US4)', url: 'https://gateway.qg4.apps.qualys.com' },
  { label: 'EU Platform 1 (EU1)', url: 'https://gateway.qg1.apps.qualys.eu' },
  { label: 'EU Platform 2 (EU2)', url: 'https://gateway.qg2.apps.qualys.eu' },
  { label: 'EU Platform 3 (EU3)', url: 'https://gateway.qg3.apps.qualys.it' },
  { label: 'India Platform 1 (IN1)', url: 'https://gateway.qg1.apps.qualys.in' },
  { label: 'Canada Platform 1 (CA1)', url: 'https://gateway.qg1.apps.qualys.ca' },
  { label: 'UAE Platform 1 (AE1)', url: 'https://gateway.qg1.apps.qualys.ae' },
  { label: 'UK Platform 1 (UK1)', url: 'https://gateway.qg1.apps.qualys.co.uk' },
  { label: 'Australia Platform 1 (AU1)', url: 'https://gateway.qg1.apps.qualys.com.au' },
  { label: 'KSA Platform 1 (KSA1)', url: 'https://gateway.qg1.apps.qualysksa.com' },
]
export const CUSTOM = '__custom__'

export function Setup({ onDone }: { onDone: () => void }) {
  const [pod, setPod] = useState('')          // selected preset URL, or CUSTOM, or '' (unset)
  const [customUrl, setCustomUrl] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const gateway = pod === CUSTOM ? customUrl.trim() : pod

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!gateway) { setError('Select your Qualys platform (or enter a custom gateway URL).'); return }
    setBusy(true); setError(null)
    try {
      await api.saveCreds({ gateway_url: gateway, username: username.trim(), password })
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate credentials')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="setup-wrap">
      <form className="setup-card card" onSubmit={submit}>
        <div className="brand" style={{ marginBottom: 18 }}>
          <span className="dot" /> Qualys Posture Dashboard
        </div>
        <h1>Connect your Qualys account</h1>
        <p className="lead">
          Enter your Qualys platform credentials once. We validate them, then pull your CSPM posture
          across all your cloud accounts. Everything stays on this machine.
        </p>

        {error && <div className="error-box">{error}</div>}

        <div className="setup-field">
          <label htmlFor="pod">Qualys platform</label>
          <select id="pod" value={pod} onChange={(e) => setPod(e.target.value)} required autoFocus>
            <option value="" disabled>Select your Qualys platform…</option>
            {PODS.map((p) => <option key={p.url} value={p.url}>{p.label} — {p.url.replace('https://', '')}</option>)}
            <option value={CUSTOM}>Custom gateway URL…</option>
          </select>
          {pod === CUSTOM ? (
            <input type="text" placeholder="https://gateway.<pod>.apps.qualys.com  (or a POD id like US1)"
              value={customUrl} onChange={(e) => setCustomUrl(e.target.value)} required
              style={{ marginTop: 8 }} />
          ) : (
            <span className="hint">Not sure? It's the platform your Qualys UI runs on (shown in your Qualys URL).</span>
          )}
        </div>

        <div className="setup-field">
          <label htmlFor="user">Username</label>
          <input id="user" type="text" autoComplete="username"
            value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>

        <div className="setup-field">
          <label htmlFor="pw">Password</label>
          <input id="pw" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />
          <span className="hint">
            Needs CloudView / CSPM read access (Reader-equivalent API permissions). Stored encrypted
            on this machine only, never logged or transmitted anywhere but your Qualys gateway.
          </span>
        </div>

        <button className="btn primary" type="submit" disabled={busy} style={{ width: '100%', justifyContent: 'center', marginTop: 6 }}>
          {busy ? <><span className="spinner" /> Validating &amp; starting first pull…</> : 'Connect & pull posture'}
        </button>
      </form>
    </div>
  )
}
