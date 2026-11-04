import io, re, unicodedata
from sqlalchemy.orm import Session
from sqlalchemy import text
from pypdf import PdfReader
from docx import Document
from .models import KnowledgeDocument, KnowledgeChunk


def extract_text(filename, raw):
    name = filename.lower()
    if name.endswith('.pdf'):
        r = PdfReader(io.BytesIO(raw))
        if len(r.pages) > 100: raise ValueError('O limite é de 100 páginas por documento.')
        txt = '\n'.join(page.extract_text() or '' for page in r.pages)
        if not txt.strip(): raise ValueError('PDF sem texto selecionável. Digitalizações precisam passar por OCR antes do envio.')
        return txt
    if name.endswith('.docx'):
        doc = Document(io.BytesIO(raw))
        chunks = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows: chunks.append(' | '.join(cell.text for cell in row.cells))
        return '\n'.join(chunks)
    if name.endswith(('.txt', '.md')):
        return raw.decode('utf-8-sig', errors='replace')
    raise ValueError('Formato não permitido. Use PDF, DOCX, TXT ou MD.')


def make_chunks(content, max_chars=1100, overlap=200):
    s = re.sub(r'\s+', ' ', content).strip()
    if not s: return []
    out, start = [], 0
    while start < len(s):
        end = min(start + max_chars, len(s))
        if end < len(s):
            cut = s.rfind(' ', start + max_chars//2, end)
            if cut > start: end = cut
        out.append(s[start:end])
        if end == len(s): break
        start = max(start + 1, end - overlap)
    return out


def init_fts(db):
    if db.bind.dialect.name == 'sqlite':
        db.execute(text('CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(chunk_id UNINDEXED, content, tokenize="unicode61 remove_diacritics 2")'))
        db.commit()
        # Heal full text index if upgrading or restoring a backup
        actual = {r[0] for r in db.execute(text('SELECT chunk_id FROM knowledge_fts')).all()}
        missing = db.query(KnowledgeChunk).filter(~KnowledgeChunk.id.in_(actual)).all() if actual else db.query(KnowledgeChunk).all()
        for chunk in missing: db.execute(text('INSERT INTO knowledge_fts(chunk_id,content) VALUES (:id,:content)'), {'id':chunk.id, 'content':chunk.content})
        db.commit()


def save_document(db: Session, doc: KnowledgeDocument):
    old = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    if db.bind.dialect.name == 'sqlite':
        for ch in old: db.execute(text('DELETE FROM knowledge_fts WHERE chunk_id=:id'), {'id':ch.id})
    for ch in old: db.delete(ch)
    db.flush()
    for i, content in enumerate(make_chunks(doc.content)):
        ch = KnowledgeChunk(document_id=doc.id, position=i, content=content)
        db.add(ch); db.flush()
        if db.bind.dialect.name == 'sqlite':
            db.execute(text('INSERT INTO knowledge_fts(chunk_id,content) VALUES (:id,:content)'), {'id':ch.id,'content':content})
    db.commit()


def remove_document(db: Session, doc):
    if db.bind.dialect.name == 'sqlite':
        for ch in doc.chunks: db.execute(text('DELETE FROM knowledge_fts WHERE chunk_id=:id'), {'id':ch.id})
    db.delete(doc); db.commit()


def retrieve(db: Session, question: str, limit=5):
    words = re.findall(r'[^\W_]{3,}', question.lower(), re.UNICODE)
    stop = {'para','como','com','uma','das','dos','que','por','estao','sobre','atividade','registro','documento','evidencia','resultados','objetivo','fotos','parte','foram','realizado','realizada','seus','suas','esta','este','essa','esse','pela','pelo','onde','quando','todas','todos','mais','menos','cada','terceiro','segundo','primeiro'}
    words = list(dict.fromkeys(w for w in words if w not in stop))[:18]
    if not words: words = ['cerne']
    if db.bind.dialect.name == 'sqlite':
        try:
            # Quoted tokens avoid FTS syntax injection; OR finds some related sources.
            match = ' OR '.join('"'+w.replace('"','')+'"' for w in words)
            rows = db.execute(text('SELECT chunk_id, bm25(knowledge_fts) AS rank FROM knowledge_fts WHERE knowledge_fts MATCH :q ORDER BY rank LIMIT :n'), {'q':match,'n':limit}).all()
            ids = [r[0] for r in rows]
            chunk_map = {c.id:c for c in db.query(KnowledgeChunk).filter(KnowledgeChunk.id.in_(ids)).all()}
            return [{'id':c.id,'document_id':c.document_id,'title':c.document.title,'text':c.content,'verified':c.document.verified} for i in ids if (c:=chunk_map.get(i))]
        except Exception: return []
    # Database independent fallback. PostgreSQL can upgrade to pgvector/tsvector.
    return [{'id':c.id,'document_id':c.document_id,'title':c.document.title,'text':c.content,'verified':c.document.verified} for c in db.query(KnowledgeChunk).limit(1500).all() if any(w in c.content.lower() for w in words)][:limit]
