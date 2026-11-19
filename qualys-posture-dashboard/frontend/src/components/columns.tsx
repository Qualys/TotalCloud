import { useEffect, useRef, useState } from 'react'

export interface ColumnDef { key: string; label: string; required?: boolean; default?: boolean }

/** Column-visibility preference, persisted to localStorage. Defaults to the required + `default` set;
 *  required columns can't be hidden. */
export function useColumns(storageKey: string, defs: ColumnDef[]) {
  const baseline = () => new Set(defs.filter((d) => d.required || d.default).map((d) => d.key))
  const [visible, setVisible] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const keys: string[] = JSON.parse(saved)
        const valid = new Set(defs.map((d) => d.key))
        const s = new Set(keys.filter((k) => valid.has(k)))
        defs.forEach((d) => { if (d.required) s.add(d.key) })   // required always on
        return s
      }
    } catch { /* ignore */ }
    return baseline()
  })
  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify([...visible])) } catch { /* ignore */ }
  }, [storageKey, visible])

  const has = (k: string) => visible.has(k)
  const toggle = (k: string) => setVisible((prev) => {
    if (defs.find((d) => d.key === k)?.required) return prev
    const next = new Set(prev)
    if (next.has(k)) next.delete(k); else next.add(k)
    return next
  })
  const reset = () => setVisible(baseline())
  const count = defs.filter((d) => visible.has(d.key)).length
  return { has, toggle, reset, count, defs }
}

export function ColumnPicker({ cols }: { cols: ReturnType<typeof useColumns> }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])
  return (
    <div className="col-picker" ref={ref}>
      <button className="btn ghost" onClick={() => setOpen((o) => !o)} title="Choose which columns to show">
        ⊞ Columns <span className="subtle">({cols.count})</span>
      </button>
      {open && (
        <div className="col-menu">
          <div className="col-menu-head">
            <span>Show columns</span>
            <button className="btn ghost" onClick={cols.reset} style={{ padding: '2px 6px' }}>Reset</button>
          </div>
          {cols.defs.map((d) => (
            <label key={d.key} className="col-item">
              <input type="checkbox" checked={cols.has(d.key)} disabled={d.required} onChange={() => cols.toggle(d.key)} />
              <span>{d.label}</span>
              {d.required && <span className="subtle" style={{ marginLeft: 'auto', fontSize: 11 }}>required</span>}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
