import type { ControlRow, ResourceRow, ResourceStats, TrendPoint } from '../types'
import { scoreColor } from '../util'
import { TrendChart } from './TrendChart'

type View = 'controls' | 'resources'

interface Props {
  view: View
  controls: ControlRow[]
  resources: ResourceRow[]
  rstats: ResourceStats
  trend: TrendPoint[]
}

export function HeroBand({ view, controls, resources, rstats, trend }: Props) {
  void resources
  let score = 0, pass = 0, fail = 0
  if (view === 'controls') {
    pass = controls.reduce((s, r) => s + r.passed, 0)
    fail = controls.reduce((s, r) => s + r.failed, 0)
    score = pass + fail > 0 ? Math.round((pass / (pass + fail)) * 100) : 100
  } else {
    pass = rstats.passing_resources
    fail = rstats.failing_resources
    const tot = rstats.total_resources || pass + fail
    score = tot > 0 ? Math.round((pass / tot) * 100) : 100
  }
  const failPctTotal = pass + fail > 0 ? Math.round((fail / (pass + fail)) * 100) : 0
  const delta = trend.length >= 2
    ? (() => {
        const a = trend[0], b = trend[trend.length - 1]
        const sa = a.passed + a.failed > 0 ? (a.passed / (a.passed + a.failed)) * 100 : 100
        const sb = b.passed + b.failed > 0 ? (b.passed / (b.passed + b.failed)) * 100 : 100
        return Math.round(sb - sa)
      })()
    : null
  const unit = view === 'controls' ? 'checks' : 'resources'
  const label = score >= 90 ? 'Excellent' : score >= 75 ? 'Good standing' : score >= 50 ? 'Needs attention' : 'At risk'

  return (
    <div className="hero">
      <div className="htile">
        <div className="lbl">Posture score</div>
        <div className="score">
          <div className="gauge" style={{ background: `conic-gradient(${scoreColor(score)} 0 ${score}%, var(--surface-3) 0)` }}>
            <span>{score}</span>
          </div>
          <div className="meta">
            <div className="big">{label}</div>
            {delta !== null && (
              <div className="delta" style={{ color: delta >= 0 ? 'var(--ok)' : 'var(--sev-high)' }}>
                {delta >= 0 ? '▲' : '▼'} {delta >= 0 ? '+' : ''}{delta} pts vs 30 days ago
              </div>
            )}
            <div className="sub">{pass.toLocaleString()} passing of {(pass + fail).toLocaleString()} {unit}</div>
          </div>
        </div>
      </div>

      <div className="htile">
        <div className="lbl">Compliance</div>
        <div className="donut">
          <div className="ring" style={{ background: `conic-gradient(var(--sev-high) 0 ${failPctTotal}%, var(--ok) 0)` }}>
            <div className="c"><div><b>{score}%</b><br /><small>pass</small></div></div>
          </div>
          <div className="legend">
            <div><i style={{ background: 'var(--ok)' }} />Passing · {pass.toLocaleString()}</div>
            <div><i style={{ background: 'var(--sev-high)' }} />Failing · {fail.toLocaleString()}</div>
          </div>
        </div>
      </div>

      <div className="htile">
        <div className="lbl">30-day posture trend</div>
        <TrendChart data={trend} />
      </div>
    </div>
  )
}
