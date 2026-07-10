import './App.css'
import { BrowserRouter } from 'react-router-dom'
import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Callback from './pages/Callback'  // <-- agrega este
import PlaylistGallery from './pages/PlaylistGallery'
import PlaylistDetail from './pages/PlaylistDetail'
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
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/search"    element={<Search />} />
          <Route path="/playlists" element={<PlaylistGallery />} />
          <Route path="/playlists/:playlistId" element={<PlaylistDetail />} />
        </Routes>
        <NowPlaying />
      </PlayerProvider>
    </BrowserRouter>
  )
}

export default App