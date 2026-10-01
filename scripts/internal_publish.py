#!/usr/bin/env python3
"""Verify protected GitHub state, then publish only this run's gated assets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_e2e

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {'governance', 'product-e2e (macos-15)', 'product-e2e (macos-15-intel)'}
RELEASE_JOBS = {'release-preflight', 'internal-build', 'installed-e2e (arm64)', 'installed-e2e (x86_64)', 'internal-gate'}
REPO = 'lzhe72/TokenMeter'


def command(args, *, input_value=None):
    result = subprocess.run(args, input=input_value, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} operation failed ({result.returncode}); no release override was attempted')
    return result.stdout.strip()


def api(endpoint, *, body=None):
    args = ['gh', 'api', f'repos/{REPO}/{endpoint}']
    if body is not None:
        args += ['--method', 'POST', '--input', '-']
    return json.loads(command(args, input_value=None if body is None else json.dumps(body)))


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): value.update(block)
    return value.hexdigest()


def context(candidate):
    env = os.environ
    required = {'GITHUB_ACTIONS':'true', 'GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_REF':'refs/heads/master', 'GITHUB_REF_PROTECTED':'true',
        'GITHUB_REPOSITORY':REPO, 'GITHUB_SHA':candidate, 'GITHUB_WORKFLOW_SHA':candidate,
        'GITHUB_WORKFLOW_REF':REPO+'/.github/workflows/internal-release.yml@refs/heads/master'}
    if (not re.fullmatch(r'[a-f0-9]{40}', candidate)
            or any(env.get(k) != v for k,v in required.items())
            or not env.get('GITHUB_RUN_ID','').isdigit() or not env.get('GITHUB_RUN_ATTEMPT','').isdigit()):
        raise ValueError('Internal publication requires this exact protected master dispatch')
    if command(['git','-C',str(ROOT),'rev-parse','HEAD']) != candidate:
        raise ValueError('Checkout differs from candidate')
    if command(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=all']):
        raise ValueError('Candidate checkout must remain clean')
    return {'repository': REPO, 'workflow':env['GITHUB_WORKFLOW_REF'], 'run_id':env['GITHUB_RUN_ID'],
            'run_attempt':env['GITHUB_RUN_ATTEMPT'], 'sha':candidate,
            'event_name':env['GITHUB_EVENT_NAME'], 'ref':env['GITHUB_REF']}


def validate_remote_checks(branch, checks, candidate):
    protection = branch.get('protection',{}).get('required_status_checks',{})
    if (branch.get('protected') is not True or branch.get('commit',{}).get('sha') != candidate
            or branch.get('protection',{}).get('enabled') is not True
            or protection.get('enforcement_level') != 'everyone'
            or not CHECKS.issubset(set(protection.get('contexts',[])))):
        raise ValueError('Master protection or exact branch candidate is not in force')
    for name in CHECKS:
        matches = [c for c in checks if c.get('name') == name]
        if (not matches or any(c.get('status') != 'completed' or c.get('conclusion') != 'success'
                or c.get('head_sha') != candidate or c.get('app',{}).get('slug') != 'github-actions' for c in matches)):
            raise ValueError('Required candidate check has not passed: '+name)


def verify_remote(candidate):
    branch = api('branches/master')
    checks = api(f'commits/{candidate}/check-runs?per_page=100')['check_runs']
    validate_remote_checks(branch, checks, candidate)
    environment = api('environments/release-validation')
    policies = api('environments/release-validation/deployment-branch-policies')
    if (environment.get('deployment_branch_policy') != {'protected_branches':False,'custom_branch_policies':True}
            or [(p.get('name'),p.get('type')) for p in policies.get('branch_policies',[])] != [('master','branch')]):
        raise ValueError('Release environment must allow only master')
    return {'branch':branch,'checks':checks,'environment':environment,'policies':policies}


def validate_jobs(jobs, candidate, attempt):
    for name in RELEASE_JOBS:
        selected = [job for job in jobs if job.get('name') == name]
        if len(selected) != 1 or any(job.get('status') != 'completed' or job.get('conclusion') != 'success'
                or job.get('head_sha') != candidate or str(job.get('run_attempt')) != str(attempt) for job in selected):
            raise ValueError('This release dependency did not pass in this attempt: '+name)


def absent_release(rid):
    # Successful list calls distinguish absence from a permission/network failure.
    tags = api('git/matching-refs/tags/'+rid)
    if any(t['ref'] == 'refs/tags/'+rid for t in tags):
        raise ValueError('Release tag already exists; do not move or recreate it')
    releases = json.loads(command(['gh','api','--paginate','--slurp',f'repos/{REPO}/releases?per_page=100']))
    if any(r.get('tag_name') == rid for page in releases for r in page):
        raise ValueError('Release already exists; do not replace its assets')


def preflight(candidate, output):
    ci = context(candidate)
    rid = json.loads((ROOT/'releases/current.json').read_text())['release_id']
    if not re.fullmatch(r'v\d+\.\d+\.\d+-\d{8}T\d{6}Z', rid): raise ValueError('Invalid release ID')
    remote = verify_remote(candidate)
    absent_release(rid)
    result = {'state':'PASS','scope':'release_context_only','release_eligible':False,
        'release_id':rid,'candidate_sha':candidate,'ci':ci,'run_id':secrets.token_hex(24),
        'verified_at':datetime.now(timezone.utc).isoformat(),'remote':remote}
    (output/'preflight.json').write_text(json.dumps(result,indent=2)+'\n')
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
        stream.write(f'release_id={rid}\nrun_id={result["run_id"]}\n')
    return result


def verified_assets(manifest_path, passport_path, candidate, ci, run_id):
    manifest = json.loads(manifest_path.read_text()); passport = json.loads(passport_path.read_text())
    rid = manifest['release_id']
    if (passport.get('state') != 'PASS' or passport.get('release_eligible') is not True
            or passport.get('distribution_profile') != 'internal' or manifest.get('distribution_profile') != 'internal'
            or passport.get('candidate_sha') != candidate or manifest.get('candidate_sha') != candidate
            or passport.get('release_id') != rid or passport.get('ci') != ci or passport.get('run_id') != run_id
            or passport.get('package_manifest_sha256') != digest(manifest_path)):
        raise ValueError('Passport does not bind this protected run and original package')
    selected=[]
    for key in ('dmg','candidate_zip','server_zip'):
        item=manifest['artifacts'][key]; relative=Path(item['path']); path=manifest_path.parent/relative
        if (relative.is_absolute() or '..' in relative.parts or path.is_symlink()
                or not path.resolve().is_relative_to(manifest_path.parent.resolve())
                or not path.is_file() or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']):
            raise ValueError('Release asset differs from tested package: '+key)
        selected.append(path)
    return rid,selected


def verified_evidence(archives, passport_path):
    """Keep the raw results queryable after transient Actions artifacts expire."""
    passport=json.loads(passport_path.read_text())
    assets=[]
    with tempfile.TemporaryDirectory(prefix='tokenmeter-publication-evidence-') as temporary:
        root=Path(temporary).resolve()
        for architecture in ('arm64','x86_64'):
            archive=archives/('evidence-'+architecture+'.tar.gz')
            if not archive.is_file() or archive.is_symlink(): raise ValueError('Missing original platform evidence archive')
            with tarfile.open(archive,'r:gz') as bundle:
                seen=set()
                for member in bundle.getmembers():
                    path=Path(member.name)
                    if (path.is_absolute() or '..' in path.parts or not path.parts
                            or path.parts[0] != architecture or member.name in seen
                            or not (member.isfile() or member.isdir())):
                        raise ValueError('Unsafe or duplicate evidence archive member')
                    seen.add(member.name)
                    destination=root/path
                    if member.isdir(): destination.mkdir(parents=True,exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        with bundle.extractfile(member) as source, destination.open('xb') as target:
                            import shutil
                            shutil.copyfileobj(source,target)
            report_path=root/architecture/'result.json'
            platform=passport['platforms'][architecture]
            if digest(report_path) != platform['report_sha256']:
                raise ValueError('Archived report differs from the gated platform')
            report=json.loads(report_path.read_text())
            for suite in report['suites']:
                relative=Path(suite['xcresult'])
                if relative.is_absolute() or '..' in relative.parts: raise ValueError('Native bundle path escapes evidence')
                if native_e2e.tree_digest(root/architecture/relative) != platform['xcresult_sha256'][suite['case_id']]:
                    raise ValueError('Archived native bundle differs from the gated raw evidence')
            assets.append(archive)
    return assets


def publish(args, output):
    ci=context(args.candidate_sha)
    remote=verify_remote(args.candidate_sha)
    jobs=api(f'actions/runs/{ci["run_id"]}/attempts/{ci["run_attempt"]}/jobs?per_page=100')['jobs']
    validate_jobs(jobs,args.candidate_sha,ci['run_attempt'])
    rid,assets=verified_assets(args.package_manifest,args.passport,args.candidate_sha,ci,args.run_id)
    assets += verified_evidence(args.evidence_archives,args.passport)
    gate_report=args.passport.parent/'report.json'
    gate=json.loads(gate_report.read_text())
    if (gate.get('state') != 'PASS' or gate.get('passport_sha256') != digest(args.passport)
            or gate.get('candidate_sha') != args.candidate_sha or gate.get('run_id') != args.run_id):
        raise ValueError('Original gate report does not bind the passport')
    assets.append(gate_report)
    if rid != json.loads((ROOT/'releases/current.json').read_text())['release_id']:
        raise ValueError('Passport version differs from repository version')
    absent_release(rid)
    changelog=(ROOT/'CHANGELOG.md').read_text()
    heading='## '+rid+'\n'
    if changelog.count(heading) != 1: raise ValueError('Changelog must have exactly one release heading')
    notes=changelog.split(heading,1)[1].split('\n## ',1)[0].strip()
    notes += '\n\n最终内部DMG已通过本次受保护流程的两平台安装与全部六例回归。通行证及校验和见附件。'
    notes += '\n\n支持macOS15 Apple Silicon/Intel。首次内部自签安装可能需要在系统隐私与安全性中选择“仍要打开”；无需Apple开发者账号。管理员首次初始化为admin / 123456，首次登录改密；已有库保留现有密码。\n'
    notes_file=output/'release-notes.md'; notes_file.write_text(notes)
    # Preserve original names; include original package manifest and passport.
    assets += [args.package_manifest,args.passport,notes_file,ROOT/'docs/releases/02-installation.md']
    checksums=output/'SHA256SUMS.txt'
    checksums.write_text(''.join(f'{digest(path)}  {path.name}\n' for path in assets))
    assets.append(checksums)
    tag=api('git/tags',body={'tag':rid,'message':rid+' — internal release; protected package gate PASS',
                          'object':args.candidate_sha,'type':'commit'})
    ref=api('git/refs',body={'ref':'refs/tags/'+rid,'sha':tag['sha']})
    (output/'created-tag.json').write_text(json.dumps({'tag':tag,'ref':ref},indent=2)+'\n')
    command(['gh','release','create',rid,'--repo',REPO,'--verify-tag','--title',rid,
             '--notes-file',str(notes_file),*[str(a) for a in assets]])
    release=api('releases/tags/'+rid)
    actual=api('git/tags/'+api('git/ref/tags/'+rid)['object']['sha'])
    if actual['object']['sha'] != args.candidate_sha or actual['object']['type'] != 'commit' or release['name'] != rid:
        raise ValueError('Published tag/release differs from candidate')
    expected={path.name:digest(path) for path in assets}
    if {a['name'] for a in release['assets']} != set(expected): raise ValueError('Release asset set differs')
    for asset in release['assets']:
        if asset.get('digest') != 'sha256:'+expected[asset['name']]:
            raise ValueError('GitHub stored asset digest differs: '+asset['name'])
    return {'state':'PASS','release_id':rid,'candidate_sha':args.candidate_sha,'ci':ci,
            'release_url':release['html_url'],'assets':expected,'remote':remote,'jobs':jobs}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['preflight','publish'])
    parser.add_argument('--candidate-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--package-manifest',type=Path)
    parser.add_argument('--passport',type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--evidence-archives',type=Path)
    args=parser.parse_args()
    try:
        args.output.mkdir(parents=True,exist_ok=False)
        if args.operation=='publish' and not all((args.package_manifest,args.passport,args.run_id,args.evidence_archives)):
            raise ValueError('Publish requires original package, passport and run ID')
        result=preflight(args.candidate_sha,args.output) if args.operation=='preflight' else publish(args,args.output)
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('state','release_id','candidate_sha')}))
        return 0
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
        result={'state':'BLOCKED','release_eligible':False,'reason':str(error)}
        if args.output.is_dir() and not (args.output/'result.json').exists():
            (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result)); return 2


if __name__=='__main__':
    raise SystemExit(main())
