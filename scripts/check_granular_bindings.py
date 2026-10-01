#!/usr/bin/env python3
"""Check real Playwright registration and exact TC selection without launching UI."""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

import granular_e2e as runner

ROOT=Path(__file__).resolve().parents[1]

def titles(payload):
    found=[]
    for suite in payload.get('suites',[]):
        found.extend(spec['title'] for spec in suite.get('specs',[]))
        found.extend(titles(suite))
    return found

def execute():
    catalog=runner.read_catalog()
    parents={c['parent_id'] for c in catalog if c.get('parent_id')}
    expected={c['id'] for c in catalog if runner.case_spec(c['id']) and c['id'] not in parents and not c.get('variant_blocked_reason')}
    groups={runner.case_spec(identity) for identity in expected}
    observations=[]
    with tempfile.TemporaryDirectory(prefix='tokenmeter-registration-') as directory:
        private=Path(directory).resolve();database=private/'test.sqlite'
        sqlite3.connect(database).close()
        context=private/'context.json'
        context.write_text(json.dumps({'app_path':str(private/'TokenMeter.app'),'database_path':str(database),'profile_path':str(private/'profile'),'case_id':'TC-TM001-LOGIN-17#A'}))
        os.chmod(context,0o600)
        found=[]
        for spec in sorted(groups):
            env=dict(os.environ,TM_E2E_CONTEXT=str(context),TM_E2E_JSON=str(private/'unused.json'),TM_E2E_CASE_OUTPUT=str(private),TM_E2E_SPEC=spec)
            argv=[str(ROOT/'apps/desktop/node_modules/.bin/playwright'),'test','e2e/'+spec,'--config','e2e/playwright.config.ts','--list','--reporter=json']
            result=subprocess.run(argv,cwd=ROOT/'apps/desktop',env=env,capture_output=True,text=True,timeout=60,check=False)
            selected=titles(json.loads(result.stdout)) if result.returncode==0 else []
            observations.append({'spec':spec,'exit_code':result.returncode,'registered':selected,'stderr':result.stderr})
            found.extend(selected)
        selector=r'(?:^|\s)'+re.escape('TC-TM001-LOGIN-17#A')+'$'
        env['TM_E2E_SPEC']='granular-login.spec.ts'
        result=subprocess.run([str(ROOT/'apps/desktop/node_modules/.bin/playwright'),'test','e2e/granular-login.spec.ts','--config','e2e/playwright.config.ts','--list','--reporter=json','--grep',selector],cwd=ROOT/'apps/desktop',env=env,capture_output=True,text=True,timeout=60,check=False)
        selected=titles(json.loads(result.stdout)) if result.returncode==0 else []
        exact=result.returncode==0 and selected==['TC-TM001-LOGIN-17#A']
    missing=sorted(expected-set(found));extra=sorted(set(found)-expected)
    passed=not missing and not extra and len(found)==len(set(found)) and exact and all(x['exit_code']==0 for x in observations)
    return {'scope':'fixed_test_registration_only','state':'PASS' if passed else 'FAIL','release_eligible':False,
        'expected':len(expected),'registered':len(found),'missing':missing,'extra':extra,'exact_selector':exact,'observations':observations}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=execute()
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['state']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
