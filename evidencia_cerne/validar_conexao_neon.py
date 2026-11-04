"""Valida conexão PostgreSQL Neon somente com SELECT; não revela credenciais."""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

raw = os.getenv('DATABASE_URL', '').strip()
if not raw:
    sys.exit('DATABASE_URL não definida. Configure-a como variável de ambiente privada.')
url = raw.replace('postgres://', 'postgresql+psycopg://', 1).replace('postgresql://', 'postgresql+psycopg://', 1)
try:
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql':
        sys.exit('DATABASE_URL não é uma URL PostgreSQL.')
    print('Host:', parsed.host or '(indisponível)')
    print('Banco:', parsed.database or '(indisponível)')
    print('SSL:', parsed.query.get('sslmode', '(não declarado)'))
    if parsed.query.get('sslmode') not in ('require','verify-ca','verify-full'):
        sys.exit('Conexão SSL não está obrigatória. Use sslmode=require ou mais restritivo.')
    eng = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 10})
    with eng.connect() as con:
        info = con.execute(text('SELECT current_database() as db, current_user as role')).mappings().one()
        print('Conexão PostgreSQL confirmada. Banco:', info['db'], '| usuário:', info['role'])
    eng.dispose()
except Exception as exc:
    # Não exibir texto cru de exceções de banco, pois pode incluir detalhes de URL.
    print('Falha ao conectar. Verifique usuário, senha, host, banco, SSL e acesso de rede.')
    print('Tipo do erro:', type(exc).__name__)
    sys.exit(1)
