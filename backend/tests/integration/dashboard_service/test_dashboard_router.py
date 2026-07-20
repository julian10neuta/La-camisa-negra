# Test de integración del router del dashboard vía TestClient de FastAPI.
# Comprueba la VALIDACIÓN de la petición (los 422 que FastAPI genera de las
# restricciones de los Query/Header) y que una petición válida devuelve la
# composición. compose_dashboard se mockea: aquí probamos el router, no la red.
import pytest
from fastapi.testclient import TestClient

from dashboard_service.main import app
from dashboard_service.routers import dashboard_router

pytestmark = pytest.mark.integration

client = TestClient(app)
HEADERS = {"X-Spotify-ID": "u1"}


@pytest.fixture()
def stub_compose(monkeypatch):
    """Sustituye compose_dashboard por uno que devuelve algo fijo, sin red."""
    async def _fake(spotify_id, days, top, period, limit):
        return {"ok": True, "spotify_id": spotify_id, "days": days,
                "top": top, "period": period, "limit": limit}
    monkeypatch.setattr(dashboard_router, "compose_dashboard", _fake)


def test_valid_request_returns_composition(stub_compose):
    r = client.get("/dashboard", params={"days": 7, "period": "monthly"}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["spotify_id"] == "u1"
    assert body["days"] == 7
    assert body["period"] == "monthly"


def test_defaults_apply_when_params_omitted(stub_compose):
    r = client.get("/dashboard", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7 and body["top"] == 5 and body["period"] == "weekly" and body["limit"] == 15


def test_missing_spotify_id_header_is_422(stub_compose):
    assert client.get("/dashboard").status_code == 422


@pytest.mark.parametrize("params", [
    {"days": 0},          # < 1
    {"days": 400},        # > 365
    {"top": 0},           # < 1
    {"top": 50},          # > 20
    {"period": "yearly"}, # fuera del Literal weekly/monthly
    {"limit": 0},         # < 1
    {"limit": 99},        # > 50
])
def test_out_of_range_params_are_422(stub_compose, params):
    assert client.get("/dashboard", params=params, headers=HEADERS).status_code == 422
