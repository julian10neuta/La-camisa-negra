function PlaylistGallery() {
  const createPlaylist = () => {

  }

  const showPlaylists = () => {
    var playlists = []

    for(var i = 0; i < 3; i++) {
      playlists.push(
        <button key={i} onClick={() => {}}>
          Playlist {i + 1}
        </button>)
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'flex-start' }}>
        {playlists}
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div>
            <h1>Mis playlists</h1>
          </div>
          <div>
            <button onClick={createPlaylist}>
            Crear playlist
          </button>
          </div>
      </div>
        {showPlaylists()}
    </div>
  )
}

export default PlaylistGallery