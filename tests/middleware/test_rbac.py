from pathlib import Path
import sys

from flask import Blueprint, Flask, g, jsonify, session

# Allows running this test file directly with `python tests/.../test_require_permission.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.middleware.auth_middleware as auth_middleware
from app.config import Config
from app.middleware.auth_middleware import require_permission
from app.models.permission import Permission


class DummyUser:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    def has_permission(self, permission: Permission) -> bool:
        return self.allowed


def _set_valid_session(client, *, allowed: bool):
    with client.session_transaction() as sess:
        sess["token"] = "Bearer valid_token"
        sess["user_data"] = {"roles": ["ADMIN"]}
        sess["user_allowed"] = allowed


def _build_test_app(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["TESTING"] = True

    auth_bp = Blueprint("auth", __name__)
    portal_bp = Blueprint("portal_ui", __name__)

    @auth_bp.route("/login")
    def login():
        return "login", 200

    @portal_bp.route("/")
    def index():
        return "portal", 200

    @app.before_request
    def inject_current_user():
        allowed = session.get("user_allowed")
        g.current_user = DummyUser(allowed) if allowed is not None else None

    @app.route("/perm-json", methods=["POST"])
    @require_permission(Permission.CCO_EDIT)
    def perm_json():
        return jsonify({"ok": True}), 200

    @app.route("/perm-html", methods=["GET"])
    @require_permission(Permission.CCO_EDIT)
    def perm_html():
        return "ok", 200

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(portal_bp)

    monkeypatch.setattr(Config, "DISABLE_AUTH", "False")
    return app


def test_require_permission_bypasses_all_checks_when_auth_is_disabled(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()

    monkeypatch.setattr(Config, "DISABLE_AUTH", "True")

    response = client.get("/perm-html")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"


def test_require_permission_returns_json_403_when_user_lacks_permission(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()

    monkeypatch.setattr(auth_middleware.auth_service, "validate_token", lambda token: (True, {}))
    _set_valid_session(client, allowed=False)

    response = client.post("/perm-json", json={})

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["success"] is False
    assert Permission.CCO_EDIT.value in payload["error"]


def test_require_permission_redirects_and_flashes_when_not_json(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()

    monkeypatch.setattr(auth_middleware.auth_service, "validate_token", lambda token: (True, {}))
    _set_valid_session(client, allowed=False)

    response = client.get("/perm-html")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any(
        category == "danger" and Permission.CCO_EDIT.value in message
        for category, message in flashes
    )


def test_require_permission_allows_access_when_user_has_permission(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()

    monkeypatch.setattr(auth_middleware.auth_service, "validate_token", lambda token: (True, {}))
    _set_valid_session(client, allowed=True)

    response = client.get("/perm-html")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))