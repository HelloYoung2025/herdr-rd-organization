"""Adapter failure-path tests. No Herdr process, live panes, or model calls."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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
        self.next_tab = 0
        self.fail_prompt = False
        self.prompt_calls = 0
        self.close_calls = 0
        self.rename_behavior = "apply"
        self.drop_label_on_start = False

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
            if args[:2] == ["tab", "create"]:
                self.next_tab += 1
                tab_id = f"w1:t{self.next_tab}"
            else:
                tab_id = self.panes[args[2]]["tab_id"]
            pane = {"pane_id": f"w1:p{self.next_id}", "tab_id": tab_id, "workspace_id": "w1",
                    "terminal_id": f"terminal-{self.next_id}", "agent_status": "idle", "agent_session": None}
            self.panes[pane["pane_id"]] = pane
            return {"tab": {"tab_id": tab_id}, "root_pane": copy.deepcopy(pane), "pane": copy.deepcopy(pane)}
        if args[:2] == ["pane", "rename"]:
            if self.rename_behavior == "error":
                raise OSError("Pane rename failed")
            if self.rename_behavior != "ignore":
                self.panes[args[2]]["label"] = args[3]
            return {"type": "pane_renamed"}
        if args[:2] == ["pane", "get"]:
            pane = copy.deepcopy(self.panes[args[2]])
            if self.rename_behavior == "wrong-pane" and "label" in pane:
                pane["pane_id"] = "w1:unrelated"
            elif self.rename_behavior == "wrong-tab" and "label" in pane:
                pane["tab_id"] = "w1:unrelated-tab"
            return {"pane": pane}
        if args[:2] == ["agent", "start"]:
            pane = self.panes[args[args.index("--pane") + 1]]
            if self.drop_label_on_start:
                pane.pop("label", None)
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

    def test_all_roles_have_visible_titles_distinct_from_agent_names(self):
        result = self.lab.start("visible-title-run")
        titles = {"research": "Research Engineer", "orchestrator": "Engineering Orchestrator",
                  "worker": "Worker", "qa": "Independent QA", "curator": "Skills Curator"}
        for role, binding in result["roles"].items():
            pane = self.fake.panes[binding["pane_id"]]
            self.assertEqual(pane.get("label"), titles[role] + " | itle-run")
            self.assertEqual(binding.get("pane_label"), pane["label"])
            self.assertTrue(binding.get("pane_label_confirmed"))
            self.assertNotEqual(pane["label"], pane["name"])

    def test_run_titles_differ_and_unrelated_panes_keep_their_labels(self):
        self.fake.panes["w1:other"] = {"pane_id": "w1:other", "tab_id": "w1:other-tab",
                                       "label": "User's existing pane"}
        original = copy.deepcopy(self.fake.panes["w1:other"])
        first = self.lab.load("fixture-run")["roles"]["worker"]
        second = self.lab.start("other-run", "worker")["roles"]["worker"]
        self.assertNotEqual(self.fake.panes[first["pane_id"]].get("label"),
                            self.fake.panes[second["pane_id"]].get("label"))
        self.assertEqual(self.fake.panes["w1:other"], original)

    def test_missing_or_failed_title_prevents_starting_the_agent(self):
        for behavior in ("ignore", "error", "wrong-pane", "wrong-tab"):
            with self.subTest(behavior=behavior):
                self.fake.rename_behavior = behavior
                run_id = "rename-" + behavior
                before = sum(c[:2] == ["agent", "start"] for c in self.fake.calls)
                with self.assertRaises((lab_module.LabError, OSError)):
                    self.lab.start(run_id, "worker,qa")
                result = self.lab.load(run_id)
                self.assertEqual(result["status"], "creation_uncertain")
                self.assertFalse(result["roles"]["worker"].get("pane_label_confirmed"))
                self.assertEqual(len(result["owned_panes"]), 1)
                self.assertEqual(before, sum(c[:2] == ["agent", "start"] for c in self.fake.calls))

    def test_title_disappearing_during_startup_is_not_reported_as_success(self):
        self.fake.drop_label_on_start = True
        with self.assertRaisesRegex(lab_module.LabError, "label"):
            self.lab.start("startup-title-loss", "worker,qa")
        result = self.lab.load("startup-title-loss")
        self.assertEqual(result["status"], "creation_uncertain")
        self.assertFalse(result["roles"]["worker"].get("pane_label_confirmed"))
        self.assertEqual(len(result["owned_panes"]), 1)

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

    def test_recovered_submitting_reconciles_saved_response_without_replay(self):
        self.send()
        manifest = self.lab.load("fixture-run")
        manifest["messages"]["task-one"]["state"] = "submitting"
        self.lab.save(manifest)
        result = self.send()
        self.assertEqual(result["message"]["state"], "submitted")
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_legacy_submitting_without_outcome_becomes_uncertain(self):
        self.send()
        manifest = self.lab.load("fixture-run")
        record = manifest["messages"]["task-one"]
        Path(record["submission_evidence_file"]).unlink()
        for key in ("submission_state", "submission_evidence_file", "submission_evidence_sha256", "submission_response"):
            record.pop(key, None)
        record["state"] = "submitting"
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

    def test_creation_cannot_adopt_existing_pane_or_wrong_workspace(self):
        original_call = self.fake.call
        original_panes = copy.deepcopy(self.fake.panes)
        for scenario in ("existing", "wrong-workspace", "identity-changed"):
            with self.subTest(scenario=scenario):
                def corrupted(args):
                    if args[:2] != ["tab", "create"]:
                        return original_call(args)
                    if scenario == "existing":
                        pane = copy.deepcopy(next(iter(original_panes.values())))
                        return {"tab": {"tab_id": pane["tab_id"]}, "root_pane": pane}
                    result = original_call(args)
                    if scenario == "wrong-workspace":
                        result["root_pane"]["workspace_id"] = "w2"
                    else:
                        self.fake.panes[result["root_pane"]["pane_id"]]["tab_id"] = "w1:other-tab"
                    return result
                self.fake.call = corrupted
                before = len([call for call in self.fake.calls if call[:2] in (["pane", "rename"], ["agent", "start"])])
                with self.assertRaises(lab_module.LabError):
                    self.lab.start("creation-" + scenario, "worker")
                manifest = self.lab.load("creation-" + scenario)
                self.assertEqual(manifest["status"], "creation_uncertain")
                self.assertEqual(manifest["owned_panes"], [])
                self.assertEqual(before, len([call for call in self.fake.calls if call[:2] in (["pane", "rename"], ["agent", "start"])]))
                for pane_id, pane in original_panes.items():
                    self.assertEqual(self.fake.panes[pane_id], pane)
        self.fake.call = original_call

    def test_split_cannot_return_an_existing_parent(self):
        original_call = self.fake.call
        def corrupted(args):
            if args[:2] == ["pane", "split"]:
                return {"pane": copy.deepcopy(self.fake.panes[args[2]])}
            return original_call(args)
        self.fake.call = corrupted
        with self.assertRaisesRegex(lab_module.LabError, "existing pane"):
            self.lab.start("split-corruption", "worker,qa")
        manifest = self.lab.load("split-corruption")
        self.assertEqual(len(manifest["owned_panes"]), 1)
        self.assertNotIn("qa", manifest["roles"])

    def test_cleanup_rechecks_each_role_after_a_prior_close(self):
        self.lab.capture("fixture-run")
        qa_id = self.lab.load("fixture-run")["roles"]["qa"]["pane_id"]
        original_call = self.fake.call
        def changing(args):
            result = original_call(args)
            if args[:2] == ["pane", "close"]:
                self.fake.panes[qa_id]["agent_status"] = "working"
            return result
        self.fake.call = changing
        with self.assertRaises(lab_module.LabError):
            self.lab.cleanup("fixture-run", "worker,qa")
        manifest = self.lab.load("fixture-run")
        self.assertEqual(self.fake.close_calls, 1)
        self.assertEqual(manifest["roles"]["worker"]["state"], "closed")
        self.assertEqual(self.fake.panes[qa_id]["agent_status"], "working")

    def test_duplicate_cleanup_roles_fail_before_closing(self):
        self.lab.capture("fixture-run", "worker")
        with self.assertRaisesRegex(lab_module.LabError, "distinct"):
            self.lab.cleanup("fixture-run", "worker,worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_uncertain_creation_blocks_dispatch_to_created_role(self):
        manifest = self.lab.load("fixture-run")
        manifest["status"] = "creation_uncertain"
        self.lab.save(manifest)
        with self.assertRaisesRegex(lab_module.LabError, "creation"):
            self.send()
        self.assertEqual(self.fake.prompt_calls, 0)

    def test_malformed_configuration_is_rejected_before_herdr(self):
        variants = [None, [], "wrong", {**self.config, "schema_version": True}, {**self.config, "schema_version": 1.0}, {**self.config, "session": None},
                    {**self.config, "workspace_id": []}, {**self.config, "session": " REPLACE_WITH_SESSION"}]
        for field, value in (("model", ["wrong"]), ("effort", 5), ("template_file", None)):
            config = copy.deepcopy(self.config)
            config["roles"]["worker"][field] = value
            variants.append(config)
        config = copy.deepcopy(self.config)
        config["roles"]["worker"] = None
        variants.append(config)
        for config in variants:
            with self.subTest(config=config):
                path = self.root / "malformed.json"
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(lab_module.LabError):
                    lab_module.load_config(path, resolve_executable=False)

    def test_non_object_rpc_envelopes_are_structured_errors(self):
        client = lab_module.Herdr(self.config)
        for envelope in (None, [], "wrong", {"result": []}):
            with self.subTest(envelope=envelope):
                client.raw = lambda args: json.dumps(envelope)
                with self.assertRaises(lab_module.LabError):
                    client.call(["api", "snapshot"])

    def test_local_plan_does_not_require_an_installed_herdr(self):
        config = copy.deepcopy(self.config)
        config["herdr_executable"] = "missing-herdr-fixture-20261001"
        path = self.root / "offline.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        loaded = lab_module.load_config(path, resolve_executable=False)
        plan = lab_module.Lab(loaded).plan("worker")
        self.assertFalse(plan["mutates_herdr"])
        with self.assertRaisesRegex(lab_module.LabError, "not found"):
            lab_module.load_config(path)

    def concurrent_send(self, phases, uncertain=False, controls=False, via_main=False):
        original_call = self.fake.call
        children = []
        def cli(arguments, expected=0):
            child = subprocess.run([sys.executable, "-B", "-X", "utf8", str(MODULE), "--config",
                                    self.config["config_file"], *arguments], cwd=self.root,
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(child.returncode, expected, child.stderr)
            children.append(json.loads(child.stdout) if child.stdout else None)
        def during_prompt(arguments):
            if arguments[:2] != ["agent", "prompt"]:
                return original_call(arguments)
            self.fake.prompt_calls += 1
            if controls:
                cli(["send", "--run-id", "fixture-run", "--role", "worker", "--message-id", "task-one", "--body-file", str(self.body)])
                cli(["pause", "--run-id", "fixture-run"])
                cli(["send", "--run-id", "fixture-run", "--role", "worker", "--message-id", "after-pause", "--body-file", str(self.body)], expected=1)
            for phase in phases:
                cli(["receipt", "--run-id", "fixture-run", "--message-id", "task-one", "--phase", phase,
                     "--evidence-file", str(self.evidence(phase))])
            if uncertain:
                raise OSError("uncertain response after actual child receipts")
            return {"submitted": True}
        self.fake.call = during_prompt
        if via_main:
            argv = [str(MODULE), "--config", self.config["config_file"], "send", "--run-id", "fixture-run",
                    "--role", "worker", "--message-id", "task-one", "--body-file", str(self.body)]
            output = io.StringIO()
            with patch.object(sys, "argv", argv), patch.object(lab_module, "Herdr", return_value=self.fake), contextlib.redirect_stdout(output):
                self.assertEqual(lab_module.main(), 0)
            self.assertTrue(json.loads(output.getvalue())["ok"])
        elif uncertain:
            with self.assertRaisesRegex(OSError, "uncertain response"):
                self.send()
        else:
            self.send()
        manifest = self.lab.load("fixture-run")
        record = manifest["messages"]["task-one"]
        self.assertEqual(record["state"], phases[-1])
        self.assertEqual([item["phase"] for item in record["receipts"]], phases)
        self.assertEqual(record["submission_state"], "uncertain" if uncertain else "submitted")
        self.assertEqual(self.fake.prompt_calls, 1)
        return manifest, children

    def test_received_cli_can_write_while_main_send_waits(self):
        self.concurrent_send(["received"], via_main=True)

    def test_completed_child_receipts_survive_submission_response(self):
        self.concurrent_send(["received", "started", "completed"])

    def test_failed_child_receipt_survives_submission_response(self):
        self.concurrent_send(["failed"])

    def test_uncertain_response_keeps_completed_receipts_and_never_replays(self):
        self.concurrent_send(["received", "started", "completed"], uncertain=True)
        duplicate = self.send()
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["message"]["state"], "completed")
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_uncertain_response_keeps_started_receipts(self):
        self.concurrent_send(["received", "started"], uncertain=True)

    def test_pause_and_duplicate_during_send_preserve_latest_state(self):
        manifest, children = self.concurrent_send(["received", "started", "completed"], controls=True)
        self.assertTrue(manifest["paused"])
        self.assertEqual(manifest["epoch"], 2)
        self.assertTrue(children[0]["result"]["duplicate"])
        self.assertEqual(children[0]["result"]["message"]["state"], "submitting")
        self.assertNotIn("after-pause", manifest["messages"])

    def test_final_cleanup_snapshot_identity_change_prevents_close(self):
        self.lab.capture("fixture-run", "worker")
        binding = self.lab.load("fixture-run")["roles"]["worker"]
        original_call = self.fake.call
        agent_reads = 0
        def changing(args):
            nonlocal agent_reads
            if args[:2] == ["agent", "get"]:
                agent_reads += 1
            if args[:2] == ["api", "snapshot"] and agent_reads == 2:
                self.fake.panes[binding["pane_id"]]["agent_session"]["value"] = "observed-replacement"
            return original_call(args)
        self.fake.call = changing
        with self.assertRaisesRegex(lab_module.LabError, "mismatched"):
            self.lab.cleanup("fixture-run", "worker")
        self.assertEqual(self.fake.close_calls, 0)

    def test_label_check_rejects_observed_workspace_drift_before_start(self):
        original_call = self.fake.call
        def changing(args):
            response = original_call(args)
            if args[:2] == ["pane", "get"] and "label" in response["pane"]:
                response["pane"]["workspace_id"] = "w2"
            return response
        self.fake.call = changing
        before = sum(c[:2] == ["agent", "start"] for c in self.fake.calls)
        with self.assertRaisesRegex(lab_module.LabError, "workspace"):
            self.lab.start("label-workspace-drift", "worker")
        self.assertEqual(before, sum(c[:2] == ["agent", "start"] for c in self.fake.calls))

    def test_historical_status_reads_manifest_after_template_is_removed(self):
        Path(self.config["roles"]["worker"]["template_file"]).unlink()
        child = subprocess.run([sys.executable, "-B", "-X", "utf8", str(MODULE), "--config", self.config["config_file"],
                                "status", "--run-id", "fixture-run"], cwd=self.root, capture_output=True,
                               text=True, encoding="utf-8", timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout)["result"]["run_id"], "fixture-run")

    def test_snapshot_with_empty_identity_is_rejected(self):
        original_call = self.fake.call
        def changing(args):
            result = original_call(args)
            if args[:2] == ["api", "snapshot"]:
                result["snapshot"]["panes"][0]["pane_id"] = ""
            return result
        self.fake.call = changing
        with self.assertRaisesRegex(lab_module.LabError, "invalid"):
            self.lab.preflight()

    def test_blocked_response_merge_preserves_outcome_for_no_replay_retry(self):
        original_call = self.fake.call
        held = []
        def during_prompt(args):
            response = original_call(args)
            if args[:2] == ["agent", "prompt"]:
                lock = lab_module.state_lock(self.lab.state)
                lock.__enter__()
                held.append(lock)
            return response
        self.fake.call = during_prompt
        try:
            with patch.object(lab_module.time, "monotonic", side_effect=[0, 6]):
                with self.assertRaisesRegex(lab_module.LabError, "outcome preserved"):
                    self.send()
        finally:
            for lock in held:
                lock.__exit__(None, None, None)
        self.assertEqual(self.lab.load("fixture-run")["messages"]["task-one"]["state"], "submitting")
        result = self.send()
        self.assertTrue(result["duplicate"])
        self.assertFalse(result["dispatched"])
        self.assertEqual(result["message"]["state"], "submitted")
        self.assertEqual(self.fake.prompt_calls, 1)

    def test_changed_submission_evidence_is_rejected_without_replay(self):
        self.send()
        record = self.lab.load("fixture-run")["messages"]["task-one"]
        path = Path(record["submission_evidence_file"])
        evidence = json.loads(path.read_text(encoding="utf-8"))
        evidence["response"] = {"changed": True}
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaisesRegex(lab_module.LabError, "evidence has changed"):
            self.send()
        self.assertEqual(self.fake.prompt_calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
