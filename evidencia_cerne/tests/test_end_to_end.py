"""Execute com: python -m pytest -q tests/"""
import os
import tempfile
from pathlib import Path

# Isolated test database: no test data is written to the real project directory.
_TEMP = tempfile.TemporaryDirectory(prefix='evidencia_tests_')
os.environ['EVIDENCIA_DATA_DIR'] = _TEMP.name
from fastapi.testclient import TestClient
from PIL import Image
from io import BytesIO
from zipfile import ZipFile
from app.documents import REFERENCE_DOCX
from docx import Document
from pypdf import PdfReader
from app.main import app
from app.database import DATA_DIR
from app.knowledge import retrieve
from app.database import SessionLocal


_FIRST_CREDENTIALS = None

def client_auth():
    global _FIRST_CREDENTIALS
    client=TestClient(app)
    client.__enter__()
    if _FIRST_CREDENTIALS is None:
        lines=(DATA_DIR/'ACESSO_INICIAL.txt').read_text().splitlines()
        username=next(x.split(': ',1)[1] for x in lines if x.startswith('Login:'))
        pw=next(x.split(': ',1)[1] for x in lines if x.startswith('Senha:'))
        _FIRST_CREDENTIALS=(username,pw)
    username,pw=_FIRST_CREDENTIALS
    r=client.post('/api/auth/login',json={'email':username,'password':pw})
    assert r.status_code==200
    client.headers['X-CSRF-Token']=r.json()['csrf']
    return client


def test_01_auth_and_csrf():
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/activities').status_code==401
        assert anonymous.post('/api/activities').status_code in (401,403)
    with client_auth() as c:
        assert c.get('/api/auth/me').status_code==200
        other=c.post('/api/activities',headers={'X-CSRF-Token':'incorrect'})
        assert other.status_code==403


def test_02_crud_ai_knowledge_and_export():
    with client_auth() as c:
        p=c.post('/api/projects',json={'name':'Germinare','description':'Projeto de incubação'});assert p.status_code==200
        project=p.json()['id']
        pe=c.post('/api/people',json={'name':'Componente de robótica','kind':'component','role':'Circuito'});assert pe.status_code==200
        k=c.post('/api/knowledge',json={'title':'Manual de referência teste','source':'Texto demonstrativo','content':'O registro deve apresentar objetivo, contexto e resultados que sejam efetivamente comprovados. A documentação de atividades inclui evidências e participantes.','verified':False})
        assert k.status_code==200
        with SessionLocal() as db:
            references=retrieve(db,'comprovados documentação objetivo resultados')
            assert len(references)>=1
            assert references[0]['title']=='Manual de referência teste'
        a=c.post('/api/activities');assert a.status_code==200
        aid=a.json()['id'];assert len(a.json()['groups'])==3
        patch={'title':'Oficina de robótica','activity_date':'2026-11-03','project_id':project,'description':'Os estudantes montaram um robô no laboratório.','objective':'Desenvolver a montagem de componentes.','results':'Foi montado um protótipo.','conclusions':'A atividade registrou a montagem do protótipo.','participants':'Turma do módulo II; Professores convidados','indicators':'Protótipos montados: 1\nFotografias anexadas: 2','competencies':'Trabalho em equipe: montagem conjunta.\nOrganização: separação de componentes.','groups':[{'position':1,'title':'Componentes','people':'Turma do módulo II','description':'Peças organizadas.'},{'position':2,'title':'Montagem','description':'Estudantes trabalhando na estrutura.'}]}
        assert c.patch('/api/activities/'+aid,json=patch).status_code==200
        image=Image.new('RGB',(840,460),(164,184,211));raw=BytesIO();image.save(raw,'JPEG')
        upload=c.post(f'/api/activities/{aid}/photos/1',files=[('files',('a.jpg',raw.getvalue(),'image/jpeg')),('files',('b.jpg',raw.getvalue(),'image/jpeg'))])
        assert upload.status_code==200,upload.text
        assert len(upload.json()['groups'][0]['photos'])==2  # response must contain uploaded images
        photos=upload.json()['groups'][0]['photos']
        assert c.get(photos[0]['url']).status_code==200
        r=c.post('/api/photos/'+photos[1]['id']+'/move',json={'direction':'up'});assert r.status_code==200
        reordered=c.get('/api/activities/'+aid).json()['groups'][0]['photos']
        assert reordered[0]['id']==photos[1]['id']
        assert c.post('/api/activities/'+aid+'/generate',json={'format':'docx'}).status_code==409
        assert c.patch('/api/activities/'+aid,json={'status':'approved'}).status_code==200
        doc=c.post('/api/activities/'+aid+'/generate',json={'format':'docx'});assert doc.status_code==200,doc.text
        pdf=c.post('/api/activities/'+aid+'/generate',json={'format':'pdf'});assert pdf.status_code==200,pdf.text
        original=c.get('/api/templates/modelo-original/docx')
        assert original.status_code==200 and original.content==REFERENCE_DOCX.read_bytes()
        d=c.get(doc.json()['download']);assert d.status_code==200;assert d.content[:2]==b'PK'
        file=BytesIO(d.content);word=Document(file)
        full_text=' '.join(p.text for p in word.paragraphs)
        assert 'Resultados:' in full_text and 'Oficina de robótica' in full_text
        assert full_text.index('Descrição:') < full_text.index('Registro 1') < full_text.index('Registro 2') < full_text.index('Registro 3') < full_text.index('Participantes dessa ação:') < full_text.index('Objetivo:') < full_text.index('Resultados:') < full_text.index('Indicadores alcançados:') < full_text.index('Competências e habilidades:')
        assert 'Protótipos montados: 1' in full_text and 'Trabalho em equipe: montagem conjunta.' in full_text
        assert len(word.inline_shapes)==2
        assert 'BRINCANDO DE STARTUPS NA ESCOLA VIRGÍNIA NOVA' not in full_text
        with ZipFile(BytesIO(d.content)) as zz:
            used_media=[n for n in zz.namelist() if n.startswith('word/media/') and not n.endswith('/')]
            assert len(used_media)==1  # fotos idênticas deduplicadas; fotos ilustrativas do modelo removidas
        pdfbody=c.get(pdf.json()['download']).content
        assert pdfbody.startswith(b'%PDF')
        pdftext=' '.join(x.extract_text() or '' for x in PdfReader(BytesIO(pdfbody)).pages)
        assert 'Indicadores alcan' in pdftext
        assert c.get('/api/activities/'+aid).json()['indicators'].startswith('Protótipos')
        assert len(c.get('/api/activities/'+aid+'/history').json())>=4
        voice=c.post('/api/ai/interpret',json={'text':'No primeiro registro, os estudantes organizam componentes. No segundo registro, fazem a montagem. No terceiro registro, o robô está pronto.'})
        assert voice.status_code==200 and len(voice.json()['groups'])==3
        assert c.post('/api/activities/'+aid+'/ai/refine').status_code==200
        assert c.get('/api/documents').status_code==200
        copy=c.post('/api/activities/'+aid+'/duplicate');assert copy.status_code==200
        assert len(copy.json()['groups'][0]['photos'])==2
        assert copy.json()['competencies'].startswith('Trabalho em equipe')
        assert c.delete('/api/photos/'+photos[0]['id']).status_code==200
        assert c.get('/api/activities/'+aid).status_code==200
        assert c.delete('/api/activities/'+aid).status_code==200
        assert c.get('/api/activities/'+aid).status_code==404


def test_02b_photo_annotations_and_complete_backup():
    import sqlite3
    with client_auth() as c:
        a=c.post('/api/activities').json()
        aid=a['id']
        data={'title':'Atividade com foto descrita','description':'Registro da oficina técnica.',
              'objective':'Registrar a oficina.', 'results':'Oficina realizada.'}
        assert c.patch(f'/api/activities/{aid}',json=data).status_code==200
        image=Image.new('RGB',(740,420),(193,198,216)); raw=BytesIO();image.save(raw,'JPEG')
        r=c.post(f'/api/activities/{aid}/photos/2',files={'files':('foto.jpg',raw.getvalue(),'image/jpeg')})
        assert r.status_code==200
        photo=r.json()['groups'][1]['photos'][0]
        annotation={'description':'Mesa de montagem com componentes organizados.','people':'Equipe participante'}
        r=c.patch('/api/photos/'+photo['id'],json=annotation)
        assert r.status_code==200, r.text
        photo=c.get('/api/activities/'+aid).json()['groups'][1]['photos'][0]
        assert photo['description']==annotation['description']
        assert photo['people']==annotation['people']
        assert c.patch(f'/api/activities/{aid}',json={'status':'approved'}).status_code==200
        r=c.post(f'/api/activities/{aid}/generate',json={'format':'docx'})
        assert r.status_code==200,r.text
        doc=Document(BytesIO(c.get(r.json()['download']).content))
        txt=' '.join(p.text for p in doc.paragraphs)
        assert 'Descrição da fotografia: Mesa de montagem' in txt
        assert 'Participantes/componentes na foto: Equipe participante' in txt
        r=c.post(f'/api/activities/{aid}/generate',json={'format':'pdf'})
        assert r.status_code==200,r.text
        pdftext=' '.join(p.extract_text() or '' for p in PdfReader(BytesIO(c.get(r.json()['download']).content)).pages)
        assert 'Mesa de montagem' in pdftext
        assert 'Equipe participante' in pdftext
        backup=c.get('/api/admin/backup')
        assert backup.status_code==200,backup.text[:200] if backup.status_code!=200 else ''
        with ZipFile(BytesIO(backup.content)) as zf:
            paths=zf.namelist()
            assert 'evidencias.db' in paths
            assert 'LEIA_BACKUP.json' in paths
            assert any(x.startswith('uploads/') for x in paths)
            assert any(x.startswith('documents/') for x in paths)
            assert '.env' not in paths and '.session_key' not in paths
            with tempfile.TemporaryDirectory() as temp:
                database=Path(temp)/'backup.db'
                database.write_bytes(zf.read('evidencias.db'))
                with sqlite3.connect(database) as con:
                    assert con.execute('select count(*) from activities where id=?',(aid,)).fetchone()[0]==1
                    assert con.execute('select description from photos where id=?',(photo['id'],)).fetchone()[0]==annotation['description']
        # a saved photo caption invalidates previous approval
        assert c.patch('/api/photos/'+photo['id'],json={'description':'Nova descrição','people':''}).status_code==200
        assert c.get('/api/activities/'+aid).json()['status']=='draft'
        assert c.post(f'/api/activities/{aid}/generate',json={'format':'docx'}).status_code==409


def test_03_knowledge_upload_and_delete():
    with client_auth() as c:
        raw=b'Manual CERNE exemplo somente para testes. Os indicadores devem estar ligados a registros comprovados.'
        r=c.post('/api/knowledge/upload',files={'file':('base.txt',raw,'text/plain')},data={'title':'Base de teste'})
        assert r.status_code==200 and r.json()['chunks']>=1
        item=r.json()['id']
        assert c.delete('/api/knowledge/'+item).status_code==200
        assert item not in [k['id'] for k in c.get('/api/knowledge').json()]


def test_03a_ai_panel_credentials_are_encrypted_and_admin_only():
    from app.ai_settings import public_settings, current_settings
    from app.agent import provider
    from app.models import User
    from app.security import hash_password
    with client_auth() as c:
        assert c.put('/api/admin/ai',json={'provider':'gemini','api_key':'example-fake-api-key-98765','model':'gemini-2.5-flash'}).status_code==200
        cfg=c.get('/api/admin/ai').json()
        assert cfg['configured'] is True and cfg['provider']=='gemini'
        assert cfg['key_hint'].endswith('8765') and 'api_key' not in cfg
        assert b'example-fake-api-key-98765' not in (DATA_DIR/'.ai_credentials.enc').read_bytes()
        assert provider()=='Gemini'
        assert c.put('/api/admin/ai',json={'provider':'gemini','api_key':'','model':'gemini-2.5-flash'}).status_code==200
        assert current_settings()['api_key']=='example-fake-api-key-98765'
        assert c.put('/api/admin/ai',json={'provider':'openai','api_key':'','model':''}).status_code==422
        with SessionLocal() as db:
            db.add(User(email='limited@local.test',name='Limitado',password_hash=hash_password('StrongPassword_2026!'),role='editor'))
            db.commit()
        with TestClient(app) as restricted:
            response=restricted.post('/api/auth/login',json={'email':'limited@local.test','password':'StrongPassword_2026!'})
            assert response.status_code==200
            restricted.headers['X-CSRF-Token']=response.json()['csrf']
            assert restricted.get('/api/admin/ai').status_code==403
            assert restricted.put('/api/admin/ai',json={'provider':'none'}).status_code==403
        assert c.put('/api/admin/ai',json={'provider':'none'}).status_code==200
        assert public_settings()['configured'] is False
        assert provider() is None
        assert c.post('/api/auth/logout').status_code==200
        assert c.get('/api/admin/ai').status_code==401


def test_03b_dictation_interpreter_does_not_invent_results():
    from app.agent import rule_based_interpret
    narrative=('No dia 03/11/2026 realizamos uma oficina de robótica no laboratório de informática com 20 alunos. '
      'O objetivo foi desenvolver habilidades de montagem e programação. '
      'No primeiro registro, os estudantes organizaram as peças. '
      'No segundo registro, fizeram a montagem. '
      'No terceiro registro, o robô estava pronto. Foram desenvolvidos 5 projetos.')
    result=rule_based_interpret(narrative)
    assert result['fields']['activity_date']=='2026-11-03'
    assert 'laboratório de informática' in result['fields']['location']
    assert '20 alunos' in result['fields']['participants']
    assert 'Alunos: 20' in result['fields']['indicators']
    assert len(result['groups'])==3
    assert '5 projetos' in result['fields']['results']
    assert result['fields']['conclusions']==''


def test_03c_generate_uses_panel_key_not_just_env(monkeypatch):
    from app.ai_settings import save_settings
    from app import agent
    save_settings('openai','test-key-panel-no-real-account-12345','gpt-4o-mini')
    class Reply:
        def raise_for_status(self): pass
        def json(self):return {'choices':[{'message':{'content':'{"ok":true}'}}]}
    def fake_post(url,headers,json,timeout):
        assert url=='https://api.openai.com/v1/chat/completions'
        assert headers['Authorization']=='Bearer test-key-panel-no-real-account-12345'
        return Reply()
    monkeypatch.setattr(agent.requests,'post',fake_post)
    assert agent.generate('Retorne {"ok":true}') == {'ok':True}
    save_settings('none')


def test_04_reset_password_preserves_activities():
    from redefinir_acesso import reset_password
    from app.models import User
    with client_auth() as client:
        old_login=(DATA_DIR/'ACESSO_INICIAL.txt').read_text(encoding='utf-8').split('Login: ')[1].splitlines()[0]
        old_pw=(DATA_DIR/'ACESSO_INICIAL.txt').read_text(encoding='utf-8').split('Senha: ')[1].splitlines()[0]
        before = client.get('/api/overview').json()['activities']
    assert reset_password('inexistente@evidencias.local','SenhaNova_MuitoSegura1') is False
    assert reset_password(old_login,'SenhaNova_MuitoSegura1') is True
    assert not (DATA_DIR/'ACESSO_INICIAL.txt').exists()
    with TestClient(app) as client:
        assert client.post('/api/auth/login', json={'email':old_login,'password':old_pw}).status_code == 401
        new = client.post('/api/auth/login', json={'email':old_login,'password':'SenhaNova_MuitoSegura1'})
        assert new.status_code == 200
        assert client.get('/api/overview').json()['activities'] == before


def test_05_public_health():
    with TestClient(app) as c:
        r = c.get('/api/health')
        assert r.status_code == 200
        assert r.json()['app'] == 'evidencia_cerne'
        assert r.json()['ok'] is True


def test_02c_binary_storage_survives_local_file_removal():
    """Render free has ephemeral disk: media must be readable from DB alone."""
    from app.models import Photo, GeneratedDocument
    from app.models import User
    from app.security import hash_password
    with SessionLocal() as db:
        if not db.query(User).filter_by(email='testblob@local.test').first():
            db.add(User(email='testblob@local.test',name='Admin de teste',password_hash=hash_password('TestPassword#987654321'),role='admin'))
            db.commit()
    with TestClient(app) as c:
        auth = c.post('/api/auth/login',json={'email':'testblob@local.test','password':'TestPassword#987654321'})
        assert auth.status_code == 200,auth.text
        c.headers['X-CSRF-Token'] = auth.json()['csrf']
        activity = c.post('/api/activities').json()
        activity_id = activity['id']
        c.patch('/api/activities/' + activity_id, json={
            'title': 'Evidência persistente', 'description': 'Registros de teste.',
            'objective': 'Registrar fotos.', 'results': 'Registro criado.'})
        source = Image.new('RGB', (300, 150), (95, 140, 185))
        buf = BytesIO(); source.save(buf, 'JPEG')
        response = c.post('/api/activities/'+activity_id+'/photos/1', files={'files': ('x.jpg',buf.getvalue(),'image/jpeg')})
        assert response.status_code == 200
        pid = response.json()['groups'][0]['photos'][0]['id']
        with SessionLocal() as db:
            photo = db.get(Photo, pid)
            assert photo.blob and photo.blob[:2] == b'\xff\xd8'
            (DATA_DIR/'uploads'/photo.filename).unlink(missing_ok=True)
        assert c.get('/api/photos/'+pid+'/file').content[:2] == b'\xff\xd8'
        assert c.patch('/api/activities/'+activity_id,json={'status':'approved'}).status_code == 200
        response = c.post('/api/activities/'+activity_id+'/generate',json={'format':'docx'})
        assert response.status_code == 200,response.text
        docid = response.json()['id']
        with SessionLocal() as db:
            doc = db.get(GeneratedDocument, docid)
            assert doc.blob and doc.blob[:2] == b'PK'
            (DATA_DIR/'documents'/doc.filename).unlink(missing_ok=True)
        assert c.get('/api/documents/'+docid+'/download').content[:2] == b'PK'
        assert c.delete('/api/activities/'+activity_id).status_code == 200
