import { exportXlsxUrl, type ExportView } from '../api'
import type { Filters } from '../types'

/** Excel export button. Unlike the CSV export (built in the browser from the loaded rows), the
 *  workbook is rendered by the backend so it can carry a **Manual remediation** column — the
 *  remediation text is joined per control server-side. It reflects the active filters; the
 *  client-side sort order and column picks do not apply. */
export function ExportXlsx({ view, filters }: { view: ExportView; filters: Partial<Filters> }) {
  return (
    <a
      className="btn ghost"
      href={exportXlsxUrl(view, filters)}
      title="Download this view as Excel (.xlsx), including a Manual remediation column"
    >
      ⭳ Export Excel
    </a>
  )
}
