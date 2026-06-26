import './App.css'
import {BrowserRouter} from 'react-router-dom'
import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import { useState } from 'react'


function App() {
  const [count, setCount] = useState(0)

  return (
    <BrowserRouter>
      <Routes>
      <Route path="/"          element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
