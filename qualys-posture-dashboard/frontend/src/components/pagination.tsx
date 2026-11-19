import { useEffect, useState } from 'react'

export const PAGE_SIZES = [50, 100, 200]
const DEFAULT_SIZE = 50

/** Client-side pagination with a user-selectable page size (persisted). Only `size` rows render at
 *  once (keeps the DOM small → fast scroll). `resetKey` (e.g. the sort spec) snaps back to page 1
 *  when it changes; growing/shrinking row sets are clamped so a background refresh never throws you
 *  off the end. */
export function usePagination<T>(rows: T[], resetKey: string) {
  const [size, setSizeState] = useState<number>(() => {
    const saved = Number(localStorage.getItem('qpd-page-size'))
    return PAGE_SIZES.includes(saved) ? saved : DEFAULT_SIZE
  })
  const [page, setPage] = useState(1)
  useEffect(() => { setPage(1) }, [resetKey, size])
  const setSize = (s: number) => { setSizeState(s); try { localStorage.setItem('qpd-page-size', String(s)) } catch { /* ignore */ } }

  const total = rows.length
  const totalPages = Math.max(1, Math.ceil(total / size))
  const clamped = Math.min(page, totalPages)
  const pageRows = rows.slice((clamped - 1) * size, clamped * size)
  return { page: clamped, setPage, pageRows, total, totalPages, size, setSize }
}

export function Pagination({ page, totalPages, total, size, setSize, onPage, top }: {
  page: number; totalPages: number; total: number; size: number
  setSize: (s: number) => void; onPage: (p: number) => void; top?: boolean
}) {
  if (total <= PAGE_SIZES[0] && total <= size) return null
  const from = total === 0 ? 0 : (page - 1) * size + 1
  const to = Math.min(page * size, total)
  return (
    <div className={`pagination${top ? ' pagination-top' : ''}`}>
      <span className="pg-left">
        <span className="subtle">{from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}</span>
        <label className="pg-size">Rows
          <select value={size} onChange={(e) => setSize(Number(e.target.value))}>
            {PAGE_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </span>
      <div className="pager">
        <button className="btn ghost" disabled={page <= 1} onClick={() => onPage(1)} title="First">«</button>
        <button className="btn ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹ Prev</button>
        <span className="subtle" style={{ padding: '0 6px' }}>Page {page} / {totalPages}</span>
        <button className="btn ghost" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Next ›</button>
        <button className="btn ghost" disabled={page >= totalPages} onClick={() => onPage(totalPages)} title="Last">»</button>
      </div>
    </div>
  )
}
