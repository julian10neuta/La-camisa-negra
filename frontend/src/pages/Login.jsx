function Login() {
  const handleLogin = async () => {
    const res = await fetch("http://localhost:8000/auth/login-url");
    const data = await res.json();
    window.location.href = data.url;
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