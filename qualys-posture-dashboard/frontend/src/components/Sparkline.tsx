interface Props {
  values: number[]
  width?: number
  height?: number
  color?: string
}

/** Tiny inline SVG sparkline of a numeric series (e.g. 30-day failing count). */
export function Sparkline({ values, width = 96, height = 24, color = 'var(--sev-high)' }: Props) {
  if (!values.length) return <span className="subtle">—</span>
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const n = values.length
  const step = n > 1 ? width / (n - 1) : 0
  const pts = values.map((v, i) => {
    const x = i * step
    const y = height - 2 - ((v - min) / range) * (height - 4)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const last = values[n - 1]
  const lastX = (n - 1) * step
  const lastY = height - 2 - ((last - min) / range) * (height - 4)
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinejoin="round" strokeLinecap="round" opacity="0.85" />
      <circle cx={lastX} cy={lastY} r="2" fill={color} />
    </svg>
  )
}
