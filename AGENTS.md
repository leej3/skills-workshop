# Skills Workshop working agreement

Skills Workshop coordinates skill discovery and cross-project evidence; APM owns reusable dependency installation and locks.
This file follows the [AGENTS.md convention](https://agents.md/).
Before editing a path, read any applicable nested `AGENTS.md`; the nearest file takes precedence for conflicting project instructions, while nonconflicting parent guidance still applies.
Explicit user instructions take precedence over repository guidance.

## Development and validation

Run commands from the repository root using the locked Pixi environment.

- Restore tooling with `pixi install --locked` and skills with `pixi run --locked setup-skills`.
- Run `pixi run validate` before committing code changes: it checks lint, formatting, compilation, tests, metadata, memory, and shareable feedback.
- For focused iteration, run `pixi run pytest -q tests/<test_file>.py`; format Python with `pixi run format`.
- For reusable skill packaging changes, run `pixi run check-apm`; for control packaging changes, run `pixi run check-controls-apm`.
  These verify installation, restoration, and tamper detection.
- For documentation-only changes, run Snapper on the changed files with `pixi run pre-commit run snapper --files <paths>` and validate any changed skill or memory records.

Keep command examples synchronized with `pixi.toml` and relevant checks in `.github/workflows/`.
Keep human-facing setup and overview material in `README.md`; use this file for actionable agent instructions.

## Commit Workshop changes

- Commit every intentional change made in this repository before completing the task.
  Do not include unrelated changes in that commit; include pre-existing changes only when the task covers them.
- Validate the affected Workshop state before committing, including each changed native skill.
- Treat valid, intentional Workshop memory as tracked project data.
  Validate and commit records created or updated during a task before completing it, including when the main task is in another project.
  Batch records within a task, never defer their commit to a later task.
  Report validation or Git blockers and the remaining paths explicitly.
  When asked to sync the Workshop, inspect and include relevant pending memory records rather than excluding them solely because they predate the task.
  Stage explicit paths to avoid unrelated files, and push when publication is authorized by the task.
- Record only durable, externally useful contributions (such as an upstream issue, pull request, or release).
  Do not create Workshop events solely to document routine Workshop commits or bookkeeping.

## Reusable skill dependencies

Run `pixi run --locked setup-skills` before starting work; it restores the versions in `apm.lock.yaml`.
Start a new agent task after setup so native discovery sees the installed skills.
APM-owned copies are generated and Git-ignored; do not edit or commit them.
This repository publishes reusable source from `.apm/skills/`; edit that source here and run `pixi run apm install` to refresh the deployment lock.
Consumers pin published skill sources through APM and never develop deployed copies.
Keep their setup and agent guidance independent of Workshop; its repository URL is only a dependency coordinate.
Workshop control-skill source is tracked in `controls/skills/` and published separately through `controls/apm.yml`.
Activate those controls at user scope with `pixi run setup-agent --apply`; do not place them in this project's discovery directory.
If setup fails, report it rather than claiming missing skills were loaded.
Run `pixi run --locked audit-skills` to check integrity and drift.

`autoharness-reflect` belongs at user scope for reflection across projects, not in Workshop's project dependencies.
Workshop coordinates discovery, creation, and installation; invoke reflection in the actual work context.


## Tool landscape and architecture assessments

Keep cumulative assessments of tools, protocols, and architectural alternatives in `docs/agents/`.
Before proposing or adopting a component, consult `docs/agents/context-stack-landscape.md` and the relevant existing research ledger.
Update the landscape during material tool reviews, including candidates tested and rejected; do not leave the only assessment in chat or an experiment directory.
Keep executable fixtures and detailed run instructions with experiments, and link them from the assessment.

For each materially assessed candidate, record its roles (including overlaps), primary sources, review date, evidence level, current decision, data/export boundary, hosted or model dependencies, and the next discriminating test.
Distinguish source-reviewed claims, local probes, production use, and untested hypotheses; a candidate listing is not adoption or evidence of skill use.
Treat the landscape diagram as a map of interchangeable capabilities, not an installation plan.
Preserve canonical identities, original evidence, sensitivity decisions, and portable records independently of downstream indexes and application databases.
Update an existing assessment rather than creating a parallel ledger, and mark superseded conclusions explicitly.
