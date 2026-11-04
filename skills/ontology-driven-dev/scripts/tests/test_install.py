"""install.sh keeps the checker's runtime files out of the repository."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_ontology_check import git, SCRIPTS

INSTALL = SCRIPTS / 'install.sh'


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q', '-b', 'main')
        (self.root / 'README.md').write_text('hi\n')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'init', '--author', 't <t@t>')

    def tearDown(self):
        self.tmp.cleanup()

    def install(self):
        return subprocess.run(['bash', str(INSTALL)], cwd=self.root, capture_output=True, text=True)

    def test_state_file_and_evidence_dir_are_ignored(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        ignored = (self.root / '.gitignore').read_text().splitlines()
        self.assertIn('.claude/ontology-state.jsonl', ignored)
        self.assertIn('.claude/ontology-state.evidence/', ignored)

    def test_running_twice_adds_the_lines_once(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        lines = (self.root / '.gitignore').read_text().splitlines()
        self.assertEqual(lines.count('.claude/ontology-state.jsonl'), 1)
        self.assertEqual(lines.count('.claude/ontology-state.evidence/'), 1)

    def test_existing_gitignore_is_kept(self):
        (self.root / '.gitignore').write_text('node_modules/\n')
        self.assertEqual(self.install().returncode, 0)
        lines = (self.root / '.gitignore').read_text().splitlines()
        self.assertEqual(lines[0], 'node_modules/')
        self.assertIn('.claude/ontology-state.jsonl', lines)


if __name__ == '__main__':
    unittest.main()
