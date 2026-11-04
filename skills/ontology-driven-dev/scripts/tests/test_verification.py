"""Real commands must supply evidence; documentation edits cannot create it."""
import json
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

    def test_timeout_stops_descendant_processes(self):
        import time
        child = "import time; from pathlib import Path; time.sleep(.5); Path('late-side-effect').touch()"
        parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(2)"
        result = subprocess.run([sys.executable, str(SCRIPTS / 'ontology_verify.py'),
                                 '--rule', 'An Order is larger', '--timeout', '.2', '--',
                                 sys.executable, '-c', parent], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        time.sleep(.6)
        self.assertFalse((self.root / 'late-side-effect').exists())


class StopWarnsOnEvidence(Repo):
    """The Stop hook says when recorded evidence is bad, even with a clean diff.
    With exit 0 Claude Code shows nothing from stderr, so the warning is a JSON
    systemMessage on stdout, which the host draws for the user."""

    def verify(self, code):
        return subprocess.run([sys.executable, str(SCRIPTS / 'ontology_verify.py'),
                               '--rule', 'An Order is larger', '--', sys.executable, '-c', code],
                              cwd=self.root, capture_output=True, text=True)

    def stop(self):
        r = check(self.root, '--changed', '--stop')
        self.assertEqual(r.returncode, 0, r.stderr)  # advisory, never a block
        return r

    def message(self, r):
        return json.loads(r.stdout)['systemMessage']  # stdout is one JSON object and nothing else

    def test_failed_evidence_warns_at_stop_with_a_clean_diff(self):
        self.assertNotEqual(self.verify("raise AssertionError('bad order')").returncode, 0)
        message = self.message(self.stop())
        self.assertIn('An Order is larger', message)
        self.assertIn('failed', message)

    def test_stale_evidence_warns_after_an_edit_anywhere(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        self.write('README.md', 'changed\n')
        message = self.message(self.stop())
        self.assertIn('An Order is larger', message)
        self.assertIn('stale', message)

    def test_passing_evidence_is_quiet(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        r = self.stop()
        self.assertEqual(r.stdout.strip(), '')
        self.assertNotIn('Verification', r.stderr)

    def test_review_summary_and_warning_share_one_message_on_an_acknowledged_change(self):
        self.assertEqual(self.verify('print(1)').returncode, 0)
        self.edit('src/types.ts', 'price: number', 'price: string')
        self.edit('mcp/schema.py', 'One item.', 'One item line.')
        self.edit('ontology/orders.md', 'Initial.', 'Item representation reviewed.')
        message = self.message(self.stop())
        self.assertIn('Review: acknowledged', message)
        self.assertIn('stale', message)

    def test_without_stop_the_warning_is_plain_text_on_stderr(self):
        self.assertNotEqual(self.verify("raise AssertionError('bad order')").returncode, 0)
        r = check(self.root, '--changed')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '')
        self.assertIn('failed', r.stderr)

    def test_a_block_still_speaks_through_stderr_and_exit_2(self):
        self.edit('src/types.ts', 'price: number', 'price: string')
        self.edit('mcp/schema.py', 'One item.', 'One item line.')
        r = check(self.root, '--changed', '--stop')
        self.assertEqual(r.returncode, 2)
        self.assertIn('Item', r.stderr)
        self.assertEqual(r.stdout.strip(), '')


class EvidenceUnavailableDoesNotBlock(Repo):
    """A fingerprint the runner cannot take makes evidence unavailable; it never fails review."""

    def setUp(self):
        super().setUp()
        run = subprocess.run([sys.executable, str(SCRIPTS / 'ontology_verify.py'),
                              '--rule', 'An Order is larger', '--', sys.executable, '-c', 'print(1)'],
                             cwd=self.root, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        (self.root / 'docs-link').symlink_to('README.md')  # unrelated, untracked

    def test_unrelated_commit_is_not_blocked(self):
        r = check(self.root, '--changed', '--staged')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('unavailable', r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec['review'], 'not_required')
        self.assertEqual(rec['verification'][0]['status'], 'unavailable')

    def test_acknowledged_change_still_passes_review(self):
        self.edit('src/types.ts', 'price: number', 'price: string')
        self.edit('mcp/schema.py', 'One item.', 'One item line.')
        self.edit('ontology/orders.md', 'Initial.', 'Item representation reviewed.')
        r = check(self.root, '--changed')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state(self.root)[-1]['review'], 'acknowledged')

    def test_skip_marker_still_works(self):
        self.edit('src/types.ts', 'price: number', 'price: string')
        self.edit('mcp/schema.py', 'One item.', 'One item line.')
        r = check(self.root, '--changed', env={'ONTOLOGY_SKIP': 'rename only'})
        self.assertEqual(r.returncode, 0, r.stderr)
