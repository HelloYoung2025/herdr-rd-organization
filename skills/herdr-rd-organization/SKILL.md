---
name: herdr-rd-organization
description: "Set up and operate a project research and engineering organization in Herdr: Research, Orchestrator, Worker, independent QA, and Curator. Use for Herdr 研发组织, multi-pane coordination, evidence-based correction, and project method trials. Do not activate for ordinary coding or research that does not request a Herdr organization."
---

# Herdr R&D Organization

Use this skill to turn an authorized project task into a bounded research, execution, independent verification, and feedback cycle. The bundled program manages run identity, messages, receipts, capture, and owned temporary panes. The current provider adapter is Windows with Grok; the agent invoking this skill may be Codex or another compatible host.

## Select the operation

- For a new project or installation, read [quickstart](references/quickstart.md). It covers dependencies, discovery, local configuration, and the first Research dispatch. The skill directory alone is sufficient; the older starter ZIP is not required.
- For role allocation, scientific feedback, defect routing, or Curator trials, read [organization](references/organization.md), then only the needed role/task templates in `assets/templates`.
- For an existing run, use its recorded config and run ID. Verify the target with `scripts/check_context.py --config <absolute-config-path>`, then query `status` before control. `status` reads the saved manifest; it does not locate the caller. Do not initialize replacement state or adopt older panes.
- For compatibility, sharing, or a claim about automation, read [portability](references/portability.md). [Overview](references/overview.md) maps the bundled resources.

## Establish the project contract

Read the target project's active rules, workflow, worktree requirements, and existing state ownership before writing. Preserve its existing business-status source; the runtime is the sole writer of its own run manifest.

Resolve this installed skill's directory from the actual loaded `SKILL.md` path, not the current directory or a fixed user path. The program is `scripts/runtime/herdr_lab.py`; use an absolute path when invoking it. `scripts/init_project.py` prepares new project-local copies without starting Herdr. Keep config, filled tasks, outputs, and run state inside the target project, outside the installed skill. Do not have a role modify this installed skill or its templates during an experiment.

Take goals, acceptance conditions, allowed inputs, write scope, budget, and rollback from the user's actual instructions. Ask only for missing decisions that matter. Preparation and read-only preflight can continue while they are pending; draft goal contracts and pending authorization cannot become approved merely because this skill was invoked. Existing session-specific authorization remains usable within its scope. Research may adjust methods; only the user changes goals, acceptance, or authorization scope.

Before the first workspace/pane query or initialization, run `scripts/check_context.py` from the actual Herdr caller using this skill's absolute path. It checks inherited socket/session binding and verifies the caller pane, returning canonical session/workspace IDs. Do not treat launch-time `HERDR_WORKSPACE_ID` or `HERDR_PANE_ID` as current identity, reuse IDs from another session, or fall back to the focused pane. A failed check is a binding problem, not permission to create replacement panes. Recovery and external-host options are in [quickstart](references/quickstart.md).

Use the installed Herdr CLI's `herdr --skill` for CLI operations and require verified session/workspace, provider, model, and effort. Pin every subsequent Herdr RPC with `--session <verified-session>`. Its built-in guide assumes a Herdr-managed caller. Outside Herdr, local initialization and `plan` remain available; do not inspect or control a focused session. Query/control a specifically named session from an external host only within the user's authorized target and scope; otherwise perform the steps inside Herdr. Do not fake `HERDR_ENV`. This skill does not install dependencies, copy credentials, supply default account access, or infer pane identity from a title.

## Run the bounded cycle

1. Configure and inspect the plan before creating roles. Reuse a compatible recorded run when continuing work. Create only roles justified by the task. Research and Orchestrator are preserved main roles; Workers and QA may be temporary. Curator consumes approved milestone evidence rather than constantly scanning all activity.
2. `start` creates roles with verified visible pane labels but sends no task. Agent names and pane labels are separate; see [quickstart](references/quickstart.md) for naming and existing-pane repair. Explicitly dispatch the filled Research task. Require its actual terminal receipt and plan artifact before sending the Orchestrator intake task; a successful submission is not a business receipt.
3. Orchestrator dispatches bounded implementation, obtains Worker artifacts, and separately dispatches QA on a frozen version and acceptance. Preserve initial failures. Repairs use a new version/message and independent retest. Roles author their own findings and receipts; do not manufacture another role's completion.
4. Orchestrator sends actual results, failures, costs, and unknowns to Research. Research records whether to retain, revise, or reject the method. A technical invalid run or missing evidence is not automatically a scientific negative result; changed goals or thresholds require the user.
5. Curator may propose an ordinary project method with sources, conditions, counterexamples, and rollback. Independent review precedes a bounded trial within existing authorization. Bind the trial to a saved version, record the outcome, and support withdrawal. A draft or single successful trial does not establish improvement and does not authorize global skill installation.
6. Report accepted work, failures, and remaining gaps against the user's frozen criteria. Capture final evidence before authorized temporary-role cleanup. Keep main roles and unrelated panes.

## Preserve executable checks

Use the bundled runtime for all run mutations, including receipts. Do not edit its manifest directly or build a second competing message/state writer. Its help is authoritative for CLI flags. References give practical examples; explicit project paths and run/message IDs replace examples.

- Keep the actual session binding and exact TASK HEADER fields. Missing, stale, conflicting, or overwritten parent/child identities are gaps; do not replace a parent identity with the last headless child's UUID.
- Every recipient records received, started, and completed or failed from its own observations. Completed cites real artifacts and hashes and truthfully lists pending tools or approvals. Bind messages to immutable bodies and versions; uncertain submissions are investigated before retrying.
- Task authorization, host tool approval, and the downstream provider's approval are separate checks. Read the complete current operation before an authorized one-time approval. This skill supplies no automatic broad approval or arbitrary-shell authorization.
- `pause` gates future dispatch through this runtime. It does not prove running tools stopped. Check actual processes and provider state before claiming cancellation or resuming effects.
- Capture preserves visible/recent text and a snapshot, not necessarily the full native session log. Cleanup requires terminal messages, no observed pending approvals/tools, a fresh capture, a matching identity, and idle/done state. Never close an unknown, working, blocked, or main role.

Responsibilities and independent audit are the chosen first-stage controls. A shared account and arbitrary shell remain capable of bypassing them. Do not claim hard filesystem isolation, clean blind testing, unattended approval, restart recovery, cross-machine operation, or scientific gains without separate fresh evidence.
