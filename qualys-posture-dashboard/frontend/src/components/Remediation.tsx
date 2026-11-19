import { useEffect, useState } from 'react'
import { api } from '../api'

/** Manual remediation text per control, fetched ONCE per session and shared by every table.
 *  Rendering it as a column (not only in the expand drawer) means the fix is visible without a
 *  click and lands in the CSV export; the drawer still carries CLI / IaC / rationale / references. */
let cache: Record<string, string> | null = null
let inflight: Promise<Record<string, string>> | null = null

export function useRemediationMap(): Record<string, string> {
  const [map, setMap] = useState<Record<string, string>>(cache || {})
  useEffect(() => {
    if (cache) { setMap(cache); return }
    let alive = true
    inflight = inflight || api.remediationMap().catch(() => ({}))
    inflight.then((m) => { cache = m; if (alive) setMap(m) })
    return () => { alive = false }
  }, [])
  return map
}

export const remediationFor = (map: Record<string, string>, csp: string, controlId: string) =>
  map[`${csp}:${controlId}`] || ''

/** Table cell: two clamped lines, full text on hover. */
export function RemediationCell({ text }: { text: string }) {
  if (!text) return <td className="subtle">—</td>
  return (
    <td className="rem-cell" title={text}>
      <div className="clamp2">{text}</div>
    </td>
  )
}
