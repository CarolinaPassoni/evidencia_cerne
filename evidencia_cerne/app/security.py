import os, secrets, hashlib, hmac
from pathlib import Path
from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session
from .database import DATA_DIR, db_session
from .models import User, AppSession
from datetime import datetime, timezone, timedelta
from threading import Lock
from time import monotonic

_attempts = {}
_attempt_lock = Lock()

def check_login_rate(request):
    # Single-process deployment; cap failures per peer over a five-minute window.
    peer = request.client.host if request.client else "unknown"
    now = monotonic()
    with _attempt_lock:
        for key in list(_attempts):
            if now - _attempts[key][0] > 300:
                del _attempts[key]
        start, count = _attempts.get(peer, (now, 0))
        if count >= 20:
            raise HTTPException(429, "Muitas tentativas. Aguarde cinco minutos.", headers={"Retry-After": "300"})
        _attempts[peer] = (start, count + 1)

def start_session(request, db, user):
    old = request.session.get("sid")
    if old:
        db.query(AppSession).filter_by(id=old).delete()
    now = datetime.now(timezone.utc)
    db.query(AppSession).filter(AppSession.expires_at <= now).delete()
    sid = secrets.token_urlsafe(32)
    db.add(AppSession(id=sid, user_id=user.id, expires_at=now + timedelta(hours=12)))
    db.commit()
    request.session.clear()
    request.session.update({"user_id": user.id, "sid": sid, "csrf": secrets.token_urlsafe(32)})


KEYFILE = DATA_DIR / '.session_key'

def secret_key():
    if os.getenv('SESSION_SECRET'): return os.environ['SESSION_SECRET']
    if not KEYFILE.exists():
        KEYFILE.write_text(secrets.token_urlsafe(64), encoding='utf-8')
        try: KEYFILE.chmod(0o600)
        except OSError: pass
    return KEYFILE.read_text(encoding='utf-8').strip()

def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
    return f'pbkdf2_sha256$310000${salt.hex()}${dk.hex()}'

def verify_password(password, digest):
    try:
        _, n, salt, expected = digest.split('$')
        calc = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(n))
        return hmac.compare_digest(calc, bytes.fromhex(expected))
    except Exception: return False

def user_or_401(request: Request, db: Session = Depends(db_session)):
    uid = request.session.get('user_id')
    user = db.get(User, uid) if uid else None
    record = db.get(AppSession, request.session.get('sid', ''))
    now = datetime.now(timezone.utc)
    expiry = record.expires_at if record else None
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if not user or not record or record.user_id != uid or expiry <= now:
        request.session.clear()
        raise HTTPException(401, 'Faça login para continuar.')
    if request.method not in ['GET', 'HEAD', 'OPTIONS']:
        token = request.headers.get('X-CSRF-Token', '')
        if not token or not hmac.compare_digest(token, request.session.get('csrf', '')):
            raise HTTPException(403, 'Sessão inválida. Atualize a página e tente novamente.')
    return user

def admin_or_403(user: User = Depends(user_or_401)):
    if user.role != 'admin': raise HTTPException(403, 'Acesso exclusivo do administrador.')
    return user
