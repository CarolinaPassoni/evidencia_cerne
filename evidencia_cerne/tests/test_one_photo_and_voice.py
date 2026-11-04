import os
from pathlib import Path
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient

from test_end_to_end import app, client_auth
from app.agent import complete_field


def test_field_completion_without_ai(monkeypatch):
    monkeypatch.setattr('app.agent.provider', lambda: None)
    ans=complete_field('objective','Apresentar o sistema.','Demonstrar o registro das atividades aos participantes.')
    assert ans['mode']=='basic'
    assert ans['text']=='Apresentar o sistema. Demonstrar o registro das atividades aos participantes.'
    assert 'participantes' in ans['text']


def test_field_completion_with_mock_ai(monkeypatch):
    monkeypatch.setattr('app.agent.provider', lambda: 'Gemini')
    def fake_generate(prompt):
        assert 'Apresentar o sistema.' in prompt
        assert 'Demonstrar a exportação' in prompt
        return {'text':'Apresentar o sistema e demonstrar a exportação dos documentos.'}
    monkeypatch.setattr('app.agent.generate',fake_generate)
    ans=complete_field('objective','Apresentar o sistema.','Demonstrar a exportação dos documentos.')
    assert ans['mode']=='ai'
    assert 'exportação' in ans['text']


def test_fotos_and_document_model_are_one_per_group():
    doc=Path(__file__).resolve().parents[1]/'app'/'documents.py'
    source=doc.read_text()
    assert 'photos=list(group.photos)[:1] if group else []' in source
    assert 'photos=list(g.photos)[:1]' in source
    page=Path(__file__).resolve().parents[1]/'app'/'static'/'app.js'
    js=page.read_text()
    assert "files.length!==1" in js
    assert 'completeFieldDictation(session,spoken)' in js
    assert "'/ai/complete-field'" in js
    assert 'multiple accept="image/jpeg' not in js


def test_field_api_requires_login():
    with TestClient(app) as client:
        r=client.post('/api/ai/complete-field',json={'field':'objective','existing':'x','spoken':'y'})
        assert r.status_code==401


def test_field_api_authorized_completes_text_without_ai(monkeypatch):
    monkeypatch.setattr('app.agent.provider', lambda: None)
    from app.models import User
    from app.database import SessionLocal
    from app.security import hash_password
    with TestClient(app) as client:
        with SessionLocal() as db:
            db.add(User(email='microfone-teste@example.invalid',name='Teste Voz',
                        password_hash=hash_password('password_for_isolated_test_2026')))
            db.commit()
        login=client.post('/api/auth/login',json={'email':'microfone-teste@example.invalid','password':'password_for_isolated_test_2026'})
        assert login.status_code==200, login.text
        client.headers['X-CSRF-Token']=login.json()['csrf']
        response=client.post('/api/ai/complete-field',json={
            'field':'objective','existing':'Promover a oficina.','spoken':'Registrar a participação.'})
        assert response.status_code==200, response.text
        assert response.json()['text']=='Promover a oficina. Registrar a participação.'
        bad=client.post('/api/ai/complete-field',json={'field':'status','existing':'','spoken':'Aprovado'})
        assert bad.status_code==422
