import { createPlaylist as createPlaylistRequest, 
  listPlaylists,
  getToken } from '../api';
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";

function PlaylistGallery() {
  const navigate = useNavigate();
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadPlaylists = async () => {
      if (!getToken()){
        navigate("/");
        return;
      }
      try {
        const data = await listPlaylists();
        setPlaylists(data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    loadPlaylists();
  }, []);

  const handleCreatePlaylist = async () => {
    try {
      const newPlaylist = await createPlaylistRequest(
        'Mi playlist desde La Camisa Negra',
        'Creada desde el frontend',
        false
      );
      setPlaylists((prev) => [newPlaylist, ...prev]);
      console.log('Playlist creada:', newPlaylist);
      alert(`Playlist creada: ${newPlaylist.name}`);
    } catch (error) {
      console.error(error);
      alert('No se pudo crear la playlist');
    }
  };

  const detailPlaylist = (playlist_id) => {
    
    navigate(`/playlists/${playlist_id}`);
    return;
  }

  const showPlaylists = () => {
    if (loading) {
      return <p>Cargando playlists...</p>;
    }

    return (
      <table className="playlist-table">
        <tbody>
          {playlists.map((playlist, index) => (
            <tr key={playlist.id} onClick={() => detailPlaylist(playlist.id)}>
              <td>
                <div className="album-cell">
                  <span className="playlist-cover" />
                  <span>{playlist.name}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <Layout>
      <div>
        <div className="dash-header">
          <div>
            <h1 className="page-title">Mis playlists</h1>
            <p className="playlist-counter">
              {playlists.length} playlist{playlists.length === 1 ? "" : "s"}
            </p>
          </div>
          <div>
            <button className="btn" onClick={handleCreatePlaylist}>
              Crear playlist
            </button>
          </div>
        </div>
      </div>

      {showPlaylists()}
    </Layout>
  );
}

export default PlaylistGallery;