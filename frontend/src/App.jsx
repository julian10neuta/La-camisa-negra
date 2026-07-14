import './App.css'
import { BrowserRouter } from 'react-router-dom'
import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Callback from './pages/Callback'
import Search from './pages/Search'
import { PlayerProvider } from './player/PlayerContext'
import NowPlaying from './components/NowPlaying'

function App() {
  return (
    <BrowserRouter>
      {/* El reproductor vive por encima de las rutas: así la música y su estado
          persisten al navegar. El overlay NowPlaying se monta una sola vez. */}
      <PlayerProvider>
        <Routes>
          <Route path="/"          element={<Login />} />
          <Route path="/callback"  element={<Callback />} />
          <Route path="/home"      element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/search"    element={<Search />} />
        </Routes>
        <NowPlaying />
      </PlayerProvider>
    </BrowserRouter>
  )
}

export default App