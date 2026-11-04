#!/usr/bin/env python3
"""Live local ontology observer. Start explicitly; tests only run after a button click."""
from __future__ import annotations
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import webbrowser

PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / 'skills/ontology-driven-dev/scripts'
sys.path.insert(0, str(SCRIPTS))
from ontology_lib import load_all
from ontology_evidence import rule_key, statuses, evidence_dir


def configuration(root, onts):
    path = root / 'ontology/checks.json'
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {'checks'} or not isinstance(data['checks'], list):
            raise ValueError('expected an object containing a checks list')
        rules = {(o['domain'], r['text']): r for o in onts for r in o['invariants']}
        result = {}
        for entry in data['checks']:
            if not isinstance(entry, dict) or set(entry) != {'domain', 'rule', 'command'}:
                raise ValueError('each check needs domain, exact rule text and command')
            command = entry['command']
            if not isinstance(command, list) or not command or not all(isinstance(x, str) and x and '\0' not in x for x in command):
                raise ValueError('command must be a nonempty argv list')
            key = (entry['domain'], entry['rule'])
            if key not in rules:
                raise ValueError('check does not match an exact ontology rule')
            ident = rule_key(key[0], rules[key])
            if ident in result:
                raise ValueError('duplicate check for a rule')
            result[ident] = command
        return result
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f'ontology/checks.json: {exc}') from exc


def command_hash(command):
    return hashlib.sha256(json.dumps(command).encode()).hexdigest()


class ObserverState:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.running = None
        self.last_error = ''

    def read(self):
        error = ''
        with self.lock:
            running = self.running
        try:
            onts = load_all(self.root)
            evidence = statuses(self.root, onts)
        except Exception as exc:
            return {'root': str(self.root), 'rules': [], 'questions': [], 'error': f'Unable to check: {exc}', 'updated': time.time()}
        try:
            commands = configuration(self.root, onts)
        except ValueError as exc:
            commands, error = {}, str(exc)
        # A fresh comparison detects editor changes even if no agent turn runs.
        try:
            check = subprocess.run([sys.executable, str(SCRIPTS / 'ontology_check.py'), '--changed'],
                                   cwd=self.root, capture_output=True, text=True, timeout=25)
            review = (check.stdout + '\n' + check.stderr).strip()
            if check.returncode not in (0, 2):
                error = 'Unable to compare changes: ' + review
            validation = subprocess.run([sys.executable, str(SCRIPTS / 'ontology_check.py'), '--validate'],
                                        cwd=self.root, capture_output=True, text=True, timeout=25)
            if validation.returncode:
                error = 'Ontology validation failed: ' + validation.stdout + validation.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            review, error = '', f'Unable to check: {exc}'
        rows = []
        index = 0
        for ontology in onts:
            for rule in ontology['invariants']:
                entry = dict(evidence[index]); index += 1
                ident = rule_key(ontology['domain'], rule)
                entry.update(id=ident, authority=rule['status'], gate=rule['gate'],
                             files=ontology['governs'], lastCommand=entry.get('command'), command=commands.get(ident),
                             commandHash=command_hash(commands[ident]) if ident in commands else None,
                             running=running == ident, busy=running is not None,
                             outputText='', lastRun=None)
                if entry.get('output'):
                    path = Path(entry['output'])
                    # Evidence cannot turn this endpoint into an arbitrary file reader.
                    if path.parent.resolve() == evidence_dir(self.root).resolve() and not path.is_symlink():
                        try:
                            entry['lastRun'] = path.stat().st_mtime
                            with path.open('r', errors='replace') as stream:
                                entry['outputText'] = stream.read(65536)
                                if stream.read(1): entry['outputText'] += '\n[Output truncated at 64 KiB]'
                        except OSError:
                            entry['outputText'] = 'Output unavailable.'
                rows.append(entry)
        if not onts and not error: error = 'No ontology found. Set up ontology/ at the repository root.'
        return {'root': str(self.root), 'rules': rows, 'error': error or self.last_error,
                'review': review, 'updated': time.time(),
                'questions': [{'domain': o['domain'], 'text': o['sections']['Open questions']}
                              for o in onts if o['sections'].get('Open questions')]}

    def run(self, payload):
        if set(payload) != {'id', 'commandHash'}:
            raise ValueError('Select a configured check; commands cannot be supplied by the browser.')
        with self.lock:
            if self.running is not None: raise ValueError('A check is already running.')
            onts = load_all(self.root)
            commands = configuration(self.root, onts)
            ident = payload['id']
            if not isinstance(ident, str) or ident not in commands or command_hash(commands[ident]) != payload['commandHash']:
                raise ValueError('Check configuration changed. Refresh and review the command before running.')
            o, r = next((o, r) for o in onts for r in o['invariants'] if rule_key(o['domain'], r) == ident)
            command = [sys.executable, str(SCRIPTS / 'ontology_verify.py'), '--domain', o['domain'], '--rule', r['text'], '--', *commands[ident]]
            self.running, self.last_error = ident, ''
        def worker():
            try:
                result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
                if result.returncode and not result.stdout.strip():
                    self.last_error = result.stderr[-3000:] or 'Acceptance command could not start.'
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.last_error = f'Acceptance command unavailable: {exc}'
            finally:
                self.running = None
        threading.Thread(target=worker, daemon=True).start()


def make_server(root: Path, port=0):
    state = ObserverState(root.resolve())
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Keep tokens and evidence out of access logs.

        def send(self, code, body, content_type='application/json'):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, api=True):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host or self.headers.get('Origin', 'http://' + host) != 'http://' + host:
                return False
            return not api or secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)

        def do_GET(self):
            if not self.allowed(api=self.path != '/'):
                self.send(403, {'error': 'This local observer requires its launch link.'}); return
            if self.path == '/':
                self.send(200, (PLUGIN / 'codex/observer/index.html').read_text(), 'text/html; charset=utf-8')
            elif self.path == '/api/state':
                self.send(200, state.read())
            else: self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.allowed():
                self.send(403, {'error': 'This local observer requires its launch link.'}); return
            if self.path != '/api/run':
                self.send(404, {'error': 'Not found'}); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > 8192: raise ValueError('Invalid request size')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict): raise ValueError('Expected an object')
                state.run(payload)
            except (ValueError, TypeError, OSError) as exc:
                self.send(400, {'error': str(exc)}); return
            self.send(202, {'status': 'running'})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.token = token
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--state', type=Path, help='Use the same state file as your hooks/evidence runner')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--open', action='store_true', help='Open the launch URL in your default browser')
    args = parser.parse_args()
    root = args.root.resolve()
    os.environ['ONTOLOGY_STATE'] = str(args.state.resolve()) if args.state else os.environ.get('ONTOLOGY_STATE', str(root / '.codex/ontology-state.jsonl'))
    server = make_server(root, args.port)
    url = f'http://127.0.0.1:{server.server_port}/#' + server.token
    print(url, flush=True)
    if args.open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__':
    main()
