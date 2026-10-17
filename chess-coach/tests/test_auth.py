from backend import auth
from test_coach import client

read_env = auth.read_env


def enable(monkeypatch, tmp_path, password='segreta'):
    # Point the module at a temporary .env so the real project credentials are never read.
    env = tmp_path / '.env'
    env.write_text(f'GITHUB_TOKEN=\nSPARRINGMATE_USER=dante\nSPARRINGMATE_PASSWORD="{password}"\n', encoding='utf-8')
    monkeypatch.delenv('CHESS_COACH_DISABLE_AUTH')
    monkeypatch.delenv('SPARRINGMATE_USER', raising=False)
    monkeypatch.delenv('SPARRINGMATE_PASSWORD', raising=False)
    monkeypatch.setattr(auth, 'read_env', lambda path: read_env(env))
    return env



def test_login_protects_the_api_until_valid_credentials(client, monkeypatch, tmp_path):
    assert client.get('/api/auth/session').json() == {'required': False, 'authenticated': True, 'user': None}
    env = enable(monkeypatch, tmp_path)
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/games').status_code == 401
    assert client.get('/api/auth/session').json() == {'required': True, 'authenticated': False, 'user': None}
    assert client.post('/api/auth/login', json={'username': 'dante', 'password': 'sbagliata'}).status_code == 401
    response = client.post('/api/auth/login', json={'username': 'dante', 'password': 'segreta'})
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    assert client.get('/api/games').status_code == 200
    assert client.get('/api/auth/session').json() == {'required': True, 'authenticated': True, 'user': 'dante'}
    # A tampered cookie or a new password ends the session.
    good = client.cookies.get(auth.COOKIE)
    client.cookies.clear()
    assert client.get('/api/games', cookies={auth.COOKIE: good[:-1] + ('0' if good[-1] != '0' else '1')}).status_code == 401
    client.cookies.set(auth.COOKIE, good)
    assert client.get('/api/games').status_code == 200
    env.write_text('SPARRINGMATE_USER=dante\nSPARRINGMATE_PASSWORD=nuova\n', encoding='utf-8')
    assert client.get('/api/games').status_code == 401
    assert client.post('/api/auth/login', json={'username': 'dante', 'password': 'nuova'}).status_code == 200
    client.post('/api/auth/logout')
    assert client.get('/api/games').status_code == 401


def test_repeated_failures_are_throttled(client, monkeypatch, tmp_path):
    enable(monkeypatch, tmp_path)
    for _ in range(auth.MAX_FAILURES):
        assert client.post('/api/auth/login', json={'username': 'dante', 'password': 'x'}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'dante', 'password': 'segreta'}).status_code == 429
