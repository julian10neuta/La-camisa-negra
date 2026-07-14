import { createPlaylist as createPlaylistRequest, 
  listPlaylists,
  getToken } from '../api';
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";

function PlaylistNameModal({ isOpen, onClose, onSubmit }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit(name.trim(), description.trim());
    setName('');
    setDescription('');
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div>
          <h1 className='page-title'> Crea una nueva playlist!</h1>
        </div>
        <form onSubmit={handleSubmit}>
          <div>
            <input
              className='input'
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="¿Cómo se llamará?"
              autoFocus
            />
          </div>
          <input
            className='input'
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describela un poco"
            autoFocus
          />
          <div className="modal-actions">
            <button className="btn-ghost btn" type="button" onClick={onClose}>Cancel</button>
            <button className="btn" type="submit">Create</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PlaylistGallery() {
  const navigate = useNavigate();
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

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

  const handleCreatePlaylist = async (name, description) => {
    try {
      const newPlaylist = await createPlaylistRequest(
        name,
        description,
        false
      );
      setPlaylists((prev) => [newPlaylist, ...prev]);
      console.log('Playlist creada:', newPlaylist);
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
            <button className="btn" onClick={() => setShowModal(true)}>Crear playlist</button>
            <PlaylistNameModal
              isOpen={showModal}
              onClose={() => setShowModal(false)}
              onSubmit={handleCreatePlaylist}
            />
          </div>
        </div>
      </div>

      {showPlaylists()}
    </Layout>
  );
}

export default PlaylistGallery;