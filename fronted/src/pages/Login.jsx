function Login() {
  const handleLogin = () => {
    window.location.href = 'http://localhost:8000/login'
  }

  return (
    <div>
      <h1>La Camisa Negra</h1>
      <button onClick={handleLogin}>
        Iniciar sesión con Spotify
      </button>
    </div>
  )
}

export default Login