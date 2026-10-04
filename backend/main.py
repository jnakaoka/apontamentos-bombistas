import base64, csv, hashlib, hmac, io, os, secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from contextlib import asynccontextmanager
import jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import create_engine, String, Integer, Boolean, Numeric, DateTime, Text, ForeignKey, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(150))
    email: Mapped[str]=mapped_column(String(254),unique=True)
    password: Mapped[str]=mapped_column(Text)
    role: Mapped[str]=mapped_column(String(20))
    active: Mapped[bool]=mapped_column(default=True)
class Catalog(Base):
    __tablename__='catalog'
    id: Mapped[int]=mapped_column(primary_key=True)
    kind: Mapped[str]=mapped_column(String(20))
    name: Mapped[str]=mapped_column(String(200))
    address: Mapped[str]=mapped_column(String(500),default='')
    client_id: Mapped[int|None]=mapped_column(ForeignKey('catalog.id'),nullable=True)
    active: Mapped[bool]=mapped_column(default=True)
class Entry(Base):
    __tablename__='entries'
    id: Mapped[int]=mapped_column(primary_key=True)
    operator_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    client_id: Mapped[int]=mapped_column(ForeignKey('catalog.id'))
    site_id: Mapped[int]=mapped_column(ForeignKey('catalog.id'))
    pump_id: Mapped[int]=mapped_column(ForeignKey('catalog.id'))
    helper_id: Mapped[int|None]=mapped_column(ForeignKey('catalog.id'),nullable=True)
    start: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    end: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    pause_minutes: Mapped[int]=mapped_column(Integer,default=0)
    concrete_m3: Mapped[Decimal]=mapped_column(Numeric(12,2))
    line_m: Mapped[Decimal]=mapped_column(Numeric(12,2))
    origin: Mapped[str]=mapped_column(String(500))
    destination: Mapped[str]=mapped_column(String(500))
    notes: Mapped[str]=mapped_column(Text,default='')
    status: Mapped[str]=mapped_column(String(20),default='draft')
    revision: Mapped[int]=mapped_column(Integer,default=1)
    review_note: Mapped[str]=mapped_column(Text,default='')
class Audit(Base):
    __tablename__='audit'
    id: Mapped[int]=mapped_column(primary_key=True)
    entry_id: Mapped[int]=mapped_column(ForeignKey('entries.id'))
    actor_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(Text)
    at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

engine=create_engine(os.getenv('DATABASE_URL','sqlite:///./bombistas.db'),**({'connect_args':{'check_same_thread':False}} if os.getenv('DATABASE_URL','sqlite:').startswith('sqlite:') else {}))
Sessions=sessionmaker(engine)
SECRET=os.getenv('JWT_SECRET','')

def hash_password(value):
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',value.encode(),salt.encode(),600000).hex()
    return salt+':'+digest

def check_password(value,encoded):
    salt,digest=encoded.split(':')
    return hmac.compare_digest(digest,hashlib.pbkdf2_hmac('sha256',value.encode(),salt.encode(),600000).hex())

@asynccontextmanager
async def lifespan(app):
    if len(SECRET)<32: raise RuntimeError('JWT_SECRET deve ter pelo menos 32 caracteres.')
    with Sessions() as db:
        if not db.scalar(select(User.id)):
            password=os.getenv('ADMIN_PASSWORD','')
            if len(password)<12: raise RuntimeError('Defina ADMIN_PASSWORD com pelo menos 12 caracteres.')
            db.add(User(name='Administrador',email=os.getenv('ADMIN_EMAIL','admin@example.com').strip().lower(),password=hash_password(password),role='admin'))
            db.commit()
    yield
app=FastAPI(title='Apontamentos de Bombistas',lifespan=lifespan)
bearer=HTTPBearer()
def session():
    with Sessions() as db: yield db

def current(auth:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(session)):
    try:
        payload=jwt.decode(auth.credentials,SECRET,algorithms=['HS256'])
        user=db.get(User,int(payload['sub']))
    except (jwt.PyJWTError,ValueError,KeyError): raise HTTPException(401,'Sessão inválida ou expirada.')
    if not user or not user.active: raise HTTPException(401,'Utilizador inativo.')
    return user

def admin(user:User=Depends(current)):
    if user.role!='admin': raise HTTPException(403,'Acesso exclusivo do administrador.')
    return user
class Login(BaseModel):
    email:str
    password:str
class UserInput(BaseModel):
    name:str=Field(min_length=1,max_length=150)
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=12,max_length=200)
    role:Literal['admin','bombista']='bombista'
class CatalogInput(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    address:str=Field(default='',max_length=500)
    client_id:int|None=None
    active:bool=True
class EntryInput(BaseModel):
    client_id:int
    site_id:int
    pump_id:int
    helper_id:int|None=None
    start:datetime
    end:datetime
    pause_minutes:int=Field(default=0,ge=0)
    concrete_m3:Decimal=Field(ge=0,le=9999999999,decimal_places=2)
    line_m:Decimal=Field(ge=0,le=9999999999,decimal_places=2)
    origin:str=Field(min_length=1,max_length=500)
    destination:str=Field(min_length=1,max_length=500)
    notes:str=Field(default='',max_length=5000)
    @model_validator(mode='after')
    def times(self):
        if self.start.tzinfo is None or self.end.tzinfo is None: raise ValueError('Horários devem incluir fuso horário.')
        self.start=self.start.astimezone(timezone.utc); self.end=self.end.astimezone(timezone.utc)
        if self.end<=self.start: raise ValueError('Fim deve ser posterior ao início.')
        if self.pause_minutes*60 >= (self.end-self.start).total_seconds(): raise ValueError('Pausa deve ser inferior à duração do serviço.')
        if not self.origin.strip() or not self.destination.strip(): raise ValueError('Preencha origem e destino.')
        return self
class EditInput(EntryInput):
    revision:int
class Review(BaseModel):
    status:Literal['approved','returned']
    note:str=Field(default='',max_length=2000)
    revision:int

def user_out(u): return dict(id=u.id,name=u.name,email=u.email,role=u.role,active=u.active)
def catalog_out(c): return dict(id=c.id,kind=c.kind,name=c.name,address=c.address,client_id=c.client_id,active=c.active)
def utc(d): return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
def entry_out(e,db):
    result={c.name:getattr(e,c.name) for c in Entry.__table__.columns}
    result['start']=utc(e.start); result['end']=utc(e.end)
    result['hours']=round((utc(e.end)-utc(e.start)).total_seconds()/3600-e.pause_minutes/60,2)
    result['operator']=db.get(User,e.operator_id).name
    for key in ['client','site','pump','helper']:
        item=db.get(Catalog,getattr(e,key+'_id')) if getattr(e,key+'_id') else None
        result[key]=item.name if item else ''
    return result

def owned(id,db,user):
    e=db.get(Entry,id,with_for_update=True)
    if not e or (user.role!='admin' and e.operator_id!=user.id): raise HTTPException(404,'Apontamento não encontrado.')
    return e

def validate_catalog(data,db):
    for kind,key in [('clients','client_id'),('sites','site_id'),('pumps','pump_id'),('helpers','helper_id')]:
        value=getattr(data,key)
        if value is None and kind=='helpers': continue
        item=db.get(Catalog,value)
        if not item or item.kind!=kind or not item.active: raise HTTPException(422,f'Cadastro inválido ou inativo: {kind}.')
    if db.get(Catalog,data.site_id).client_id!=data.client_id: raise HTTPException(422,'A obra não pertence ao cliente.')

def overlap(data,db,operator_id,exclude=None):
    if db.bind.dialect.name=="postgresql": db.execute(text("SELECT pg_advisory_xact_lock(7319401)"))
    candidates=db.scalars(select(Entry).where(Entry.start<data.end,Entry.end>data.start)).all()
    for other in candidates:
        if other.id==exclude: continue
        if other.operator_id==operator_id or other.pump_id==data.pump_id or (data.helper_id and other.helper_id==data.helper_id):
            raise HTTPException(409,'Horário sobreposto para bombista, bomba ou ajudante.')

def audit(db,e,user,action): db.add(Audit(entry_id=e.id,actor_id=user.id,action=action))
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/auth/login')
def login(data:Login,db:Session=Depends(session)):
    u=db.scalar(select(User).where(User.email==data.email.strip().lower()))
    if not u or not u.active or not check_password(data.password,u.password): raise HTTPException(401,'Email ou senha incorretos.')
    token=jwt.encode({'sub':str(u.id),'exp':datetime.now(timezone.utc)+timedelta(hours=8)},SECRET,algorithm='HS256')
    return {'access_token':token,'user':user_out(u)}
@app.get('/auth/me')
def me(user:User=Depends(current)): return user_out(user)
@app.get('/users')
def users(user:User=Depends(admin),db:Session=Depends(session)): return [user_out(u) for u in db.scalars(select(User))]
@app.post('/users',status_code=201)
def add_user(data:UserInput,user:User=Depends(admin),db:Session=Depends(session)):
    email=data.email.strip().lower()
    if '@' not in email or db.scalar(select(User.id).where(User.email==email)): raise HTTPException(422,'Email inválido ou já cadastrado.')
    u=User(name=data.name,email=email,password=hash_password(data.password),role=data.role); db.add(u); db.commit(); return user_out(u)
@app.patch('/users/{id}/active')
def user_active(id:int,active:bool,user:User=Depends(admin),db:Session=Depends(session)):
    u=db.get(User,id)
    if not u: raise HTTPException(404,'Utilizador não encontrado.')
    if id==user.id and not active: raise HTTPException(422,'Não pode desativar a própria conta.')
    u.active=active; db.commit(); return user_out(u)

KINDS={'clients','sites','pumps','helpers'}
@app.get('/catalog/{kind}')
def catalogs(kind:str,include_inactive:bool=False,user:User=Depends(current),db:Session=Depends(session)):
    if kind not in KINDS: raise HTTPException(404,'Cadastro desconhecido.')
    q=select(Catalog).where(Catalog.kind==kind)
    if not (user.role=='admin' and include_inactive): q=q.where(Catalog.active==True)
    return [catalog_out(c) for c in db.scalars(q.order_by(Catalog.name))]

def catalog_validate(kind,data,db):
    if kind not in KINDS: raise HTTPException(404,'Cadastro desconhecido.')
    if not data.name.strip(): raise HTTPException(422,'Nome obrigatório.')
    if kind=='sites':
        c=db.get(Catalog,data.client_id) if data.client_id else None
        if not c or c.kind!='clients' or not c.active: raise HTTPException(422,'Selecione um cliente ativo.')
    elif data.client_id is not None: raise HTTPException(422,'Cliente só se aplica a obras.')
@app.post('/catalog/{kind}',status_code=201)
def add_catalog(kind:str,data:CatalogInput,user:User=Depends(admin),db:Session=Depends(session)):
    catalog_validate(kind,data,db)
    c=Catalog(kind=kind,**data.model_dump()); db.add(c); db.commit(); return catalog_out(c)
@app.put('/catalog/{kind}/{id}')
def edit_catalog(kind:str,id:int,data:CatalogInput,user:User=Depends(admin),db:Session=Depends(session)):
    catalog_validate(kind,data,db); c=db.get(Catalog,id)
    if not c or c.kind!=kind: raise HTTPException(404,'Cadastro não encontrado.')
    if kind=='sites' and c.client_id!=data.client_id and db.scalar(select(Entry.id).where(Entry.site_id==id)):
        raise HTTPException(409,'Obra com apontamentos não pode mudar de cliente.')
    for k,v in data.model_dump().items(): setattr(c,k,v)
    db.commit(); return catalog_out(c)
@app.get('/entries')
def entries(date_from:datetime|None=None,date_to:datetime|None=None,operator_id:int|None=None,client_id:int|None=None,site_id:int|None=None,pump_id:int|None=None,user:User=Depends(current),db:Session=Depends(session)):
    q=select(Entry)
    if user.role!='admin': q=q.where(Entry.operator_id==user.id)
    elif operator_id: q=q.where(Entry.operator_id==operator_id)
    if date_from: q=q.where(Entry.start>=date_from)
    if date_to: q=q.where(Entry.start<date_to)
    for field,value in [('client_id',client_id),('site_id',site_id),('pump_id',pump_id)]:
        if value: q=q.where(getattr(Entry,field)==value)
    return [entry_out(e,db) for e in db.scalars(q.order_by(Entry.start.desc()))]
@app.post('/entries',status_code=201)
def add_entry(data:EntryInput,user:User=Depends(current),db:Session=Depends(session)):
    validate_catalog(data,db); overlap(data,db,user.id)
    e=Entry(operator_id=user.id,**data.model_dump()); db.add(e); db.flush(); audit(db,e,user,'Criado'); db.commit(); return entry_out(e,db)
@app.put('/entries/{id}')
def edit_entry(id:int,data:EditInput,user:User=Depends(current),db:Session=Depends(session)):
    e=owned(id,db,user)
    if e.status=='approved' or (user.role!='admin' and e.status not in ('draft','returned')): raise HTTPException(409,'Apontamento não permite edição.')
    if e.revision!=data.revision: raise HTTPException(409,'Apontamento alterado. Atualize a página.')
    validate_catalog(data,db); overlap(data,db,e.operator_id,id)
    before=str(entry_out(e,db))
    for k,v in data.model_dump(exclude={'revision'}).items(): setattr(e,k,v)
    e.revision+=1; audit(db,e,user,'Editado. Antes: '+before); db.commit(); return entry_out(e,db)
@app.post('/entries/{id}/submit')
def submit(id:int,revision:int,user:User=Depends(current),db:Session=Depends(session)):
    e=owned(id,db,user)
    if e.revision!=revision or e.status not in ('draft','returned'): raise HTTPException(409,'Estado ou versão inválidos.')
    e.status='submitted'; e.revision+=1; audit(db,e,user,'Submetido'); db.commit(); return entry_out(e,db)
@app.post('/entries/{id}/review')
def review(id:int,data:Review,user:User=Depends(admin),db:Session=Depends(session)):
    e=owned(id,db,user)
    if e.revision!=data.revision or e.status!='submitted': raise HTTPException(409,'Estado ou versão inválidos.')
    if data.status=='returned' and not data.note.strip(): raise HTTPException(422,'Informe o motivo da devolução.')
    e.status=data.status; e.review_note=data.note; e.revision+=1; audit(db,e,user,data.status+': '+data.note); db.commit(); return entry_out(e,db)
@app.get('/entries/{id}/history')
def history(id:int,user:User=Depends(admin),db:Session=Depends(session)):
    owned(id,db,user)
    return [dict(at=a.at,actor=db.get(User,a.actor_id).name,action=a.action) for a in db.scalars(select(Audit).where(Audit.entry_id==id).order_by(Audit.id))]
@app.get('/reports')
def reports(date_from:datetime|None=None,date_to:datetime|None=None,operator_id:int|None=None,client_id:int|None=None,site_id:int|None=None,pump_id:int|None=None,user:User=Depends(admin),db:Session=Depends(session)):
    rows=entries(date_from,date_to,operator_id,client_id,site_id,pump_id,user,db)
    rows=[r for r in rows if r['status']=='approved']
    return {'rows':rows,'totals':{'services':len(rows),'hours':round(sum(r['hours'] for r in rows),2),'concrete_m3':sum(r['concrete_m3'] for r in rows),'line_m':sum(r['line_m'] for r in rows)}}
@app.get('/reports.csv')
def export(date_from:datetime|None=None,date_to:datetime|None=None,operator_id:int|None=None,client_id:int|None=None,site_id:int|None=None,pump_id:int|None=None,user:User=Depends(admin),db:Session=Depends(session)):
    rows=reports(date_from,date_to,operator_id,client_id,site_id,pump_id,user,db)['rows']; buffer=io.StringIO(); writer=csv.writer(buffer,delimiter=';')
    fields=['id','start','operator','client','site','pump','helper','hours','concrete_m3','line_m','origin','destination','notes']
    writer.writerow(fields)
    for r in rows:
        values=[]
        for f in fields:
            value=str(r[f]); values.append("'"+value if value.startswith(('=','+','-','@','\t','\r')) else value)
        writer.writerow(values)
    return Response('\ufeff'+buffer.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=apontamentos.csv'})
