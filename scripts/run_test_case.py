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
import shlex
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
KEY_DIR_PLACEHOLDER = '<KEY_DIR_FROM_LOCAL_CONFIG>'


class ReplayBlocked(Exception):
    """The requested replay cannot start because its local signing input is absent."""


def requires_signing_inputs(case_id: str | None, all_cases: bool) -> bool:
    return all_cases or case_id == 'TC-TM001-UPDATE-05' or bool(
        case_id and case_id.startswith('TC-TM001-UPDATE-05#'))


def redact_signing_text(value: str, key_dir: Path | None) -> str:
    """Keep a private path out of reports, replay commands and ordinary logs."""
    if key_dir is None:
        return value
    original = str(key_dir)
    forms = {original, os.path.abspath(original), os.path.realpath(original)}
    for path in tuple(forms):
        forms.update((json.dumps(path, ensure_ascii=False)[1:-1],
                      json.dumps(path, ensure_ascii=True)[1:-1],
                      repr(path)[1:-1], shlex.quote(path)))
    for form in sorted((item for item in forms if item), key=len, reverse=True):
        value = value.replace(form, KEY_DIR_PLACEHOLDER)
    return value


def redact_signing_data(value, key_dir: Path | None):
    if isinstance(value, str):
        return redact_signing_text(value, key_dir)
    if isinstance(value, list):
        return [redact_signing_data(item, key_dir) for item in value]
    if isinstance(value, dict):
        return {redact_signing_data(key, key_dir): redact_signing_data(item, key_dir)
                for key, item in value.items()}
    return value

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
            run_id: str, key_dir: Path | None = None) -> list[str]:
    if bool(case_id)==bool(all_cases): raise ValueError('Choose exactly one TC or the complete catalog')
    if key_dir is not None and not key_dir.is_absolute():
        raise ReplayBlocked('Signing input directory must be an absolute path')
    if requires_signing_inputs(case_id, all_cases) and key_dir is None:
        raise ReplayBlocked('UPDATE-05 requires an explicit absolute --key-dir before App launch')
    manifest_path=manifest_path.resolve(strict=True)
    package=json.loads(manifest_path.read_text())
    artifacts=package['artifacts']
    result=[sys.executable,str(ROOT/'scripts/granular_e2e.py'),'--package-manifest',str(manifest_path),
        '--dmg',str(manifest_path.parent/artifacts['dmg']['path']),
        '--update-zip',str(manifest_path.parent/artifacts['update_zip']['path']),
        '--candidate-sha',package['candidate_sha'],'--run-id',run_id,'--output',str(ROOT/'.local/ci'/run_id)]
    if development:result.append('--development')
    if key_dir is not None:result.extend(['--key-dir',str(key_dir)])
    if case_id:result.extend(['--case-id',case_id])
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--case-id');group.add_argument('--all',action='store_true')
    parser.add_argument('--package-manifest',type=Path,required=True)
    parser.add_argument('--development',action='store_true')
    parser.add_argument('--key-dir',type=Path,help='Absolute restricted local signing input directory for UPDATE-05')
    parser.add_argument('--source-report',type=Path,help='Require the recorded test-source hashes before repeating an earlier run')
    args=parser.parse_args(argv);run_id='local-'+uuid.uuid4().hex
    try:
        invocation=command(args.package_manifest,case_id=args.case_id,all_cases=args.all,
            development=args.development,run_id=run_id,key_dir=args.key_dir)
    except ReplayBlocked as error:
        output=ROOT/'.local/ci'/run_id
        output.mkdir(parents=True,mode=0o700)
        os.chmod(output,0o700)
        report=redact_signing_data({'scope':'replay_argument_preflight','run_id':run_id,
            'state':'BLOCKED','case_id':args.case_id,'reason':str(error)},args.key_dir)
        result=output/'result.json'
        descriptor=os.open(result,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump(report,stream,ensure_ascii=False)
            stream.write('\n')
        print(json.dumps({'run_id':run_id,'state':'BLOCKED','report':str(result),
                          'reason':report['reason']},ensure_ascii=False),flush=True)
        return 2
    if args.source_report:
        verify_replay(args.source_report,args.package_manifest)
    print(json.dumps({'run_id':run_id,'command':redact_signing_data(invocation,args.key_dir)},ensure_ascii=False),flush=True)
    log_path=ROOT/'.local/ci'/f'{run_id}.console.log'
    log_path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    os.chmod(log_path.parent,0o700)
    descriptor=os.open(log_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as log:
        try:
            process=subprocess.Popen(invocation,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        except OSError as error:
            reason=redact_signing_text(str(error),args.key_dir)
            log.write(reason+'\n')
            print(json.dumps({'run_id':run_id,'state':'BLOCKED','reason':reason,
                              'console_log':str(log_path)},ensure_ascii=False),flush=True)
            return 2
        assert process.stdout is not None
        for line in process.stdout:
            safe_line=redact_signing_text(line,args.key_dir)
            log.write(safe_line);log.flush();print(safe_line,end='',flush=True)
        code=process.wait()
    print(json.dumps({'run_id':run_id,'exit_code':code,'console_log':str(log_path)}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
