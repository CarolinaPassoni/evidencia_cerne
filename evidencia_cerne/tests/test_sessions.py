from fastapi.testclient import TestClient
from test_end_to_end import app, SessionLocal
from app.models import User
from app.security import hash_password, _attempts


def login(client, email):
    response = client.post('/api/auth/login', json={'email': email, 'password': 'original-password-123'})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf']


def test_logout_and_password_revoke_copied_sessions():
    _attempts.clear()
    with TestClient(app) as first, TestClient(app) as second:
        with SessionLocal() as db:
            db.add(User(email='session-check@example.invalid', password_hash=hash_password('original-password-123')))
            db.commit()
        login(first, 'session-check@example.invalid')
        copied = first.cookies.get('session')
        assert first.post('/api/auth/logout').status_code == 200
        first.cookies.set('session', copied)
        assert first.get('/api/auth/me').status_code == 401
        first.cookies.clear()
        login(first, 'session-check@example.invalid')
        login(second, 'session-check@example.invalid')
        assert first.post('/api/auth/password', json={'old_password': 'original-password-123', 'new_password': 'replacement-password-123'}).status_code == 200
        assert second.get('/api/auth/me').status_code == 401
        assert first.get('/api/auth/me').status_code == 200
        assert first.post('/api/activities').status_code == 200


def test_login_rate_limit_and_origin():
    _attempts.clear()
    with TestClient(app) as client:
        assert client.post('/api/auth/login', headers={'Origin': 'https://foreign.invalid'}, json={'email': 'a', 'password': 'b'}).status_code == 403
        for _ in range(20):
            assert client.post('/api/auth/login', json={'email': 'missing@example.invalid', 'password': 'wrong'}).status_code == 401
        assert client.post('/api/auth/login', json={'email': 'missing@example.invalid', 'password': 'wrong'}).status_code == 429
    _attempts.clear()
