"""Adapter failure-path tests. No Herdr process, live panes, or model calls."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
MODULE = Path(__file__).resolve().parents[1] / "runtime" / "herdr_lab.py"
spec = importlib.util.spec_from_file_location("herdr_lab", MODULE)
lab_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab_module)


class FakeHerdr:
    def __init__(self):
        self.calls = []
        self.panes = {}
        self.next_id = 0
        self.fail_prompt = False
        self.prompt_calls = 0
        self.close_calls = 0

    def raw(self, args, session=True):
        self.calls.append(list(args))
        if args[:2] == ["agent", "read"]:
            return "Non-JSON terminal transcript\n任务执行完成\n"
        if args[:2] == ["pane", "read"]:
            return "Non-JSON visible terminal\nGrok 4.5 low default\n"
        if args == ["--version"]:
            return "herdr fake-version"
        raise AssertionError(f"Unexpected fake raw command: {args}")

    def call(self, args):
        self.calls.append(list(args))
        if args[:2] == ["api", "snapshot"]:
            return {"snapshot": {"workspaces": [{"workspace_id": "w1"}],
                                  "panes": list(copy.deepcopy(self.panes).values())}}
        if args[:2] in (["tab", "create"], ["pane", "split"]):
            self.next_id += 1
            pane = {"pane_id": f"w1:p{self.next_id}", "tab_id": "w1:t9", "workspace_id": "w1",
                    "terminal_id": f"terminal-{self.next_id}", "agent_status": "idle", "agent_session": None}
            self.panes[pane["pane_id"]] = pane
            return {"tab": {"tab_id": "w1:t9"}, "root_pane": copy.deepcopy(pane), "pane": copy.deepcopy(pane)}
        if args[:2] == ["agent", "start"]:
            pane = self.panes[args[args.index("--pane") + 1]]
            pane["name"] = args[2]
            pane["agent"] = "grok"
            pane["agent_session"] = {"kind": "id", "value": args[args.index("--session-id") + 1],
                                     "source": "fake-native", "agent": "grok"}
            return {"agent": copy.deepcopy(pane), "argv": list(args)}
        if args[:2] == ["agent", "get"]:
            return {"agent": copy.deepcopy(self.panes[args[2]])}
        if args[:2] == ["agent", "prompt"]:
            self.prompt_calls += 1
            if self.fail_prompt:
                raise OSError("crash after possible dispatch, before acknowledged result")
            return {"type": "agent_prompted", "agent": copy.deepcopy(self.panes[args[2]])}
        if args[:2] in (["agent", "read"], ["pane", "read"]):
            raise AssertionError("CLI read commands return plain text and must use raw")
        if args[:2] == ["pane", "close"]:
            self.close_calls += 1
            self.panes.pop(args[2])
            return {"type": "ok"}
        raise AssertionError(f"Unexpected fake API call: {args}")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        template = self.root / "role.txt"
        template.write_text("Role contract at {{project_root}} for {{run_id}}.", encoding="utf-8")
        self.config = {"schema_version": 1, "config_file": str(self.root / "config.json"),
                       "herdr_executable": sys.executable, "project_root": str(self.root),
                       "state_dir": str(self.root / "state"), "session": "default", "workspace_id": "w1",
                       "roles": {role: {"provider": "grok", "model": "grok-4.5", "effort": "low",
                                        "template_file": str(template), "temporary": role not in lab_module.MAIN_ROLES,
                                        "session_args": []} for role in lab_module.ROLES}}
        (self.root / "config.json").write_text(json.dumps(self.config), encoding="utf-8")
        self.fake = FakeHerdr()
        self.lab = lab_module.Lab(self.config, self.fake)
        self.lab.start("fixture-run", "worker,qa")
        self.body = self.root / "body.txt"
        self.body.write_text("Execute the assigned bounded local task.", encoding="utf-8")

    def send(self, message="task-one"):
        return self.lab.send("fixture-run", "worker", message, self.body)

    def evidence(self, phase, message="task-one"):
        record = self.lab.load("fixture-run")["messages"][message]
        evidence = {key: record[key] for key in ("run_id", "message_id", "destination_role", "pane_id",
                                                "session_ref", "expected_native_session_id", "body_sha256")}
        evidence.update({"phase": phase, "summary": "Agent evidence from an isolated fixture", "artifacts": [],
                         "pending_tools_or_approvals": []})
        if phase == "completed":
            artifact = self.root / "artifact.txt"
            artifact.write_text("independently inspectable fixture output", encoding="utf-8")
            evidence["artifacts"] = [{"path": str(artifact), "sha256": lab_module.digest(artifact.read_bytes())}]
        path = self.root / (phase + ".json")
        path.write_text(json.dumps(evidence), encoding="utf-8")
        return path

    def complete(self):
        for phase in ("received", "started", "completed"):
            self.lab.receipt("fixture-run", "task-one", phase, self.evidence(phase))

    def test_duplicate_message_does_not_resubmit(self):
        self.send()
        result = self.send()
        self.assertTrue(result["duplicate"])
        self.assertFalse(result["dispatched"])
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_conflicting_body_is_rejected_without_dispatch(self):
        self.send()
        self.body.write_text("A different task must have a different message ID", encoding="utf-8")
        with self.assertRaisesRegex(lab_module.LabError, "conflicts"):
            self.send()
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_pause_prevents_new_dispatch(self):
        first = self.lab.pause("fixture-run")
        with self.assertRaisesRegex(lab_module.LabError, "paused"):
            self.send()
        self.assertEqual(self.fake.prompt_calls, 0)
        resumed = self.lab.pause("fixture-run", resume=True)
        self.assertGreater(resumed["epoch"], first["epoch"])
        self.send()
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_crash_leaves_uncertain_and_does_not_blindly_retry(self):
        self.fake.fail_prompt = True
        with self.assertRaises(OSError):
            self.send()
        self.assertEqual(self.lab.load("fixture-run")["messages"]["task-one"]["state"], "uncertain")
        self.fake.fail_prompt = False
        result = self.send()
        self.assertEqual(result["message"]["state"], "uncertain")
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_recovered_submitting_is_uncertain_not_resubmitted(self):
        self.send()
        manifest = self.lab.load("fixture-run")
        manifest["messages"]["task-one"]["state"] = "submitting"
        self.lab.save(manifest)
        result = self.send()
        self.assertEqual(result["message"]["state"], "uncertain")
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_cleanup_refuses_non_owned_pane(self):
        manifest = self.lab.load("fixture-run")
        manifest["owned_panes"] = []
        self.lab.save(manifest)
        with self.assertRaisesRegex(lab_module.LabError, "not owned"):
            self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_session_identity_mismatch_prevents_send(self):
        binding = self.lab.load("fixture-run")["roles"]["worker"]
        self.fake.panes[binding["pane_id"]]["agent_session"]["value"] = "stale-native-session"
        with self.assertRaisesRegex(lab_module.LabError, "mismatched"):
            self.send()
        self.assertEqual(self.fake.prompt_calls, 0)

    def test_submission_success_is_not_completion(self):
        result = self.send()
        self.assertEqual(result["message"]["state"], "submitted")
        self.assertEqual(result["message"]["receipts"], [])
        with self.assertRaisesRegex(lab_module.LabError, "unresolved"):
            self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_completed_requires_prior_receipts_and_artifact(self):
        self.send()
        with self.assertRaisesRegex(lab_module.LabError, "earlier"):
            self.lab.receipt("fixture-run", "task-one", "completed", self.evidence("completed"))
        self.complete()
        self.assertEqual(self.lab.load("fixture-run")["messages"]["task-one"]["state"], "completed")

    def test_capture_and_cleanup_only_own_idle_temporary(self):
        self.send()
        self.complete()
        self.lab.capture("fixture-run", "worker")
        result = self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(result["closed"], ["worker"])
        self.assertEqual(self.fake.close_calls, 1)
        self.assertEqual(self.lab.load("fixture-run")["roles"]["qa"]["state"], "created")

    def test_capture_preserves_non_json_text_and_visible_footer(self):
        records = self.lab.capture("fixture-run", "worker")
        capture = records[0]
        recent = Path(capture["file"])
        visible = Path(capture["visible_file"])
        self.assertEqual(recent.suffix, ".txt")
        self.assertEqual(recent.read_text(encoding="utf-8"), "Non-JSON terminal transcript\n任务执行完成\n")
        self.assertIn("Grok 4.5 low default", visible.read_text(encoding="utf-8"))
        self.assertFalse(recent.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(lab_module.digest(recent.read_bytes()), capture["sha256"])
        self.assertEqual(lab_module.digest(visible.read_bytes()), capture["visible_sha256"])
        self.assertEqual(Path(capture["snapshot"]).suffix, ".json")

    def test_unknown_status_refuses_cleanup(self):
        binding = self.lab.load("fixture-run")["roles"]["worker"]
        self.lab.capture("fixture-run", "worker")
        self.fake.panes[binding["pane_id"]]["agent_status"] = "unknown"
        with self.assertRaises(lab_module.LabError):
            self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_completed_done_interactive_agent_can_be_cleaned_up(self):
        self.send()
        self.complete()
        binding = self.lab.load("fixture-run")["roles"]["worker"]
        self.fake.panes[binding["pane_id"]].update({"agent_status": "done", "interactive_ready": True})
        self.lab.capture("fixture-run", "worker")
        result = self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(result["closed"], ["worker"])
        self.assertEqual(self.fake.close_calls, 1)

    def test_working_blocked_unknown_remain_ineligible_for_cleanup(self):
        self.send()
        self.complete()
        self.lab.capture("fixture-run", "worker")
        binding = self.lab.load("fixture-run")["roles"]["worker"]
        for status in ("working", "blocked", "unknown"):
            with self.subTest(status=status):
                self.fake.panes[binding["pane_id"]]["agent_status"] = status
                with self.assertRaises(lab_module.LabError):
                    self.lab.cleanup("fixture-run", "worker")
                self.assertEqual(self.fake.close_calls, 0)

    def test_main_role_cleanup_is_prohibited(self):
        self.lab.start("main-run", "research")
        with self.assertRaisesRegex(lab_module.LabError, "temporary"):
            self.lab.cleanup("main-run", "research")
        self.assertEqual(self.fake.close_calls, 0)

    def test_capture_before_receipt_cannot_authorize_cleanup(self):
        self.send()
        self.lab.capture("fixture-run", "worker")
        self.complete()
        with self.assertRaisesRegex(lab_module.LabError, "receipt"):
            self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_config_rejects_session_identity_override(self):
        self.config["roles"]["worker"]["session_args"] = ["--session-id", "wrong"]
        path = self.root / "config.json"
        path.write_text(json.dumps(self.config), encoding="utf-8")
        with self.assertRaisesRegex(lab_module.LabError, "session identity"):
            lab_module.load_config(path)

    def test_pending_approval_in_terminal_receipt_prevents_cleanup(self):
        self.send()
        for phase in ("received", "started"):
            self.lab.receipt("fixture-run", "task-one", phase, self.evidence(phase))
        source = self.evidence("completed")
        evidence = json.loads(source.read_text(encoding="utf-8"))
        evidence["pending_tools_or_approvals"] = ["request-still-pending"]
        source.write_text(json.dumps(evidence), encoding="utf-8")
        self.lab.receipt("fixture-run", "task-one", "completed", source)
        self.lab.capture("fixture-run", "worker")
        with self.assertRaisesRegex(lab_module.LabError, "pending or unknown"):
            self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_always_approve_and_short_session_alias_are_rejected(self):
        for extras in (["--always-approve"], ["--permission-mode", "bypassPermissions"], ["-s", "bad"], ["--effort", "high"]):
            with self.subTest(extras=extras):
                self.config["roles"]["worker"]["session_args"] = extras
                path = self.root / "config.json"
                path.write_text(json.dumps(self.config), encoding="utf-8")
                with self.assertRaises(lab_module.LabError):
                    lab_module.load_config(path)

    def test_state_owner_lock_rejects_another_writer(self):
        with lab_module.state_lock(self.lab.state):
            with self.assertRaisesRegex(lab_module.LabError, "Another wrapper"):
                with lab_module.state_lock(self.lab.state):
                    self.fail("Second state owner acquired the lock")


if __name__ == "__main__":
    unittest.main(verbosity=2)
