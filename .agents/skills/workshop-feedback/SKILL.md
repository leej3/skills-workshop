---
name: workshop-feedback
description: Record lightweight Skills Workshop memory after an agent actually uses a skill in a task. Use at a meaningful task milestone or completion to capture what helped, failed, enabled new work, or should improve. Installation, merely reading a skill, and routine memory bookkeeping are not use.
---

# Workshop feedback

Close the loop after real skill use without interrupting the main task.
This is a user-level control skill; working skills stay in their owning projects.
It requires Pixi and a Skills Workshop checkout with the `feedback` command.
Use the checkout's Pixi environment for Python; a system Python installation is not required.
Configure that checkout in `~/.config/skills-workshop/config.json` as `{"workshop_root": "/absolute/checkout"}`, or set `SKILLS_WORKSHOP_ROOT`.
The bundled launcher locates and runs the CLI; it never installs software or publishes anything.

At a meaningful milestone, record one short observation per skill that materially participated.
Capture failures, abandonment, and unclear benefit as readily as success.
Merely loading instructions is insufficient.
Do not record this feedback skill itself, repeated reads, routine commits, or bookkeeping.

Read the configured checkout path from the JSON file (or `SKILLS_WORKSHOP_ROOT`).
Use the bundled launcher from any project, replacing the manifest path with that checkout's `pixi.toml` and the launcher path with the installed skill directory:

```console
pixi run --manifest-path /absolute/checkout/pixi.toml \
  python /path/to/workshop-feedback/scripts/feedback.py <skill-name-or-uuid> \
  --task "Short, sanitized account of the work" \
  --rationale "What this skill changed, missed, or made possible" \
  --outcome success --benefit new-capability \
  --project-path /path/to/active-project \
  --asserted-kind agent --asserted-by codex
```

Only the skill, task, rationale, and actor flags are required.
Outcome and invocation default to unknown.
Do not infer success from a finished agent turn.
A rating is optional; do not manufacture one.
If warranted, the scale is 1 harmful, 2 unhelpful, 3 mixed, 4 useful, 5 decisive.

- For a skill not yet remembered, include `--skill-path /path/to/skill/SKILL.md`.
  The CLI records its observed source and description.
  For a known skill this also retains a digest of the entrypoint actually used; it is not a full-tree controlled-evaluation artifact.
  Use a UUID when names are ambiguous.
- `--project-path` matches an already remembered project by Git remote.
  If none matches, feedback still succeeds without a project link.
  Add a durable project record only when useful; do not turn that into a prerequisite for feedback.
- Add `--next-step "Concrete improvement"` when there is an actionable gap.
  This records a proposal, not permission to change the skill or post an upstream issue.
- Add `--evidence https://...` for a useful, sanitized durable result link.
  Record only runtime/model information actually known; omit the rest.
- Use `--benefit` for an observed `new-capability`, `saved-time`, `avoided-error`, `better-result`, `no-clear-benefit`, or `harmful` effect.
  These are observations, not causal proof.
- The launcher supplies the current Codex task ID as `--session` when available, preventing identical retries for the same skill/task.
  For a later meaningful milestone or correction, use a distinct task summary.
  Never rewrite old events.

Keep task summaries free of secrets and private transcripts.
Observations are agent assertions and remain unreviewed.
Do not ask the user to rate every use.
If uncertain, say so in the rationale.

Batch memory bookkeeping at the end of the task: validate the Workshop memory, inspect changed records, and commit only the task's intentional paths under the checkout's commit conventions.
Honor its provenance requirement.
Do not push without publication authorization.
If the checkout, tools, or commit provenance are unavailable, finish the main task and briefly report the pending observation; do not invent a record or repeatedly retry.

Later, `pixi run workshop recall "task I remember"` retrieves experience and `pixi run workshop insights --since YYYY-MM-DD` summarizes benefits, failures, evidence gaps, and proposed improvements.
An upstream contribution requires separate authorization; record its link once it actually exists.
