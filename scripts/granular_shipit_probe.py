"""Negative runner-isolation probes in synthetic home directories (not App E2E)."""
from pathlib import Path
import hashlib
import os
import tempfile
from unittest.mock import patch
import local_e2e as runner

def probe(parent: Path, run_id: str) -> dict:
    results=[]
    for kind in ('cache','launchd','byhost'):
        with tempfile.TemporaryDirectory(prefix='shipit-'+kind+'-',dir=parent) as name:
            home=Path(name);(home/'Library/Caches').mkdir(parents=True)
            sentinel=home/'untouched';sentinel.write_bytes(b'owned-independent-sentinel')
            if kind=='cache':
                cache=home/'Library/Caches'/runner.SHIPIT_LABEL;cache.mkdir();(cache/'foreign').write_bytes(b'preserve')
            if kind=='byhost':
                pref=home/'Library/Preferences/ByHost';pref.mkdir(parents=True)
                (pref/(runner.SHIPIT_LABEL+'.fixture.plist')).write_bytes(b'foreign-preference')
            before={str(p.relative_to(home)):hashlib.sha256(p.read_bytes()).hexdigest() for p in home.rglob('*') if p.is_file()}
            blocked=False
            with patch.object(runner.Path,'home',return_value=home),patch.object(runner,'_shipit_job_present',return_value=kind=='launchd'):
                try:runner.prepare_owned_shipit(run_id)
                except runner.Blocked:blocked=True
            after={str(p.relative_to(home)):hashlib.sha256(p.read_bytes()).hexdigest() for p in home.rglob('*') if p.is_file()}
            results.append({'kind':kind,'blocked':blocked,'unchanged':before==after,'files':before})
    return {'scope':'runner_isolation_components','run_id':run_id,'results':results,'passed':all(r['blocked'] and r['unchanged'] for r in results)}
