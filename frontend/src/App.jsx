import './App.css'
import { BrowserRouter } from 'react-router-dom'
import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Callback from './pages/Callback'
import Search from './pages/Search'
import Settings from './pages/Settings'
import { PlayerProvider } from './player/PlayerContext'
import { SettingsProvider } from './settings/SettingsContext'
import NowPlaying from './components/NowPlaying'

function App() {
  return (
    <BrowserRouter>
      {/* Los ajustes envuelven al reproductor porque este también los lee
          (autoplay), y ambos van por encima de las rutas: así la música y las
          preferencias sobreviven a la navegación. */}
      <SettingsProvider>
        {/* El reproductor vive por encima de las rutas: así la música y su estado
            persisten al navegar. El overlay NowPlaying se monta una sola vez. */}
        <PlayerProvider>
          <Routes>
            <Route path="/"          element={<Login />} />
            <Route path="/callback"  element={<Callback />} />
            <Route path="/home"      element={<Home />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/search"    element={<Search />} />
            <Route path="/settings"  element={<Settings />} />
          </Routes>
          <NowPlaying />
        </PlayerProvider>
      </SettingsProvider>
    </BrowserRouter>
  )
}

export default App