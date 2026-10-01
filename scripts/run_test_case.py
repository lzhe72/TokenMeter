#!/usr/bin/env python3
"""Repeat one fixed product TC (including all variants) or the full catalog.

This command generates only run identity/output paths. Inputs, UI operations,
assertions, fixtures and pass/fail decisions live in versioned test programs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]

def verify_replay(report_path: Path, manifest_path: Path) -> None:
    previous=json.loads(report_path.read_text())
    hashes=previous.get('test_inputs_sha256')
    if not isinstance(hashes,dict) or not hashes:raise ValueError('Source report lacks test-source hashes')
    for relative,expected in hashes.items():
        path=ROOT/relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Test source differs from recorded run: '+relative)
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=previous.get('package',{}).get('manifest_sha256'):
        raise ValueError('Package manifest differs from recorded run')

def command(manifest_path: Path, *, case_id: str | None, all_cases: bool, development: bool,
            run_id: str) -> list[str]:
    if bool(case_id)==bool(all_cases): raise ValueError('Choose exactly one TC or the complete catalog')
    manifest_path=manifest_path.resolve(strict=True)
    package=json.loads(manifest_path.read_text())
    artifacts=package['artifacts']
    result=[sys.executable,str(ROOT/'scripts/granular_e2e.py'),'--package-manifest',str(manifest_path),
        '--dmg',str(manifest_path.parent/artifacts['dmg']['path']),
        '--update-zip',str(manifest_path.parent/artifacts['update_zip']['path']),
        '--candidate-sha',package['candidate_sha'],'--run-id',run_id,'--output',str(ROOT/'.local/ci'/run_id)]
    if development:result.append('--development')
    if case_id:result.extend(['--case-id',case_id])
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--case-id');group.add_argument('--all',action='store_true')
    parser.add_argument('--package-manifest',type=Path,required=True)
    parser.add_argument('--development',action='store_true')
    parser.add_argument('--source-report',type=Path,help='Require the recorded test-source hashes before repeating an earlier run')
    args=parser.parse_args();run_id='local-'+uuid.uuid4().hex
    if args.source_report:
        verify_replay(args.source_report,args.package_manifest)
    invocation=command(args.package_manifest,case_id=args.case_id,all_cases=args.all,
        development=args.development,run_id=run_id)
    print(json.dumps({'run_id':run_id,'command':invocation},ensure_ascii=False),flush=True)
    log_path=ROOT/'.local/ci'/f'{run_id}.console.log'
    log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open('x',encoding='utf-8') as log:
        os.chmod(log_path,0o600)
        process=subprocess.Popen(invocation,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line);log.flush();print(line,end='',flush=True)
        code=process.wait()
    print(json.dumps({'run_id':run_id,'exit_code':code,'console_log':str(log_path)}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
