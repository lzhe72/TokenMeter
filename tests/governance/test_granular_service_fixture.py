import concurrent.futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import sys
from pathlib import Path
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from granular_service_fixture import ServiceFixture

class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.observed=[]; observed=self.observed
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length',0)))
                observed.append((self.path,body))
                self.send_response(201);self.send_header('Content-Length','15');self.end_headers();self.wfile.write(b'{"actual":true}')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.fixture=ServiceFixture(f'http://127.0.0.1:{self.server.server_port}')
    def tearDown(self):
        self.assertTrue(self.fixture.close());self.server.shutdown();self.server.server_close();self.thread.join()
    def control(self,mode,**values):
        req=Request(self.fixture.control_url+'/mode',data=json.dumps({'mode':mode,'route':'/v1/auth/login',**values}).encode(),headers={'Authorization':'Bearer '+self.fixture.token})
        with urlopen(req,timeout=5) as res:return res.status
    def request(self):
        req=Request(self.fixture.url+'/v1/auth/login',data=b'{}',headers={'Authorization':'Bearer synthetic-token','X-TM-Test-Probe':'1'})
        with urlopen(req,timeout=5) as res:return res.status,res.read()
    def test_real_forward_and_redacted_audit(self):
        self.assertEqual(self.request(),(201,b'{"actual":true}'))
        self.assertEqual(len(self.observed),1)
        record=self.fixture.requests[0];self.assertTrue(record['forwarded']);self.assertTrue(record['probe'])
        self.assertEqual(record['authorization_sha256'],hashlib.sha256(b'Bearer synthetic-token').hexdigest())
        self.assertNotIn('synthetic-token',json.dumps(record))
    def test_faults_never_forward_and_recover(self):
        self.control('unavailable')
        with self.assertRaises(HTTPError) as error:self.request()
        self.assertEqual(error.exception.code,503);self.assertFalse(self.observed)
        self.control('offline')
        with self.assertRaises(Exception):self.request()
        self.assertFalse(self.observed)
        self.control('normal');self.assertEqual(self.request()[0],201)
    def test_delay_waits_for_explicit_recovery(self):
        self.control('delay')
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future=pool.submit(self.request)
            deadline=time.monotonic()+3
            while not self.fixture.requests and time.monotonic()<deadline:time.sleep(.01)
            self.assertFalse(future.done());self.assertFalse(self.observed)
            self.control('normal');self.assertEqual(future.result(timeout=5)[0],201)
        self.assertGreater(self.fixture.requests[0]['delayed_seconds'],0)
    def test_control_requires_token(self):
        with self.assertRaises(HTTPError) as error:urlopen(self.fixture.control_url+'/observations')
        self.assertEqual(error.exception.code,403)

    def test_new_request_finishes_before_explicitly_released_old_request(self):
        self.control('delay')
        with concurrent.futures.ThreadPoolExecutor() as pool:
            old=pool.submit(self.request)
            deadline=time.monotonic()+3
            while not self.fixture.requests and time.monotonic()<deadline:time.sleep(.01)
            self.control('normal',release_delayed=False)
            self.assertEqual(self.request(),(201,b'{"actual":true}'))
            self.assertFalse(old.done())
            self.assertEqual(len(self.observed),1)
            release=Request(self.fixture.control_url+'/release-delayed',data=b'{}',headers={'Authorization':'Bearer '+self.fixture.token})
            with urlopen(release,timeout=5) as response:self.assertEqual(response.status,200)
            self.assertEqual(old.result(timeout=5),(201,b'{"actual":true}'))
            self.assertEqual(len(self.observed),2)

if __name__=='__main__':unittest.main()
