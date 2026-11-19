import type { AccountRef, Severity } from './types'

// Qualys CloudView CSPM criticality has only three levels: HIGH / MEDIUM / LOW.
export const SEVERITIES: Severity[] = ['HIGH', 'MEDIUM', 'LOW']

/** "acme-prod (123456789012)" when the alias is known, else the bare account id. */
export function accountLabel(account: string, name?: string | null): string {
  return name ? `${name} (${account})` : account
}

export function accountRefLabel(a: AccountRef): string {
  return accountLabel(a.account, a.name)
}

/** Failing percentage of an evaluated control (0 when nothing evaluated). */
export function failPct(failed: number, total: number): number {
  return total > 0 ? Math.round((failed / total) * 100) : 0
}

/** Graduated colour class for a fail-% cell (green → amber → orange → red). */
export function pctTone(pct: number): string {
  if (pct < 25) return 'pct-ok'
  if (pct < 50) return 'pct-warn'
  if (pct < 75) return 'pct-bad'
  return 'pct-crit'
}

/** Lower-cased cloud class for a tinted csp-badge (aws/azure/gcp). */
export function cloudClass(csp: string): string {
  const c = (csp || '').toLowerCase()
  return c === 'aws' || c === 'azure' || c === 'gcp' ? c : ''
}

/** Score → gauge arc colour (muted, graded). */
export function scoreColor(score: number): string {
  if (score >= 90) return 'var(--ok)'
  if (score >= 75) return 'var(--accent)'
  if (score >= 50) return 'var(--sev-medium)'
  return 'var(--sev-high)'
}

const SEV_RANK: Record<Severity, number> = {
  CRITICAL: 5, HIGH: 4, MEDIUM: 3, LOW: 2, INFORMATIONAL: 1,
}
export const sevRank = (s: string) => SEV_RANK[(s || 'MEDIUM').toUpperCase() as Severity] ?? 0

export const sevVar = (s: Severity) => `var(--sev-${s.toLowerCase()})`

export function relTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'never'
  const s = Math.round((Date.now() - then) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export function downloadCsv(filename: string, rows: (string | number)[][]) {
  const esc = (v: string | number) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = rows.map((r) => r.map(esc).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
