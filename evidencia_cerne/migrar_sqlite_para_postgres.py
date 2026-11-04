"""Migração única do SQLite do Windows para PostgreSQL do Render.

Uso: configure DATABASE_URL no ambiente, coloque a cópia de data/evidencias.db e
as pastas data/uploads e data/documents juntas e execute:
  python migrar_sqlite_para_postgres.py --data-dir ./data

NÃO executa automaticamente em produção; exige banco remoto vazio.
"""
import os
import sqlite3
import argparse
from pathlib import Path
from sqlalchemy import create_engine, select, func, DateTime, Boolean
from datetime import datetime
from app.database import Base
from app import models  # noqa: F401 - registra as tabelas

ORDER = ['users','projects','people','activities','photo_groups','photos',
         'knowledge_documents','knowledge_chunks','document_templates',
         'generated_documents','audit_logs']


def migrate(source: Path, target_url: str):
    if not source.is_file():
        raise SystemExit('Banco SQLite não encontrado em '+str(source))
    if not target_url.startswith(('postgres://','postgresql://','postgresql+psycopg://')):
        raise SystemExit('DATABASE_URL precisa apontar para PostgreSQL, nunca para SQLite.')
    url = target_url.replace('postgres://','postgresql+psycopg://',1).replace('postgresql://','postgresql+psycopg://',1)
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    root = source.parent
    with sqlite3.connect(source) as local:
        local.row_factory = sqlite3.Row
        existing = {r[0] for r in local.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with engine.begin() as dest:
            counts={name:dest.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar_one() for name in ORDER}
            if any(counts.values()):
                raise SystemExit('Migração cancelada: o PostgreSQL já tem registros. Faça backup e use um banco vazio.')
            total=0
            for name in ORDER:
                if name not in existing: continue
                table=Base.metadata.tables[name]
                rows=local.execute(f'SELECT * FROM "{name}"').fetchall()
                for row in rows:
                    record={k:row[k] for k in row.keys() if k in table.c and k not in ('blob',)}
                    for col_name, value in list(record.items()):
                        if value is None: continue
                        if isinstance(table.c[col_name].type, DateTime) and isinstance(value, str):
                            record[col_name] = datetime.fromisoformat(value)
                        elif isinstance(table.c[col_name].type, Boolean):
                            record[col_name] = bool(value)
                    if name in ('photos','generated_documents'):
                        sub='uploads' if name=='photos' else 'documents'
                        fp=root/sub/record['filename']
                        if not fp.is_file():
                            raise SystemExit(f'Migração interrompida: arquivo ausente: {fp}. Nenhuma linha migrada.')
                        record['blob']=fp.read_bytes()
                    dest.execute(table.insert().values(**record))
                total+=len(rows)
                print(f'{name}: {len(rows)} registro(s)')
    print(f'Migração concluída: {total} registros copiados. Verifique a aplicação antes de remover o SQLite.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args()
    target=os.getenv('DATABASE_URL','')
    if not target:
        raise SystemExit('Defina a variável DATABASE_URL da instância PostgreSQL.')
    migrate(args.data_dir/'evidencias.db',target)
