import { useState } from 'react'

/** Light (default, Qualys product look) ↔ dark (demo-lab charcoal). Persisted to localStorage. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'),
  )
  const toggle = () => {
    const next = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    if (next === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
    else document.documentElement.removeAttribute('data-theme')
    try { localStorage.setItem('qpd-theme', next) } catch { /* ignore */ }
  }
  return (
    <button className="btn ghost theme-toggle" onClick={toggle}
      title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
