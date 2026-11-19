import { useState } from 'react'

export type SortDir = 'asc' | 'desc'
export interface SortState { key: string; dir: SortDir }
export type Accessor<T> = (r: T) => string | number | null | undefined

/** Sort state + a toggle: first click on a column sorts desc, second flips to asc. */
export function useSortState(init: SortState) {
  const [sort, setSort] = useState<SortState>(init)
  const onSort = (key: string) =>
    setSort((p) => (p.key === key ? { key, dir: p.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))
  return { sort, onSort }
}

/** Pure sort — numbers compare numerically, everything else by locale string. */
export function sortRows<T>(rows: T[], sort: SortState, accessors: Record<string, Accessor<T>>): T[] {
  const acc = accessors[sort.key]
  if (!acc) return rows
  const mul = sort.dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = acc(a), bv = acc(b)
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mul
    return String(av ?? '').localeCompare(String(bv ?? '')) * mul
  })
}

/** A clickable sortable header cell. `align` right-aligns numeric columns. */
export function Th({ label, col, sort, onSort, align, style }: {
  label: React.ReactNode
  col: string
  sort: SortState
  onSort: (k: string) => void
  align?: 'right'
  style?: React.CSSProperties
}) {
  const active = sort.key === col
  return (
    <th
      className={`sortable-th ${active ? 'active' : ''} ${align === 'right' ? 'right' : ''}`}
      style={style} onClick={() => onSort(col)} title="Click to sort"
    >
      <span className="th-inner">{label}<span className="sort-arrow">{active ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'}</span></span>
    </th>
  )
}
