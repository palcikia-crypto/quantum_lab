#!/usr/bin/env python3
"""brain_api.py — HTTP API для мозга (порт 8300)."""
import os, sys, json, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
import brain

PORT = 8300

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == '/state': self._send(200, json.dumps(brain.get_full_state(), ensure_ascii=False, indent=2))
            elif u.path == '/health':
                h = brain.health_check()
                self._send(200, json.dumps({'healthy': h['healthy'], 'issues': h['issues']}, ensure_ascii=False, indent=2))
            elif u.path == '/decisions':
                s = brain.get_full_state()
                self._send(200, json.dumps(brain.decide(s), ensure_ascii=False, indent=2))
            elif u.path == '/history': self._send(200, json.dumps(brain.get_history(), ensure_ascii=False, indent=2))
            elif u.path == '/': self._send(200, '{"endpoints":["/state","/health","/decisions","/history"]}')
            else: self._send(404, '{"error":"not found"}')
        except Exception as e:
            self._send(500, json.dumps({'error': str(e)}))

if __name__ == '__main__':
    brain.init_brain_db()
    print(f'Brain API: http://127.0.0.1:{PORT}')
    HTTPServer(('127.0.0.1', PORT), H).serve_forever()
