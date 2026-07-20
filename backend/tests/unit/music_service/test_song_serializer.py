# Test unitario del serializador de búsqueda:
# music_service/serializers/song_serializer._serialize_track
# Aplana el track crudo de Spotify a lo que la pantalla Search necesita.
from music_service.serializers.song_serializer import _serialize_track


def test_serialize_full_track():
    raw = {
        "id": "abc",
        "name": "La Camisa Negra",
        "artists": [{"name": "Juanes"}, {"name": "Feat"}],
        "album": {"name": "Mi Sangre", "images": [{"url": "big"}, {"url": "small"}]},
        "duration_ms": 213000,
    }
    assert _serialize_track(raw) == {
        "spotify_track_id": "abc",
        "name": "La Camisa Negra",
        "artist": "Juanes",       # primer artista
        "album": "Mi Sangre",
        "cover_url": "big",        # primera imagen = mayor resolución
        "duration_ms": 213000,
    }


def test_serialize_missing_optionals_degrade():
    out = _serialize_track({"id": "x"})
    assert out["spotify_track_id"] == "x"
    assert out["name"] == "Unknown"
    assert out["artist"] == "Unknown"
    assert out["album"] is None
    assert out["cover_url"] is None
    assert out["duration_ms"] is None


def test_serialize_empty_artists_and_images_lists():
    raw = {"id": "y", "name": "N", "artists": [], "album": {"name": "A", "images": []}}
    out = _serialize_track(raw)
    assert out["artist"] == "Unknown"
    assert out["album"] == "A"
    assert out["cover_url"] is None
