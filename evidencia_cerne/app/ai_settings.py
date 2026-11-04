"""Admin-controlled AI settings, encrypted at rest and never returned to the browser.

Local installs keep encrypted configuration in data/ and a separate machine key in
that same directory. Protect this directory and back it up securely when migrating.
Environment variables remain a compatible fallback until dashboard settings are saved.
"""
import json
import os
import re
import secrets
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from .database import DATA_DIR, SessionLocal, engine
from .models import AppSetting

_CONFIG = DATA_DIR / '.ai_credentials.enc'
_KEY = DATA_DIR / '.ai_credentials.key'
_MODELS = {'gemini': 'gemini-2.5-flash', 'openai': 'gpt-4o-mini'}


def _machine_key(create=False):
    if engine.dialect.name == 'postgresql':
        key = os.getenv('AI_ENCRYPTION_KEY', '').strip().encode()
        if not key:
            raise ValueError('AI_ENCRYPTION_KEY é obrigatória no servidor online.')
        try: Fernet(key)
        except ValueError as exc: raise ValueError('AI_ENCRYPTION_KEY inválida.') from exc
        return key
    if not _KEY.exists():
        if not create:
            raise ValueError('A chave local de proteção da IA não foi encontrada. Restaure-a junto com as configurações ou refaça o cadastro.')
        fd = os.open(str(_KEY), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(Fernet.generate_key())
    return _KEY.read_bytes().strip()


def _saved():
    if engine.dialect.name == 'postgresql':
        with SessionLocal() as db:
            setting = db.get(AppSetting, 'ai_credentials')
            if setting is None: return None
            try:
                return json.loads(Fernet(_machine_key()).decrypt(setting.value.encode()).decode('utf-8'))
            except (InvalidToken, ValueError, KeyError, json.JSONDecodeError) as exc:
                raise ValueError('Chave de IA inválida no banco. Configure novamente com a mesma AI_ENCRYPTION_KEY.') from exc
    if not _CONFIG.exists():
        return None
    try:
        return json.loads(Fernet(_machine_key()).decrypt(_CONFIG.read_bytes()).decode('utf-8'))
    except (InvalidToken, ValueError, KeyError, json.JSONDecodeError):
        raise ValueError('Configuração de IA ilegível. Restaure os dois arquivos .ai_credentials da pasta data ou recadastre a chave.')


def current_settings():
    saved = _saved()
    if saved is not None:
        return {**saved, 'source': 'painel'}
    selection = os.getenv('AI_PROVIDER', '').strip().lower()
    if selection in ('none', 'off', 'basic'):
        return {'provider': 'none', 'api_key': '', 'model': '', 'source': 'ambiente'}
    if selection not in _MODELS:
        selection = 'gemini' if os.getenv('GEMINI_API_KEY') else ('openai' if os.getenv('OPENAI_API_KEY') else 'none')
    if selection == 'none':
        return {'provider': 'none', 'api_key': '', 'model': '', 'source': 'ambiente'}
    prefix = selection.upper()
    key = os.getenv(prefix + '_API_KEY', '')
    return {'provider': selection if key else 'none', 'api_key': key,
            'model': os.getenv(prefix + '_MODEL') or _MODELS[selection], 'source': 'ambiente'}


def public_settings():
    settings = current_settings()
    key = settings.get('api_key') or ''
    return {'provider': settings.get('provider') or 'none', 'model': settings.get('model') or '',
            'configured': bool(key) and settings.get('provider') in _MODELS,
            'key_hint': ('••••' + key[-4:]) if key else '',
            'source': settings['source']}


def save_settings(provider, api_key='', model=''):
    provider = str(provider or '').strip().lower()
    if provider not in ('none', *tuple(_MODELS)):
        raise ValueError('Escolha Gemini, OpenAI ou Desativada.')
    current = current_settings()
    key = str(api_key or '').strip()
    if provider == 'none':
        key = ''
        model = ''
    else:
        if not key and current['provider'] == provider:
            key = current.get('api_key') or ''
        if not key:
            raise ValueError('Informe uma chave de API para o serviço escolhido.')
        if len(key) < 8 or len(key) > 1024 or any(c.isspace() for c in key):
            raise ValueError('A chave deve ter de 8 a 1024 caracteres, sem espaços.')
        model = str(model or '').strip() or _MODELS[provider]
        if len(model) > 120 or not re.fullmatch(r'[a-zA-Z0-9._/-]+', model):
            raise ValueError('Nome de modelo inválido.')
    payload = json.dumps({'provider': provider, 'api_key': key, 'model': model}).encode('utf-8')
    token = Fernet(_machine_key(create=True)).encrypt(payload)
    if engine.dialect.name == 'postgresql':
        with SessionLocal() as db:
            row = db.get(AppSetting, 'ai_credentials')
            if row is None: db.add(AppSetting(key='ai_credentials', value=token.decode('ascii')))
            else: row.value = token.decode('ascii')
            db.commit()
        return public_settings()
    temporary = DATA_DIR / ('.ai_credentials.' + secrets.token_hex(7) + '.tmp')
    try:
        with temporary.open('wb') as f:
            f.write(token)
        temporary.chmod(0o600)
        temporary.replace(_CONFIG)
    finally:
        temporary.unlink(missing_ok=True)
    return public_settings()
