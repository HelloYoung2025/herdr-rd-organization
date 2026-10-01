#!/usr/bin/env python3
"""Read-only Herdr session/workspace binding check. Never creates or adopts panes."""
from __future__ import annotations

import argparse
import json
import ntpath
import os
from pathlib import Path
import subprocess
import sys

from runtime.herdr_lab import Herdr, LabError, read_json


class BindingError(LabError):
    def __init__(self, code, message, context):
        super().__init__(message)
        self.code = code
        self.context = context


def socket_key(value):
    # Herdr currently targets Windows here; accept slash/case differences in its paths.
    return ntpath.normcase(ntpath.normpath(value))


def inspect_context(session=None, workspace=None, pane=None, herdr_executable="herdr",
                    project_root=None, environ=None, transport=Herdr):
    env = os.environ if environ is None else environ
    inherited = {key: env[key] for key in (
        "HERDR_ENV", "HERDR_SESSION", "HERDR_SOCKET_PATH", "HERDR_WORKSPACE_ID",
        "HERDR_TAB_ID", "HERDR_PANE_ID") if env.get(key)}
    context = {"read_only": True, "inherited": inherited}

    def fail(code, message):
        raise BindingError(code, message, context)

    for label, value in (("session", session), ("workspace", workspace), ("pane", pane)):
        if value is not None and (not isinstance(value, str) or not value.strip() or value != value.strip() or value.startswith("REPLACE_")):
            fail("invalid_target", f"{label} must be explicit and nonempty")
    config = {"herdr_executable": herdr_executable,
              "project_root": str(Path(project_root or Path.cwd()).resolve()), "session": "default"}
    # Listing sessions is filesystem inventory, not a request to the focused server.
    # This local CLI command returns a top-level object, unlike RPC result envelopes.
    inventory = json.loads(transport(config).raw(["session", "list", "--json"]))
    sessions = inventory.get("sessions") if isinstance(inventory, dict) else None
    if not isinstance(sessions, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("name"), str)
        or not isinstance(item.get("socket_path"), str) or not isinstance(item.get("running"), bool)
        for item in sessions
    ):
        fail("invalid_session_inventory", "Herdr returned an invalid session inventory")
    context["sessions"] = [{key: item[key] for key in ("name", "socket_path", "running")} for item in sessions]
    managed = env.get("HERDR_ENV") == "1"
    caller_session = None
    caller_source = None
    if managed:
        if env.get("HERDR_SOCKET_PATH"):
            matches = [item for item in sessions if socket_key(item["socket_path"]) == socket_key(env["HERDR_SOCKET_PATH"])]
            if len(matches) == 1:
                caller_session = matches[0]["name"]
                caller_source = "inherited_socket"
        else:
            caller_session = env.get("HERDR_SESSION") or "default"
            caller_source = "inherited_session"
    context["caller_session"] = caller_session
    if session is None:
        if not managed:
            fail("explicit_target_required", "Outside Herdr: supply the authorized --session and --workspace. No focused-session fallback.")
        if caller_session is None:
            fail("unresolved_inherited_socket", "Inherited socket does not identify one listed session. Re-enter a live Herdr pane; do not guess from workspace/pane IDs.")
        session = caller_session
        source = caller_source
    else:
        source = "explicit_session"
    context["target_session"] = session
    selected = [item for item in sessions if item["name"] == session]
    if len(selected) != 1 or not selected[0]["running"]:
        fail("session_unavailable", "Target session is missing or not running. No session was started or substituted.")
    # Explicit selection intentionally overrides an inherited socket; all RPCs are pinned.
    config["session"] = session
    api = transport(config)
    workspaces = api.call(["workspace", "list"]).get("workspaces")
    if not isinstance(workspaces, list) or any(not isinstance(item, dict) or not isinstance(item.get("workspace_id"), str) for item in workspaces):
        fail("invalid_workspace_inventory", "Herdr returned an invalid workspace inventory")
    context["available_workspaces"] = [item["workspace_id"] for item in workspaces]
    # An explicit workspace is a target, not a claim to be the invoking pane.
    inherited_pane = pane is None and workspace is None and managed and caller_session == session
    if inherited_pane:
        pane = env.get("HERDR_PANE_ID")
        if not pane:
            fail("missing_caller_pane", "Managed caller has no pane ID. Re-enter a live Herdr pane or use an explicitly verified target.")
    if pane:
        context["requested_pane"] = pane
        try:
            actual = api.call(["pane", "get", pane]).get("pane")
        except LabError as exc:
            fail("pane_lookup_failed", f"Pane lookup failed in session {session}: {exc}. Do not reuse stale IDs or create replacements; verify the live caller or the recorded run.")
        if not isinstance(actual, dict) or not all(isinstance(actual.get(key), str) and actual[key] for key in ("pane_id", "tab_id", "workspace_id")):
            fail("invalid_pane_identity", "Herdr returned incomplete pane identity")
        if workspace is not None and workspace != actual["workspace_id"]:
            fail("workspace_pane_conflict", "Explicit workspace disagrees with the verified pane. No target was substituted.")
        workspace = actual["workspace_id"]
        pane = actual["pane_id"]
        context["verified_pane"] = {key: actual[key] for key in ("pane_id", "tab_id", "workspace_id")}
        # Native pane aliases can resolve a moved pane's launch-time IDs.
        context["launch_ids_changed"] = inherited_pane and (
            pane != env.get("HERDR_PANE_ID") or workspace != env.get("HERDR_WORKSPACE_ID"))
    if workspace is None:
        fail("explicit_workspace_required", "Supply --workspace for the selected session. Caller IDs from another session are not reusable.")
    if workspace not in context["available_workspaces"]:
        fail("workspace_not_found", f"Workspace {workspace} does not exist in session {session}. Use the listed IDs only after confirming the intended target.")
    context["binding"] = {"session": session, "workspace_id": workspace, "source": source}
    if pane:
        context["binding"]["pane_id"] = pane
    return context


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Check a recorded project config without changing it")
    parser.add_argument("--session")
    parser.add_argument("--workspace")
    parser.add_argument("--pane", help="Optional exact pane to verify; never adopted")
    parser.add_argument("--herdr-executable", default="herdr")
    args = parser.parse_args()
    try:
        root = None
        if args.config:
            config = read_json(args.config)
            if not isinstance(config, dict):
                raise LabError("Config must be a JSON object")
            for option, field in (("session", "session"), ("workspace", "workspace_id")):
                value = config.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise LabError(f"Config requires explicit {field}")
                if getattr(args, option) is not None and getattr(args, option) != value:
                    raise LabError(f"--{option} conflicts with the recorded config")
                setattr(args, option, value)
            root = config["project_root"]
            args.herdr_executable = config["herdr_executable"]
            if not isinstance(root, str) or not Path(root).is_absolute() or not Path(root).is_dir():
                raise LabError("Config project_root must be an existing absolute directory")
            if not isinstance(args.herdr_executable, str) or not args.herdr_executable.strip():
                raise LabError("Config requires explicit herdr_executable")
        result = inspect_context(args.session, args.workspace, args.pane, args.herdr_executable, root)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except BindingError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": str(exc), **exc.context}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except (LabError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "read_only": True, "code": "context_check_failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
