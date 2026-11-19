import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

// Apply the saved theme before first paint (default: light, matching the Qualys product) to avoid a flash.
if (localStorage.getItem('qpd-theme') === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
