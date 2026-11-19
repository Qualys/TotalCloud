/** Resource tags rendered as chips. Two independent kinds, never merged:
 *   - `kind="cloud"`  — the provider's own tags (AWS cloudTags), "key=value"
 *   - `kind="qualys"` — Qualys asset tag names, from the resource-inventory API
 *  Both are sparse by nature, so an empty cell is normal, not a bug. Full set is on the title. */
export function TagsCell({ tags, kind = 'cloud' }: { tags: string; kind?: 'cloud' | 'qualys' }) {
  const list = (tags || '').split('; ').filter(Boolean)
  if (!list.length) return <td className="subtle">—</td>
  return (
    <td style={{ maxWidth: 280 }} title={list.join('\n')}>
      <div className="tag-chips">
        {list.slice(0, 2).map((t) => <span className={`tag-chip ${kind}`} key={t}>{t}</span>)}
        {list.length > 2 && <span className="tag-chip more">+{list.length - 2}</span>}
      </div>
    </td>
  )
}

/** Same chips, for the drawers (not a table cell). One row per tag kind. */
export function TagChips({ tags, qualysTags }: { tags: string; qualysTags: string }) {
  return (
    <>
      <TagRow label="Cloud tags" tags={tags} kind="cloud" />
      <TagRow label="Qualys tags" tags={qualysTags} kind="qualys" />
    </>
  )
}

function TagRow({ label, tags, kind }: { label: string; tags: string; kind: 'cloud' | 'qualys' }) {
  const list = (tags || '').split('; ').filter(Boolean)
  if (!list.length) return null
  return (
    <div className="tag-row">
      <span className="tag-row-label">{label}</span>
      <div className="tag-chips">
        {list.map((t) => <span className={`tag-chip ${kind}`} key={t}>{t}</span>)}
      </div>
    </div>
  )
}
