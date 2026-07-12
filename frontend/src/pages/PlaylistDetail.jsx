import { NavLink, useNavigate, useParams } from "react-router-dom" 
import Layout from "../components/Layout";
import { useEffect, useState} from "react";
import { getPlaylistTracksById,
    getToken
 } from "../api";
import { usePlayer } from "../player/PlayerContext";

function buildTrackList(rawTracks = []) {
    return rawTracks.map((track) => ({
        spotify_track_id: track.spotify_track_id || track.id || track.spotify_track_id,
        name: track.name || track.title || "Canción sin título",
        artist: track.artist || track.artists?.map((artist) => artist.name).join(", ") || "Artista desconocido",
        album: track.album || track.album_name || "Álbum desconocido",
        cover_url: track.cover_url || track.album?.images?.[0]?.url || null,
        duration_ms: track.duration_ms ?? null,
    }));
}

function PlaylistDetail(){
    const navigate = useNavigate();
    const { playlistId } = useParams();
    const [loading, setLoading] = useState(true);
    const [playlist, setPlaylist] = useState(null);
    const player = usePlayer();
    var { playlistName } = "Default name"

    useEffect(() => {
        if (!playlistId) {
            navigate("/playlists");
            return;
        }

        const loadPlaylist = async () => {
            if (!getToken()){
                navigate("/");
                return;
            }
            try {
                const data = await getPlaylistTracksById(playlistId);
                const normalizedTracks = buildTrackList(data);
                setPlaylist(/* normalizedTracks */data);
            } 
            catch (error) 
            {
                console.error(error);
            } 
            finally
            {
                setLoading(false);
            }
        }
        loadPlaylist();
    }, [navigate, playlistId]);

    const handleGoBack = () => {
        navigate(`/playlists`);
    }

    const displayTracks = () => {
    if (loading) {
        return <p>Cargando canciones...</p>;
    }

    if (!playlist || playlist.length === 0) {
        return <p>No hay canciones en esta playlist.</p>;
    }

    return (
    <table className="track-table">
        <thead>
            <tr>
                <th className="col-index">#</th>
                <th>Canción / Artista</th>
                <th>Álbum</th>
                <th>Duración</th>
                <th style={{ textAlign: "right" }}>Acciones</th>
            </tr>
        </thead>
        <tbody>
            {playlist.map((track, index) => (
                <tr key={track.spotify_track_id || index}>
                    <td className="col-index">{index + 1}</td>
                    <td>
                        <div className="track-cell">
                            {track.cover_url ? (
                                <img className="track-cover" src={track.cover_url} alt="" />
                            ) : (
                                <span className="track-cover" />
                            )}
                            <div>
                                <div className="track-name">{track.name}</div>
                                <div className="track-artist">{track.artist}</div>
                            </div>
                        </div>
                    </td>
                    <td className="col-album">{track.album || "—"}</td>
                    <td className="col-duration">{track.duration_ms ? `${Math.floor(track.duration_ms / 60000)}:${String(Math.floor((track.duration_ms % 60000) / 1000)).padStart(2, "0")}` : "—"}</td>
                    <td>
                        <div className="track-actions">
                            <button
                            className="icon-btn"
                            onClick={() => player.playTrack(track, { mode: "search" })}
                            title="Reproducir"
                            aria-label="Reproducir"
                            >
                            ▶
                            </button>
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
                <h1 className="page-title"> {playlistName} </h1>
                <NavLink to="/playlists" className="navlink">
                        <span> Volver a playlists</span>
                </NavLink>

                {displayTracks()}

            </div>
        </Layout>
    );

}

export default PlaylistDetail