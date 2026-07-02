import './App.css'
import { BrowserRouter } from 'react-router-dom'
import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Callback from './pages/Callback'
import Search from './pages/Search'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"          element={<Login />} />
        <Route path="/callback"  element={<Callback />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/search"    element={<Search />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App