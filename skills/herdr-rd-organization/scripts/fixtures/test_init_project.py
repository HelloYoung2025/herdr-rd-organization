"""Bootstrap tests confined to the explicitly supplied --test-root. No Herdr calls."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import redirect_stderr
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[2]
HELPER = SKILL / "scripts" / "init_project.py"
TEST_ROOT = None


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.case = TEST_ROOT / (self._testMethodName + "-" + uuid.uuid4().hex[:8])
        self.project = self.case / "project"
        self.project.mkdir(parents=True)
        self.inputs = self.project / ".herdr-input"
        self.state = self.project / ".herdr-state"

    def invoke(self, helper=HELPER, **overrides):
        values = {"project-root": str(self.project), "input-dir": str(self.inputs), "state-dir": str(self.state),
                  "session": "reviewed-session", "workspace": "w7", "model": "grok-explicit-custom",
                  "effort": "xhigh", "run-id": "bootstrap-test"}
        values.update(overrides)
        argv = [sys.executable, "-B", str(helper)]
        for key, value in values.items():
            argv.extend(["--" + key, value])
        environment = os.environ.copy()
        environment["PATH"] = ""  # Herdr is unavailable; initialization must still work.
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=environment, shell=False)

    def copied_skill(self):
        copied = self.project / "installation"
        (copied / "scripts" / "runtime").mkdir(parents=True)
        shutil.copy2(HELPER, copied / "scripts" / "init_project.py")
        shutil.copy2(SKILL / "scripts" / "runtime" / "herdr_lab.py", copied / "scripts" / "runtime" / "herdr_lab.py")
        shutil.copytree(SKILL / "assets", copied / "assets")
        return copied

    def load_module(self, name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def hashes(self):
        return {str(path.relative_to(self.inputs)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.inputs.rglob("*") if path.is_file()}

    def test_initialization_creates_drafts_and_correct_installed_runtime_paths(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)["result"]
        self.assertEqual(len(report["files"]), 12)
        self.assertFalse(report["herdr_called"])
        self.assertFalse(self.state.exists())
        self.assertFalse(any(path.name == "manifest.json" for path in self.project.rglob("*")))
        config = json.loads((self.inputs / "lab-config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["session"], "reviewed-session")
        self.assertEqual(config["workspace_id"], "w7")
        for settings in config["roles"].values():
            self.assertEqual(settings["model"], "grok-explicit-custom")
            self.assertEqual(settings["effort"], "xhigh")
            self.assertTrue(Path(settings["template_file"]).is_file())
        research = json.loads((self.inputs / "research-task.json").read_text(encoding="utf-8"))
        self.assertEqual(research["goal_contract"]["status"], "draft")
        self.assertEqual(research["execution_contract"]["authorization_status"], "pending")
        orchestrator = json.loads((self.inputs / "orchestrator-task.json").read_text(encoding="utf-8"))
        prefix = orchestrator["wrapper_argv_prefix"]
        self.assertEqual(prefix, [sys.executable, str(SKILL / "scripts" / "runtime" / "herdr_lab.py"),
                                  "--config", str(self.inputs / "lab-config.json")])
        for path in self.inputs.rglob("*"):
            if path.is_file():
                content = path.read_bytes()
                self.assertFalse(content.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn("C:/Tools/herdr-lab", content.decode("utf-8"))
                self.assertNotIn("C:/Projects/demo", content.decode("utf-8"))
                if path.suffix == ".md":
                    variables = set(re.findall(r"\{\{([^{}]+)\}\}", content.decode("utf-8")))
                    self.assertLessEqual(variables, {"project_root", "state_dir", "run_id"})
                    self.assertIn("本次 TASK BODY", content.decode("utf-8"))

    def test_qa_second_assignment_and_new_run_use_current_body_and_binding(self):
        initialized = self.invoke(workspace="w1")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        original_fixtures = self.load_module("bootstrap_runtime_fixtures", SKILL / "scripts" / "fixtures" / "test_herdr_lab.py")
        runtime = original_fixtures.lab_module
        config_file = self.inputs / "lab-config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config["herdr_executable"] = sys.executable
        config_file.write_text(json.dumps(config), encoding="utf-8")
        client = original_fixtures.FakeHerdr()
        lab = runtime.Lab(runtime.load_config(config_file), client)
        for run, version in (("cycle-one", "qa-v1"), ("cycle-two", "qa-v2")):
            lab.start(run, "qa")
            body = self.project / (version + ".txt")
            body.write_text("Verify task " + version + " against acceptance-" + version + " using evidence-" + version, encoding="utf-8")
            lab.send(run, "qa", version, body)
        prompts = [call[3] for call in client.calls if call[:2] == ["agent", "prompt"]]
        self.assertEqual(len(prompts), 2)
        self.assertIn("运行: cycle-two", prompts[1])
        self.assertIn("Verify task qa-v2 against acceptance-qa-v2 using evidence-qa-v2", prompts[1])
        self.assertNotIn("运行: cycle-one", prompts[1])
        self.assertNotIn("bootstrap-test-task-001", prompts[1])
        self.assertNotIn(str(self.inputs / "task.json"), prompts[1])
        self.assertNotIn("cycle-evidence.json", prompts[1])
        self.assertNotIn("{{", prompts[1])

    def test_existing_inputs_are_refused_without_byte_changes(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.hashes()
        second = self.invoke()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("Refusing to overwrite", second.stderr)
        self.assertEqual(self.hashes(), before)

    def test_ordinary_directory_names_do_not_override_project_scope(self):
        named_project = self.project / "private" / "dps_v4.5"
        named_project.mkdir(parents=True)
        result = self.invoke(**{"project-root": str(named_project),
                                "input-dir": str(named_project / ".herdr-input"),
                                "state-dir": str(named_project / ".herdr-state")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((named_project / ".herdr-input" / "lab-config.json").is_file())
        self.assertFalse((named_project / ".herdr-state").exists())

    def test_existing_empty_input_directory_is_refused(self):
        self.inputs.mkdir()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.inputs.iterdir()), [])

    def test_existing_state_file_is_refused_before_writing(self):
        self.state.write_text("preserve-existing-state-file", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.inputs.exists())
        self.assertEqual(self.state.read_text(encoding="utf-8"), "preserve-existing-state-file")

    def test_installed_skill_project_input_and_state_are_refused(self):
        copied = self.copied_skill()
        helper = copied / "scripts" / "init_project.py"
        cases = ({"project-root": str(copied)},
                 {"input-dir": str(copied / "assets" / "new-inputs")},
                 {"state-dir": str(copied / "scripts" / "future-state")})
        for values in cases:
            with self.subTest(values=values):
                result = self.invoke(helper=helper, **values)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("outside the installed skill", result.stderr)
                self.assertFalse(self.inputs.exists())
                self.assertFalse((copied / "assets" / "new-inputs").exists())

    @unittest.skipUnless(os.name == "nt", "Windows path alias semantics")
    def test_windows_trailing_dot_and_space_fail_before_creation(self):
        cases = ({"input-dir": str(self.inputs) + "."}, {"input-dir": str(self.inputs) + " "},
                 {"state-dir": str(self.state) + "."}, {"project-root": str(self.project) + " "})
        for values in cases:
            with self.subTest(values=values):
                result = self.invoke(**values)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ending in a dot or space", result.stderr)
                self.assertFalse(self.inputs.exists())

    def test_input_escape_and_project_root_output_are_refused(self):
        for destination in (self.case / "outside-input", self.project):
            with self.subTest(destination=destination):
                result = self.invoke(**{"input-dir": str(destination)})
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.case / "outside-input").exists())
        self.assertFalse(self.inputs.exists())

    def test_state_escape_and_overlap_are_refused_before_writing(self):
        for destination in (self.case / "outside-state", self.project, self.inputs, self.inputs / "nested-state"):
            with self.subTest(destination=destination):
                result = self.invoke(**{"state-dir": str(destination)})
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.inputs.exists())

    def test_invalid_run_id_and_missing_model_do_not_create_inputs(self):
        for values in ({"run-id": "../escape"}, {"model": ""}, {"effort": "REPLACE_WITH_EFFORT"}, {"input-dir": "relative-input"}):
            with self.subTest(values=values):
                result = self.invoke(**values)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.inputs.exists())

    def test_resolved_symlink_escape_is_refused(self):
        outside = self.case / "outside"
        outside.mkdir()
        link = self.project / "linked-parent"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                self.skipTest(f"OS cannot create the symlink fixture: {exc}")
            environment = os.environ.copy()
            environment["HERDR_FIXTURE_LINK"] = str(link)
            environment["HERDR_FIXTURE_TARGET"] = str(outside)
            created = subprocess.run(["powershell", "-NoProfile", "-Command",
                                      "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path $env:HERDR_FIXTURE_LINK -Target $env:HERDR_FIXTURE_TARGET | Out-Null"],
                                     capture_output=True, text=True, encoding="utf-8", env=environment, shell=False)
            if created.returncode:
                self.skipTest(f"OS cannot create symlink or junction fixture: {created.stderr}")
        self.assertEqual(link.resolve(), outside.resolve())
        result = self.invoke(**{"input-dir": str(link / "inputs")})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((outside / "inputs").exists())

    def test_malformed_shapes_unknown_provider_and_placeholders_are_structured_errors(self):
        copied = self.copied_skill()
        helper = copied / "scripts" / "init_project.py"
        config_file = copied / "assets" / "templates" / "config.example.json"
        original = config_file.read_text(encoding="utf-8")
        invalid_values = [[], {**json.loads(original), "roles": []}]
        unsupported = json.loads(original)
        unsupported["roles"]["worker"]["provider"] = "unsupported-provider"
        invalid_values.append(unsupported)
        for value in invalid_values:
            with self.subTest(value=value):
                config_file.write_text(json.dumps(value), encoding="utf-8")
                result = self.invoke(helper=helper)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(json.loads(result.stderr)["ok"])
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(self.inputs.exists())
        config_file.write_text(original, encoding="utf-8")
        role_file = copied / "assets" / "templates" / "roles" / "qa.md"
        role_file.write_text(role_file.read_text(encoding="utf-8") + "\n{{unrecognized_acceptance}}", encoding="utf-8")
        result = self.invoke(helper=helper)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown placeholder", json.loads(result.stderr)["error"])
        self.assertFalse(self.inputs.exists())

    def test_templates_cannot_synthesize_user_approval(self):
        copied = self.copied_skill()
        for name in ("research-task", "orchestrator-task", "task"):
            path = copied / "assets" / "templates" / (name + ".example.json")
            value = json.loads(path.read_text(encoding="utf-8"))
            value["execution_contract"].update({"authorization_status": "approved", "authorization_ref": "fake-approval"})
            if "goal_contract" in value:
                value["goal_contract"].update({"status": "approved", "user_decision_ref": "fake-owner-decision"})
            path.write_text(json.dumps(value), encoding="utf-8")
        result = self.invoke(helper=copied / "scripts" / "init_project.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)["result"]
        for name in ("research-task", "orchestrator-task", "task"):
            value = json.loads((self.inputs / (name + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(value["execution_contract"]["authorization_status"], summary["authorization_status"])
            self.assertEqual(summary["authorization_status"], "pending")
            self.assertIsNone(value["execution_contract"]["authorization_ref"])
            if "goal_contract" in value:
                self.assertEqual(value["goal_contract"]["status"], summary["goal_status"])
                self.assertEqual(summary["goal_status"], "draft")
                self.assertIsNone(value["goal_contract"]["user_decision_ref"])

    def test_partial_io_failure_reports_paths_and_count_without_overwriting_retry(self):
        helper = self.load_module("bootstrap_failure_helper", HELPER)
        original = helper.write_new
        calls = 0

        def fail_second(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("SIMULATED_SECOND_WRITE_FAILURE")
            return original(path, value)

        argv = [str(HELPER)]
        values = {"project-root": str(self.project), "input-dir": str(self.inputs), "state-dir": str(self.state),
                  "session": "reviewed-session", "workspace": "w7", "model": "explicit-model", "effort": "xhigh", "run-id": "bootstrap-test"}
        for key, value in values.items():
            argv.extend(["--" + key, value])
        error_output = io.StringIO()
        with patch.object(helper, "write_new", fail_second), patch.object(sys, "argv", argv), redirect_stderr(error_output):
            self.assertEqual(helper.main(), 1)
        error = json.loads(error_output.getvalue())
        self.assertEqual(error["partial_input_dir"], str(self.inputs))
        self.assertEqual(error["completed_file_count"], 1)
        self.assertTrue(Path(error["completed_files"][0]).is_file())
        self.assertEqual(Path(error["failed_path"]).parent, self.inputs)
        self.assertNotIn(error["failed_path"], error["completed_files"])
        before = self.hashes()
        retry = self.invoke()
        self.assertNotEqual(retry.returncode, 0)
        self.assertEqual(self.hashes(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-root", required=True)
    parsed, remaining = parser.parse_known_args()
    candidate = Path(parsed.test_root)
    if not candidate.is_absolute():
        raise SystemExit("--test-root must be an explicit absolute path")
    TEST_ROOT = candidate.resolve()
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
