import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Dashboard() {
  const [user, setUser] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = localStorage.getItem('user')
    
    if (!token) {
      navigate('/') // si no hay token, vuelve al login
      return
    }

    setUser(JSON.parse(userData))
  }, [navigate])

  return (
    <div>
      <h1>Dashboard</h1>
      {user ? (
        <p>Bienvenido, {user.name}</p>
      ) : (
        <p>Cargando...</p>
      )}
    </div>
  )
}

export default Dashboard