import os, tempfile
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(suffix='.db')
os.environ['JWT_SECRET']='test-secret-value-at-least-32-characters'
os.environ['ADMIN_PASSWORD']='test-admin-password'
os.environ['ADMIN_EMAIL']='admin@example.com'
from fastapi.testclient import TestClient
from main import app, Base, engine
Base.metadata.create_all(engine)

def test_workflow_and_permissions():
    with TestClient(app) as c:
        a=c.post('/auth/login',json={'email':'admin@example.com','password':'test-admin-password'}).json()['access_token']
        ah={'Authorization':'Bearer '+a}
        for name in ['Um','Dois']:
            assert c.post('/users',headers=ah,json={'name':name,'email':name+'@example.com','password':'password-123456'}).status_code==201
        bh={'Authorization':'Bearer '+c.post('/auth/login',json={'email':'Um@example.com','password':'password-123456'}).json()['access_token']}
        ch={'Authorization':'Bearer '+c.post('/auth/login',json={'email':'Dois@example.com','password':'password-123456'}).json()['access_token']}
        def add(kind,name,**kw):
            r=c.post('/catalog/'+kind,headers=ah,json={'name':name,**kw}); assert r.status_code==201; return r.json()['id']
        client=add('clients','Cliente'); site=add('sites','Obra',client_id=client); pump=add('pumps','Bomba'); helper=add('helpers','Ajudante')
        data=dict(client_id=client,site_id=site,pump_id=pump,helper_id=helper,start='2026-10-04T08:00:00+01:00',end='2026-10-04T12:00:00+01:00',pause_minutes=30,concrete_m3='25.50',line_m='40',origin='Estaleiro',destination='Obra B',notes='Teste')
        assert c.post('/catalog/clients',headers=bh,json={'name':'Intruso'}).status_code==403
        assert c.get('/reports',headers=bh).status_code==403
        assert c.get('/reports.csv',headers=bh).status_code==403
        r=c.post('/entries',headers=bh,json=data); assert r.status_code==201,r.text
        entry=r.json(); id=entry['id']; assert entry['hours']==3.5
        assert c.get('/entries',headers=ch).json()==[]
        assert c.put(f'/entries/{id}',headers=ch,json={**data,'revision':1}).status_code==404
        assert c.post('/entries',headers=bh,json=data).status_code==409
        assert c.post('/entries',headers=ch,json=data).status_code==409
        second={**data,'start':'2026-10-04T13:00:00+01:00','end':'2026-10-04T16:00:00+01:00'}
        assert c.post('/entries',headers=bh,json=second).status_code==201
        assert c.post('/entries',headers=bh,json={**second,'end':second['start']}).status_code==422
        assert c.post(f'/entries/{id}/submit?revision=1',headers=bh).status_code==200
        assert c.put(f'/entries/{id}',headers=bh,json={**data,'revision':2}).status_code==409
        assert c.post(f'/entries/{id}/review',headers=ah,json={'status':'returned','note':'Corrigir','revision':2}).status_code==200
        assert c.put(f'/entries/{id}',headers=bh,json={**data,'revision':1}).status_code==409
        assert c.put(f'/entries/{id}',headers=bh,json={**data,'revision':3}).status_code==200
        assert c.post(f'/entries/{id}/submit?revision=4',headers=bh).status_code==200
        assert c.post(f'/entries/{id}/review',headers=ah,json={'status':'approved','revision':5}).status_code==200
        assert c.put(f'/entries/{id}',headers=ah,json={**data,'revision':6}).status_code==409
        totals=c.get('/reports',headers=ah).json()['totals']; assert totals['hours']==3.5 and totals['services']==1
        assert '25.50' in c.get('/reports.csv',headers=ah).text
        assert len(c.get(f'/entries/{id}/history',headers=ah).json())==6
        assert c.get(f'/entries/{id}/history',headers=bh).status_code==403
        other=add('clients','Outro')
        assert c.post('/entries',headers=bh,json={**second,'client_id':other}).status_code==422
        assert c.patch('/users/2/active?active=false',headers=ah).status_code==200
        assert c.get('/entries',headers=bh).status_code==401
