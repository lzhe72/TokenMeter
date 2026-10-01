"""Exercise actual owned services/SQLite; no UI success is inferred here."""
import json
from pathlib import Path
import sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import granular_e2e as runner
import local_e2e as base
import bootstrap_sqlite as bootstrap
import pytest
fixtures=base.module('runtime_fixture_accounts','tests/server/fixtures.py')

@pytest.mark.parametrize('case_id',['TC-TM001-LOGIN-17#A','TC-TM001-PASSWORD-09#B','TC-TM001-UPDATE-05#SHA'])
def test_variant_fixture_is_migrated_and_readable_through_readonly_sqlite(tmp_path,case_id):
    private=tmp_path/runner.private_case_name(case_id);private.mkdir()
    out=tmp_path/'evidence';out.mkdir()
    database,*_=runner.prepared_database({'id':case_id},private,out,bootstrap,fixtures)
    snapshot=base.safe_snapshot_database(database,case_id,'variant-regression')
    assert len(snapshot['users'])==4
    assert {u['username'] for u in snapshot['users']}=={'test-admin','test-alice','test-bob','test-disabled'}
    assert '#' not in str(database)

def test_clock_dependency_expires_real_session_without_editing_database(tmp_path):
    private=tmp_path/'private';private.mkdir();out=tmp_path/'evidence';out.mkdir()
    database,*_=runner.prepared_database({'id':'TC-TM001-SESSION-07'},private,out,bootstrap,fixtures)
    clock=private/'clock.txt';clock.write_text('1700000000')
    service=base.Service(database,private,clock_file=clock)
    try:
        req=Request(service.url+'/v1/auth/login',data=json.dumps({'username':'test-alice','password':'TEST-ONLY-alice-42!'}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as response: session=json.load(response)
        auth={'Authorization':'Bearer '+session['access_token']}
        clock.write_text(str(1700000000+30*86400-1))
        with urlopen(Request(service.url+'/v1/me',headers=auth)) as response:assert response.status==200
        clock.write_text(str(1700000000+30*86400))
        try:urlopen(Request(service.url+'/v1/me',headers=auth));raise AssertionError('Expired token accepted')
        except HTTPError as error:assert error.code==401
    finally:assert service.close()

def test_restart_keeps_owned_listener_and_database(tmp_path):
    private=tmp_path/'private';private.mkdir();out=tmp_path/'evidence';out.mkdir()
    database,*_=runner.prepared_database({'id':'TC-TM001-ADMIN-05#CONCURRENT'},private,out,bootstrap,fixtures)
    snapshot=base.safe_snapshot_database(database,'TC-TM001-ADMIN-05','fixture')
    assert len(snapshot['users'])==5
    assert sum(user['role']=='admin' for user in snapshot['users'])==2
    service=base.Service(database,private)
    try:
        old=service.url;result=service.restart()
        assert result['same_origin'] and result['health']==200 and result['old_pid']!=result['new_pid']
        assert service.url==old
        assert snapshot==base.safe_snapshot_database(database,'TC-TM001-ADMIN-05','fixture')
    finally:assert service.close()

def test_owned_service_clock_enforces_299_and_300_second_rate_limit_boundary(tmp_path):
    private=tmp_path/'limit';private.mkdir();out=tmp_path/'evidence';out.mkdir()
    database,*_=runner.prepared_database({'id':'TC-TM001-LOGIN-16'},private,out,bootstrap,fixtures)
    clock=private/'clock.txt';clock.write_text('1700000000')
    service=base.Service(database,private,clock_file=clock)
    def login(password):
        request=Request(service.url+'/v1/auth/login',data=json.dumps({'username':'test-alice','password':password}).encode(),headers={'Content-Type':'application/json'})
        try:
            with urlopen(request) as response:return response.status
        except HTTPError as error:return error.code
    try:
        assert [login('incorrect') for _ in range(5)]==[401]*5
        clock.write_text('1700000299');assert login('TEST-ONLY-alice-42!')==429
        clock.write_text('1700000300');assert login('TEST-ONLY-alice-42!')==200
    finally:assert service.close()
