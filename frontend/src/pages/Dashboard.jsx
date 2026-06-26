import { useEffect, useState } from 'react'

function Dashboard() {
  const [status, setStatus] = useState('Verificando cookies...')

  useEffect(() => {
    // Ahora llamamos a /api/test-cookies en lugar de la URL completa
    fetch('/api/test-cookies', {
        credentials: 'include' // Esto le dice al navegador que incluya las cookies locales
    })
        .then(r => r.json())
        .then(data => setStatus(JSON.stringify(data, null, 2)))
        .catch(err => setStatus('Error: ' + err.message))
    }, [])

  return (
    <div>
      <h1>Dashboard</h1>
      <pre>{status}</pre>
    </div>
  )
}

export default Dashboard