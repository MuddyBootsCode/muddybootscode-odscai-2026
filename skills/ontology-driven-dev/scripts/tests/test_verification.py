"""Real commands must supply evidence; documentation edits cannot create it."""
import subprocess
import sys
from test_ontology_check import Repo, check, state, git, SCRIPTS


class Verification(Repo):
    def setUp(self):
        super().setUp()
        self.edit('src/types.ts', 'price: number', 'price: string')
        self.edit('mcp/schema.py', 'One item.', 'One item line.')
        self.edit('ontology/orders.md', 'Initial.', 'Item representation reviewed.')

    def verify(self, code, rule='An Order is larger'):
        return subprocess.run([sys.executable, str(SCRIPTS / 'ontology_verify.py'),
                               '--rule', rule, '--', sys.executable, '-c', code],
                              cwd=self.root, capture_output=True, text=True)

    def status(self):
        r = check(self.root, '--changed')
        self.assertEqual(r.returncode, 0, r.stderr)
        return state(self.root)[-1]

    def test_acknowledgment_is_not_verification(self):
        rec = self.status()
        self.assertEqual(rec.get('review'), 'acknowledged')
        self.assertEqual(rec['verification'][0]['status'], 'not_run')

    def test_passing_command_records_output_and_becomes_stale_after_edit(self):
        run = self.verify("print('counterexample checked')")
        self.assertEqual(run.returncode, 0, run.stderr)
        evidence = self.status()['verification'][0]
        self.assertEqual(evidence['status'], 'passed')
        self.assertIn('counterexample checked', (self.root / evidence['output']).read_text())
        self.edit('src/types.ts', 'price: string', 'price: boolean')
        self.assertEqual(self.status()['verification'][0]['status'], 'stale')

    def test_failed_command_supersedes_previous_success(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        self.assertNotEqual(self.verify("raise AssertionError('duplicate person')").returncode, 0)
        self.assertEqual(self.status()['verification'][0]['status'], 'failed')

    def test_command_that_edits_source_cannot_verify_original_snapshot(self):
        result = self.verify("from pathlib import Path; Path('src/types.ts').write_text('changed')")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('changed during', result.stderr)

    def test_unknown_rule_does_not_execute_command(self):
        result = self.verify("from pathlib import Path; Path('SHOULD_NOT_EXIST').touch()", 'unknown rule')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'SHOULD_NOT_EXIST').exists())

    def test_changed_test_invalidates_evidence(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        self.edit('tests/itemPlacement.test.ts', 'placement', 'different check')
        # Gate edit remains reviewable; evidence is stale regardless of review status.
        check(self.root, '--changed')
        self.assertEqual(state(self.root)[-1]['verification'][0]['status'], 'stale')

    def test_ambiguous_rule_does_not_execute_command(self):
        self.edit('ontology/orders.md', '## Vocabulary', '- An Order is larger than nothing.\n\n## Vocabulary')
        result = self.verify("from pathlib import Path; Path('SHOULD_NOT_EXIST').touch()")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'SHOULD_NOT_EXIST').exists())

    def test_unrelated_ontology_edit_does_not_acknowledge_gate_change(self):
        self.edit('tests/itemPlacement.test.ts', 'placement', 'changed behavior')
        result = check(self.root, '--changed')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('gate review', result.stderr)

    def test_staged_check_cannot_claim_worktree_evidence(self):
        git(self.root, 'add', '-A')
        self.assertEqual(self.verify('print(1)').returncode, 0)
        self.edit('tests/itemPlacement.test.ts', 'placement', 'unstaged behavior')
        self.assertEqual(self.verify('print(2)').returncode, 0)
        check(self.root, '--changed', '--staged')
        self.assertNotEqual(state(self.root)[-1]['verification'][0]['status'], 'passed')

    def test_missing_executable_supersedes_success(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        result = subprocess.run([sys.executable, str(SCRIPTS / 'ontology_verify.py'),
                                 '--rule', 'An Order is larger', '--', '/missing/ontology-command'],
                                cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.status()['verification'][0]['status'], 'unavailable')

    def test_timeout_supersedes_success(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        result = subprocess.run([sys.executable, str(SCRIPTS / 'ontology_verify.py'),
                                 '--rule', 'An Order is larger', '--timeout', '0.05', '--',
                                 sys.executable, '-c', 'import time; time.sleep(2)'],
                                cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.status()['verification'][0]['status'], 'unavailable')

    def test_deleted_output_is_not_passing_evidence(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        rec = self.status()['verification'][0]
        (self.root / rec['output']).unlink()
        self.assertEqual(self.status()['verification'][0]['status'], 'unavailable')

    def test_tampered_output_is_not_passing_evidence(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        rec = self.status()['verification'][0]
        (self.root / rec['output']).write_text('invented success')
        self.assertEqual(self.status()['verification'][0]['status'], 'unavailable')

    def test_symlink_source_cannot_hide_changed_external_input(self):
        self.write('.gitignore', 'external.py\n')
        self.write('external.py', 'original')
        source = self.root / 'src/types.ts'
        source.unlink()
        source.symlink_to('../external.py')
        result = self.verify('print(1)')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stderr.lower())
