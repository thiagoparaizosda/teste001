import time

from freezegun import freeze_time
import jwt
import pytest
import responses
from app import create_app
from app.config import Config

@pytest.fixture
def app():
    app = create_app()

    app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "GATEWAY_URL": "http://localhost:8080/api/authenticate"
    })
    
    with app.app_context():
        yield app

    return app

@pytest.fixture
def client(app, monkeypatch):
    from app.middleware import auth_middleware

    monkeypatch.setattr(
        auth_middleware.auth_service,
        "validate_token",
        lambda token: (True, {"sub": "user123"})
    )

    client = app.test_client()

    with client.session_transaction() as sess:
        sess["token"] = "fake-test-token"
        sess["roles"] = ["USER", "ADMIN"]
        sess["token_exp"] = 9999999999
        sess["user_data"] = {
            "id": "user123",
            "email": "test@ppsa.com",
            "roles": ["VIEWER"]
        }

    return client

@pytest.fixture
@freeze_time("2026-04-13 12:50:00")
def mock_api_gateway(monkeypatch):
    """Fixture para interceptar chamadas ao Gateway JHipster."""

    payload = {
        "sub": "user123",
        "jti": "mock-jti-12345",
        "exp": int(time.time()) + 3600,
        "auth": "ROLE_VIEWER"
    }
    token = jwt.encode(payload, "test-secret", algorithm='HS256')
    
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.POST,
            "http://localhost:8080/api/authenticate",
            json={"id_token": token},
            status=200,
            content_type='application/json',
        )
        
        yield rsps