"""Exercise observer HTTP boundary and real acceptance commands."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
import urllib.request
import urllib.error

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / 'skills/ontology-driven-dev/scripts/tests'))
from test_ontology_check import Repo
SCRIPT = PLUGIN / 'codex/scripts/ontology_observer.py'


class Observer(Repo):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location('observer', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.write('.gitignore', '.claude/\n__pycache__/\n')
        self.rule = 'An Order is larger than any Item in it.'
        self.command = [sys.executable, '-c', "from pathlib import Path; assert Path('README.md').read_text() == 'hi\\n', 'wrong content'"]
        self.config()
        self.server = self.module.make_server(self.root, port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def config(self):
        self.write('ontology/checks.json', json.dumps({'checks': [
            {'domain': 'demo', 'rule': self.rule, 'command': self.command}]}))

    def request(self, path='/api/state', data=None, token=True, origin=None, host=None):
        headers = {'Authorization': 'Bearer ' + self.server.token} if token else {}
        if origin: headers['Origin'] = origin
        if host: headers['Host'] = host
        if data is not None: headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def row(self):
        return self.request()['rules'][0]

    def run_check(self):
        row = self.row()
        self.request('/api/run', {'id': row['id'], 'commandHash': row['commandHash']})
        for _ in range(80):
            result = self.row()
            if not result['running']: return result
            time.sleep(.05)
        self.fail('check did not finish')

    def test_real_run_fail_repair_and_stale(self):
        self.assertEqual(self.row()['status'], 'not_run')
        self.assertEqual(self.run_check()['status'], 'passed')
        self.write('README.md', 'wrong')
        self.assertEqual(self.row()['status'], 'stale')
        failed = self.run_check()
        self.assertEqual(failed['status'], 'failed')
        self.assertIn('wrong content', failed['outputText'])
        self.write('README.md', 'hi\n')
        self.assertEqual(self.run_check()['status'], 'passed')

    def test_api_requires_token_and_rejects_other_origins(self):
        for kwargs in [{'token':False}, {'origin':'https://example.invalid'}, {'host':'example.invalid'}]:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(**kwargs)
            self.assertEqual(caught.exception.code,403)
            caught.exception.close()

    def test_browser_cannot_supply_an_arbitrary_command(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/api/run', {'id':'unknown', 'commandHash':'x', 'command':['touch','oops']})
        self.assertEqual(caught.exception.code,400)
        caught.exception.close()
        self.assertFalse((self.root/'oops').exists())

    def test_changed_command_requires_refresh_before_run(self):
        row=self.row()
        self.command=[sys.executable,'-c',"raise AssertionError('new command')"]
        self.config()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/api/run', {'id':row['id'],'commandHash':row['commandHash']})
        self.assertEqual(caught.exception.code,400)
        caught.exception.close()

    def test_invalid_config_visible_and_disables_run(self):
        self.write('ontology/checks.json', '{broken')
        state=self.request()
        self.assertIn('checks.json',state['error'])
        self.assertIsNone(state['rules'][0]['command'])

    def test_page_contains_no_token_or_external_asset(self):
        page=urllib.request.urlopen(self.url).read().decode()
        self.assertNotIn(self.server.token,page)
        self.assertNotIn('https://',page)
        self.assertIn('Ontology observer',page)

    def test_open_questions_preserve_source_answerer_and_impact(self):
        self.edit('ontology/orders.md', '## Vocabulary',
                  '## Open questions\n\n- Which scope?\n  Source: owner.\n  Answerer: developer.\n  Impact: blocks widening.\n\n## Vocabulary')
        question = self.request()['questions'][0]['text']
        self.assertIn('Answerer: developer.', question)
        self.assertIn('Impact: blocks widening.', question)

    def test_only_one_check_can_run_at_a_time(self):
        self.command = [sys.executable, '-c', 'import time; time.sleep(1)']
        self.config()
        row = self.row()
        payload = {'id': row['id'], 'commandHash': row['commandHash']}
        self.request('/api/run', payload)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/api/run', payload)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        for _ in range(80):
            if not self.row()['running']: break
            time.sleep(.05)
        else: self.fail('check did not finish')
