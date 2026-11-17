import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { API_BASE } from './lib/analysis'
import './index.css'

// The backend sleeps when idle. Wake it as soon as the page opens, so it has usually
// finished loading the model by the time someone submits a clip.
if (API_BASE) fetch(`${API_BASE}/api/v1/health`, { cache: 'no-store' }).catch(() => {})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)