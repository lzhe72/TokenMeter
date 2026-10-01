#!/usr/bin/env python3
"""Revalidate and archive local release originals; never upload release assets."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_local_gate',ROOT/'scripts/local_gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def new_directory(path):
    path=Path(path).absolute()
    gate.require(not path.exists() and all(not p.is_symlink() for p in [path,*path.parents]),'Destination already exists or is a symlink')
    path.mkdir(parents=True,mode=0o700)
    return path

def copy_evidence(source,destination):
    source=Path(source).absolute();destination=Path(destination).absolute()
    gate.require(source.is_dir() and all(not p.is_symlink() for p in [source,*source.parents]),'Invalid evidence source')
    files=[]
    for file in sorted(source.rglob('*')):
        gate.require(not file.is_symlink() and (file.is_file() or file.is_dir()),'Unsafe evidence entry')
        if file.is_file():files.append(file)
    new_directory(destination)
    index={}
    for file in files:
        relative=file.relative_to(source);target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with file.open('rb') as read, target.open('xb') as write:
            os.chmod(target,0o600);shutil.copyfileobj(read,write)
        digest=gate.sha256(file)
        gate.require(gate.sha256(target)==digest,'Copied evidence changed')
        index[str(relative)]=digest
    return index

def existing_or_new_directory(path):
    """Create a version directory, or reuse it without following a symlink."""
    path=Path(path).absolute()
    gate.require(all(not p.is_symlink() for p in [path,*path.parents]),'Installation directory is a symlink')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    gate.require(path.is_dir() and all(not p.is_symlink() for p in [path,*path.parents]),'Invalid installation directory')
    return path

def publish_final_dmg(archive_dir,release_id,descriptor,*,dmg_root=None):
    """Expose only a completed, hash-checked archive's original DMG by name."""
    gate.require(isinstance(release_id,str) and gate.re.fullmatch(r'v\d+\.\d+\.\d+-\d{8}T\d{6}Z',release_id),'Invalid release identity')
    gate.require(isinstance(descriptor,dict),'Missing DMG descriptor')
    filename=f'TokenMeter-{release_id}-internal.dmg'
    gate.require(descriptor.get('path')==filename,'Unexpected final DMG filename')
    archive_dir=Path(archive_dir).absolute()
    marker=archive_dir/'INCOMPLETE.json'
    gate.require(not marker.exists() and not marker.is_symlink(),'Incomplete release archive')
    receipt=gate.read_json(gate.safe_path(archive_dir,'release-index.json'))
    gate.require(isinstance(receipt,dict) and isinstance(receipt.get('files'),dict),
                 'Invalid release archive index')
    gate.require(receipt.get('schema_version')==2 and receipt.get('state')=='PASS'
                 and receipt.get('release_id')==release_id
                 and receipt.get('dmg')=='package/'+filename
                 and receipt['files'].get('package/'+filename)==descriptor.get('sha256')
                 and receipt.get('dmg_sha256')==descriptor.get('sha256')
                 and isinstance(receipt.get('milestone_sha'),str)
                 and gate.re.fullmatch(r'[0-9a-f]{40}',receipt['milestone_sha'])
                 and isinstance(receipt.get('milestone_tree'),str)
                 and gate.re.fullmatch(r'[0-9a-f]{40}',receipt['milestone_tree'])
                 and receipt.get('milestone_sha')==receipt.get('candidate_sha')==receipt.get('git_head')
                 and receipt.get('milestone_tree')==receipt.get('candidate_tree')
                 and isinstance(receipt.get('master_tip_sha'),str)
                 and gate.re.fullmatch(r'[0-9a-f]{40}',receipt['master_tip_sha'])
                 and receipt.get('remote_source_state')=='PENDING'
                 and receipt.get('github_release') is False,
                 'Release archive does not authorize this DMG')
    for relative,field in (('package/package-manifest.json','package_manifest_sha256'),
                           ('evidence/'+release_id+'.passport.json','passport_sha256')):
        digest=receipt.get(field)
        gate.require(receipt['files'].get(relative)==digest,
                     'Release index source digest differs')
        gate.checked_file(archive_dir,{'path':relative,'sha256':digest})
    source=gate.checked_file(archive_dir/'package',descriptor)
    version_dir=existing_or_new_directory((ROOT/'dmg' if dmg_root is None else Path(dmg_root))/release_id)
    target=version_dir/filename
    gate.require(not target.exists() and not target.is_symlink(),'Final DMG already exists')
    temporary=None
    try:
        fd,name=tempfile.mkstemp(prefix='.TokenMeter-copy-',suffix='.part',dir=version_dir)
        temporary=Path(name)
        with os.fdopen(fd,'wb') as write,source.open('rb') as read:
            shutil.copyfileobj(read,write)
            write.flush();os.fsync(write.fileno())
        gate.require(gate.sha256(temporary)==descriptor['sha256'],'Copied DMG changed')
        os.link(temporary,target,follow_symlinks=False)
        try:
            gate.checked_file(version_dir,{'path':filename,'sha256':descriptor['sha256'],'bytes':descriptor.get('bytes',source.stat().st_size)})
        except (OSError,ValueError,KeyError,TypeError):
            target.unlink()
            raise
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def verify_inputs(gate_dir,manifest):
    gate_dir=gate_dir.resolve(strict=True);manifest=manifest.resolve(strict=True)
    result=gate.read_json(gate_dir/'gate.json')
    rid=result.get('release_id')
    gate.require(isinstance(rid,str) and gate.re.fullmatch(r'v\d+\.\d+\.\d+-\d{8}T\d{6}Z',rid),'Invalid release identity')
    passport_path=gate.safe_path(gate_dir,rid+'.passport.json')
    passport=gate.read_json(passport_path)
    for key in ('state','scope','run_id','supplemental_run_id','release_id','candidate_sha','candidate_tree','package_manifest_sha256','report','expected_cases','host','started_at','finished_at','granular_evidence','granular_workbook','final_product_result'):
        gate.require(passport.get(key)==result.get(key),f'Passport differs from parent gate: {key}')
    gate.require(result.get('state')=='PASS' and result.get('release_eligible') is True and result.get('phase')=='release','No release qualification')
    gate.require(passport.get('release_eligible') is True and passport.get('phase')=='release','Passport does not authorize release')
    gate.require(passport.get('schema_version')==2 and passport.get('distribution_profile')=='internal' and passport.get('storage')=='local_only' and passport.get('github_release') is False,'Wrong passport policy')
    gate.require(gate.sha256(manifest)==result['package_manifest_sha256'],'Package manifest differs')
    supplemental_id=result.get('supplemental_run_id')
    gate.require(isinstance(supplemental_id,str) and gate.re.fullmatch(r'local-[0-9a-f]{32}',supplemental_id)
                 and supplemental_id!=result['run_id'],'Supplemental run identity is invalid or reused')
    gate.require(not gate.git('status','--porcelain'),'Working tree changed')
    gate.require(gate.git('rev-parse','HEAD^{tree}')==result['candidate_tree'],'Current source differs from tested tree')
    gate.require(gate.git('rev-parse',result['candidate_sha']+'^{tree}')==result['candidate_tree'],'Candidate mapping differs')
    required_inputs={'tests/feature_matrix.json','tests/acceptance.json','tests/datasets.json',
                     'tests/test_cases.json','tests/granular_login_variants.json','tests/granular_update_variants.json',
                     'docs/catalog.json','scripts/granular_gate.py','sop/SOP-014-e2e.md',
                     'sop/SOP-018-release-gate.md','apps/desktop/package-lock.json'}
    gate.require(set(passport.get('source_inputs',{}))==required_inputs,'Passport source input set differs')
    for relative,digest in passport.get('source_inputs',{}).items():
        gate.checked_file(ROOT,{'path':relative,'sha256':digest})
    gate.require(bool(passport.get('source_inputs')),'No source inputs')
    report_path=gate.checked_file(gate_dir,result['report'])
    primary_path=gate.safe_path(gate_dir,'granular/result.json')
    report,package=gate.verify_report(report_path,manifest,run_id=supplemental_id,
        candidate_sha=result['candidate_sha'],candidate_tree=result['candidate_tree'],
        not_before=result['started_at'],parent_run_id=result['run_id'],
        parent_report_sha256=gate.sha256(primary_path))
    gate.require(passport.get('artifacts')==package['artifacts'],'Passport artifact set differs')
    gate.require(isinstance(result.get('granular_evidence'),dict),'Missing detailed release evidence')
    granular=gate.verify_granular_run(gate_dir,manifest,run_id=result['run_id'],candidate_sha=result['candidate_sha'],
                                      candidate_tree=result['candidate_tree'],not_before=result['started_at'])
    gate.require(result['granular_evidence']==granular,'Detailed release evidence differs from originals')
    gate.require(isinstance(result.get('granular_workbook'),dict),'Missing combined TC workbook evidence')
    workbook=gate.verify_granular_workbook(gate_dir,run_id=result['run_id'])
    gate.require(result['granular_workbook']==workbook,'Combined TC workbook evidence differs from originals')
    final_descriptor=result.get('final_product_result')
    gate.require(isinstance(final_descriptor,dict) and final_descriptor.get('path')=='final-product-result.json',
                 'Missing final product result descriptor')
    gate.checked_file(gate_dir,final_descriptor)
    final_result=gate.verify_final_product_result(gate_dir,run_id=result['run_id'],
                                                  candidate_sha=result['candidate_sha'],candidate_tree=result['candidate_tree'])
    gate.require(final_descriptor==final_result,'Final product result differs from originals')
    return result,passport,report,package

def _git_result(*args):
    return subprocess.run(['git',*args],cwd=ROOT,text=True,capture_output=True,check=False)

def verify_local_milestone(result,passport,package,*,milestone_sha,milestone_tree,expected_master_tip=None):
    """Bind the tested original to one clean, locally integrated commit."""
    sha_pattern=r'[0-9a-f]{40}'
    for name,value in (('milestone SHA',milestone_sha),('milestone tree',milestone_tree),
                       ('candidate SHA',result.get('candidate_sha')),('candidate tree',result.get('candidate_tree'))):
        gate.require(isinstance(value,str) and gate.re.fullmatch(sha_pattern,value),f'Invalid {name}')
    gate.require(result['candidate_sha']==milestone_sha and result['candidate_tree']==milestone_tree,
                 'Explicit local milestone differs from tested candidate')
    for name,source in (('passport',passport),('package',package)):
        gate.require(isinstance(source,dict) and source.get('release_id')==result.get('release_id')
                     and source.get('candidate_sha')==milestone_sha
                     and source.get('candidate_tree')==milestone_tree,
                     f'{name} does not belong to the local milestone')
    rid=result.get('release_id')
    gate.require(isinstance(rid,str) and gate.re.fullmatch(r'v\d+\.\d+\.\d+-\d{8}T\d{6}Z',rid),
                 'Invalid local milestone release ID')
    current=gate.read_json(ROOT/'releases/current.json')
    version=gate.read_json(ROOT/'releases'/rid/'00-manifest.json')
    gate.require(current.get('release_id')==rid and version.get('release_id')==rid,
                 'Checked-out version does not own the release')
    status=_git_result('status','--porcelain')
    gate.require(status.returncode==0 and not status.stdout.strip(),'Local milestone checkout is not clean')
    head=_git_result('rev-parse','--verify','HEAD^{commit}')
    tree=_git_result('rev-parse','--verify','HEAD^{tree}')
    candidate_tree=_git_result('rev-parse','--verify',milestone_sha+'^{tree}')
    gate.require(all(item.returncode==0 for item in (head,tree,candidate_tree))
                 and head.stdout.strip()==milestone_sha
                 and tree.stdout.strip()==milestone_tree
                 and candidate_tree.stdout.strip()==milestone_tree,
                 'Local checkout SHA/tree differs from tested milestone')
    master=_git_result('rev-parse','--verify','refs/heads/master^{commit}')
    if master.returncode!=0:raise gate.Blocked('Local master ref is unavailable')
    master_tip=master.stdout.strip()
    gate.require(bool(gate.re.fullmatch(sha_pattern,master_tip)),'Invalid local master ref')
    ancestry=_git_result('merge-base','--is-ancestor',milestone_sha,'refs/heads/master')
    if ancestry.returncode==1:raise gate.Invalid('Tested milestone is not an ancestor of local master')
    if ancestry.returncode!=0:raise gate.Blocked('Cannot verify local master ancestry')
    if expected_master_tip is not None:
        gate.require(master_tip==expected_master_tip,'Local master advanced while archiving')
    return {'milestone_sha':milestone_sha,'milestone_tree':milestone_tree,'master_tip_sha':master_tip}

def archive(gate_dir,manifest,destination,*,milestone_sha,milestone_tree):
    result,passport,report,package=verify_inputs(gate_dir,manifest)
    milestone=verify_local_milestone(result,passport,package,
                                     milestone_sha=milestone_sha,milestone_tree=milestone_tree)
    destination=new_directory(destination)
    marker=destination/'INCOMPLETE.json'
    gate.write_new(marker,{'release_id':result['release_id'],'state':'COPYING','started_at':time.time()})
    index={}
    # Signed Apps contain legitimate framework symlinks. Archive the verified
    # distributable files, never follow/copy arbitrary source directory entries.
    package_dir=new_directory(destination/'package')
    for name,descriptor in package['artifacts'].items():
        source=gate.checked_file(manifest.parent,descriptor)
        target=package_dir/descriptor["path"]
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        gate.require(not target.exists(),'Artifact filename collision')
        with source.open('rb') as read,target.open('xb') as write:
            os.chmod(target,0o600);shutil.copyfileobj(read,write)
        gate.require(gate.sha256(target)==descriptor['sha256'],'Archive artifact changed')
        index[str(target.relative_to(destination))]=descriptor['sha256']
    shutil.copyfile(manifest,package_dir/'package-manifest.json');os.chmod(package_dir/'package-manifest.json',0o600)
    index['package/package-manifest.json']=gate.sha256(manifest)
    tree_tool=gate.module('local_archive_tree',ROOT/'scripts/package_release_dmg.py')
    app_trees={}
    for name in ('app','update_app'):
        info=package[name]
        relative=info.get('relative_path',info.get('path'))
        source=gate.safe_path(manifest.parent,relative,directory=True)
        for item in source.rglob('*'):
            if item.is_symlink():
                gate.require(item.resolve(strict=True).is_relative_to(source.resolve()),'App symlink escapes its signed bundle')
        target=package_dir/relative
        gate.require(not target.exists(),'App destination exists')
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        gate.command(['/usr/bin/ditto',str(source),str(target)])
        gate.require(tree_tool.tree_sha256(target)==info['tree_sha256'],'Archived App changed')
        app_trees['package/'+relative]=info['tree_sha256']
    evidence=copy_evidence(gate_dir,destination/'evidence')
    index.update({'evidence/'+path:digest for path,digest in evidence.items()})
    # Stable installation is always build100. The controlled build101 is evidence.
    dmg_name=package['artifacts']['dmg']['path']
    readme=destination/'INSTALL.txt'
    readme.write_text('TokenMeter '+result['release_id']+'\n\n安装包：package/'+dmg_name+'\n平台：macOS 15 / Intel (x64)\n更新试验101仅供测试，不是稳定安装包。\n\nAPI默认 http://127.0.0.1:49176；更新源默认 http://127.0.0.1:49177/version.json。\n新生产库初始管理员 admin / 123456，首次登录须改密；已有生产库保持原密码。\n替换已有App前请退出并保存备份。此包为内部自签，未宣称Apple公证。\n',encoding='utf-8');os.chmod(readme,0o600)
    index['INSTALL.txt']=gate.sha256(readme)
    receipt={'schema_version':2,'release_id':result['release_id'],'state':'PASS','candidate_sha':result['candidate_sha'],
             'candidate_tree':result['candidate_tree'],'git_head':milestone_sha,'run_id':result['run_id'],
             'dmg':'package/'+dmg_name,'passport':'evidence/'+result['release_id']+'.passport.json',
             'passport_sha256':index['evidence/'+result['release_id']+'.passport.json'],
             'package_manifest_sha256':index['package/package-manifest.json'],
             'dmg_sha256':index['package/'+dmg_name],
             'files':index,'app_trees':app_trees,'archived_at':time.time(),'github_release':False,
             'remote_source_state':'PENDING',**milestone}
    for name,digest in index.items():gate.checked_file(destination,{'path':name,'sha256':digest})
    verify_inputs(destination/'evidence',package_dir/'package-manifest.json')
    verify_local_milestone(result,passport,package,milestone_sha=milestone_sha,
                            milestone_tree=milestone_tree,expected_master_tip=milestone['master_tip_sha'])
    gate.write_new(destination/'release-index.json',receipt)
    marker.unlink()
    installation_dmg=publish_final_dmg(destination,result['release_id'],package['artifacts']['dmg'])
    return {**receipt,'installation_dmg':str(installation_dmg)}

def post_status(gate_dir,manifest,pr):
    result,passport,report,package=verify_inputs(gate_dir,manifest)
    repo=json.loads(gate.command(['gh','repo','view','--json','nameWithOwner']))['nameWithOwner']
    gate.require(repo=='lzhe72/TokenMeter','Unexpected Git repository')
    remote=json.loads(gate.command(['gh','pr','view',str(pr),'--json','headRefOid,baseRefName,state']))
    gate.require(remote['headRefOid']==result['candidate_sha'] and remote['baseRefName']=='master' and remote['state']=='OPEN','Remote PR is not the tested candidate')
    description=f"Local macOS15 x64: {len(result['expected_cases'])} E2E passed; DMG {package['artifacts']['dmg']['sha256'][:12]}"
    response=gate.command(['gh','api',f"repos/{repo}/statuses/{result['candidate_sha']}",'-f','state=success','-f','context=local-final-package','-f','description='+description])
    status=json.loads(response)
    gate.require(status.get('state')=='success' and status.get('context')=='local-final-package','Git status readback differs')
    return {'state':'PASS','scope':'verified_local_candidate_status','candidate_sha':result['candidate_sha'],'pr':pr,'status_id':status['id']}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['verify','archive','status'])
    p.add_argument('--gate-dir',type=Path,required=True);p.add_argument('--package-manifest',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--pr',type=int)
    p.add_argument('--milestone-sha');p.add_argument('--milestone-tree')
    a=p.parse_args(argv)
    try:
        if a.action=='verify':
            gate.require(a.milestone_sha is not None and a.milestone_tree is not None,
                         'Local milestone SHA/tree are required')
            result,passport,_,package=verify_inputs(a.gate_dir,a.package_manifest)
            milestone=verify_local_milestone(result,passport,package,
                milestone_sha=a.milestone_sha,milestone_tree=a.milestone_tree)
            answer={'state':'PASS','release_id':result['release_id'],'candidate_sha':result['candidate_sha'],
                    'scope':'local_originals_and_milestone_reverified',**milestone}
        elif a.action=='status':
            gate.require(a.pr is not None,'--pr is required');answer=post_status(a.gate_dir,a.package_manifest,a.pr)
        else:
            gate.require(a.milestone_sha is not None and a.milestone_tree is not None,
                         'Local milestone SHA/tree are required')
            result,*_=verify_inputs(a.gate_dir,a.package_manifest)
            target=a.output or ROOT/'dmg'/result['release_id']/'release-archive'
            answer=archive(a.gate_dir,a.package_manifest,target,
                           milestone_sha=a.milestone_sha,milestone_tree=a.milestone_tree)
        print(json.dumps(answer,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
        print(json.dumps({'state':'BLOCKED' if isinstance(e,(gate.Blocked,FileNotFoundError)) else 'FAIL','release_eligible':False,'error':str(e)},ensure_ascii=False));return 2 if isinstance(e,(gate.Blocked,FileNotFoundError)) else 1

if __name__=='__main__':raise SystemExit(main())
