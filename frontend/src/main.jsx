import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { wakeBackend } from './lib/backend'
import './index.css'

// Wake the sleeping backend as soon as the page opens, so it has usually finished
// loading the model by the time someone submits a clip.
wakeBackend()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
