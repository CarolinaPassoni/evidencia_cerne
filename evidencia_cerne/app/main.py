import os, json, re, secrets, shutil, io, sys, sqlite3, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import or_, func, inspect, text
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from .database import Base, engine, SessionLocal, db_session, DATA_DIR, BASE_DIR
from .models import User, Project, Person, Activity, PhotoGroup, Photo, KnowledgeDocument, KnowledgeChunk, DocumentTemplate, GeneratedDocument, AuditLog
from .security import user_or_401, admin_or_403, hash_password, verify_password, secret_key, check_login_rate, start_session
from .models import AppSession
from .knowledge import init_fts, extract_text, save_document, remove_document
from .agent import provider, generate, refine_activity, interpret_voice, describe_photo_groups
from .ai_settings import current_settings, public_settings, save_settings
from .documents import create_docx, create_pdf, REFERENCE_DOCX

MAX_IMAGE=12*1024*1024
MAX_KNOWLEDGE=8*1024*1024
FIELDS=['title','description','activity_date','location','participants','objective','results','indicators','competencies','conclusions','project_id','status']
GROUP_FIELDS=['title','description','people']

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv('RENDER') and engine.dialect.name == 'sqlite':
        raise RuntimeError('DATABASE_URL PostgreSQL é obrigatória no Render; SQLite temporário não é permitido.')
    Base.metadata.create_all(bind=engine)
    # Migração aditiva: atualizar instalações antigas sem apagar tabelas, fotos ou histórico.
    migration_fields = {
        'activities': [('indicators', 'TEXT'), ('competencies', 'TEXT')],
        'document_templates': [('layout', "VARCHAR(30) DEFAULT 'institutional'")],
        'photos': [('description', 'TEXT'), ('people', 'TEXT'), ('blob', 'BLOB' if engine.dialect.name == 'sqlite' else 'BYTEA')],
        'generated_documents': [('blob', 'BLOB' if engine.dialect.name == 'sqlite' else 'BYTEA')],
    }
    with engine.begin() as connection:
        for table_name, columns in migration_fields.items():
            existing = {c['name'] for c in inspect(connection).get_columns(table_name)}
            for column_name, column_type in columns:
                if column_name not in existing:
                    connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
    with SessionLocal() as db:
        init_fts(db)
        if not db.query(DocumentTemplate).count():
            db.add(DocumentTemplate(name='Institucional azul', subtitle='RELATÓRIO DE EVIDÊNCIA',color='#125e78',institution='REGISTRO DE EVIDÊNCIA',footer='Evidência documental | Registro institucional'))
            db.add(DocumentTemplate(name='Institucional grafite', subtitle='RELATÓRIO DE ATIVIDADE',color='#32445c',institution='GESTÃO DE EVIDÊNCIAS',footer='Registro institucional'))
            db.commit()
        if not db.query(DocumentTemplate).filter_by(name='Modelo fiel ao documento enviado').first():
            db.add(DocumentTemplate(name='Modelo fiel ao documento enviado',layout='reference',subtitle='MODELO DE EVIDÊNCIA',color='#111111'))
            db.commit()
        if not db.query(User).count():
            email = os.getenv('ADMIN_EMAIL', 'admin@evidencias.local')
            password = os.getenv('ADMIN_PASSWORD') or secrets.token_urlsafe(15)
            db.add(User(name='Administrador',email=email,password_hash=hash_password(password)))
            db.commit()
            if not os.getenv('ADMIN_PASSWORD'):
                target=DATA_DIR/'ACESSO_INICIAL.txt'
                target.write_text(f'ACESSO INICIAL, ALTERE A SENHA APÓS ENTRAR\nEndereço: http://127.0.0.1:8000\nLogin: {email}\nSenha: {password}\n',encoding='utf-8')
                try: target.chmod(0o600)
                except OSError: pass
                print(f'\n*** PRIMEIRO ACESSO: consulte {target} ***\n',flush=True)
    yield

app=FastAPI(title='Evidência CERNE',version='1.7',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(SessionMiddleware,secret_key=secret_key(),same_site='strict',https_only=os.getenv('COOKIE_HTTPS','0')=='1',max_age=60*60*12)
app.mount('/static',StaticFiles(directory=BASE_DIR/'app'/'static'),name='static')

@app.middleware('http')
async def security_headers(request,call_next):
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS') :
        # Together with SameSite cookies and CSRF header, mitigate cross-site writes.
        origin=request.headers.get('origin')
        host=request.headers.get('host','')
        if origin and origin.replace('https://','').replace('http://','').rstrip('/')!=host:
            return JSONResponse({'detail':'Origem não autorizada.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'max-age=300'
    return response

@app.get('/')
def home(): return FileResponse(BASE_DIR/'app'/'static'/'index.html')

@app.get('/api/health')
def health():
    """Diagnóstico público de conectividade, sem dados de usuários."""
    return {'ok': True, 'app': 'evidencia_cerne', 'version': '1.7'}

class Login(BaseModel):
    email: str
    password: str

@app.post('/api/auth/login')
def login(data: Login,request:Request,db:Session=Depends(db_session)):
    check_login_rate(request)
    user=db.query(User).filter(func.lower(User.email)==data.email.strip().lower()).first()
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,'Login ou senha incorretos.')
    start_session(request, db, user)
    return {'id':user.id,'name':user.name,'email':user.email,'role':user.role,'csrf':request.session['csrf']}

@app.get('/api/auth/me')
def me(request:Request,user:User=Depends(user_or_401)):
    return {'id':user.id,'name':user.name,'email':user.email,'role':user.role,'csrf':request.session['csrf'],'provider':provider(),'model':public_settings()['model']}

@app.post('/api/auth/logout')
def logout(request:Request,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    db.query(AppSession).filter_by(id=request.session.get('sid')).delete()
    db.commit()
    request.session.clear(); return {'ok':True}

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

@app.post('/api/auth/password')
def change_password(data:PasswordUpdate,request:Request,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    if not verify_password(data.old_password,user.password_hash): raise HTTPException(400,'A senha atual não confere.')
    if len(data.new_password)<12: raise HTTPException(400,'A nova senha deve ter pelo menos 12 caracteres.')
    user.password_hash=hash_password(data.new_password)
    db.query(AppSession).filter_by(user_id=user.id).delete()
    db.commit()
    csrf = request.session['csrf']
    start_session(request, db, user)
    request.session['csrf'] = csrf
    fp=DATA_DIR/'ACESSO_INICIAL.txt'
    if fp.exists(): fp.unlink()
    return {'ok':True}



@app.get('/api/admin/ai')
def ai_admin_get(user: User = Depends(admin_or_403)):
    return public_settings()

class AISettingsInput(BaseModel):
    provider: str
    api_key: str = Field(default='', max_length=1024)
    model: str = Field(default='', max_length=120)

@app.put('/api/admin/ai')
def ai_admin_save(data: AISettingsInput, user: User = Depends(admin_or_403)):
    try:
        return save_settings(data.provider, data.api_key, data.model)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.post('/api/admin/ai/test')
def ai_admin_test(user: User = Depends(admin_or_403)):
    if not provider():
        raise HTTPException(400, 'Cadastre primeiro uma chave de IA.')
    try:
        result = generate('Responda somente com JSON: {"ok": true}.')
    except ValueError as exc:
        raise HTTPException(502, str(exc))
    return {'ok': result.get('ok') is True, 'provider': provider(),
            'message': 'Serviço respondeu à solicitação de teste.' if result.get('ok') is True else 'A IA respondeu, mas não seguiu o formato pedido.'}

def iso(v): return v.isoformat() if v else None

def audit(db,activity_id,user,action,detail=''):
    db.add(AuditLog(activity_id=activity_id,user_id=user.id if user else None,action=action,detail=detail[:8000]))

def a_to_dict(a,detail=False):
    out={'id':a.id,'title':a.title,'description':a.description,'activity_date':a.activity_date,'location':a.location,'participants':a.participants,'objective':a.objective,'results':a.results,'indicators':a.indicators,'competencies':a.competencies,'conclusions':a.conclusions,'status':a.status,'project_id':a.project_id,'project_name':a.project.name if a.project else None,'created_at':iso(a.created_at),'updated_at':iso(a.updated_at)}
    if detail:
        out['groups']=[{'id':g.id,'position':g.position,'title':g.title,'description':g.description,'people':g.people,'photos':[{'id':p.id,'url':f'/api/photos/{p.id}/file','name':p.original_name,'position':p.position,'description':p.description or '', 'people':p.people or ''} for p in g.photos]} for g in a.groups]
    return out

def get_activity(db,id):
    a=db.query(Activity).options(joinedload(Activity.project),selectinload(Activity.groups).selectinload(PhotoGroup.photos)).filter_by(id=id).first()
    if not a: raise HTTPException(404,'Atividade não encontrada.')
    return a

@app.get('/api/admin/backup')
def backup_all(db: Session=Depends(db_session), user: User=Depends(admin_or_403)):
    """Consistent SQLite snapshot + uploaded photos + exported documents, no secrets/config."""
    if engine.dialect.name != 'sqlite' or not engine.url.database:
        raise HTTPException(409, 'Backup integrado disponível apenas para SQLite. Faça backup pelo serviço de banco configurado.')
    storage=DATA_DIR/'backups'
    storage.mkdir(parents=True,exist_ok=True)
    handle=tempfile.NamedTemporaryFile(prefix='evidencia_',suffix='.zip',dir=storage,delete=False)
    zip_path=Path(handle.name)
    handle.close()
    try:
        with tempfile.TemporaryDirectory(prefix='snapshot_',dir=storage) as tmp:
            snapshot=Path(tmp)/'evidencias.db'
            with sqlite3.connect(str(engine.url.database)) as origin, sqlite3.connect(str(snapshot)) as destination:
                origin.backup(destination)
            with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
                zf.write(snapshot,'evidencias.db')
                for sub in ('uploads','documents'):
                    folder=DATA_DIR/sub
                    if folder.is_dir():
                        for file in folder.rglob('*'):
                            if file.is_file() and not file.is_symlink():
                                zf.write(file,f'{sub}/{file.relative_to(folder).as_posix()}')
                manifest={
                    'application':'Evidencia+', 'version':'1.6',
                    'created_utc':datetime.now(timezone.utc).isoformat(),
                    'contents':'Banco SQLite, fotografias e documentos gerados',
                    'notice':'O backup contém dados pessoais. Proteja o arquivo e nunca o compartilhe publicamente.'
                }
                zf.writestr('LEIA_BACKUP.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(500,'Não foi possível criar o backup. Verifique o espaço disponível em disco.')
    name='Evidencia_Backup_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip'
    return FileResponse(zip_path, filename=name, media_type='application/zip',background=BackgroundTask(lambda:zip_path.unlink(missing_ok=True)))

@app.get('/api/status')
def status(user=Depends(user_or_401)):
    return {'provider':provider(),'recognition':'Web Speech API (navegador compatível)'}

@app.get('/api/overview')
def overview(db:Session=Depends(db_session),user=Depends(user_or_401)):
    return {'activities':db.query(Activity).count(),'approved':db.query(Activity).filter_by(status='approved').count(),'projects':db.query(Project).count(),'knowledge':db.query(KnowledgeDocument).count(),'documents':db.query(GeneratedDocument).count(), 'recent':[a_to_dict(a) for a in db.query(Activity).order_by(Activity.updated_at.desc()).limit(6).all()]}

@app.get('/api/activities')
def activities(q:str='',project_id:str='',person:str='',date_from:str='',date_to:str='',status:str='',db:Session=Depends(db_session),user=Depends(user_or_401)):
    query=db.query(Activity).options(joinedload(Activity.project))
    if q.strip():
        term=f'%{q.strip()}%'
        query=query.filter(or_(Activity.title.ilike(term),Activity.description.ilike(term),Activity.participants.ilike(term)))
    if project_id: query=query.filter(Activity.project_id==project_id)
    if person: query=query.filter(Activity.participants.ilike(f'%{person}%'))
    if date_from: query=query.filter(Activity.activity_date>=date_from)
    if date_to: query=query.filter(Activity.activity_date<=date_to)
    if status: query=query.filter(Activity.status==status)
    return [a_to_dict(a) for a in query.order_by(Activity.updated_at.desc()).limit(500).all()]

@app.post('/api/activities')
def new_activity(db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    a=Activity(created_by=user.id)
    db.add(a); db.flush()
    for pos in [1,2,3]: db.add(PhotoGroup(activity_id=a.id,position=pos))
    audit(db,a.id,user,'created'); db.commit()
    return a_to_dict(get_activity(db,a.id),True)

@app.get('/api/activities/{activity_id}')
def activity_detail(activity_id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    return a_to_dict(get_activity(db,activity_id),True)

class ActivityPatch(BaseModel):
    title: str|None=None
    description: str|None=None
    activity_date: str|None=None
    location: str|None=None
    participants: str|None=None
    objective: str|None=None
    results: str|None=None
    indicators: str|None=None
    competencies: str|None=None
    conclusions: str|None=None
    project_id: str|None=None
    status: str|None=None
    groups: list[dict]|None=None

@app.patch('/api/activities/{activity_id}')
def update_activity(activity_id:str,data:ActivityPatch,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    a=get_activity(db,activity_id)
    changed={}
    for key,value in data.model_dump(exclude_unset=True,exclude={'groups'}).items():
        if key not in FIELDS: continue
        if key=='activity_date' and value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value): raise HTTPException(422,'Data inválida.')
        if key=='status' and value not in ['draft','approved']: raise HTTPException(422,'Status inválido.')
        if key=='project_id' and value and not db.get(Project,value): raise HTTPException(422,'Projeto inválido.')
        if value is not None and len(value)>15000: raise HTTPException(422,'Campo muito longo.')
        if getattr(a,key)!=value: changed[key]={'before':getattr(a,key),'after':value}; setattr(a,key,value)
    if data.groups is not None:
        if len(data.groups)>3: raise HTTPException(422,'São permitidos três grupos.')
        by_position={g.position:g for g in a.groups}
        for row in data.groups:
            pos=row.get('position')
            if pos not in by_position: raise HTTPException(422,'Grupo inválido.')
            g=by_position[pos]
            for key in GROUP_FIELDS:
                if key in row:
                    val=str(row[key] or '')
                    if len(val)>12000: raise HTTPException(422,'Campo muito longo.')
                    if getattr(g,key)!=val:
                        changed[f'grupo_{pos}_{key}']={'before':getattr(g,key),'after':val}
                        setattr(g,key,val)
    if changed:
        if any(k != 'status' for k in changed) and a.status == 'approved':
            a.status = 'draft'
            changed['status'] = {'before':'approved','after':'draft'}
        a.updated_at=datetime.now(timezone.utc)
        audit(db,a.id,user,'updated',json.dumps(changed,ensure_ascii=False))
        db.commit()
    return a_to_dict(get_activity(db,a.id),True)

@app.delete('/api/activities/{activity_id}')
def delete_activity(activity_id:str,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    a=get_activity(db,activity_id)
    files=[DATA_DIR/'uploads'/p.filename for g in a.groups for p in g.photos]
    files.extend(DATA_DIR/'documents'/d.filename for d in a.documents)
    db.delete(a); db.commit()
    for path in files: path.unlink(missing_ok=True)
    return {'ok':True}

@app.post('/api/activities/{activity_id}/duplicate')
def duplicate_activity(activity_id:str,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    source=get_activity(db,activity_id)
    a=Activity(created_by=user.id,title=source.title+' (cópia)',description=source.description,activity_date=source.activity_date,
        project_id=source.project_id,location=source.location,participants=source.participants,objective=source.objective,results=source.results,indicators=source.indicators,competencies=source.competencies,conclusions=source.conclusions,status='draft')
    db.add(a); db.flush()
    for sg in source.groups:
        g=PhotoGroup(activity_id=a.id,position=sg.position,title=sg.title,description=sg.description,people=sg.people)
        db.add(g); db.flush()
        for photo in sg.photos:
            old=DATA_DIR/'uploads'/photo.filename
            newname=secrets.token_hex(16)+old.suffix
            if old.exists() or photo.blob is not None:
                if old.exists(): shutil.copy2(old,DATA_DIR/'uploads'/newname)
                db.add(Photo(group_id=g.id,filename=newname,original_name=photo.original_name,position=photo.position,description=photo.description,people=photo.people,blob=photo.blob))
    audit(db,a.id,user,'duplicated',activity_id); db.commit()
    return a_to_dict(get_activity(db,a.id),True)

@app.post('/api/activities/{activity_id}/photos/{position}')
async def upload_photo(activity_id:str,position:int,files:list[UploadFile]=File(...),db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    a=get_activity(db,activity_id)
    group=next((g for g in a.groups if g.position==position),None)
    if group is None: raise HTTPException(404,'Registro fotográfico inválido.')
    if not files or len(files)>15 or len(files)+len(group.photos)>25: raise HTTPException(400,'Envie de 1 a 15 imagens por vez (máximo 25 por registro).')
    pending=[]
    try:
        for item in files:
            raw=await item.read(MAX_IMAGE+1)
            if len(raw)>MAX_IMAGE: raise HTTPException(413,'Imagem acima de 12 MB.')
            try:
                with Image.open(io.BytesIO(raw)) as loaded:
                    loaded.verify()
                with Image.open(io.BytesIO(raw)) as loaded:
                    loaded=ImageOps.exif_transpose(loaded)
                    if loaded.width*loaded.height>35_000_000: raise ValueError('Imagem muito grande.')
                    loaded.thumbnail((2400,2400))
                    img=loaded.convert('RGB')
                    name=secrets.token_hex(16)+'.jpg'; path=DATA_DIR/'uploads'/name
                    img.save(path,'JPEG',quality=88,optimize=True)
            except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError) as exc:
                raise HTTPException(422,'Arquivo de imagem inválido ou excessivamente grande.') from exc
            pending.append((name,os.path.basename(item.filename or 'imagem.jpg')[:230],path.read_bytes()))
        next_pos=max([p.position for p in group.photos] or [0])+1
        for i,(name,orig,blob) in enumerate(pending):
            db.add(Photo(group_id=group.id,filename=name,original_name=orig,position=next_pos+i,blob=blob))
        a.status='draft'; a.updated_at=datetime.now(timezone.utc); audit(db,a.id,user,'photos_uploaded',f'Grupo {position}, {len(files)} imagens'); db.commit(); db.expire_all()
    except Exception:
        db.rollback()
        for name,*_ in pending: (DATA_DIR/'uploads'/name).unlink(missing_ok=True)
        raise
    return a_to_dict(get_activity(db,a.id),True)

@app.get('/api/photos/{photo_id}/file')
def serve_photo(photo_id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    p=db.get(Photo,photo_id)
    if not p: raise HTTPException(404,'Foto não encontrada.')
    if p.blob is not None:
        return Response(content=p.blob,media_type='image/jpeg')
    path=DATA_DIR/'uploads'/p.filename
    if not path.is_file(): raise HTTPException(404,'Arquivo indisponível.')
    return FileResponse(path,media_type='image/jpeg')

class PhotoAnnotation(BaseModel):
    description: str = Field(default='', max_length=3000)
    people: str = Field(default='', max_length=1000)

@app.patch('/api/photos/{photo_id}')
def annotate_photo(photo_id: str, data: PhotoAnnotation, db: Session=Depends(db_session), user: User=Depends(user_or_401)):
    photo=db.get(Photo, photo_id)
    if photo is None: raise HTTPException(404, 'Foto não encontrada.')
    old={'description':photo.description or '', 'people':photo.people or ''}
    new=data.model_dump()
    if old != new:
        photo.description=new['description'].strip()
        photo.people=new['people'].strip()
        activity=db.get(Activity, photo.group.activity_id)
        if activity:
            activity.status='draft'
            activity.updated_at=datetime.now(timezone.utc)
        audit(db, photo.group.activity_id, user, 'photo_annotated', json.dumps({'photo_id':photo.id, 'before':old, 'after':new},ensure_ascii=False))
        db.commit()
    return {'ok':True,'id':photo.id,'description':photo.description or '', 'people':photo.people or ''}

@app.delete('/api/photos/{photo_id}')
def delete_photo(photo_id:str,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    photo=db.get(Photo,photo_id)
    if not photo: raise HTTPException(404,'Foto não encontrada.')
    activity_id=photo.group.activity_id; name=photo.filename
    activity=db.get(Activity,activity_id)
    if activity: activity.status='draft'
    db.delete(photo); audit(db,activity_id,user,'photo_deleted',photo_id); db.commit()
    (DATA_DIR/'uploads'/name).unlink(missing_ok=True)
    return {'ok':True}

class Direction(BaseModel): direction: str
@app.post('/api/photos/{photo_id}/move')
def move_photo(photo_id:str,data:Direction,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    photo=db.get(Photo,photo_id)
    if not photo: raise HTTPException(404,'Foto não encontrada.')
    photos=db.query(Photo).filter_by(group_id=photo.group_id).order_by(Photo.position).all()
    idx=next(i for i,p in enumerate(photos) if p.id==photo_id)
    other=idx+(-1 if data.direction=='up' else 1)
    if data.direction not in ['up','down']: raise HTTPException(422,'Direção inválida.')
    if 0<=other<len(photos):
        photos[idx],photos[other]=photos[other],photos[idx]
        for i,p in enumerate(photos): p.position=i+1
        activity=db.get(Activity,photo.group.activity_id)
        if activity: activity.status='draft'
        audit(db,photo.group.activity_id,user,'photos_reordered',photo_id)
        db.commit()
    return {'ok':True}

@app.get('/api/projects')
def list_projects(db:Session=Depends(db_session),user=Depends(user_or_401)):
    return [{'id':p.id,'name':p.name,'description':p.description,'created_at':iso(p.created_at)} for p in db.query(Project).order_by(Project.name).all()]
class ProjectInput(BaseModel):
    name: str=Field(min_length=2,max_length=250)
    description: str=''
@app.post('/api/projects')
def add_project(data:ProjectInput,db:Session=Depends(db_session),user=Depends(user_or_401)):
    p=Project(**data.model_dump()); db.add(p); db.commit(); return {'id':p.id}
@app.patch('/api/projects/{id}')
def edit_project(id:str,data:ProjectInput,db:Session=Depends(db_session),user=Depends(user_or_401)):
    p=db.get(Project,id)
    if not p: raise HTTPException(404,'Projeto não encontrado.')
    p.name=data.name; p.description=data.description; db.commit(); return {'ok':True}
@app.delete('/api/projects/{id}')
def del_project(id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    p=db.get(Project,id)
    if not p: raise HTTPException(404,'Projeto não encontrado.')
    db.delete(p); db.commit(); return {'ok':True}

@app.get('/api/people')
def list_people(db:Session=Depends(db_session),user=Depends(user_or_401)):
    return [{'id':p.id,'name':p.name,'kind':p.kind,'role':p.role,'notes':p.notes} for p in db.query(Person).order_by(Person.name).all()]
class PersonInput(BaseModel):
    name: str=Field(min_length=2,max_length=200)
    kind: str='person'
    role: str=''
    notes: str=''
@app.post('/api/people')
def add_person(data:PersonInput,db:Session=Depends(db_session),user=Depends(user_or_401)):
    if data.kind not in ['person','component']:raise HTTPException(422,'Tipo inválido.')
    p=Person(**data.model_dump());db.add(p);db.commit();return {'id':p.id}
@app.patch('/api/people/{id}')
def edit_person(id:str,data:PersonInput,db:Session=Depends(db_session),user=Depends(user_or_401)):
    p=db.get(Person,id)
    if not p: raise HTTPException(404,'Pessoa não encontrada.')
    if data.kind not in ['person','component']:raise HTTPException(422,'Tipo inválido.')
    for k,v in data.model_dump().items():setattr(p,k,v)
    db.commit();return {'ok':True}
@app.delete('/api/people/{id}')
def del_person(id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    p=db.get(Person,id)
    if not p: raise HTTPException(404,'Pessoa não encontrada.')
    db.delete(p);db.commit();return {'ok':True}

@app.get('/api/knowledge')
def knowledge_list(db:Session=Depends(db_session),user=Depends(user_or_401)):
    return [{'id':d.id,'title':d.title,'source':d.source,'content':d.content,'verified':d.verified,'updated_at':iso(d.updated_at),'chunks':len(d.chunks)} for d in db.query(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc()).all()]

class KnowledgeInput(BaseModel):
    title: str=Field(min_length=3,max_length=250)
    source: str=''
    content: str=Field(min_length=10,max_length=500000)
    verified: bool=False

@app.post('/api/knowledge')
def knowledge_create(data:KnowledgeInput,db:Session=Depends(db_session),user:User=Depends(admin_or_403)):
    d=KnowledgeDocument(**data.model_dump());db.add(d);db.flush()
    save_document(db,d)
    return {'id':d.id,'chunks':len(d.chunks)}

@app.put('/api/knowledge/{id}')
def knowledge_edit(id:str,data:KnowledgeInput,db:Session=Depends(db_session),user:User=Depends(admin_or_403)):
    d=db.get(KnowledgeDocument,id)
    if not d:raise HTTPException(404,'Referência não encontrada.')
    for k,v in data.model_dump().items():setattr(d,k,v)
    save_document(db,d)
    return {'ok':True}

@app.post('/api/knowledge/upload')
async def knowledge_upload(file:UploadFile=File(...),title:str=Form(''),verified:bool=Form(False),db:Session=Depends(db_session),user:User=Depends(admin_or_403)):
    raw=await file.read(MAX_KNOWLEDGE+1)
    if len(raw)>MAX_KNOWLEDGE: raise HTTPException(413,'Arquivo maior que 8 MB.')
    try: content=extract_text(file.filename or '',raw)
    except Exception as exc: raise HTTPException(422,str(exc))
    if len(content)<10: raise HTTPException(422,'Conteúdo textual insuficiente.')
    if len(content)>500000: raise HTTPException(413,'Documento muito longo.')
    d=KnowledgeDocument(title=title or (file.filename or 'Documento'),source=file.filename or '',content=content,verified=verified)
    db.add(d);db.flush();save_document(db,d)
    return {'id':d.id,'chunks':len(d.chunks)}

@app.delete('/api/knowledge/{id}')
def knowledge_delete(id:str,db:Session=Depends(db_session),user:User=Depends(admin_or_403)):
    d=db.get(KnowledgeDocument,id)
    if not d:raise HTTPException(404,'Referência não encontrada.')
    remove_document(db,d);return {'ok':True}

@app.get('/api/templates/modelo-original/docx')
def download_original_template(user=Depends(user_or_401)):
    if not REFERENCE_DOCX.is_file():
        raise HTTPException(404,'Modelo original não encontrado.')
    return FileResponse(REFERENCE_DOCX,media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',filename='Modelo_Original_Evidencia.docx')

@app.get('/api/templates')
def templates(db:Session=Depends(db_session),user=Depends(user_or_401)):
    return [{'id':t.id,'name':t.name,'subtitle':t.subtitle,'institution':t.institution,'color':t.color,'footer':t.footer,'layout':t.layout} for t in db.query(DocumentTemplate).order_by(DocumentTemplate.name).all()]

class TemplateInput(BaseModel):
    name:str=Field(min_length=2,max_length=200)
    layout:str='reference'
    subtitle:str='RELATÓRIO DE EVIDÊNCIA'
    institution:str=''
    color:str='#125e78'
    footer:str='Documento institucional'
@app.post('/api/templates')
def template_create(data:TemplateInput,db:Session=Depends(db_session),user=Depends(admin_or_403)):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',data.color):raise HTTPException(422,'Cor inválida.')
    if data.layout not in ('reference','institutional'):raise HTTPException(422,'Formato do modelo inválido.')
    t=DocumentTemplate(**data.model_dump());db.add(t);db.commit();return {'id':t.id}
@app.put('/api/templates/{id}')
def template_update(id:str,data:TemplateInput,db:Session=Depends(db_session),user=Depends(admin_or_403)):
    t=db.get(DocumentTemplate,id)
    if not t:raise HTTPException(404,'Modelo não encontrado.')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',data.color):raise HTTPException(422,'Cor inválida.')
    if data.layout not in ('reference','institutional'):raise HTTPException(422,'Formato do modelo inválido.')
    for k,v in data.model_dump().items():setattr(t,k,v)
    db.commit();return {'ok':True}

@app.get('/api/documents')
def documents_list(db:Session=Depends(db_session),user=Depends(user_or_401)):
    ds=db.query(GeneratedDocument,Activity.title).join(Activity,GeneratedDocument.activity_id==Activity.id).order_by(GeneratedDocument.created_at.desc()).limit(300).all()
    return [{'id':d.id,'activity_id':d.activity_id,'activity_title':title,'format':d.format,'filename':d.filename,'created_at':iso(d.created_at)} for d,title in ds]

class GenerateRequest(BaseModel):
    format:str='docx'
    template_id:str|None=None

@app.post('/api/activities/{activity_id}/generate')
def generate_document(activity_id:str,data:GenerateRequest,db:Session=Depends(db_session),user:User=Depends(user_or_401)):
    a=get_activity(db,activity_id)
    if data.format not in ['docx','pdf']:raise HTTPException(422,'Formato inválido.')
    if a.status!='approved':raise HTTPException(409,'Revise e aprove a atividade antes de gerar o documento.')
    if not a.title or not a.description or not a.objective or not a.results:raise HTTPException(422,'Preencha título, descrição, objetivo e resultados.')
    t=db.get(DocumentTemplate,data.template_id) if data.template_id else db.query(DocumentTemplate).filter_by(layout='reference').first()
    if not t:raise HTTPException(422,'Modelo não encontrado.')
    name=f'{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{secrets.token_hex(5)}.{data.format}'
    target=DATA_DIR/'documents'/name
    try:
        # O modelo aprovado continua intacto; materializa fotos temporárias do banco.
        for group in a.groups:
            for photo in group.photos:
                if photo.blob is not None:
                    (DATA_DIR/'uploads'/photo.filename).write_bytes(photo.blob)
        if data.format=='docx':create_docx(a,t,target)
        else:create_pdf(a,t,target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(500,'Erro ao gerar documento: '+str(exc)[:200])
    d=GeneratedDocument(activity_id=a.id,filename=name,format=data.format,template_id=t.id,created_by=user.id,blob=target.read_bytes())
    db.add(d);audit(db,a.id,user,'document_generated',data.format);db.commit()
    return {'id':d.id,'filename':name,'download':f'/api/documents/{d.id}/download'}

@app.get('/api/documents/{document_id}/download')
def download_document(document_id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    d=db.get(GeneratedDocument,document_id)
    if not d:raise HTTPException(404,'Documento não encontrado.')
    target=DATA_DIR/'documents'/d.filename
    med='application/vnd.openxmlformats-officedocument.wordprocessingml.document' if d.format=='docx' else 'application/pdf'
    filename=('evidencia_'+d.activity_id[:8]+'.'+d.format)
    if d.blob is not None:
        return Response(content=d.blob,media_type=med,headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    if not target.is_file(): raise HTTPException(404,'Arquivo indisponível.')
    return FileResponse(target,filename=filename,media_type=med)

@app.get('/api/activities/{activity_id}/history')
def history(activity_id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    get_activity(db,activity_id)
    out=[]
    for row in db.query(AuditLog).filter_by(activity_id=activity_id).order_by(AuditLog.timestamp.desc()).limit(100).all():
        out.append({'id':row.id,'action':row.action,'detail':row.detail,'timestamp':iso(row.timestamp)})
    return out

class VoiceInput(BaseModel):
    text:str=Field(min_length=5,max_length=16000)
@app.post('/api/ai/interpret')
def ai_interpret(data:VoiceInput,db:Session=Depends(db_session),user=Depends(user_or_401)):
    try:return interpret_voice(data.text,db)
    except ValueError as exc:raise HTTPException(502,str(exc))

@app.post('/api/activities/{activity_id}/ai/refine')
def ai_refine(activity_id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    a=get_activity(db,activity_id)
    try:return refine_activity(a,db)
    except ValueError as exc:raise HTTPException(502,str(exc))

@app.post('/api/activities/{activity_id}/ai/photos')
def ai_photos(activity_id:str,db:Session=Depends(db_session),user=Depends(user_or_401)):
    a=get_activity(db,activity_id)
    try:return describe_photo_groups(a)
    except ValueError as exc:raise HTTPException(502,str(exc))
