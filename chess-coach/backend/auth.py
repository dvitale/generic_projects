"""Single-user login: credentials come from the project .env, sessions are HMAC-signed cookies."""
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

COOKIE = 'sparringmate_session'
SESSION_SECONDS = 30 * 24 * 3600
# Paths reachable without a session: the login API itself and the health probe used by scripts/service.py.
OPEN_PATHS = {'/api/health', '/api/auth/session', '/api/auth/login', '/api/auth/logout'}
MAX_FAILURES, FAILURE_WINDOW = 5, 300


def read_env(path):
    values = {}
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Login(BaseModel):
    username: str = Field(max_length=120)
    password: str = Field(max_length=200)


def install(app, env_path, data_dir):
    """Protect every /api route except OPEN_PATHS when SPARRINGMATE_USER and SPARRINGMATE_PASSWORD are set."""
    failures = {}

    def credentials():
        # Tests and explicitly unprotected installs run without a login.
        if os.environ.get('CHESS_COACH_DISABLE_AUTH') == '1':
            return None
        saved = read_env(env_path)
        user = os.environ.get('SPARRINGMATE_USER', saved.get('SPARRINGMATE_USER', ''))
        password = os.environ.get('SPARRINGMATE_PASSWORD', saved.get('SPARRINGMATE_PASSWORD', ''))
        return (user, password) if user and password else None

    def secret():
        # Kept beside the database so sessions survive restarts; deleting it logs everyone out.
        path = Path(data_dir()) / 'session.key'
        try:
            return path.read_bytes()
        except FileNotFoundError:
            path.parent.mkdir(parents=True, exist_ok=True)
            key = secrets.token_bytes(32)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(key)
            return key

    def signature(user, password, expires):
        # The password is part of the key: changing it in .env invalidates existing sessions.
        key = hmac.new(secret(), password.encode(), hashlib.sha256).digest()
        return hmac.new(key, f'{user}|{expires}'.encode(), hashlib.sha256).hexdigest()

    def session_user(request):
        creds = credentials()
        if creds is None:
            return None
        try:
            expires, mac = request.cookies.get(COOKIE, '').split('.', 1)
            if int(expires) < time.time():
                return None
        except ValueError:
            return None
        return creds[0] if hmac.compare_digest(mac, signature(*creds, expires)) else None

    @app.middleware('http')
    async def require_login(request, call_next):
        path = request.url.path
        if path.startswith('/api/') and path not in OPEN_PATHS and credentials() is not None and session_user(request) is None:
            return JSONResponse({'detail': 'Accesso richiesto'}, status_code=401)
        return await call_next(request)

    @app.get('/api/auth/session')
    def session(request: Request):
        creds = credentials()
        user = session_user(request)
        return {'required': creds is not None, 'authenticated': creds is None or user is not None, 'user': user}

    @app.post('/api/auth/login')
    def login(body: Login, request: Request, response: Response):
        creds = credentials()
        if creds is None:
            return {'required': False, 'authenticated': True, 'user': None}
        client = request.client.host if request.client else ''
        now = time.time()
        recent = [t for t in failures.get(client, []) if now - t < FAILURE_WINDOW]
        if len(recent) >= MAX_FAILURES:
            raise HTTPException(429, 'Troppi tentativi: riprova tra qualche minuto.')
        valid = hmac.compare_digest(body.username.encode(), creds[0].encode()) & hmac.compare_digest(body.password.encode(), creds[1].encode())
        if not valid:
            failures[client] = recent + [now]
            raise HTTPException(401, 'Nome utente o password non corretti.')
        failures.pop(client, None)
        expires = str(int(now) + SESSION_SECONDS)
        response.set_cookie(COOKIE, f'{expires}.{signature(*creds, expires)}', max_age=SESSION_SECONDS, httponly=True,
                            samesite='strict', secure=request.url.scheme == 'https', path='/')
        return {'required': True, 'authenticated': True, 'user': creds[0]}

    @app.post('/api/auth/logout')
    def logout(response: Response):
        response.delete_cookie(COOKIE, path='/')
        return {'authenticated': False}
