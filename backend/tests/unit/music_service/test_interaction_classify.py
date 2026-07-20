# Test unitario de la clasificación de reproducción:
# music_service/services/interaction_service.InteractionService._classify_playback
#
# Es la regla que convierte "sonó N segundos, ¿llegó al final?, ¿la saltó?" en
# play / skip / (nada). Pura, sin self ni BD, así que se prueba directo.
from music_service.services.interaction_service import (
    InteractionService,
    MIN_PLAYBACK_SECONDS,
)

# _classify_playback no usa self; una instancia con dependencias nulas basta.
_svc = InteractionService(db=None, song_service=None, spotify_service=None)


def classify(seconds, reached_end, was_skipped):
    return _svc._classify_playback(seconds, reached_end, was_skipped)


def test_below_min_is_accidental_and_dropped():
    # Por debajo del piso (5s) es "abrir y cerrar": no cuenta, no se guarda.
    assert classify(MIN_PLAYBACK_SECONDS - 1, reached_end=False, was_skipped=True) is None
    assert classify(0, reached_end=True, was_skipped=False) is None


def test_reached_end_is_play_even_if_flagged_skipped():
    # Llegar al final manda sobre todo: es señal positiva fuerte.
    assert classify(200, reached_end=True, was_skipped=True) == "play"


def test_skipped_before_end_is_skip():
    assert classify(8, reached_end=False, was_skipped=True) == "skip"


def test_paused_or_closed_without_skip_is_play():
    # Escuchó un rato y pausó/cerró sin saltar: cuenta como play (escuchó algo).
    assert classify(45, reached_end=False, was_skipped=False) == "play"


def test_exact_min_boundary_counts():
    # Justo en el piso (5s) YA cuenta (la condición es estrictamente menor).
    assert classify(MIN_PLAYBACK_SECONDS, reached_end=False, was_skipped=True) == "skip"
