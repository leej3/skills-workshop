# Skills Workshop working agreement

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
Other consumer projects must pin a published Workshop revision and never develop these skills in their deployed copies.
Workshop control-skill source is tracked in `controls/skills/` and published separately through `controls/apm.yml`.
Activate those controls at user scope with `pixi run setup-agent --apply`; do not place them in this project's discovery directory.
If setup fails, report it rather than claiming missing skills were loaded.
Run `pixi run --locked audit-skills` to check integrity and drift.
