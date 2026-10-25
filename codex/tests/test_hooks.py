"""Real Codex event payloads against the shared checker in throwaway repos."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / "codex/scripts/ontology_hook.py"
sys.path.insert(0, str(PLUGIN / "skills/ontology-driven-dev/scripts/tests"))
from test_ontology_check import ONTOLOGY, TYPES_TS


class CodexHooks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex ontology ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.write("ontology/orders.md", ONTOLOGY.replace('  - "src/types.ts <-> mcp/schema.py"', ''))
        self.write("src/types.ts", TYPES_TS)
        self.git("add", ".")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "Fixture")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, text=True,
                              capture_output=True, check=True).stdout

    def write(self, path, text):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    def invoke(self, event="Stop", hook=HOOK, **fields):
        payload = {"cwd": str(self.root), "hook_event_name": event,
                   "session_id": "test-session", "turn_id": "test-turn", **fields}
        env = {k: v for k, v in os.environ.items()
               if k not in {"ONTOLOGY_SKIP", "ONTOLOGY_STATE"}}
        result = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                                cwd=PLUGIN, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def change_entity(self):
        self.write("src/types.ts", TYPES_TS.replace("price: number", "price: string"))

    def test_session_loads_target_ontology_not_plugin_directory(self):
        result = self.invoke("SessionStart")
        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Item", context)
        self.assertIn("Order", context)
        self.assertFalse((self.root / ".claude").exists())

    def test_stop_blocks_governed_change_and_records_codex_state(self):
        self.change_entity()
        result = self.invoke()
        self.assertEqual(result["decision"], "block")
        self.assertIn("Item", result["reason"])
        state = self.root / ".codex/ontology-state.jsonl"
        records = [json.loads(line) for line in state.read_text().splitlines()]
        self.assertEqual(records[-1]["exit"], 2)
        self.assertFalse((self.root / ".claude").exists())

    def test_repeat_stop_reports_unresolved_issue_without_loop(self):
        self.change_entity()
        result = self.invoke(stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertIn("Item", result["systemMessage"])

    def test_repair_releases_stop(self):
        self.change_entity()
        self.assertEqual(self.invoke()["decision"], "block")
        self.write("ontology/orders.md", (self.root / "ontology/orders.md").read_text()
                   + "\n- Item price representation changed; domain meaning reviewed.\n")
        self.assertNotIn("decision", self.invoke())

    def test_post_tool_returns_context_without_rejecting_completed_tool(self):
        self.change_entity()
        result = self.invoke("PostToolUse", tool_name="apply_patch",
                             tool_input={"command": "*** Begin Patch\n*** End Patch"})
        self.assertNotIn("decision", result)
        self.assertIn("Item", result["hookSpecificOutput"]["additionalContext"])

    def test_clean_workspace_has_no_issue(self):
        self.assertEqual(self.invoke(), {})
        self.assertEqual(self.invoke("PostToolUse", tool_name="Bash"), {})

    def test_missing_ontology_is_quiet_without_creating_state(self):
        shutil.rmtree(self.root / "ontology")
        for event in ("SessionStart", "PostToolUse", "Stop"):
            self.assertEqual(self.invoke(event), {})
        self.assertFalse((self.root / ".codex").exists())

    def test_malformed_ontology_blocks_once_and_stays_visible(self):
        self.write("ontology/orders.md", "# Incomplete ontology\n")
        self.assertEqual(self.invoke()["decision"], "block")
        repeat = self.invoke(stop_hook_active=True)
        self.assertNotIn("decision", repeat)
        self.assertIn("systemMessage", repeat)

    def test_target_subdirectory_finds_repo_root(self):
        self.change_entity()
        self.assertEqual(self.invoke(cwd=str(self.root / "src"))["decision"], "block")

    def test_plugin_survives_relocation_without_claude_runtime(self):
        bundle = self.root / "installed plugin"
        shutil.copytree(PLUGIN / "codex", bundle / "codex",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(PLUGIN / "skills", bundle / "skills",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.change_entity()
        result = self.invoke(hook=bundle / "codex/scripts/ontology_hook.py")
        self.assertEqual(result["decision"], "block")

    def test_invalid_payload_fails_visibly(self):
        result = subprocess.run([sys.executable, str(HOOK)], input="{}",
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cwd", result.stderr)

    def test_unborn_repository_does_not_report_clean_changes(self):
        self.git("update-ref", "-d", "HEAD")
        result = self.invoke()
        self.assertEqual(result["decision"], "block")
        self.assertIn("initial commit", result["reason"])

    def test_validation_warnings_remain_visible_without_blocking(self):
        path = self.root / "ontology/orders.md"
        path.write_text(path.read_text().replace(" [gate: `itemPlacement.test.ts`]", ""))
        result = self.invoke()
        self.assertNotIn("decision", result)
        self.assertIn("without a gate", result.get("systemMessage", ""))
        post = self.invoke("PostToolUse", tool_name="Bash")
        self.assertIn("without a gate", post.get("hookSpecificOutput", {}).get("additionalContext", ""))

    def test_nested_ontology_cannot_silently_pass_root_relative_globs(self):
        (self.root / "app").mkdir()
        shutil.move(self.root / "ontology", self.root / "app/ontology")
        shutil.move(self.root / "src", self.root / "app/src")
        self.git("add", "-A")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "Nested project")
        self.write("app/src/types.ts", TYPES_TS.replace("price: number", "price: string"))
        result = self.invoke(cwd=str(self.root / "app"))
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("Git root", result["reason"])

    def test_broken_git_index_does_not_record_a_clean_diff(self):
        self.change_entity()
        (self.root / ".git/index").write_bytes(b"broken-index")
        result = self.invoke()
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("Git", result["reason"])
        records = [json.loads(line) for line in (self.root / ".codex/ontology-state.jsonl").read_text().splitlines()]
        self.assertFalse(any(record["mode"] == "changed" and record["exit"] == 0 for record in records))

    def test_manifest_hook_command_handles_plugin_path_with_spaces(self):
        bundle = self.root / "plugin with spaces"
        shutil.copytree(PLUGIN / "codex", bundle / "codex",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(PLUGIN / "skills", bundle / "skills",
                        ignore=shutil.ignore_patterns("__pycache__"))
        hook_config = json.loads((PLUGIN / "codex/hooks.json").read_text())
        command = hook_config["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.change_entity()
        env = {k: v for k, v in os.environ.items()
               if k not in {"ONTOLOGY_SKIP", "ONTOLOGY_STATE"}}
        env["PLUGIN_ROOT"] = str(bundle)
        result = subprocess.run(["bash", "-c", command], cwd=PLUGIN, env=env,
                                input=json.dumps({"cwd": str(self.root), "hook_event_name": "Stop"}),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
