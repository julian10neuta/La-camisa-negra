import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Dashboard() {
  const [user, setUser] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = localStorage.getItem('user')
    
    if (!token) {
      navigate('/')
      return
    }

    setUser(JSON.parse(userData))
  }, [navigate])

  const handleLogout = async () => {
    await fetch("http://127.0.0.1:8000/auth/logout", { method: "POST" })
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    navigate('/')
  }

  return (
    <div>
      <h1>Dashboard</h1>
      {user ? (
        <>
          <p>Bienvenido, {user.name}</p>
          <button onClick={handleLogout}>Cerrar sesión</button>
        </>
      ) : (
        <p>Cargando...</p>
      )}
    </div>
  )
}

export default Dashboard