import os
from pathlib import Path
from sqlalchemy import create_engine, event
from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
# Le o .env da raiz sem sobrescrever variaveis definidas no sistema/Docker.
load_dotenv(BASE_DIR / '.env', override=False)
DATA_DIR = Path(os.environ.get('EVIDENCIA_DATA_DIR', BASE_DIR / 'data')).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATa := DATA_DIR / 'uploads').mkdir(exist_ok=True)
(DATA_DIR / 'documents').mkdir(exist_ok=True)
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + str(DATA_DIR / 'evidencias.db'))
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgres://'):]
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgresql://'):]
connect_args = {'check_same_thread': False, 'timeout': 30} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute('PRAGMA foreign_keys=ON')
        cur.execute('PRAGMA journal_mode=WAL')
        cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
