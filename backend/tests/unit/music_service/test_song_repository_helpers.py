# Tests unitarios de los helpers PUROS de song_repository.py
# (_album_name, _cover_url, _normalize_genres). Sin BD.
from music_service.repositories.song_repository import (
    _album_name,
    _cover_url,
    _normalize_genres,
)


def test_album_name_reads_nested_album():
    assert _album_name({"album": {"name": "Mi Sangre"}}) == "Mi Sangre"
    assert _album_name({}) is None
    assert _album_name({"album": None}) is None


def test_cover_url_picks_first_image_or_none():
    data = {"album": {"images": [{"url": "big"}, {"url": "small"}]}}
    assert _cover_url(data) == "big"     # la primera = mayor resolución
    assert _cover_url({"album": {"images": []}}) is None
    assert _cover_url({}) is None


def test_normalize_genres_accepts_list_or_string():
    # El bug que evita: ",".join(sobre un string) explotaría el género carácter a
    # carácter. Por eso un string se devuelve tal cual.
    assert _normalize_genres(["latin", "pop"]) == "latin,pop"
    assert _normalize_genres("latin,pop") == "latin,pop"


def test_normalize_genres_empty_is_none():
    assert _normalize_genres([]) is None
    assert _normalize_genres("") is None
    assert _normalize_genres(None) is None
