# Test de integración de UserRepository contra SQLite en memoria.
import pytest
from datetime import datetime

from shared.models import User
from authentication_service.repositories.user_repository import UserRepository

pytestmark = pytest.mark.integration


def _data(spotify_id="u1", token="tok1", premium=True, name="Julian"):
    return {
        "spotify_id": spotify_id, "name": name,
        "access_token": token, "refresh_token": "r1",
        "token_expiry": datetime(2030, 1, 1), "is_premium": premium,
    }


def test_create_then_get_by_spotify_id(db_session):
    UserRepository.create_or_update_user(db_session, _data())
    user = UserRepository.get_by_spotify_id(db_session, "u1")
    assert user is not None
    assert user.name == "Julian" and user.is_premium is True


def test_get_by_spotify_id_missing_is_none(db_session):
    assert UserRepository.get_by_spotify_id(db_session, "nope") is None


def test_create_or_update_updates_existing_without_duplicating(db_session):
    UserRepository.create_or_update_user(db_session, _data(token="old", premium=False, name="Viejo"))
    UserRepository.create_or_update_user(db_session, _data(token="new", premium=True, name="Nuevo"))

    assert db_session.query(User).filter_by(spotify_id="u1").count() == 1   # no duplicó
    user = UserRepository.get_by_spotify_id(db_session, "u1")
    assert user.access_token == "new"     # actualizó tokens
    assert user.is_premium is True
    assert user.name == "Nuevo"


def test_update_tokens(db_session):
    UserRepository.create_or_update_user(db_session, _data())
    user = UserRepository.get_by_spotify_id(db_session, "u1")
    UserRepository.update_tokens(db_session, user, "refreshed", datetime(2031, 1, 1))
    assert user.access_token == "refreshed"
    assert user.token_expiry == datetime(2031, 1, 1)
