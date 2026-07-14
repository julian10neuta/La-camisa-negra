import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { applySettings, loadSettings } from './settings/settingsStore'

// Los ajustes visuales se aplican ANTES de montar React: si esperáramos al
// primer render, la app se pintaría un instante con el tema por defecto y luego
// saltaría al del usuario (el clásico parpadeo de tema).
applySettings(loadSettings())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
