import { useEffect, useRef, useState } from 'react'

// Página de prueba MÍNIMA para comprobar que la reproducción con el
// Spotify Web Playback SDK funciona. No es la versión final del reproductor,
// solo sirve para validar la capacidad de reproducir audio dentro del navegador.

const GATEWAY = 'http://localhost:8000'
// Canción de prueba fija (Mr. Brightside - The Killers). Cambia el URI si quieres.
const TRACK_URI = 'spotify:track:3n3Ppam7vgaVa1iaRUc9Lp'

export default function Player() {
  const [status, setStatus] = useState('Inicializando...')
  const [deviceId, setDeviceId] = useState(null)
  const [trackName, setTrackName] = useState(null)

  const playerRef = useRef(null)
  const tokenRef = useRef(null)
  const initialized = useRef(false) // evita doble ejecución en StrictMode (dev)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    async function init() {
      // 1. Sacar el spotify_id del JWT que guardó el login en localStorage
      const jwt = localStorage.getItem('token')
      if (!jwt) {
        setStatus('No hay sesión. Inicia sesión primero en la app.')
        return
      }

      let spotifyId
      try {
        // El payload del JWT (parte central) lleva { sub: spotify_id, ... }
        spotifyId = JSON.parse(atob(jwt.split('.')[1])).sub
      } catch {
        setStatus('El JWT de localStorage no es válido.')
        return
      }

      // 2. Pedir al backend el token REAL de Spotify (el SDK necesita este,
      //    no el JWT de nuestra app)
      setStatus('Obteniendo token de Spotify...')
      try {
        const res = await fetch(`${GATEWAY}/auth/tokens/${spotifyId}`)
        const data = await res.json()
        if (!data.access_token) throw new Error('respuesta sin access_token')
        tokenRef.current = data.access_token
      } catch (e) {
        setStatus('No se pudo obtener el token de Spotify: ' + e.message)
        return
      }

      // 3. Preparar el callback que el SDK invoca cuando termina de cargar
      setStatus('Cargando Spotify Web Playback SDK...')
      window.onSpotifyWebPlaybackSDKReady = () => {
        const player = new window.Spotify.Player({
          name: 'Wavely Test Player',
          getOAuthToken: (cb) => cb(tokenRef.current),
          volume: 0.5,
        })
        playerRef.current = player

        player.addListener('ready', ({ device_id }) => {
          setDeviceId(device_id)
          setStatus('Listo. Dispositivo conectado. Pulsa "Reproducir".')
        })
        player.addListener('not_ready', () => setStatus('El dispositivo se desconectó.'))
        player.addListener('authentication_error', ({ message }) =>
          setStatus('Error de autenticación: ' + message))
        player.addListener('account_error', ({ message }) =>
          setStatus('Error de cuenta (¿la cuenta es Premium?): ' + message))
        player.addListener('initialization_error', ({ message }) =>
          setStatus('Error de inicialización: ' + message))
        player.addListener('playback_error', ({ message }) =>
          setStatus('Error de reproducción: ' + message))
        player.addListener('player_state_changed', (state) => {
          const track = state?.track_window?.current_track
          if (track) {
            setTrackName(`${track.name} — ${track.artists.map((a) => a.name).join(', ')}`)
          }
        })

        player.connect()
      }

      // 4. Inyectar el script del SDK (o reutilizarlo si ya está cargado)
      if (window.Spotify) {
        window.onSpotifyWebPlaybackSDKReady()
      } else if (!document.getElementById('spotify-sdk')) {
        const script = document.createElement('script')
        script.id = 'spotify-sdk'
        script.src = 'https://sdk.scdn.co/spotify-player.js'
        script.async = true
        document.body.appendChild(script)
      }
    }

    init()

    return () => {
      if (playerRef.current) playerRef.current.disconnect()
    }
  }, [])

  // Ordena a Spotify reproducir la canción de prueba en NUESTRO dispositivo
  async function handlePlay() {
    if (!deviceId) {
      setStatus('Aún no hay dispositivo listo.')
      return
    }
    setStatus('Enviando orden de reproducción...')
    const res = await fetch(
      `https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`,
      {
        method: 'PUT',
        headers: {
          Authorization: 'Bearer ' + tokenRef.current,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ uris: [TRACK_URI] }),
      }
    )
    if (res.status === 204) setStatus('▶ Reproduciendo (deberías oír el audio).')
    else setStatus(`Spotify respondió ${res.status} al intentar reproducir.`)
  }

  return (
    <div style={{ padding: 24, fontFamily: 'sans-serif', maxWidth: 640 }}>
      <h1>Prueba de reproducción</h1>
      <p><strong>Estado:</strong> {status}</p>
      <p><strong>Device ID:</strong> {deviceId || '—'}</p>
      <p><strong>Pista actual:</strong> {trackName || '—'}</p>

      <button
        onClick={handlePlay}
        disabled={!deviceId}
        style={{ padding: '10px 18px', fontSize: 16, cursor: deviceId ? 'pointer' : 'not-allowed' }}
      >
        ▶ Reproducir canción de prueba
      </button>

      {deviceId && (
        <div style={{ marginTop: 12 }}>
          <button onClick={() => playerRef.current?.togglePlay()}>Play / Pause</button>{' '}
          <button onClick={() => playerRef.current?.nextTrack()}>Siguiente</button>{' '}
          <button onClick={() => playerRef.current?.previousTrack()}>Anterior</button>
        </div>
      )}

      <p style={{ marginTop: 24, color: '#666', fontSize: 13 }}>
        Requisitos: cuenta Spotify <strong>Premium</strong>, haber iniciado sesión en la app,
        y permitir el audio en el navegador (por eso hay que pulsar el botón).
      </p>
    </div>
  )
}
