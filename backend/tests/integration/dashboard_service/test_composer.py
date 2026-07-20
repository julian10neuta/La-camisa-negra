# Tests de la composición del dashboard: dashboard_service/services/composer.py
# Patrón API Composition: junta las respuestas de music_service y
# recommendation_service. Se mockea la llamada interna (_get) para no tocar la
# red; lo que se prueba es la LÓGICA de composición y, sobre todo, la DEGRADACIÓN.
import pytest

from dashboard_service.services import composer

pytestmark = pytest.mark.integration


def _fake_get(mapping):
    """Devuelve un _get falso que responde según qué URL se llame."""
    async def _get(client, url, spotify_id, params):
        for fragment, value in mapping.items():
            if fragment in url:
                return value
        return None
    return _get


async def test_compose_merges_all_sections(monkeypatch):
    monkeypatch.setattr(composer, "_get", _fake_get({
        "/interactions/top": {"since": "2026-07-01", "songs": [1], "artists": [2], "albums": [3]},
        "/interactions/stats": {"plays": 5},
        "/recommendations/list": {"tracks": ["t"]},
    }))
    out = await composer.compose_dashboard("u1", days=7, top=5, period="weekly", limit=15)

    assert out["window"] == {"days": 7, "since": "2026-07-01"}
    assert out["top"] == {"songs": [1], "artists": [2], "albums": [3]}
    assert out["stats"] == {"plays": 5}
    assert out["recommendations"] == {"tracks": ["t"]}
    assert out["failed"] == []          # nada falló


async def test_compose_degrades_when_recommendation_down(monkeypatch):
    monkeypatch.setattr(composer, "_get", _fake_get({
        "/interactions/top": {"since": "x", "songs": [1], "artists": [], "albums": []},
        "/interactions/stats": {"plays": 5},
        # /recommendations/list NO está en el mapa → _get devuelve None (servicio caído)
    }))
    out = await composer.compose_dashboard("u1", days=1, top=5, period="weekly", limit=15)

    assert out["recommendations"] is None
    assert out["failed"] == ["recommendations"]
    # las otras secciones se sirven igual: una caída no tumba la pantalla.
    assert out["top"]["songs"] == [1]
    assert out["stats"] == {"plays": 5}


async def test_compose_reports_multiple_failures(monkeypatch):
    # music_service caído (top y stats) pero recommendation vivo.
    monkeypatch.setattr(composer, "_get", _fake_get({
        "/recommendations/list": {"tracks": []},
    }))
    out = await composer.compose_dashboard("u1", days=7, top=5, period="monthly", limit=10)

    assert out["stats"] is None
    assert out["top"] == {"songs": [], "artists": [], "albums": []}   # defaults seguros
    assert set(out["failed"]) == {"top", "stats"}
    assert out["recommendations"] == {"tracks": []}
