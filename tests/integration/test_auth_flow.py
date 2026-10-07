from freezegun import freeze_time
from tests.conftest import mock_api_gateway
from app.services.auth_service import AuthService

auth_service = AuthService()

def test_login_redirect(client, mock_api_gateway):
    response = client.post('/login', json={
        'email': 'test@ppsa.com',
        'password': 'password123'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/' in response.headers['Location']

def test_full_auth_flow(client, mock_api_gateway):
    # 1. Login
    response = client.post('/login', json={
        'email': 'test@ppsa.com',
        'password': 'password123'
    }, follow_redirects=True)

    assert response.status_code == 200

    auth_result, error = auth_service.authenticate('test@ppsa.com', 'password123')
    token = auth_result.get('id_token')
     
    # 2. Request protegido
    response = client.get('/', 
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    
    # 3. Logout
    response = client.get('/logout',
        headers={'Authorization': f'Bearer {token}'}, follow_redirects=True)
    assert response.status_code == 200
    
    # # 4. Tentar acessar após logout
    response = client.get('/',
        headers={'Authorization': f'Bearer {token}'}, follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_invalid_token(client):
    with client.session_transaction() as sess:
        sess.clear()

    response = client.get('/',
        headers={'Authorization': 'Bearer token_invalido'}, follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_session_timeout(client, mock_api_gateway):
    from app.middleware import auth_middleware

    def validate_token_by_exp(token):
        import jwt
        from datetime import datetime, timezone

        payload = jwt.decode(token, options={"verify_signature": False})
        if payload.get('exp', 0) <= int(datetime.now(timezone.utc).timestamp()):
            return False, 'Token expirado'
        return True, payload

    auth_middleware.auth_service.validate_token = validate_token_by_exp

    # 1. Faz o login no tempo atual (Token válido)
    with freeze_time("2026-04-13 12:50:00"):
        client.post('/login', json={
        'email': 'test@ppsa.com',
        'password': 'password123'
    }, follow_redirects=False)
    
    # 2. Tenta acessar uma rota protegida 2 horas depois
    with freeze_time("2026-04-13 14:50:00"):
        response = client.get('/', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']