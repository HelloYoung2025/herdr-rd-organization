#!/usr/bin/env python3
"""Create new project-local draft inputs only. Never calls Herdr or creates run state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS = SKILL_ROOT / "assets" / "templates"
RUNTIME = SKILL_ROOT / "scripts" / "runtime" / "herdr_lab.py"


def contained(root, candidate):
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def absolute_path(value, label):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be an explicit absolute path")
    if os.name == "nt" and any(part not in {".", ".."} and part.endswith((".", " ")) for part in path.parts):
        raise ValueError(f"{label} has a Windows path component ending in a dot or space")
    return path.resolve()


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


def initialize(project_root, input_dir, state_dir, session, workspace, model, effort, run_id):
    project = absolute_path(project_root, "project_root")
    inputs = absolute_path(input_dir, "input_dir")
    state = absolute_path(state_dir, "state_dir")
    for label, path in (("project_root", project), ("input_dir", inputs), ("state_dir", state)):
        if contained(SKILL_ROOT, path):
            raise ValueError(f"{label} must remain outside the installed skill directory")
    if Path(input_dir).exists() or Path(input_dir).is_symlink():
        raise FileExistsError("Refusing to overwrite an existing input_dir")
    if not project.is_dir():
        raise ValueError("project_root must already be an existing project directory")
    for label, path in (("input_dir", inputs), ("state_dir", state)):
        if path == project or not contained(project, path):
            raise ValueError(f"{label} must resolve strictly inside project_root")
    if contained(inputs, state) or contained(state, inputs):
        raise ValueError("input_dir and state_dir must be distinct and non-overlapping")
    if inputs.exists() or inputs.is_symlink():
        raise FileExistsError("Refusing to overwrite an existing input_dir")
    if state.exists() and not state.is_dir():
        raise ValueError("state_dir exists and is not a directory")
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("run_id must match the runtime's ASCII ID rule")
    for label, value in (("session", session), ("workspace", workspace), ("model", model), ("effort", effort)):
        if not isinstance(value, str) or not value.strip() or value != value.strip() or value.startswith("REPLACE_"):
            raise ValueError(f"{label} must be explicit; no default or fallback")
    if not RUNTIME.is_file() or not ASSETS.is_dir():
        raise FileNotFoundError("Installed runtime or template assets are missing")

    config_path = inputs / "lab-config.json"
    replacements = [
        ("C:/Projects/demo/.herdr-lab-config.json", str(config_path)),
        ("C:/Projects/demo/.herdr-lab-input", str(inputs)),
        ("C:/Projects/demo/.herdr-lab", str(state)),
        ("C:/Projects/demo", str(project)),
        ("C:/Tools/herdr-lab/runtime/herdr_lab.py", str(RUNTIME)),
        ("demo-run-001", run_id),
    ]

    def adapt(value):
        if isinstance(value, dict):
            return {key: adapt(item) for key, item in value.items()}
        if isinstance(value, list):
            return [adapt(item) for item in value]
        if isinstance(value, str):
            for source, target in replacements:
                value = value.replace(source, target)
        return value

    payloads = {}
    for source in sorted(ASSETS.glob("*.json")):
        name = "lab-config.json" if source.name == "config.example.json" else source.name.replace(".example.json", ".json")
        value = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Template {source.name} must contain a JSON object")
        payloads[name] = adapt(value)
    expected = {"lab-config.json", "research-task.json", "orchestrator-task.json", "task.json", "result.json", "receipt.json", "experience.json"}
    if set(payloads) != expected:
        raise ValueError("Installed JSON template names do not match the seven required resources")
    config = payloads["lab-config.json"]
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise ValueError("Only configuration schema_version 1 is supported")
    if not isinstance(config.get("herdr_executable"), str) or not config["herdr_executable"].strip():
        raise ValueError("herdr_executable must be an explicit nonempty command string")
    config.update({"project_root": str(project), "state_dir": str(state), "session": session,
                   "workspace_id": workspace, "tab_label": "Herdr R&D " + run_id})
    role_files = {"research": "research-engineer.md", "orchestrator": "orchestrator.md",
                  "worker": "worker.md", "qa": "qa.md", "curator": "curator.md"}
    if not isinstance(config.get("roles"), dict) or set(config["roles"]) != set(role_files):
        raise ValueError("Configuration roles must contain the five known role objects")
    for role, filename in role_files.items():
        settings = config["roles"][role]
        if not isinstance(settings, dict):
            raise ValueError(f"Role {role} must be an object")
        if settings.get("provider") != "grok":
            raise ValueError("Initial adapter supports only Grok; no provider fallback")
        if not isinstance(settings.get("temporary"), bool) or (role in {"research", "orchestrator"} and settings["temporary"]):
            raise ValueError(f"Role {role} has an invalid temporary setting")
        if settings.get("session_args") != []:
            raise ValueError("Bootstrap template session_args must be empty; configure reviewed arguments explicitly afterwards")
        settings.update({"model": model, "effort": effort, "template_file": str(inputs / "roles" / filename)})
    for name in ("research-task.json", "orchestrator-task.json", "task.json"):
        contract = payloads[name].get("execution_contract")
        if not isinstance(contract, dict):
            raise ValueError(f"Template {name} requires an execution_contract object")
        contract.update({"authorization_status": "pending", "authorization_ref": None})
    for name in ("research-task.json", "task.json"):
        goal = payloads[name].get("goal_contract")
        if not isinstance(goal, dict):
            raise ValueError(f"Template {name} requires a goal_contract object")
        goal.update({"status": "draft", "user_decision_ref": None})
    payloads["research-task.json"]["task_id"] = run_id + "-research-001"
    payloads["orchestrator-task.json"]["task_id"] = run_id + "-orchestration-001"
    payloads["task.json"]["task_id"] = run_id + "-task-001"
    payloads["result.json"]["task_id"] = payloads["task.json"]["task_id"]
    payloads["receipt.json"]["run_id"] = run_id
    payloads["experience.json"]["project_scope"] = str(project)
    payloads["experience.json"].update({"state": "draft", "trial_authorization_ref": None,
                                       "grant_expansion_allowed": False, "global_install_allowed": False})
    payloads["orchestrator-task.json"]["wrapper_argv_prefix"] = [sys.executable, str(RUNTIME), "--config", str(config_path)]
    rendered_roles = {}
    for role, filename in role_files.items():
        source = ASSETS / "roles" / filename
        text = source.read_text(encoding="utf-8")
        values = {"input_dir": str(inputs), "task_id": "由本次 TASK BODY 指定",
                  "goal_ref": "以本次 TASK BODY 指定的冻结目标与验收为准",
                  "task_ref": "以本次 TASK BODY 指定的当前任务与独立验收包为准",
                  "evidence_pack_ref": "以本次 TASK BODY 指定的已筛选证据包为准",
                  "orchestrator_role_id": "orchestrator"}
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        unknown = set(re.findall(r"\{\{([^{}]+)\}\}", text)) - {"project_root", "state_dir", "run_id"}
        if unknown:
            raise ValueError(f"Unknown placeholder in {filename}: {sorted(unknown)}")
        rendered_roles[filename] = text

    goal_statuses = {payloads[name]["goal_contract"]["status"] for name in ("research-task.json", "task.json")}
    authorization_statuses = {payloads[name]["execution_contract"]["authorization_status"] for name in ("research-task.json", "orchestrator-task.json", "task.json")}
    if goal_statuses != {"draft"} or authorization_statuses != {"pending"}:
        raise ValueError("Generated task contracts must remain draft and pending")
    # No output is created until all input assets and candidate paths validate.
    outputs = []
    files = []
    attempted = inputs
    try:
        if any(path.resolve() != path for path in (project, inputs, state)):
            raise ValueError("Project/input/state resolved identity changed before creation")
        inputs.mkdir(parents=True, exist_ok=False)
        if not contained(project, inputs.resolve()):
            raise ValueError("input_dir changed its resolved scope during creation")
        attempted = inputs / "roles"
        attempted.mkdir()
        for name, value in payloads.items():
            path = inputs / name
            if not contained(inputs, path.resolve()):
                raise ValueError("Output path escaped input_dir")
            attempted = path
            write_new(path, value)
            outputs.append(path)
        for filename, text in rendered_roles.items():
            path = inputs / "roles" / filename
            if not contained(inputs, path.resolve()):
                raise ValueError("Role path escaped input_dir")
            attempted = path
            write_new(path, text)
            outputs.append(path)
        for path in outputs:
            attempted = path
            files.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    except (OSError, ValueError) as exc:
        exc.bootstrap_context = {"partial_input_dir": str(inputs), "completed_file_count": len(outputs),
                                 "completed_files": [str(path) for path in outputs], "failed_path": str(attempted),
                                 "recovery": "Inspect any partial output; use a new input_dir. Existing inputs are never overwritten or automatically deleted."}
        raise
    return {"project_root": str(project), "input_dir": str(inputs), "state_dir": str(state),
            "config_file": str(config_path), "runtime": str(RUNTIME), "run_id": run_id,
            "files": files,
            "goal_status": next(iter(goal_statuses)), "authorization_status": next(iter(authorization_statuses)), "herdr_called": False,
            "panes_started": False, "state_or_manifest_created": False,
            "next": "Fill the user goal, acceptance, permitted inputs, scope and authorization; inspect plan before start."}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("project-root", "input-dir", "state-dir", "session", "workspace", "model", "effort", "run-id"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    try:
        result = initialize(**vars(args))
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        failure = {"ok": False, "error": str(exc)}
        failure.update(getattr(exc, "bootstrap_context", {}))
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
