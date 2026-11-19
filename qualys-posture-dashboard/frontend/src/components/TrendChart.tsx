import type { TrendPoint } from '../types'

/** Compact 30-day stacked pass/fail area chart for the header. */
export function TrendChart({ data, width = 260, height = 56 }: { data: TrendPoint[]; width?: number; height?: number }) {
  if (data.length < 2) {
    return <div className="sync-meta">Not enough history yet — refresh over multiple days to build the 30-day trend.</div>
  }
  const totals = data.map((d) => d.passed + d.failed)
  const max = Math.max(...totals, 1)
  const n = data.length
  const step = width / (n - 1)
  const y = (v: number) => height - (v / max) * (height - 2) - 1

  const failLine = data.map((d, i) => `${(i * step).toFixed(1)},${y(d.failed).toFixed(1)}`)
  const failArea = `0,${height} ${failLine.join(' ')} ${width},${height}`
  const totalLine = data.map((d, i) => `${(i * step).toFixed(1)},${y(d.passed + d.failed).toFixed(1)}`)

  return (
    <div className="trend-card card">
      <div>
        <div className="section-title" style={{ marginBottom: 8 }}>30-day posture</div>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-label="30 day pass fail trend">
          <polygon points={totalLine.join(' ') + ` ${width},${height} 0,${height}`}
            fill="color-mix(in srgb, var(--ok) 22%, transparent)" />
          <polygon points={failArea} fill="color-mix(in srgb, var(--sev-high) 30%, transparent)" />
          <polyline points={failLine.join(' ')} fill="none" stroke="var(--sev-high)" strokeWidth="1.5" />
        </svg>
      </div>
      <div className="trend-legend">
        <div><span className="legend-swatch" style={{ background: 'var(--sev-high)' }} />Failing</div>
        <div><span className="legend-swatch" style={{ background: 'var(--ok)' }} />Passing</div>
      </div>
    </div>
  )
}
