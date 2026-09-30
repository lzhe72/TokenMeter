#!/usr/bin/env python3
"""Serve an already released, hash-verified candidate on this Mac's loopback.

The operator must obtain these assets from the protected GitHub Release. This
loader validates their binding; it does not issue or authenticate a passport.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def safe_file(root, relative):
    path = root / relative
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or '..' in Path(relative).parts or any(p.is_symlink() for p in (path, *path.parents))
            or not path.resolve().is_relative_to(root.resolve()) or not path.is_file()):
        raise ValueError('Release asset is missing or has an unsafe path')
    return path


def load_release(root):
    root = Path(root).resolve()
    manifest_path = safe_file(root, 'package-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    rid = manifest.get('release_id', '')
    if not re.fullmatch(r'v\d+\.\d+\.\d+-\d{8}T\d{6}Z', rid):
        raise ValueError('Invalid release ID')
    passport = json.loads(safe_file(root, rid+'.passport.json').read_text())
    if (passport.get('state') != 'PASS' or passport.get('release_eligible') is not True
            or manifest.get('distribution_profile') != 'internal'
            or passport.get('distribution_profile') != 'internal'
            or passport.get('release_id') != rid
            or not re.fullmatch(r'[a-f0-9]{40}', manifest.get('candidate_sha', ''))
            or passport.get('candidate_sha') != manifest['candidate_sha']
            or passport.get('package_manifest_sha256') != digest(manifest_path)):
        raise ValueError('Release passport does not bind this internal candidate')
    artifact = manifest['artifacts']['candidate_zip']
    archive = safe_file(root, artifact['path'])
    if digest(archive) != artifact['sha256'] or archive.stat().st_size != artifact['bytes']:
        raise ValueError('Candidate zip differs from the tested release')
    signature = manifest['signatures']['candidate_ed_signature']
    if len(base64.b64decode(signature, validate=True)) != 64:
        raise ValueError('Invalid update signature')
    app = manifest['app']
    if not re.fullmatch(r'\d+', app['build']) or not re.fullmatch(r'\d+\.\d+\.\d+', app['version']):
        raise ValueError('Invalid candidate version')
    return {'manifest': manifest, 'archive': archive.read_bytes(), 'signature': signature}


def routes_for(bundle):
    manifest, payload, signature = bundle['manifest'], bundle['archive'], bundle['signature']
    app = manifest['app']
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">'
        '<channel><title>TokenMeter internal updates</title><item>'
        f'<title>{escape(manifest["release_id"])}</title>'
        f'<sparkle:version>{escape(app["build"])}</sparkle:version>'
        f'<sparkle:shortVersionString>{escape(app["version"])}</sparkle:shortVersionString>'
        f'<sparkle:minimumSystemVersion>{escape(app["minimum_macos"])}</sparkle:minimumSystemVersion>'
        f'<enclosure url="http://127.0.0.1:49177/candidate.zip" sparkle:edSignature="{signature}" '
        f'length="{len(payload)}" type="application/octet-stream" />'
        '</item></channel></rss>\n').encode()
    return {'/appcast.xml': ('application/xml', feed),
            '/candidate.zip': ('application/octet-stream', payload),
            '/healthz': ('application/json', json.dumps({'release_id': manifest['release_id'],
                'candidate_sha': manifest['candidate_sha'], 'build': app['build']}).encode())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        routes = routes_for(load_release(args.release_dir))
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
        with ThreadingHTTPServer(('127.0.0.1', 49177), Handler) as server:
            print('TokenMeter updates: http://127.0.0.1:49177/appcast.xml', flush=True)
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
