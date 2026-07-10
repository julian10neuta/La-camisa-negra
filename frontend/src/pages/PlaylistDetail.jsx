import { NavLink, useNavigate, useParams } from "react-router-dom" 
import Layout from "../components/Layout";
import { useEffect, useState} from "react";
import { getPlaylistTracksById,
    getToken
 } from "../api";

function PlaylistDetail(){
    const navigate = useNavigate();
    const { playlistId } = useParams();
    const [loading, setLoading] = useState(true);
    const [playlist, setPlaylist] = useState(null);
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
                setPlaylist(data);
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
    <ul>
      {playlist.map((track, index) => (
        <li key={index}>{track.spotify_track_id}</li>
      ))}
    </ul>
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