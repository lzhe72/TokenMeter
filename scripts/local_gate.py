#!/usr/bin/env python3
"""Execute a fresh Electron package regression and re-read its raw evidence.

Only this parent gate issues a local passport. Same-uid files are evidence for
this internal workflow, not an independent tamper-proof attestation service.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import plistlib
import re
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts import granular_update_validation_fixture as signing_fixture

CASES=[f'E2E-TM001-{i:03d}' for i in (1,2,3,5,6,4)]
AUX_PLACEHOLDER_IDS=frozenset({
    *(f'TC-TM001-UI-{i:02d}' for i in (1,2,3)),
    *(f'TC-TM001-CATALOG-{i:02d}' for i in (1,2,3)),
    *(f'TC-TM001-RECORDS-{i:02d}' for i in (1,2)),
    *(f'TC-TM001-GATE-{i:02d}' for i in (1,2,3)),
})
MAX_CHILD_LOG_BYTES=32*1024*1024
MAX_CHILD_LINE_BYTES=1024*1024
REQUIRED_STEPS={
 'E2E-TM001-001':{'default_routes','forced_password','identity','auto_restore','logout_revokes','auto_off'},
 'E2E-TM001-002':{'login_errors','member_identity','admin_hidden','member_forbidden'},
 'E2E-TM001-003':{'admin_restored_identity','admin_restored_role','admin_session_verified',
                  'admin_session_matches_ui','admin_actions','audit','reset_revokes','disable_revokes'},
 'E2E-TM001-005':{'bootstrap_forced','admin_only','password_persists','restore'},
 'E2E-TM001-006':{'default_routes','atomic_config','origin_isolation','config_validation','restore_defaults'},
 'E2E-TM001-004':{'auto_discovery','forbidden','redirect','invalid_signature','valid_install','self_relaunch','identity_restored',
                  'new_process_profile_files','new_process_no_default_profile'},
}

class Invalid(ValueError): pass
class Blocked(Invalid): pass

def require(value, message):
    if not value: raise Invalid(message)

def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):digest.update(chunk)
    return digest.hexdigest()

def read_json(path):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError as e:raise Blocked(f'Missing {Path(path).name}') from e
    except (OSError,ValueError) as e:raise Invalid(f'Invalid JSON: {Path(path).name}') from e

def safe_path(base, relative, directory=False):
    require(isinstance(relative,str) and relative and '\\' not in relative, 'Invalid artifact path')
    p=PurePosixPath(relative)
    require(not p.is_absolute() and not any(x in ('','.','..') for x in relative.split('/')), 'Artifact escaped owner')
    base=Path(base).absolute()
    require(base.is_dir() and all(not x.is_symlink() for x in [base,*base.parents]),'Invalid artifact root')
    result=base
    for part in p.parts:
        result=result/part
        require(not result.is_symlink(), 'Symlink artifact')
    if not result.exists():raise Blocked(f'Missing artifact {relative}')
    require(result.is_dir() if directory else result.is_file(), 'Wrong artifact type')
    if not directory:require(result.stat().st_size>0, 'Empty evidence')
    return result

def checked_file(base, descriptor):
    require(isinstance(descriptor,dict), 'Missing artifact descriptor')
    path=safe_path(base,descriptor.get('path'))
    require(isinstance(descriptor.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',descriptor['sha256']), 'Invalid digest')
    require(sha256(path)==descriptor['sha256'], f'Artifact changed: {path.name}')
    if 'bytes' in descriptor:require(path.stat().st_size==descriptor['bytes'],'Artifact size changed')
    return path

def checked_bytes(base, descriptor):
    require(isinstance(descriptor,dict),'Missing artifact descriptor')
    path=safe_path(base,descriptor.get('path'))
    data=path.read_bytes()
    require(data and hashlib.sha256(data).hexdigest()==descriptor.get('sha256'),'Evidence bytes changed')
    if 'bytes' in descriptor:require(len(data)==descriptor['bytes'],'Evidence size changed')
    return data

def checked_json(base, descriptor):
    try:return json.loads(checked_bytes(base,descriptor))
    except (ValueError,UnicodeError) as e:raise Invalid('Invalid evidence JSON') from e

def verify_png(base, descriptor):
    data=checked_bytes(base,descriptor)
    require(data[:8]==b'\x89PNG\r\n\x1a\n' and len(data)>45 and data[12:16]==b'IHDR','Invalid screenshot PNG')
    width,height=struct.unpack('>II',data[16:24])
    require(0<width<=16384 and 0<height<=16384 and data[-8:-4]==b'IEND','Invalid screenshot dimensions/end')

def verify_trace(base, descriptor):
    try:
        with zipfile.ZipFile(io.BytesIO(checked_bytes(base,descriptor))) as archive:
            members=archive.infolist()
            require(0<len(members)<10000 and sum(m.file_size for m in members)<500_000_000,'Invalid trace archive size')
            require(archive.testzip() is None,'Corrupt trace archive')
            traces=[m for m in members if m.filename.endswith('.trace')]
            require(traces,'Trace archive has no Playwright events')
            events=[json.loads(line) for m in traces for line in archive.read(m).splitlines() if line.strip()]
            require(any(e.get('type')=='context-options' for e in events)
                    and any(e.get('type') in ('before','after') for e in events),'No recorded Playwright context/actions')
    except (zipfile.BadZipFile,ValueError,UnicodeError) as e:raise Invalid('Invalid Playwright trace archive') from e

def verify_restored_databases(base, restored):
    dumps=[]
    for key in ('backup','restored'):
        path=checked_file(base,restored.get(key))
        require(restored[key]['sha256']==restored.get(key+'_sha256'),'Restore digest differs')
        try:
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                require(db.execute('PRAGMA integrity_check').fetchone()==('ok',),'Corrupt restored database')
                require(db.execute('SELECT version_num FROM alembic_version').fetchall()==[('0001',)],'Restore schema differs')
                require(db.execute('SELECT username,role,is_active,must_change_password FROM users').fetchall()==[('admin','admin',1,1)],'Restored fixture is not the initial synthetic admin')
                require(db.execute('SELECT count(*) FROM sessions').fetchone()==(0,),'Restored fixture contains sessions')
                dumps.append(list(db.iterdump()))
        except sqlite3.Error as e:raise Invalid('Unreadable restored SQLite') from e
        checked_file(base,restored[key])
    require(dumps[0]==dumps[1],'Restored rows differ from backup')

def timestamp(value):
    if type(value) in (int,float):return value
    require(isinstance(value,str),'Invalid timestamp')
    value=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(value.tzinfo is not None, 'Timestamp without timezone')
    return value.timestamp()

def time_range(record,*,not_before,now=None):
    start,end=timestamp(record['started_at']),timestamp(record['finished_at'])
    require(not_before<=start<=end<=(time.time() if now is None else now)+5,'Stale, future or reversed evidence time')
    return start,end

def verify_playwright(raw,case_id,*,run_id=None,candidate_sha=None,start=None,end=None):
    require(isinstance(raw,dict) and not raw.get('errors'),'Playwright global failure')
    specs=[]
    def visit(suite):
        require(isinstance(suite,dict),'Invalid suite')
        specs.extend(suite.get('specs',[]))
        for nested in suite.get('suites',[]):visit(nested)
    for suite in raw.get('suites',[]):visit(suite)
    require(len(specs)==1,'Exactly one raw case required per suite')
    spec=specs[0]
    require(re.findall(r'E2E-TM\d{3}-\d{3}',spec.get('title',''))==[case_id], 'Raw case identity mismatch')
    require(spec.get('ok') is True and len(spec.get('tests',[]))==1,'Raw case failed or duplicated')
    test=spec['tests'][0]
    require(test.get('expectedStatus')=='passed' and test.get('status')=='expected','Unexpected/expected-failure case')
    require(len(test.get('results',[]))==1,'Multiple attempts or no attempt')
    result=test['results'][0]
    require(result.get('status')=='passed' and result.get('retry')==0 and not result.get('errors') and not result.get('error'),'Failed/skipped/retried case')
    if run_id is not None:
        metadata=raw.get('config',{}).get('metadata',{})
        require(metadata.get('run_id')==run_id and metadata.get('candidate_sha')==candidate_sha,'Foreign raw Playwright run')
        began=timestamp(result.get('startTime'))
        duration=result.get('duration')
        require(type(duration) in (int,float) and duration>=0,'Invalid test duration')
        require(start-1<=began<=began+duration/1000<=end+5,'Raw Playwright execution is stale or outside run')
    return 1

def command(args,*,cwd=ROOT):
    result=subprocess.run(args,cwd=cwd,text=True,capture_output=True,check=False)
    require(result.returncode==0,f'Command failed: {args[0]} {args[1] if len(args)>1 else ""}')
    return result.stdout.strip()

def git(*args):return command(['git',*args])

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded);return loaded

def current_cases():
    current=read_json(ROOT/'releases/current.json')['release_id']
    release=read_json(ROOT/'releases'/current/'00-manifest.json')
    matrix=read_json(ROOT/'tests/feature_matrix.json')
    targets=set(release['feature_ids'])
    cases=[c['id'] for f in matrix['features'] if f['id'] in targets or f['status']=='implemented' for c in f['cases']]
    require(len(cases)==len(set(cases)) and set(CASES).issubset(cases),'Required cases removed or duplicated')
    return current,release,cases

def verify_internal_binary_flags(app):
    magic={b'\xfe\xed\xfa\xce',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\xca\xfe\xba\xbf',b'\xbf\xba\xfe\xca'}
    count=0
    for binary in app.rglob('*'):
        if binary.is_symlink() or not binary.is_file():continue
        with binary.open('rb') as stream:header=stream.read(4)
        if header not in magic:continue
        count+=1
        details=subprocess.run(['codesign','--display','--verbose=4',str(binary)],capture_output=True,text=True,check=False)
        flags=re.search(r'flags=0x([0-9a-fA-F]+)',details.stdout+details.stderr)
        require(details.returncode==0 and flags and not (int(flags.group(1),16)&0x12000),'Internal self-signed binary unexpectedly enables runtime/library validation')
    require(count>0,'No signed Mach-O executable')

def verify_package(manifest_path, *, candidate_sha, candidate_tree):
    manifest_bytes=manifest_path.read_bytes()
    package=json.loads(manifest_bytes);base=manifest_path.parent
    require(package.get('schema_version')==2 and package.get('scope')=='final_package','Not a final Electron package')
    require(package.get('distribution_profile',package.get('profile'))=='internal','Wrong package profile')
    require(package.get('candidate_sha')==candidate_sha and package.get('candidate_tree')==candidate_tree and package.get('working_tree_dirty') is False,'Package candidate differs or is dirty')
    require(package.get('cleanup_completed') is True,'Packaging resources not restored')
    config_path=ROOT/'releases'/package['release_id']/'local-release.json'
    config=read_json(config_path)
    require(package.get('config_sha256')==sha256(config_path),'Package config changed')
    require(package.get('lock_sha256')==sha256(ROOT/'apps/desktop/package-lock.json'),'Dependency lock changed')
    require(package.get('host',{}).get('architecture')=='x86_64','Untested package architecture')
    for name in ('dmg','candidate_zip','update_zip','server_zip'):checked_file(base,package.get('artifacts',{}).get(name))
    verifier = """const c=require('node:crypto'),fs=require('node:fs');
const p=Buffer.from(process.argv[1],'base64'),s=Buffer.from(process.argv[2],'base64');
if(p.length!==32||s.length!==64)process.exit(2);
const key=c.createPublicKey({key:Buffer.concat([Buffer.from('302a300506032b6570032100','hex'),p]),format:'der',type:'spki'});
if(!c.verify(null,fs.readFileSync(process.argv[3]),key,s))process.exit(1);"""
    for name,signature in [('candidate_zip','candidate_ed_signature'),('update_zip','update_ed_signature')]:
        archive=checked_file(base,package['artifacts'][name])
        command(['node','-e',verifier,config['update_public_key'],package['signatures'][signature],str(archive)])
    tree_tool=module('local_gate_tree',ROOT/'scripts/package_release_dmg.py')
    for key,version,build in [('app','0.1.0','100'),('update_app','0.1.1','101')]:
        info=package[key]
        app=safe_path(base,info.get('relative_path',info.get('path')),directory=True)
        require(tree_tool.tree_sha256(app)==info['tree_sha256'],'Signed App bytes changed')
        require(str(info['build'])==build and info['version']==version,'Wrong App version')
        require(info.get('certificate_sha256')==config['certificate_sha256'],'Wrong signing identity')
        command(['codesign','--verify','--deep','--strict',str(app)])
        verify_internal_binary_flags(app)
        with tempfile.TemporaryDirectory(prefix='tokenmeter-gate-signature-') as scratch:
            prefix=Path(scratch)/'cert'
            command(['codesign','--display','--extract-certificates='+str(prefix),str(app)])
            require(sha256(Path(str(prefix)+'0'))==config['certificate_sha256'],'Actual signing certificate differs')
        actual_identifier=command(['plutil','-extract','CFBundleIdentifier','raw',str(app/'Contents/Info.plist')])
        require(actual_identifier==config['bundle_id'],'Wrong bundle identity')
        actual_info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
        require(actual_info.get('NSAppTransportSecurity')=={'NSExceptionDomains':{'127.0.0.1':{'NSExceptionAllowsInsecureHTTPLoads':True}}},'Unexpected transport security exceptions')
        require(actual_info.get('ElectronSquirrelPreventDowngrades') is True and actual_info.get('LSMinimumSystemVersion')=='15.0','Wrong upgrade/system policy')
        expected_resource={k:config[k] for k in ('release_id','bundle_id','api_url','update_feed_url','update_public_key','certificate_sha256')}
        expected_resource.update(candidate_sha=candidate_sha,version=version,build=build)
        require(read_json(app/'Contents/Resources/release-config.json')==expected_resource,'Actual App release defaults differ')
        icon=actual_info.get('CFBundleIconFile')
        require(isinstance(icon,str) and '/' not in icon and '\\' not in icon,'Missing product icon')
        icon_path=app/'Contents/Resources'/(icon if icon.endswith('.icns') else icon+'.icns')
        require(icon_path.is_file() and sha256(icon_path)==sha256(ROOT/'apps/desktop/resources/TokenMeter.icns'),'App uses a different or default icon')
        require(command(['lipo','-archs',str(app/'Contents/MacOS/TokenMeter')])=='x86_64','Actual App architecture differs')
        actual=command(['plutil','-extract','CFBundleVersion','raw',str(app/'Contents/Info.plist')])
        require(actual==build,'Actual App build differs')
        actual=command(['plutil','-extract','CFBundleShortVersionString','raw',str(app/'Contents/Info.plist')])
        require(actual==version,'Actual App version differs')
        requirement=info.get('designated_requirement')
        require(isinstance(requirement,str) and requirement,'Missing signing requirement')
        command(['codesign','--verify','--deep','--strict','-R','='+requirement.removeprefix('designated => '),str(app)])
    for name in ('dmg','candidate_zip','update_zip','server_zip'):checked_file(base,package['artifacts'][name])
    for key in ('app','update_app'):
        require(tree_tool.tree_sha256(safe_path(base,package[key]['relative_path'],directory=True))==package[key]['tree_sha256'],'App changed during verification')
    require(sha256(manifest_path)==hashlib.sha256(manifest_bytes).hexdigest(),'Package manifest changed during verification')
    return package

def verify_events(base,suite,run_id,start,end):
    try:events=[json.loads(line) for line in checked_bytes(base,suite.get('events')).splitlines() if line.strip()]
    except ValueError as e:raise Invalid('Invalid event stream') from e
    require(events,'Missing UI assertion events')
    for event in events:
        require(event.get('run_id')==run_id and event.get('case_id')==suite['case_id'],'Foreign assertion event')
        when=event.get('timestamp',event.get('at',event.get('utc')))
        require(start-1<=timestamp(when)<=end+1,'Event outside this run')
        require(isinstance(event.get('step'),str) and event['step'],'Unnamed assertion')
        if 'expected' in event:
            require('actual' in event and event['actual']==event['expected'],'UI assertion differs')
        if 'passed' in event:require(event['passed'] is True,'Failed assertion event')
    require(all('expected' in e and 'actual' in e and e['actual']==e['expected'] for e in events),'Missing independently compared assertion values')
    require(REQUIRED_STEPS.get(suite['case_id'],set()).issubset({e['step'] for e in events}),'Required behavior assertions missing')
    require(any(e.get('source')=='ui' for e in events),'No actual UI assertion events')
    return events

def verify_update_requests(raw,*,run_id,start,end,artifact):
    require(isinstance(raw,dict) and raw.get('run_id')==run_id and raw.get('case_id')=='E2E-TM001-004','Foreign update source evidence')
    origin=raw.get('origin')
    require(isinstance(origin,str),'Missing update source origin')
    parsed=urlsplit(origin)
    try:port=parsed.port
    except ValueError as e:raise Invalid('Invalid update source port') from e
    require(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and type(port) is int and 1024<=port<=65535
            and origin==f'http://127.0.0.1:{port}','Update source is not an owned loopback origin')
    requests=raw.get('requests')
    require(isinstance(requests,list) and requests,'Missing actual update requests')
    stages=['current','forbidden','redirect','invalid','valid']
    order=[]
    previous=start-1
    for item in requests:
        require(isinstance(item,dict) and item.get('stage') in stages,'Unknown update stage')
        index=stages.index(item['stage'])
        require(not order or index>=order[-1],'Update stages went backwards')
        order.append(index)
        when=timestamp(item.get('time'))
        require(previous<=when<=end+1,'Update request outside run or out of order');previous=when
        route=item.get('route');method=item.get('method');status=item.get('status')
        require(method in ('GET','POST') and type(status) is int,'Invalid update request')
        require(type(item.get('bytes_sent')) is int and item['bytes_sent']>=0
                and isinstance(item.get('body_sha256'),str) and re.fullmatch('[0-9a-f]{64}',item['body_sha256']),'Missing completed transfer evidence')
        if method=='POST':
            require(item['stage']!='current' and route=='/control/'+item['stage'] and status==200,'Update stage change failed')
        elif route=='/version.json':
            require(status==(204 if item['stage']=='current' else 200),'Update discovery failed')
            require(item['bytes_sent']==0 if status==204 else item['bytes_sent']>0,'Missing metadata response')
        elif route=='/redirect.zip':
            require(item['stage']=='redirect' and status==302,'Unexpected redirect transfer')
        elif route=='/update.zip':
            require(item['stage'] in ('invalid','valid') and status==200,'Forbidden or partial update download')
            require(item['bytes_sent']==artifact['bytes'] and item['body_sha256']==artifact['sha256'],'Update bytes differ or were not completely sent')
        else:
            require(route in ('/health','/observations') and status==200,'Unexpected update request route')
    require(set(order)==set(range(5)),'Update stages missing')
    for stage in stages:
        require(any(r['stage']==stage and r['method']=='GET' and r['route']=='/version.json' for r in requests),'Missing stage discovery')
        if stage!='current':
            require(any(r['stage']==stage and r['method']=='POST' and r['route']=='/control/'+stage for r in requests),'Missing owned stage transition')
    require(any(r['stage']=='redirect' and r['route']=='/redirect.zip' for r in requests),'Redirect rejection not exercised')
    for stage in ('invalid','valid'):
        require(any(r['stage']==stage and r['route']=='/update.zip' for r in requests),'Signed package transfer not exercised')

def verify_report(report_path,manifest_path,*,run_id,candidate_sha,candidate_tree,not_before,
                  parent_run_id=None,parent_report_sha256=None):
    package=verify_package(manifest_path,candidate_sha=candidate_sha,candidate_tree=candidate_tree)
    report_bytes=report_path.read_bytes()
    report=json.loads(report_bytes);base=report_path.parent
    release_id,release,expected=current_cases()
    require(report.get('schema_version')==2 and report.get('scope')=='final_package','Wrong evidence scope')
    require(report.get('run_id')==run_id and report.get('release_id')==release_id==package['release_id'],'Foreign run/release')
    if parent_run_id is not None:
        require(run_id!=parent_run_id and report.get('parent_run_id')==parent_run_id and
                report.get('parent_report_sha256')==parent_report_sha256,
                'Supplemental run is not bound to its detailed parent')
    require(report.get('distribution_profile')=='internal' and report.get('release_eligible') is False,'Runner cannot issue eligibility')
    require(report.get('source_commit')==candidate_sha and report.get('candidate_tree')==candidate_tree and report.get('working_tree_dirty') is False,'E2E source differs')
    start,end=time_range(report,not_before=not_before)
    require(report.get('state')=='PASS','Product run failed or blocked')
    require(report.get('host',{}).get('architecture')=='x86_64' and str(report['host'].get('macos','')).startswith('15.'),'Wrong host')
    proof=report.get('package',{})
    require(proof.get('manifest_sha256')==sha256(manifest_path),'E2E used another package manifest')
    require(proof.get('dmg_sha256')==package['artifacts']['dmg']['sha256'] and proof.get('app_tree_sha256')==package['app']['tree_sha256'],'E2E original package differs')
    require(str(proof.get('build'))=='100','Candidate is not stable build100')
    require(report.get('expected_cases')==expected and report.get('executed_cases')==len(expected) and report.get('passed_cases')==len(expected),'Case set/count mismatch')
    suites=report.get('suites',[])
    require(len(suites)==len(expected) and [s.get('case_id') for s in suites]==expected,'Missing/duplicate/reordered cases')
    require(report.get('cleanup_completed') is True,'Unfinished cleanup')
    cleanup=report.get('cleanup',{})
    require(all(cleanup.get(k) is True for k in ('mount','services','app_processes','profiles','installs','ports','shipit')),'Owned resources not fully cleaned')
    for suite in suites:
        require(suite.get('state')=='PASS' and suite.get('cleanup_completed') is True and suite.get('failures')==[],'Incomplete suite')
        verify_playwright(checked_json(base,suite.get('playwright_json')),suite['case_id'],run_id=run_id,candidate_sha=candidate_sha,start=start,end=end)
        events=verify_events(base,suite,run_id,start,end)
        fixture=checked_json(base,suite.get('fixture_manifest'))
        require(fixture.get('run_id')==run_id and fixture.get('case_id')==suite['case_id'],'Wrong fixture run')
        require(isinstance(fixture.get('generator'),str) and fixture['generator'],'Missing fixture generator')
        for item in fixture.get('files',[]):checked_file(base,item)
        require(fixture.get('files'),'Missing fixture source files')
        checked_file(base,suite.get('sql'))
        db=checked_json(base,suite.get('database_summary'))
        require(db.get('case_id')==suite['case_id'] and db.get('run_id')==run_id,'Wrong DB evidence')
        require(db.get('integrity_check')=='ok' and str(db.get('schema_version'))=='0001','Database integrity/schema not verified')
        users=db.get('users',[])
        require(users and all(u.get('role') in ('admin','member') and isinstance(u.get('username'),str) for u in users),'Missing real accounts')
        if suite['case_id']=='E2E-TM001-005':
            require(len(users)==1 and users[0]['username']=='admin' and users[0]['role']=='admin' and users[0]['must_change_password'] in (False,0),'Production initialization crossed account boundary')
            restored=checked_json(base,suite.get('restore'))
            require(restored.get('run_id')==run_id and restored.get('case_id')==suite['case_id'],'Foreign restore evidence')
            require(restored.get('synthetic_only') is True and restored.get('table_rows_match') is True and restored.get('integrity_check')=='ok','Database restore differs')
            require(restored.get('actual_service_database') and restored['actual_service_database']==db.get('actual_database_path'),'App did not use the restored database')
            verify_restored_databases(base,restored)
        else:
            require({u['username'] for u in users}=={'test-admin','test-alice','test-bob','test-disabled'},'Synthetic fixture account set differs')
        audit=checked_json(base,suite.get('service_audit'))
        requests=audit.get('requests') if isinstance(audit,dict) else audit
        require(isinstance(requests,list) and requests,'No real service request evidence')
        require(any(r.get('route')=='/v1/auth/login' and r.get('status')==200 for r in requests),'No actual successful authentication')
        require(any(r.get('route')=='/v1/me' and r.get('status')==200 for r in requests),'No actual identity verification')
        traces=suite.get('traces')
        require(isinstance(traces,list) and traces and suite.get('trace')==traces[0],'Missing trace segments')
        require(len({t.get('path') for t in traces})==len(traces),'Duplicate trace segments')
        for trace in traces:verify_trace(base,trace)
        require(suite.get('screenshots'),'Missing screenshot')
        for shot in suite['screenshots']:verify_png(base,shot)
        require(suite.get('installation',{}).get('app_tree_sha256')==package['app']['tree_sha256'],'Suite used a different App')
        if suite['case_id']=='E2E-TM001-004':
            update=suite.get('update',{})
            original=checked_json(base,update.get('result'))
            require(original and all(update.get(k)==v for k,v in original.items()),'Update summary differs from raw result')
            process_path=checked_file(base,update.get('process'))
            process=read_json(process_path)
            require(process.get('run_id')==run_id and process.get('case_id')==suite['case_id'],'Foreign update process')
            verify_update_requests(checked_json(base,update.get('requests')),run_id=run_id,start=start,end=end,artifact=package['artifacts']['update_zip'])
            require(type(update.get('old_pid')) is int and type(update.get('new_pid')) is int and update['old_pid']!=update['new_pid'],'No actual new update process')
            require(process.get('old_pid')==update['old_pid'] and process.get('new_pid')==update['new_pid'],'Process observation differs')
            require(str(update.get('old_build'))=='100' and str(update.get('new_build'))=='101','No actual version upgrade')
            require(update.get('old_app_tree_sha256')==package['app']['tree_sha256'] and update.get('new_app_tree_sha256')==package['update_app']['tree_sha256'],'Wrong upgraded bundle')
            profile=update.get('profile_before_after')
            require(isinstance(profile,dict) and profile.get('before') and profile['before']==profile.get('after'),'Profile not restored after upgrade')
            require(process.get('profile_path')==profile['after'],'Restarted App profile differs')
            require(process.get('process_open_files')=='process-open-files.json','Missing full restarted-process open-file evidence')
            open_file_path=safe_path(process_path.parent,process['process_open_files'])
            open_file_bytes=open_file_path.read_bytes()
            try:open_files=json.loads(open_file_bytes)
            except (ValueError,UnicodeError) as exc:raise Invalid('Invalid full restarted-process open-file evidence') from exc
            require(isinstance(open_files,dict) and open_files.get('run_id')==run_id
                    and open_files.get('case_id')==suite['case_id'] and open_files.get('pid')==update['new_pid'],
                    'Foreign restarted-process open-file evidence')
            all_open=open_files.get('all_open_paths')
            require(isinstance(all_open,list) and all(isinstance(p,str) and p for p in all_open),
                    'Incomplete restarted-process open-file list')
            default_profile=str(Path.home()/'Library/Application Support/TokenMeter')
            require(open_files.get('default_profile')==default_profile and profile['after']!=default_profile,
                    'Default and owned profiles are not isolated')
            owned=[p for p in all_open if p.startswith(profile['after']+'/')]
            default=[p for p in all_open if p==default_profile or p.startswith(default_profile+'/')]
            require(owned and open_files.get('owned_profile_paths')==owned
                    and process.get('observed_open_paths')==all_open
                    and process.get('observed_owned_open_paths')==owned,
                    'New App did not open the original profile')
            require(not default and open_files.get('default_profile_paths')==default
                    and process.get('observed_default_open_paths')==default
                    and update.get('default_profile_observed_in_lsof') is False,
                    'Restarted App accessed the default profile')
            require(start<=timestamp(open_files.get('observed_at'))<=timestamp(process.get('observed_at')),
                    'Open-file evidence is outside the restarted-process observation')
            require(open_file_path.read_bytes()==open_file_bytes,'Full open-file evidence changed during verification')
            require(process.get('installed_executable')==suite['installation'].get('path','')+'/Contents/MacOS/TokenMeter','Wrong restarted executable')
            require(type(update.get('runner_launch_count_after_install')) is int and update['runner_launch_count_after_install']==0,'Test manually launched upgraded App')
            require(update.get('profile_observed_in_lsof') is True and isinstance(update.get('runtime_sha256_before'),str)
                    and re.fullmatch('[0-9a-f]{64}',update['runtime_sha256_before'])
                    and update['runtime_sha256_before']==update.get('runtime_sha256_after'),'Runtime binding changed during upgrade')
            require(start<=timestamp(process.get('observed_at'))<=timestamp(update.get('reconnected_at'))<=end+1,'Update process evidence outside run')
            require(update.get('me_status')==200,'Upgraded identity not verified by service')
    require(sha256(report_path)==hashlib.sha256(report_bytes).hexdigest(),'Report changed during verification')
    # Read back every descriptor after parsing the raw results. This catches
    # accidental concurrent writers without claiming hostile same-uid isolation.
    def recheck(value):
        if isinstance(value,dict):
            if 'path' in value and 'sha256' in value:checked_file(base,value)
            else:
                for child in value.values():recheck(child)
        elif isinstance(value,list):
            for child in value:recheck(child)
    for suite in suites:recheck(suite)
    return report,package

def _frozen_code(report, base, required):
    """Re-read the exact fixed code bytes recorded by a detailed run."""
    snapshots=report.get('test_code_snapshot')
    require(isinstance(snapshots,list) and snapshots,'Missing fixed test-code snapshot')
    found={}
    for item in snapshots:
        require(isinstance(item,dict),'Invalid fixed-code descriptor')
        relative=item.get('path')
        require(isinstance(relative,str) and relative.startswith('test-code/'),'Fixed code escaped its snapshot root')
        source=relative.removeprefix('test-code/')
        require(source and source not in found,'Duplicate fixed-code source')
        original=safe_path(ROOT,source)
        data=checked_bytes(base,item)
        require(hashlib.sha256(data).hexdigest()==sha256(original),f'Fixed test code differs: {source}')
        found[source]=item['sha256']
    require(set(required).issubset(found),'Required fixed test source was not frozen')
    inputs=report.get('test_inputs_sha256')
    if inputs is not None:
        require(isinstance(inputs,dict) and inputs and set(inputs)==set(found),'Fixed input set differs from snapshots')
        require(inputs==found,'Fixed input SHA differs from snapshots')
    return found

def _granular_playwright(base, record, identity, run_id, candidate_sha, start, end, results):
    evidence=record.get('evidence') or {}
    raw=checked_json(base,evidence.get('playwright'))
    require(isinstance(raw,dict) and not raw.get('errors'),'Detailed Playwright global failure')
    config=raw.get('config');metadata=config.get('metadata') if isinstance(config,dict) else None
    require(isinstance(metadata,dict) and metadata.get('run_id')==run_id and
            metadata.get('candidate_sha')==candidate_sha,'Foreign detailed Playwright run')
    specs=[]
    def visit(group):
        require(isinstance(group,dict),'Malformed detailed Playwright suite')
        specs.extend(group.get('specs',[]))
        for nested in group.get('suites',[]):visit(nested)
    for group in raw.get('suites',[]):visit(group)
    require(len(specs)==1 and specs[0].get('title')==identity and specs[0].get('ok') is True,
            'Detailed Playwright identity or assertion failed')
    tests=specs[0].get('tests',[])
    require(len(tests)==1 and tests[0].get('expectedStatus')=='passed' and tests[0].get('status')=='expected',
            'Detailed Playwright case skipped or expected to fail')
    attempts=tests[0].get('results',[])
    require(len(attempts)==1 and attempts[0].get('status')=='passed' and attempts[0].get('retry')==0 and
            not attempts[0].get('errors') and not attempts[0].get('error'),'Detailed Playwright failed, skipped or retried')
    began=timestamp(attempts[0].get('startTime'))
    duration=attempts[0].get('duration')
    require(type(duration) in (int,float) and duration>=0 and start-1<=began<=began+duration/1000<=end+5,
            'Detailed Playwright attempt outside its run')
    trace=checked_bytes(base,evidence.get('trace'))
    verify_trace(base,evidence['trace'])
    calls,problem=results.completed_playwright_calls(identity,json.dumps(raw).encode(),trace)
    require(problem is None and calls,'Detailed UI trace does not bind a passed App attempt')
    shots=evidence.get('screenshots')
    require(isinstance(shots,list) and shots,'Detailed screenshot absent')
    for shot in shots:verify_png(base,shot)

def verify_granular_run(gate_dir: Path, manifest_path: Path, *, run_id: str,
                        candidate_sha: str, candidate_tree: str, not_before: float) -> dict:
    """Independently verify the detailed, auxiliary and audit originals as one candidate."""
    scripts_path=str(ROOT/'scripts')
    if scripts_path not in sys.path:sys.path.insert(0,scripts_path)
    import granular_gate
    import granular_test_result as results
    import audit_granular_evidence as auditor
    gate_dir=Path(gate_dir).absolute()
    manifest_path=Path(manifest_path).absolute()
    package=verify_package(manifest_path,candidate_sha=candidate_sha,candidate_tree=candidate_tree)
    primary_path=safe_path(gate_dir,'granular/result.json')
    primary_bytes=primary_path.read_bytes()
    primary=json.loads(primary_bytes)
    require(isinstance(primary,dict),'Detailed original must be an object')
    primary_records=primary.get('tc_results')
    if primary.get('state')=='FAIL' or (isinstance(primary_records,list) and
            any(isinstance(item,dict) and item.get('state')=='FAIL' for item in primary_records)):
        raise Invalid('Detailed product run contains raw FAIL')
    auxiliary_path=safe_path(gate_dir,'auxiliary/result.json')
    auxiliary_bytes=auxiliary_path.read_bytes()
    auxiliary=json.loads(auxiliary_bytes)
    require(isinstance(auxiliary,dict),'Auxiliary original must be an object')
    if auxiliary.get('state')=='FAIL' or (isinstance(auxiliary.get('tc_results'),list) and
            any(isinstance(item,dict) and item.get('state')=='FAIL' for item in auxiliary['tc_results'])):
        raise Invalid('Auxiliary run contains raw FAIL')
    audit_path=safe_path(gate_dir,'audit/audit.json')
    audit_bytes=audit_path.read_bytes()
    audit=json.loads(audit_bytes)
    require(isinstance(audit,dict),'Audit original must be an object')
    if audit.get('state')=='FAIL' or (isinstance(audit.get('findings'),list) and
            any(isinstance(item,dict) and item.get('state')=='FAIL' for item in audit['findings'])):
        raise Invalid('Independent audit contains raw FAIL')
    release_id,release,_=current_cases()
    catalog=read_json(ROOT/'tests/test_cases.json')
    login=read_json(ROOT/'tests/granular_login_variants.json')
    update=read_json(ROOT/'tests/granular_update_variants.json')
    docs=read_json(ROOT/'docs/catalog.json')
    variants=granular_gate.combine_variants(login,update,release_id)
    require(primary.get('schema_version')==3 and primary.get('scope')=='granular_final_package' and
            primary.get('run_id')==run_id and primary.get('release_id')==release_id==package['release_id'] and
            primary.get('release_eligible') is False,'Wrong detailed report identity or scope')
    require(primary.get('source_commit')==candidate_sha and primary.get('candidate_tree')==candidate_tree and
            primary.get('working_tree_dirty') is False,'Detailed run used another source')
    start,end=time_range(primary,not_before=not_before)
    require(primary.get('host',{}).get('architecture')=='x86_64' and
            str(primary['host'].get('macos','')).startswith('15.'),'Detailed run used another host')
    expected_package={'manifest_sha256':sha256(manifest_path),'dmg_sha256':package['artifacts']['dmg']['sha256'],
                      'app_tree_sha256':package['app']['tree_sha256'],'installed_source':'final_dmg'}
    require(primary.get('package')==expected_package,'Detailed run used another installed DMG')
    require(primary.get('cleanup')=={'mount':True,'private':True,'per_case':True} and
            primary.get('cleanup_completed') is True,'Detailed run left owned resources')
    primary_code=_frozen_code(primary,primary_path.parent,{'tests/test_cases.json','tests/granular_login_variants.json',
        'tests/granular_update_variants.json','scripts/granular_e2e.py','scripts/local_e2e.py',
        'apps/desktop/e2e/playwright.config.ts','apps/desktop/e2e/lsof.ts'})
    require(primary_code['tests/test_cases.json']==sha256(ROOT/'tests/test_cases.json') and
            primary_code['tests/granular_login_variants.json']==sha256(ROOT/'tests/granular_login_variants.json') and
            primary_code['tests/granular_update_variants.json']==sha256(ROOT/'tests/granular_update_variants.json'),
            'Detailed test catalog differs from candidate')
    observed=primary.get('tc_results')
    require(isinstance(observed,list),'Detailed run has no TC records')
    aux_ids={case['id'] for case in catalog['cases'] if case.get('feature_id')=='TM-001' and
             case['id'].startswith(results.AUX_PREFIXES)}
    if any(item.get('state')=='BLOCKED' and item.get('case_id') not in aux_ids for item in observed if isinstance(item,dict)):
        raise Blocked('Detailed product run contains an unexecuted product TC or variant')
    require(primary.get('state')=='BLOCKED','Detailed primary must retain its 11 auxiliary placeholders')
    require(auxiliary.get('schema_version')==3 and auxiliary.get('scope')=='granular_auxiliary_package' and
            auxiliary.get('release_eligible') is False,'Wrong auxiliary report scope')
    require(auxiliary.get('parent_report_sha256')==hashlib.sha256(primary_bytes).hexdigest(),
            'Auxiliary report is bound to another detailed original')
    require(auxiliary.get('package')==expected_package,'Auxiliary run used another installed DMG')
    aux_start,aux_end=time_range(auxiliary,not_before=end)
    if auxiliary.get('state')=='BLOCKED':raise Blocked('Auxiliary raw run is BLOCKED')
    require(auxiliary.get('state')=='PASS','Auxiliary raw run failed')
    _frozen_code(auxiliary,auxiliary_path.parent,{'scripts/granular_auxiliary.py','scripts/granular_gate.py',
        'apps/desktop/e2e/granular-auxiliary.spec.ts','tests/test_cases.json',
        'tests/granular_login_variants.json','tests/granular_update_variants.json'})
    require(audit.get('source_report_sha256')==hashlib.sha256(primary_bytes).hexdigest(),
            'Audit is bound to another detailed original')
    if audit.get('state')=='BLOCKED':raise Blocked('Independent audit is BLOCKED')
    require(audit.get('state')=='PASS','Independent audit failed')
    auditor_code=checked_file(audit_path.parent,audit.get('auditor_code'))
    require(audit.get('auditor_code_sha256')==sha256(auditor_code)==sha256(ROOT/'scripts/audit_granular_evidence.py'),
            'Auditor code differs from fixed candidate')
    fresh_audit=auditor.audit_run(primary_path)
    require({k:v for k,v in audit.items() if k!='auditor_code'}==fresh_audit,
            'Independent audit findings differ on reread')
    outcome=granular_gate.verify_candidate(catalog,primary,run_root=primary_path.parent,plan=release,
        variants=variants,auxiliary=auxiliary,auxiliary_root=auxiliary_path.parent,
        audit=audit,audit_root=audit_path.parent,document_catalog=docs)
    require(outcome['state']=='PASS','Detailed rule component rejected candidate: '+'; '.join(outcome['reasons']))
    for report,base,first,last,identity in ((primary,primary_path.parent,start,end,run_id),
                                            (auxiliary,auxiliary_path.parent,aux_start,aux_end,auxiliary['run_id'])):
        for item in report['tc_results']:
            if item.get('state')!='PASS' or not isinstance(item.get('evidence'),dict) or 'playwright' not in item['evidence']:
                continue
            _granular_playwright(base,item,item['case_id'],identity,candidate_sha,first,last,results)
    require(primary_path.read_bytes()==primary_bytes and auxiliary_path.read_bytes()==auxiliary_bytes and
            audit_path.read_bytes()==audit_bytes,'Detailed source reports changed during verification')
    require(sha256(manifest_path)==expected_package['manifest_sha256'] and
            sha256(checked_file(manifest_path.parent,package['artifacts']['dmg']))==expected_package['dmg_sha256'],
            'Original package changed during detailed verification')
    return {'state':'PASS','run_id':run_id,'candidate_sha':candidate_sha,'candidate_tree':candidate_tree,
            'dmg_sha256':expected_package['dmg_sha256'],'granular_report':descriptor(primary_path,gate_dir),
            'auxiliary_report':descriptor(auxiliary_path,gate_dir),'audit_report':descriptor(audit_path,gate_dir),
            'parent_cases':78,'variants':38,'auxiliary_cases':11,'audited_cases':12}

def verify_granular_workbook(gate_dir: Path, *, run_id: str) -> dict:
    """Check the independent combined TC workbook without changing product results."""
    gate_dir=Path(gate_dir).absolute()
    receipt_path=safe_path(gate_dir,'granular-reviewed/verification.json')
    receipt=read_json(receipt_path)
    primary_path=safe_path(gate_dir,'granular/result.json')
    aggregate_path=safe_path(gate_dir,'e2e/result.json')
    primary=read_json(primary_path)
    aggregate=read_json(aggregate_path)
    aggregate_id=aggregate.get('run_id')
    require(isinstance(aggregate_id,str) and re.fullmatch(r'local-[0-9a-f]{32}',aggregate_id) and
            aggregate_id!=run_id and aggregate.get('parent_run_id')==run_id and
            aggregate.get('parent_report_sha256')==sha256(primary_path),
            'Supplemental run is not bound to the detailed original')
    require(isinstance(receipt,dict),'Combined workbook receipt must be an object')
    require(receipt.get('schema_version')==1 and receipt.get('scope')=='granular_test_result_excel' and
            receipt.get('state')=='PASS' and receipt.get('run_id')==run_id and
            receipt.get('aggregate_run_id')==aggregate_id and receipt.get('product_state')=='BLOCKED',
            'Combined workbook does not belong to the preserved primary run')
    require(receipt.get('tc_counts')=={'PASS':78,'FAIL':0,'BLOCKED':0} and
            receipt.get('variant_counts')=={'PASS':38,'FAIL':0,'BLOCKED':0} and
            receipt.get('suite_count')==6 and receipt.get('audit_count')==12,
            'Combined workbook did not retain the full independently reviewed set')
    source=safe_path(gate_dir,'granular-reviewed/granular-source.json')
    require(sha256(source)==receipt.get('source_model_sha256'),'Combined workbook source model changed')
    model=read_json(source)
    require(isinstance(model,dict),'Combined workbook source model must be an object')
    auxiliary_path=safe_path(gate_dir,'auxiliary/result.json')
    audit_path=safe_path(gate_dir,'audit/audit.json')
    auxiliary=read_json(auxiliary_path)
    require(model.get('run_id')==run_id and model.get('aggregate_run_id')==aggregate_id and
            model.get('audit_run_id')==run_id and model.get('auxiliary_run_id')==auxiliary.get('run_id') and
            model.get('candidate_sha')==primary.get('source_commit') and
            model.get('package_dmg_sha256')==(primary.get('package') or {}).get('dmg_sha256') and
            model.get('aggregate_candidate_sha')==aggregate.get('source_commit')==primary.get('source_commit') and
            model.get('aggregate_dmg_sha256')==(aggregate.get('package') or {}).get('dmg_sha256')==
                (primary.get('package') or {}).get('dmg_sha256') and
            model.get('tc_counts')==receipt['tc_counts'] and model.get('variant_counts')==receipt['variant_counts'] and
            model.get('auxiliary_product_state')=='PASS' and model.get('audit_state')=='PASS' and
            model.get('aggregate_product_state')=='PASS',
            'Combined workbook model differs from this candidate or current originals')
    expected_sources={'逐 TC 主原件':sha256(primary_path),'辅助 11 TC 原件':sha256(auxiliary_path),
                      '独立复核原件':sha256(audit_path),'六组聚合原件':sha256(aggregate_path),
                      '用例目录':sha256(ROOT/'tests/test_cases.json'),
                      '参数变体目录':sha256(ROOT/'tests/granular_login_variants.json'),
                      '更新参数变体目录':sha256(ROOT/'tests/granular_update_variants.json')}
    source_files=model.get('source_files')
    require(isinstance(source_files,list) and len(source_files)==len(expected_sources),
            'Combined workbook source list is incomplete')
    seen=set()
    for item in source_files:
        require(isinstance(item,dict) and item.get('role') in expected_sources and item['role'] not in seen and
                item.get('sha256')==expected_sources[item['role']],
                'Combined workbook source SHA differs from an original')
        seen.add(item['role'])
        copied=checked_file(gate_dir/'granular-reviewed',{'path':item.get('link'),'sha256':item['sha256']})
        require(copied.is_file(),'Combined workbook omitted a linked source')
    require(seen==set(expected_sources),'Combined workbook omitted a source role')
    entry=receipt.get('workbook')
    expected_name=f'TokenMeter测试结果-{run_id}.xlsx'
    require(isinstance(entry,dict) and entry.get('path')==expected_name,'Combined workbook name differs')
    book=checked_file(gate_dir/'granular-reviewed',entry)
    try:
        with zipfile.ZipFile(book) as archive:
            require(archive.testzip() is None,'Combined XLSX archive is corrupt')
            names=archive.read('xl/workbook.xml')
            require(all(name.encode() in names for name in ('01逐例结果','02参数变体','04聚合场景','08辅助用例','11独立复核')),
                    'Combined XLSX lost required sheets')
    except (zipfile.BadZipFile,KeyError) as error:
        raise Invalid('Combined workbook is not a readable XLSX') from error
    return {'state':'PASS','run_id':run_id,'verification':descriptor(receipt_path,gate_dir),
            'source_model':descriptor(source,gate_dir),'workbook':descriptor(book,gate_dir)}

def derive_final_product_result(gate_dir: Path, *, run_id: str,
                                candidate_sha: str, candidate_tree: str) -> dict:
    """Recalculate every final TC outcome while retaining all four raw originals."""
    scripts_path=str(ROOT/'scripts')
    if scripts_path not in sys.path:sys.path.insert(0,scripts_path)
    import granular_gate
    import granular_test_result as results
    import audit_granular_evidence as auditor
    gate_dir=Path(gate_dir).absolute()
    paths={name:safe_path(gate_dir,relative) for name,relative in (
        ('primary','granular/result.json'),('auxiliary','auxiliary/result.json'),
        ('audit','audit/audit.json'),('supplemental','e2e/result.json'))}
    sources={name:descriptor(path,gate_dir) for name,path in paths.items()}
    primary,auxiliary,audit,supplemental=(read_json(paths[name]) for name in paths)
    require(all(isinstance(value,dict) for value in (primary,auxiliary,audit,supplemental)),
            'Final product sources must be JSON objects')
    release_id=primary.get('release_id')
    catalog=read_json(ROOT/'tests/test_cases.json')
    login=read_json(ROOT/'tests/granular_login_variants.json')
    update=read_json(ROOT/'tests/granular_update_variants.json')
    variants=granular_gate.combine_variants(login,update,release_id)
    parents=[case for case in catalog['cases'] if isinstance(case,dict) and case.get('feature_id')=='TM-001']
    parent_ids=[case['id'] for case in parents]
    variant_items=variants['variants']
    variant_ids=[item['id'] for item in variant_items]
    aux_ids={identity for identity in parent_ids if identity.startswith(results.AUX_PREFIXES)}
    audit_ids=list(auditor.AUDITED_CASES)
    require(catalog.get('release_id')==release_id and len(parent_ids)==78 and len(set(parent_ids))==78 and
            len(variant_ids)==38 and len(set(variant_ids))==38 and not set(parent_ids)&set(variant_ids) and
            len(aux_ids)==11,'Final product TC and variant catalogs differ from the baseline')
    require(primary.get('scope')=='granular_final_package' and primary.get('state')=='BLOCKED' and
            primary.get('run_id')==run_id and primary.get('source_commit')==candidate_sha and
            primary.get('candidate_tree')==candidate_tree and primary.get('release_eligible') is False and
            primary.get('cleanup_completed') is True,'Primary original cannot establish this final candidate')
    package=primary.get('package')
    require(isinstance(package,dict) and package.get('installed_source')=='final_dmg' and
            isinstance(package.get('dmg_sha256'),str) and re.fullmatch('[a-f0-9]{64}',package['dmg_sha256']) and
            isinstance(package.get('manifest_sha256'),str) and re.fullmatch('[a-f0-9]{64}',package['manifest_sha256']),
            'Primary original has no final installed package binding')
    require(auxiliary.get('scope')=='granular_auxiliary_package' and auxiliary.get('state')=='PASS' and
            auxiliary.get('parent_run_id')==run_id and auxiliary.get('parent_report_sha256')==sources['primary']['sha256'] and
            auxiliary.get('source_commit')==candidate_sha and auxiliary.get('candidate_tree')==candidate_tree and
            auxiliary.get('release_id')==release_id and auxiliary.get('package')==package and
            auxiliary.get('release_eligible') is False and auxiliary.get('cleanup_completed') is True,
            'Auxiliary original does not resolve this primary candidate')
    require(audit.get('state')=='PASS' and audit.get('run_id')==run_id and
            audit.get('source_commit')==candidate_sha and audit.get('source_report_sha256')==sources['primary']['sha256'] and
            audit.get('audited_cases')==audit_ids,'Independent audit original is missing or BLOCKED')
    supplemental_id=supplemental.get('run_id')
    require(supplemental.get('scope')=='final_package' and supplemental.get('state')=='PASS' and
            isinstance(supplemental_id,str) and re.fullmatch(r'local-[0-9a-f]{32}',supplemental_id) and
            supplemental_id!=run_id and supplemental_id!=auxiliary.get('run_id') and
            supplemental.get('parent_run_id')==run_id and
            supplemental.get('parent_report_sha256')==sources['primary']['sha256'] and
            supplemental.get('release_id')==release_id and
            supplemental.get('source_commit')==candidate_sha and supplemental.get('candidate_tree')==candidate_tree and
            supplemental.get('release_eligible') is False and supplemental.get('cleanup_completed') is True and
            isinstance(supplemental.get('package'),dict) and supplemental['package'].get('dmg_sha256')==package['dmg_sha256'] and
            supplemental['package'].get('manifest_sha256')==package['manifest_sha256'],
            'Supplemental original differs from the final installed candidate')
    def indexed(items,expected,identity,label):
        require(isinstance(items,list) and len(items)==len(expected),'Incomplete '+label)
        require(all(isinstance(item,dict) and isinstance(item.get(identity),str) for item in items),
                'Malformed '+label)
        found={item[identity]:item for item in items}
        require(len(found)==len(items) and set(found)==set(expected),'Missing, duplicate or foreign '+label)
        return found
    primary_results=indexed(primary.get('tc_results'),parent_ids+variant_ids,'case_id','primary TC results')
    auxiliary_results=indexed(auxiliary.get('tc_results'),aux_ids,'case_id','auxiliary TC results')
    findings=indexed(audit.get('findings'),audit_ids,'case_id','independent audit findings')
    suites=indexed(supplemental.get('suites'),CASES,'case_id','supplemental E2E suites')
    declared=primary.get('expected_cases')
    aux_declared=auxiliary.get('expected_cases')
    require(isinstance(declared,list) and len(declared)==116 and len(set(declared))==116 and
            set(declared)==set(parent_ids+variant_ids) and
            isinstance(aux_declared,list) and len(aux_declared)==11 and len(set(aux_declared))==11 and
            set(aux_declared)==aux_ids and
            supplemental.get('expected_cases')==CASES,'Final product declared case sets differ')
    for identity,item in primary_results.items():
        if identity in aux_ids:
            if item.get('state')!='BLOCKED':raise Invalid('Auxiliary primary placeholder was changed')
            require(item.get('step_results')==[] and item.get('evidence')=={} and
                    item.get('started_at') is None and item.get('finished_at') is None and
                    isinstance(item.get('reason'),str) and 'No independently registered' in item['reason'],
                    'Auxiliary primary placeholder claims execution')
        else:
            require(item.get('state')=='PASS','Final product contains primary FAIL, BLOCKED or skip')
    require(all(item.get('state')=='PASS' for item in auxiliary_results.values()),
            'Final product contains auxiliary FAIL, BLOCKED or skip')
    require(all(item.get('state')=='PASS' and item.get('original_state')=='PASS'
                for item in findings.values()),'Independent audit contains FAIL, BLOCKED or skip')
    require(all(item.get('state')=='PASS' and item.get('cleanup_completed') is True
                for item in suites.values()),'Supplemental E2E contains FAIL, BLOCKED or skip')
    model=results.build_model(catalog,primary,run_root=paths['primary'].parent,variants=variants,
                              auxiliary_report=auxiliary,auxiliary_root=paths['auxiliary'].parent,
                              audit_report=audit,audit_root=paths['audit'].parent)
    model_parents=indexed(model.get('cases'),parent_ids,'id','verified parent TC rows')
    model_variants=indexed(model.get('variants'),variant_ids,'id','verified variant rows')
    model_auxiliary=indexed(model.get('auxiliary'),aux_ids,'id','verified auxiliary TC rows')
    model_audit=indexed(model.get('audit'),audit_ids,'id','verified audit rows')
    require(model.get('auxiliary_bound') is True and model.get('tc_counts')=={'PASS':78,'FAIL':0,'BLOCKED':0} and
            model.get('auxiliary_tc_counts')=={'PASS':11,'FAIL':0,'BLOCKED':0} and
            model.get('variant_counts')=={'PASS':38,'FAIL':0,'BLOCKED':0} and
            all(item.get('state')=='PASS' and item.get('reported_state')=='PASS' and
                item.get('run_id')==auxiliary.get('run_id') for item in model_auxiliary.values()) and
            all(item.get('state')=='PASS' for item in model_audit.values()),
            'Verified detailed model is incomplete')
    parent_rows=[]
    for identity in parent_ids:
        row=model_parents[identity]
        source='auxiliary' if identity in aux_ids else 'primary'
        source_run_id=auxiliary.get('run_id') if source=='auxiliary' else run_id
        claimed=primary_results[identity]['state']
        require(row.get('state')=='PASS' and row.get('reported_state')==claimed and
                row.get('result_run_id')==source_run_id and
                (row.get('auxiliary_state')=='PASS' if source=='auxiliary' else row.get('auxiliary_state') in ('',None)) and
                row.get('audit_state')==('PASS' if identity in findings else ''),
                'Verified parent TC does not match its raw source')
        parent_rows.append({'case_id':identity,'final_state':'PASS','source':source,
                            'source_run_id':source_run_id,'primary_original_state':claimed,
                            'auxiliary_original_state':'PASS' if source=='auxiliary' else None,
                            'audit_state':'PASS' if identity in findings else None})
    variant_rows=[]
    for item in variant_items:
        identity=item['id'];row=model_variants[identity]
        require(row.get('state')=='PASS' and row.get('reported_state')=='PASS' and
                row.get('parent_id')==item['parent_id'],'Verified variant does not match its primary original')
        variant_rows.append({'case_id':identity,'parent_id':item['parent_id'],
                             'final_state':'PASS','source':'primary','source_run_id':run_id,
                             'primary_original_state':primary_results[identity]['state']})
    require(all(sources[name]==descriptor(path,gate_dir) for name,path in paths.items()),
            'Final product source originals changed during calculation')
    return {'schema_version':1,'scope':'final_product_result','state':'PASS','release_eligible':False,
            'run_id':run_id,'supplemental_run_id':supplemental_id,
            'release_id':release_id,'candidate_sha':candidate_sha,'candidate_tree':candidate_tree,
            'package_manifest_sha256':package['manifest_sha256'],'dmg_sha256':package['dmg_sha256'],
            'primary_original_state':'BLOCKED','auxiliary_original_state':'PASS',
            'audit_original_state':'PASS','supplemental_original_state':'PASS',
            'source_reports':sources,
            'source_inputs_sha256':{name:sha256(ROOT/name) for name in (
                'tests/test_cases.json','tests/granular_login_variants.json','tests/granular_update_variants.json')},
            'parent_cases':parent_rows,'variants':variant_rows,
            'audited_cases':[{'case_id':identity,'state':'PASS'} for identity in audit_ids],
            'supplemental_cases':[{'case_id':identity,'state':'PASS'} for identity in CASES]}

def verify_final_product_result(gate_dir: Path, *, run_id: str,
                                candidate_sha: str, candidate_tree: str) -> dict:
    """Compare the stored normalized original with a fresh four-source calculation."""
    gate_dir=Path(gate_dir).absolute()
    path=safe_path(gate_dir,'final-product-result.json')
    original=path.read_bytes()
    try:stored=json.loads(original)
    except (UnicodeError,ValueError) as error:raise Invalid('Final product result is invalid JSON') from error
    require(isinstance(stored,dict),'Final product result must be an object')
    calculated=derive_final_product_result(gate_dir,run_id=run_id,candidate_sha=candidate_sha,
                                           candidate_tree=candidate_tree)
    require(stored==calculated and path.read_bytes()==original,
            'Final product result differs from its four original sources')
    for source in calculated['source_reports'].values():checked_file(gate_dir,source)
    return descriptor(path,gate_dir)

def copy_reviewed_export(source: Path, destination: Path) -> None:
    """Keep the SOP-014 result entry and a byte-identical copy with gate evidence."""
    source=Path(source).absolute();destination=Path(destination).absolute()
    require(source.is_dir() and not destination.exists(),'Combined workbook source/destination is unavailable')
    require(all(not path.is_symlink() for path in (source,*source.parents,destination,*destination.parents)),
            'Combined workbook copy path contains a symlink')
    destination.mkdir(mode=0o700)
    copied=0
    for original in sorted(source.rglob('*')):
        require(not original.is_symlink() and (original.is_dir() or original.is_file()),
                'Combined workbook export has an unsafe entry')
        target=destination/original.relative_to(source)
        if original.is_dir():
            target.mkdir(parents=True,exist_ok=True,mode=0o700)
            continue
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with original.open('rb') as reader,target.open('xb') as writer:
            os.chmod(target,0o600)
            shutil.copyfileobj(reader,writer)
        require(sha256(target)==sha256(original),'Combined workbook copy differs from SOP-014 original')
        copied+=1
    require(copied>0,'Combined workbook export is empty')

def descriptor(path,base):return {'path':str(path.relative_to(base)),'sha256':sha256(path),'bytes':path.stat().st_size}

def write_new(path,value):
    with path.open('x') as f:
        os.chmod(path,0o600);json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')

def _private_path_forms(paths):
    """Cover ordinary, resolved, JSON-escaped and repr-escaped spellings."""
    forms=set()
    for source in paths:
        original=str(source)
        for path in (original,os.path.realpath(original)):
            if not path:
                continue
            forms.add(path)
            forms.add(json.dumps(path,ensure_ascii=True)[1:-1])
            forms.add(json.dumps(path,ensure_ascii=False)[1:-1])
            forms.add(repr(path)[1:-1])
    return sorted(forms,key=len,reverse=True)

def redact_private_paths(value, paths):
    result=str(value)
    for form in _private_path_forms(paths):
        result=result.replace(form,'<SIGNING_INPUT_DIR>')
    return result

def run_logged(argv,log_path,*,redact_paths=()):
    """Stream child output into a bounded, private and redacted evidence log."""
    with log_path.open('x',encoding='utf-8') as log:
        os.chmod(log_path,0o600)
        child=subprocess.Popen(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                               start_new_session=True)
        try:
            total=0
            assert child.stdout is not None
            while line:=child.stdout.readline(MAX_CHILD_LINE_BYTES+1):
                total+=len(line)
                if len(line)>MAX_CHILD_LINE_BYTES or total>MAX_CHILD_LOG_BYTES:
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    child.wait()
                    log.write('[Child output exceeded the safe log bound; process stopped]\n')
                    raise Blocked('Child runner output exceeded the safe log bound')
                log.write(redact_private_paths(line.decode('utf-8',errors='replace'),redact_paths))
            return child.wait()
        finally:
            if child.stdout is not None:
                child.stdout.close()
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()

def verify_detailed_runner_completion(exit_code, raw):
    require(isinstance(raw,dict),'Detailed runner did not produce a JSON object')
    rows=raw.get('tc_results')
    require(isinstance(rows,list) and rows,'Detailed runner has no TC originals')
    require(all(isinstance(row,dict) and isinstance(row.get('case_id'),str) and
                row.get('state') in ('PASS','FAIL','BLOCKED') for row in rows),
            'Detailed runner has malformed TC originals')
    identities=[row['case_id'] for row in rows]
    require(len(identities)==len(set(identities)),'Detailed runner repeats TC identities')
    failed=sorted(row['case_id'] for row in rows if row['state']=='FAIL')
    if failed:
        raise Invalid('Detailed runner original FAIL: '+', '.join(failed))
    blocked={row['case_id'] for row in rows if row['state']=='BLOCKED'}
    if raw.get('state')!='BLOCKED' or exit_code!=2:
        raise Invalid(f'Detailed runner state/exit mismatch: {raw.get("state")}/{exit_code}; '
                      'expected BLOCKED/2 for 11 auxiliary placeholders; '
                      'BLOCKED TC: '+(', '.join(sorted(blocked)) or 'none'))
    extra=sorted(blocked-AUX_PLACEHOLDER_IDS)
    if extra:
        raise Blocked('Detailed runner has additional BLOCKED TC: '+', '.join(extra))
    missing=sorted(AUX_PLACEHOLDER_IDS-blocked)
    if missing:
        raise Blocked('Detailed runner lacks required auxiliary placeholders: '+', '.join(missing))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-manifest',type=Path,required=True)
    parser.add_argument('--key-dir',type=Path,required=True,
                        help='Absolute, owner-restricted internal signing input directory')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['iteration','release'],default='release')
    args=parser.parse_args(argv)
    started=time.time();run_id='local-'+uuid.uuid4().hex
    out=args.output.absolute();owns_output=False;state={'state':'BLOCKED','release_eligible':False,'run_id':run_id,'started_at':started}
    try:
        require(platform.system()=='Darwin' and platform.machine()=='x86_64','Current profile requires Intel macOS')
        if not args.key_dir.is_absolute() or any(ord(character)<32 for character in str(args.key_dir)):
            raise Blocked('Signing input directory must be an absolute path without control characters')
        require(not out.exists() and all(not p.is_symlink() for p in [out,*out.parents]),'Output must be new and unsymlinked')
        out.mkdir(parents=True,mode=0o700)
        owns_output=True
        candidate=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}')
        require(not git('status','--porcelain'),'Candidate must be committed and clean')
        release_id,release,expected=current_cases()
        require(release.get('execution_profile')=='local_electron' and release.get('execution_bindings_status')=='ready','Electron bindings not ready')
        dependency_check=subprocess.run([sys.executable,'-c','import alembic, fastapi, sqlalchemy, uvicorn'],capture_output=True,check=False)
        if dependency_check.returncode:
            raise Blocked('Service dependencies are unavailable in this Python; use .local/venv-tm001/bin/python scripts/quality_gate.py with the same arguments after SOP-009')
        manifest=args.package_manifest.resolve(strict=True)
        package=verify_package(manifest,candidate_sha=candidate,candidate_tree=tree)
        dmg=checked_file(manifest.parent,package['artifacts']['dmg'])
        update_zip=checked_file(manifest.parent,package['artifacts']['update_zip'])
        try:
            signing_fixture.validate_signing_inputs(args.key_dir,package,update_zip)
        except signing_fixture.SigningInputsUnavailable as error:
            raise Blocked(str(error)) from error
        except OSError as error:
            raise Blocked('Internal signing input access failed') from error
        granular=out/'granular'
        granular_cmd=[sys.executable,str(ROOT/'scripts/granular_e2e.py'),'--package-manifest',str(manifest),
                      '--dmg',str(dmg),'--update-zip',str(update_zip),'--output',str(granular),
                      '--candidate-sha',candidate,'--run-id',run_id,'--key-dir',str(args.key_dir)]
        state['granular_exit_code']=run_logged(granular_cmd,out/'granular-runner.log',
                                              redact_paths=(args.key_dir,))
        if not (granular/'result.json').is_file():raise Blocked('Detailed runner produced no original result; see granular-runner.log')
        state['granular_report']=descriptor(granular/'result.json',out)
        granular_raw=read_json(granular/'result.json')
        verify_detailed_runner_completion(state['granular_exit_code'],granular_raw)
        if granular_raw.get('cleanup_completed') is not True:
            error='Detailed run did not safely clean owned resources; see its original result'
            if granular_raw.get('state')=='FAIL':raise Invalid(error)
            raise Blocked(error)
        auxiliary=out/'auxiliary'
        auxiliary_id='aux-'+uuid.uuid4().hex
        auxiliary_cmd=[sys.executable,str(ROOT/'scripts/granular_auxiliary.py'),
                       '--parent-report',str(granular/'result.json'),'--run-id',auxiliary_id,
                       '--output',str(auxiliary),'--with-ui','--package-manifest',str(manifest),
                       '--dmg',str(dmg),'--update-zip',str(update_zip)]
        state['auxiliary_exit_code']=run_logged(auxiliary_cmd,out/'auxiliary-runner.log')
        if not (auxiliary/'result.json').is_file():
            error='Auxiliary runner produced no cleanup or TC original; see auxiliary-runner.log'
            if granular_raw.get('state')=='FAIL':raise Invalid(error)
            raise Blocked(error)
        state['auxiliary_report']=descriptor(auxiliary/'result.json',out)
        auxiliary_raw=read_json(auxiliary/'result.json')
        if auxiliary_raw.get('cleanup_completed') is not True:
            error='Auxiliary run did not safely clean owned resources; see its original result'
            if auxiliary_raw.get('state')=='FAIL' or granular_raw.get('state')=='FAIL':raise Invalid(error)
            raise Blocked(error)
        audit=out/'audit';audit.mkdir(mode=0o700)
        audit_cmd=[sys.executable,str(ROOT/'scripts/audit_granular_evidence.py'),
                   '--report',str(granular/'result.json'),'--output',str(audit/'audit.json')]
        state['audit_exit_code']=run_logged(audit_cmd,out/'audit-runner.log')
        if (audit/'audit.json').is_file():state['audit_report']=descriptor(audit/'audit.json',out)
        e2e=out/'e2e'
        supplemental_id='local-'+uuid.uuid4().hex
        state['supplemental_run_id']=supplemental_id
        e2e_cmd=[sys.executable,str(ROOT/'scripts/local_e2e.py'),'--package-manifest',str(manifest),
                 '--dmg',str(dmg),'--update-zip',str(update_zip),'--output',str(e2e),
                 '--candidate-sha',candidate,'--run-id',supplemental_id,
                 '--parent-report',str(granular/'result.json')]
        state['supplemental_exit_code']=run_logged(e2e_cmd,out/'supplemental-runner.log')
        if (e2e/'result.json').is_file():state['report']=descriptor(e2e/'result.json',out)
        require(git('rev-parse','HEAD')==candidate and not git('status','--porcelain'),'Source changed during testing')
        originals=[read_json(path) for path in (granular/'result.json',auxiliary/'result.json',audit/'audit.json',e2e/'result.json') if path.is_file()]
        if len(originals)!=4:raise Blocked('Current invocation did not produce all four original results')
        reviewed=ROOT/'.local/test-results'/run_id/'granular-reviewed'
        require(not reviewed.exists(),'Combined workbook output already exists')
        export_cmd=[sys.executable,str(ROOT/'scripts/granular_test_result.py'),
                    '--report',str(granular/'result.json'),'--aux-report',str(auxiliary/'result.json'),
                    '--audit-report',str(audit/'audit.json'),'--aggregate-report',str(e2e/'result.json'),
                    '--output',str(reviewed)]
        state['granular_export_exit_code']=run_logged(export_cmd,out/'granular-export.log')
        if (reviewed/'verification.json').is_file():
            state['granular_export_verification_sha256']=sha256(reviewed/'verification.json')
        if any(item.get('state')=='FAIL' for item in originals):raise Invalid('A current product or audit original is FAIL')
        if any(item.get('state')=='BLOCKED' for item in originals[1:]):raise Blocked('Auxiliary, audit or six-suite original is BLOCKED')
        if state['granular_export_exit_code']!=0:
            if state['granular_export_exit_code']==2:raise Blocked('Combined TC workbook export is BLOCKED; see granular-export.log')
            raise Invalid('Combined TC workbook export failed; see granular-export.log')
        copy_reviewed_export(reviewed,out/'granular-reviewed')
        granular_evidence=verify_granular_run(out,manifest,run_id=run_id,candidate_sha=candidate,
                                              candidate_tree=tree,not_before=started)
        report,package=verify_report(e2e/'result.json',manifest,run_id=supplemental_id,
                                     candidate_sha=candidate,candidate_tree=tree,not_before=started,
                                     parent_run_id=run_id,parent_report_sha256=sha256(granular/'result.json'))
        workbook_evidence=verify_granular_workbook(out,run_id=run_id)
        write_new(out/'final-product-result.json',derive_final_product_result(out,run_id=run_id,
                  candidate_sha=candidate,candidate_tree=tree))
        final_product_result=verify_final_product_result(out,run_id=run_id,candidate_sha=candidate,
                                                         candidate_tree=tree)
        for name in ('verification.json','granular-source.json',f'TokenMeter测试结果-{run_id}.xlsx'):
            require(sha256(reviewed/name)==sha256(out/'granular-reviewed'/name),
                    'SOP-014 result entry differs from archived gate copy')
        require(state['auxiliary_exit_code']==0 and state['audit_exit_code']==0 and
                state['supplemental_exit_code']==0,'One or more product runners exited unsuccessfully')
        state.update(state='PASS',release_eligible=args.phase=='release',release_id=release_id,candidate_sha=candidate,candidate_tree=tree,
                     package_manifest_sha256=sha256(manifest),report=descriptor(e2e/'result.json',out),expected_cases=expected,
                     granular_evidence=granular_evidence,granular_workbook=workbook_evidence,
                     final_product_result=final_product_result,
                     host=report['host'],phase=args.phase,
                     scope='local_final_package',finished_at=time.time())
        if args.phase=='release':
            require(git('rev-parse','HEAD')==candidate and git('rev-parse','HEAD^{tree}')==tree and not git('status','--porcelain'),'Source changed during evidence verification')
            passport={**state,'schema_version':2,'distribution_profile':'internal','storage':'local_only','github_release':False,
                      'artifacts':package['artifacts'],'signing':{'certificate_sha256':package['app']['certificate_sha256']},
                      'evidence_identity':{'uid':os.getuid(),'hostname':platform.node(),'run_id':run_id},
                      'source_inputs':{p:sha256(ROOT/p) for p in (
                          'tests/feature_matrix.json','tests/acceptance.json','tests/datasets.json',
                          'tests/test_cases.json','tests/granular_login_variants.json','tests/granular_update_variants.json',
                          'docs/catalog.json','scripts/granular_gate.py','sop/SOP-014-e2e.md',
                          'sop/SOP-018-release-gate.md','apps/desktop/package-lock.json')}}
            write_new(out/(release_id+'.passport.json'),passport)
    except (OSError,Invalid,KeyError,TypeError,ValueError,subprocess.SubprocessError) as exc:
        state.update(state='BLOCKED' if isinstance(exc,(Blocked,FileNotFoundError)) else 'FAIL',
                     release_eligible=False,error=redact_private_paths(str(exc),(args.key_dir,)),
                     finished_at=time.time())
    if owns_output and out.is_dir() and not (out/'gate.json').exists():write_new(out/'gate.json',state)
    print(json.dumps(state,ensure_ascii=False))
    return 0 if state['state']=='PASS' else 2 if state['state']=='BLOCKED' else 1

if __name__=='__main__':raise SystemExit(main())
