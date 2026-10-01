"""Session-routing regression cases. No live pane or model operations."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_context as checker


class FakeTransport:
    calls = []
    sessions = []
    workspaces = {}
    panes = {}

    def __init__(self, config):
        self.session = config["session"]

    def raw(self, args, session=True):
        self.calls.append((self.session, list(args)))
        if args == ["session", "list", "--json"]:
            return json.dumps({"sessions": self.sessions})
        raise AssertionError("Unexpected raw command: " + repr(args))

    def call(self, args):
        self.calls.append((self.session, list(args)))
        if args == ["workspace", "list"]:
            return {"workspaces": [{"workspace_id": value} for value in self.workspaces[self.session]]}
        if args[:2] == ["pane", "get"]:
            pane = self.panes.get((self.session, args[2]))
            if pane is None:
                raise checker.LabError("pane_not_found")
            return {"pane": pane}
        raise AssertionError("Unexpected command: " + repr(args))


class ContextTests(unittest.TestCase):
    def setUp(self):
        FakeTransport.calls = []
        FakeTransport.sessions = [
            {"name": "default", "socket_path": r"C:\Herdr\herdr.sock", "running": True},
            {"name": "project-b", "socket_path": r"C:\Herdr\sessions\project-b\herdr.sock", "running": True},
            {"name": "offline", "socket_path": r"C:\Herdr\sessions\offline\herdr.sock", "running": False},
        ]
        FakeTransport.workspaces = {"default": ["w1"], "project-b": ["w1", "w2"]}
        # The same qualified pane ID exists in different servers with different identity.
        FakeTransport.panes = {
            ("default", "w1:p1"): {"pane_id": "w1:p1", "tab_id": "w1:t1", "workspace_id": "w1"},
            ("project-b", "w1:p1"): {"pane_id": "w1:p1", "tab_id": "w1:t7", "workspace_id": "w1"},
            ("project-b", "w2:p8"): {"pane_id": "w2:p8", "tab_id": "w2:t3", "workspace_id": "w2"},
        }
        self.env = {"HERDR_ENV": "1", "HERDR_SESSION": "default",
                    "HERDR_SOCKET_PATH": r"C:\Herdr\sessions\project-b\herdr.sock",
                    "HERDR_WORKSPACE_ID": "w2", "HERDR_TAB_ID": "w2:t3", "HERDR_PANE_ID": "w2:p8"}

    def inspect(self, **kwargs):
        return checker.inspect_context(environ=kwargs.pop("environ", self.env), transport=FakeTransport, **kwargs)

    def assert_failure(self, code, **kwargs):
        with self.assertRaises(checker.BindingError) as raised:
            self.inspect(**kwargs)
        self.assertEqual(raised.exception.code, code)
        self.assertTrue(raised.exception.context["read_only"])
        return raised.exception.context

    def test_inherited_socket_selects_actual_server_not_default_session_env(self):
        result = self.inspect()
        self.assertEqual(result["binding"], {"session": "project-b", "workspace_id": "w2", "pane_id": "w2:p8", "source": "inherited_socket"})
        self.assertEqual(FakeTransport.calls[1:], [("project-b", ["workspace", "list"]), ("project-b", ["pane", "get", "w2:p8"])])

    def test_duplicate_pane_ids_do_not_identify_a_session(self):
        result = self.inspect(environ={**self.env, "HERDR_WORKSPACE_ID": "w1", "HERDR_PANE_ID": "w1:p1"})
        self.assertEqual(result["verified_pane"]["tab_id"], "w1:t7")

    def test_socket_path_case_and_slashes_match_on_windows(self):
        result = self.inspect(environ={**self.env, "HERDR_SOCKET_PATH": "c:/HERDR/sessions/project-b/herdr.sock"})
        self.assertEqual(result["binding"]["session"], "project-b")

    def test_stale_socket_does_not_fall_back_to_session_or_other_server_pane(self):
        self.assert_failure("unresolved_inherited_socket", environ={**self.env, "HERDR_SOCKET_PATH": r"C:\Old\herdr.sock"})
        self.assertEqual(len(FakeTransport.calls), 1)

    def test_closed_caller_does_not_fall_back_to_workspace_or_create_panes(self):
        del FakeTransport.panes[("project-b", "w2:p8")]
        failure = self.assert_failure("pane_lookup_failed")
        self.assertEqual(failure["target_session"], "project-b")
        self.assertEqual(failure["available_workspaces"], ["w1", "w2"])
        self.assertEqual(FakeTransport.calls[-1], ("project-b", ["pane", "get", "w2:p8"]))

    def test_native_moved_pane_alias_returns_canonical_workspace(self):
        FakeTransport.panes[("project-b", "w2:p8")] = {"pane_id": "w1:p12", "tab_id": "w1:t4", "workspace_id": "w1"}
        result = self.inspect()
        self.assertEqual(result["binding"]["workspace_id"], "w1")
        self.assertEqual(result["binding"]["pane_id"], "w1:p12")
        self.assertTrue(result["launch_ids_changed"])

    def test_explicit_target_does_not_reuse_caller_ids(self):
        result = self.inspect(session="default", workspace="w1")
        self.assertEqual(result["binding"], {"session": "default", "workspace_id": "w1", "source": "explicit_session"})
        self.assertEqual(FakeTransport.calls[-1], ("default", ["workspace", "list"]))

    def test_new_explicit_session_requires_workspace_not_foreign_caller(self):
        self.assert_failure("explicit_workspace_required", session="default")
        self.assertFalse(any(args[:2] == ["pane", "get"] for _, args in FakeTransport.calls))

    def test_external_host_has_no_focused_session_fallback(self):
        self.assert_failure("explicit_target_required", environ={})
        self.assertEqual(len(FakeTransport.calls), 1)

    def test_external_named_target_works_without_managed_env(self):
        self.assertEqual(self.inspect(session="project-b", workspace="w2", environ={})["binding"]["session"], "project-b")

    def test_explicit_workspace_must_match_verified_pane(self):
        self.assert_failure("workspace_pane_conflict", session="project-b", workspace="w1", pane="w2:p8")

    def test_missing_workspace_reports_available_ids_without_retargeting(self):
        failure = self.assert_failure("workspace_not_found", session="default", workspace="w2")
        self.assertEqual(failure["available_workspaces"], ["w1"])

    def test_missing_or_offline_session_does_not_start_server(self):
        for session in ("unknown", "offline"):
            with self.subTest(session=session):
                self.assert_failure("session_unavailable", session=session, workspace="w1")
        self.assertTrue(all(args == ["session", "list", "--json"] for _, args in FakeTransport.calls))

    def test_managed_default_session_without_socket(self):
        result = self.inspect(environ={"HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p1", "HERDR_WORKSPACE_ID": "w1"})
        self.assertEqual(result["binding"]["session"], "default")

    def test_only_routing_environment_is_exposed(self):
        result = self.inspect(environ={**self.env, "PRIVATE_API_KEY": "never-print"})
        self.assertNotIn("never-print", json.dumps(result))

    def test_cli_config_conflict_is_rejected_before_herdr_calls(self):
        config = {"session": "project-b", "workspace_id": "w2"}
        with patch.object(sys, "argv", ["check_context.py", "--config", "saved.json", "--session", "default"]), patch.object(checker, "read_json", return_value=config), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(checker.main(), 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])
        self.assertEqual(FakeTransport.calls, [])

    def test_real_subprocess_adapter_pins_session_despite_inherited_socket(self):
        api = checker.Herdr({"herdr_executable": "herdr", "project_root": str(Path.cwd()), "session": "project-b"})
        response = subprocess.CompletedProcess([], 0, '{"result":{"workspaces":[]}}', "")
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": r"C:\Old\herdr.sock", "HERDR_SESSION": "default"}), patch("runtime.herdr_lab.subprocess.run", return_value=response) as run:
            self.assertEqual(api.call(["workspace", "list"]), {"workspaces": []})
        self.assertEqual(run.call_args.args[0], ["herdr", "--session", "project-b", "workspace", "list"])
        self.assertFalse(run.call_args.kwargs["shell"])


if __name__ == "__main__":
    unittest.main()
