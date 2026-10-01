"""An owned denied HTTP target on this Mac, with independent request evidence."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import secrets
import subprocess
import threading
from urllib.request import Request, ProxyHandler, build_opener

class DeniedTarget:
    def __init__(self):
        result=subprocess.run(['/usr/sbin/ipconfig','getifaddr','en0'],capture_output=True,text=True,check=False)
        address=result.stdout.strip()
        parsed=ipaddress.ip_address(address)
        if result.returncode or not parsed.is_private or parsed.is_loopback:raise ValueError('An owned private IPv4 interface is required')
        self.requests=[];self.token=secrets.token_urlsafe(32);owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                if self.path=='/observations':
                    if self.headers.get('Authorization')!='Bearer '+owner.token:
                        self.send_error(403);return
                    body=json.dumps({'requests':owner.requests}).encode()
                else:
                    owner.requests.append({'route':self.path,'probe':self.headers.get('X-TM-Test-Probe')=='1','time':datetime.now(timezone.utc).isoformat()})
                    body=b'owned-denied-target'
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        self.server=ThreadingHTTPServer((address,0),Handler)
        self.server.daemon_threads=False
        self.url=f'http://{address}:{self.server.server_port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        try:
            with build_opener(ProxyHandler({})).open(Request(self.url+'/probe',headers={'X-TM-Test-Probe':'1'}),timeout=5) as res:
                if res.read()!=b'owned-denied-target':raise ValueError('Denied target probe mismatch')
        except BaseException:
            self.close();raise
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        return not self.thread.is_alive()
