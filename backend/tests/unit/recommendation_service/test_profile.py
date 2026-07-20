# Tests unitarios del "cerebro" del recomendador: recommendation_service/services/profile.py
# Lógica pura (sin BD ni red): pesos por interacción, construcción del perfil y
# score de afinidad. Aquí es donde de verdad se decide qué se recomienda, así que
# es lo más valioso de blindar.
import math
from types import SimpleNamespace

from recommendation_service.services.profile import (
    interaction_weight,
    split_genres,
    build_profile,
    score_candidate,
    Profile,
    LIKE_WEIGHT,
    DISLIKE_WEIGHT,
    PLAY_WEIGHT,
    SKIP_EARLY_WEIGHT,
    SKIP_LATE_WEIGHT,
    ARTIST_BOOST,
)


def _row(type_, artist="A", genres="pop", track_id="t", secs=None):
    """Fabrica una fila (Interaction, Song) como la que build_profile espera,
    con objetos ligeros en vez de modelos de SQLAlchemy."""
    interaction = SimpleNamespace(type=type_, time_reproduced=secs)
    song = SimpleNamespace(artist=artist, genres=genres, spotify_track_id=track_id)
    return (interaction, song)


# ─── interaction_weight ───────────────────────────────────────────────────────

def test_weight_like_dislike_play():
    assert interaction_weight("like", None) == LIKE_WEIGHT
    assert interaction_weight("dislike", None) == DISLIKE_WEIGHT
    assert interaction_weight("play", None) == PLAY_WEIGHT


def test_weight_skip_depends_on_seconds():
    # < 10s = rechazo fuerte; >= 10s = desinterés leve. El límite (10) es "late".
    assert interaction_weight("skip", 3) == SKIP_EARLY_WEIGHT
    assert interaction_weight("skip", 9) == SKIP_EARLY_WEIGHT
    assert interaction_weight("skip", 10) == SKIP_LATE_WEIGHT
    assert interaction_weight("skip", 40) == SKIP_LATE_WEIGHT


def test_weight_skip_without_seconds_counts_as_early():
    # time_reproduced None → 0 segundos → skip temprano.
    assert interaction_weight("skip", None) == SKIP_EARLY_WEIGHT


def test_weight_unknown_type_is_zero():
    assert interaction_weight("query", None) == 0.0
    assert interaction_weight("", 5) == 0.0


# ─── split_genres ─────────────────────────────────────────────────────────────

def test_split_genres_normalizes_and_drops_empties():
    assert split_genres("Pop, Rock ,, latin ") == ["pop", "rock", "latin"]


def test_split_genres_handles_none_and_blank():
    assert split_genres(None) == []
    assert split_genres("") == []
    assert split_genres("   ") == []


# ─── build_profile ────────────────────────────────────────────────────────────

def test_build_profile_accumulates_scores_and_excludes():
    rows = [
        _row("like", artist="Juanes", genres="latin, pop", track_id="t1"),
        _row("play", artist="Juanes", genres="latin", track_id="t2"),
        _row("dislike", artist="Nickelback", genres="rock", track_id="t3"),
    ]
    p = build_profile(rows)

    # Todo lo tocado se excluye de futuras recomendaciones, sea del tipo que sea.
    assert p.excluded_ids == {"t1", "t2", "t3"}
    # Juanes suma like(+3) + play(+2) = 5; Nickelback dislike = -4.
    assert p.artist_scores["Juanes"] == LIKE_WEIGHT + PLAY_WEIGHT
    assert p.artist_scores["Nickelback"] == DISLIKE_WEIGHT
    # latin aparece en like(+3) y play(+2) = 5; pop solo en el like = 3; rock = -4.
    assert p.genre_scores["latin"] == LIKE_WEIGHT + PLAY_WEIGHT
    assert p.genre_scores["pop"] == LIKE_WEIGHT
    assert p.genre_scores["rock"] == DISLIKE_WEIGHT


def test_build_profile_norm_is_euclidean_of_genre_scores():
    rows = [_row("like", genres="a", track_id="t1"), _row("play", genres="b", track_id="t2")]
    p = build_profile(rows)
    expected = math.sqrt(LIKE_WEIGHT ** 2 + PLAY_WEIGHT ** 2)
    assert p.norm == expected


def test_build_profile_empty_has_no_signal_and_norm_one():
    p = build_profile([])
    assert p.norm == 1.0
    assert p.has_signal is False


def test_profile_top_lists_only_positive_scores_sorted():
    p = Profile(
        genre_scores={"pop": 5.0, "rock": -4.0, "latin": 2.0},
        artist_scores={"Juanes": 5.0, "Nickelback": -4.0},
    )
    assert p.top_genres == ["pop", "latin"]   # rock excluido (negativo), ordenado desc
    assert p.top_artists == ["Juanes"]        # Nickelback excluido
    assert p.has_signal is True


# ─── score_candidate ──────────────────────────────────────────────────────────

def test_score_zero_when_candidate_has_no_genres():
    p = build_profile([_row("like", genres="pop", track_id="t1")])
    assert score_candidate(p, [], "X") == 0.0


def test_score_zero_when_no_genre_overlap():
    p = build_profile([_row("like", genres="pop", track_id="t1")])
    assert score_candidate(p, ["jazz"], "X") == 0.0


def test_score_is_cosine_like_value():
    p = build_profile([_row("like", genres="pop", track_id="t1")])   # pop = 3, norm = 3
    # dot = 3 ; sqrt(len=1)=1 ; norm=3 → 3/(1*3) = 1.0
    assert score_candidate(p, ["pop"], "Otro") == 1.0


def test_score_disliked_genre_drags_negative():
    p = build_profile([_row("dislike", genres="reggaeton", track_id="t1")])
    assert score_candidate(p, ["reggaeton"], "X") < 0


def test_score_artist_boost_applies_for_favorite_artist():
    p = build_profile([_row("like", artist="Juanes", genres="pop", track_id="t1")])
    base = score_candidate(p, ["pop"], "Desconocido")
    boosted = score_candidate(p, ["pop"], "Juanes")
    assert boosted == base * ARTIST_BOOST
