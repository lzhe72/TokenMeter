#!/usr/bin/env python3
"""Serve an already released, hash-verified candidate on this Mac's loopback.

Input is a completed local version directory created by local_release.py.
This loader checks candidate bytes and passport binding. It does not issue a
passport or claim same-uid local files provide independent authentication.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def safe_file(root, relative):
    if not isinstance(relative,str):raise ValueError('Invalid release asset path')
    path = root / relative
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or '..' in Path(relative).parts or any(p.is_symlink() for p in (path, *path.parents))
            or not path.resolve().is_relative_to(root.resolve()) or not path.is_file()):
        raise ValueError('Release asset is missing or has an unsafe path')
    return path


def load_release(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root,*root.parents)) or (root/'INCOMPLETE.json').exists():
        raise ValueError('Incomplete or unsafe local archive')
    index=json.loads(safe_file(root,'release-index.json').read_text())
    manifest_path = safe_file(root, 'package/package-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    rid = manifest.get('release_id', '')
    if not re.fullmatch(r'v\d+\.\d+\.\d+-\d{8}T\d{6}Z', rid):
        raise ValueError('Invalid release ID')
    passport = json.loads(safe_file(root, 'evidence/'+rid+'.passport.json').read_text())
    if (index.get('state')!='PASS' or index.get('release_id')!=rid or index.get('candidate_sha')!=manifest.get('candidate_sha') or index.get('github_release') is not False
        or manifest.get('schema_version')!=2 or manifest.get('scope')!='final_package'
        or passport.get('schema_version')!=2 or passport.get('storage')!='local_only' or passport.get('github_release') is not False):
        raise ValueError('Not a completed local Electron release')
    if (passport.get('state') != 'PASS' or passport.get('release_eligible') is not True
            or manifest.get('distribution_profile') != 'internal'
            or passport.get('distribution_profile') != 'internal'
            or passport.get('release_id') != rid
            or not re.fullmatch(r'[a-f0-9]{40}', manifest.get('candidate_sha', ''))
            or passport.get('candidate_sha') != manifest['candidate_sha']
            or passport.get('package_manifest_sha256') != digest(manifest_path)):
        raise ValueError('Release passport does not bind this internal candidate')
    artifact = manifest['artifacts']['candidate_zip']
    archive = safe_file(root/'package', artifact['path'])
    if digest(archive) != artifact['sha256'] or archive.stat().st_size != artifact['bytes']:
        raise ValueError('Candidate zip differs from the tested release')
    signature = manifest['signatures']['candidate_ed_signature']
    if len(base64.b64decode(signature, validate=True)) != 64:
        raise ValueError('Invalid update signature')
    app = manifest['app']
    if not re.fullmatch(r'\d+', app['build']) or not re.fullmatch(r'\d+\.\d+\.\d+', app['version']):
        raise ValueError('Invalid candidate version')
    return {'manifest': manifest, 'archive': archive.read_bytes(), 'signature': signature}


def routes_for(bundle, port=49177):
    if type(port) is not int or not 1024<=port<=65535:
        raise ValueError('Invalid loopback server port')
    manifest,payload,signature=bundle['manifest'],bundle['archive'],bundle['signature']
    app=manifest['app']
    metadata={'schema_version':1,'version':app['version'],'build':app['build'],
              'url':f'http://127.0.0.1:{port}/candidate.zip','sha256':hashlib.sha256(payload).hexdigest(),
              'bytes':len(payload),'ed25519_signature':signature}
    return {'/version.json':('application/json',json.dumps(metadata).encode()),
            '/candidate.zip':('application/octet-stream',payload),
            '/healthz':('application/json',json.dumps({'release_id':manifest['release_id'],
                'candidate_sha':manifest['candidate_sha'],'build':app['build']}).encode())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', type=Path, required=True)
    parser.add_argument('--port',type=int,default=49177)
    args = parser.parse_args()
    try:
        routes = routes_for(load_release(args.release_dir),args.port)
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                route = routes.get(self.path)
                if route is None:
                    self.send_error(404)
                    return
                content_type, body = route
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *_args):
                pass
        with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
            print(f'TokenMeter updates: http://127.0.0.1:{args.port}/version.json', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'state': 'BLOCKED', 'reason': str(error)}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
