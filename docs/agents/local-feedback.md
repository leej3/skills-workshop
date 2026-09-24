# Local feedback and learning

Routine skill use should yield cheap, consistent measurements without publishing a task history.
The implementation separates three layers:

| Layer | Storage | Purpose |
|---|---|---|
| Baseline observations | Private append-only JSONL outside Git | Outcomes, task categories, optional measured durations and skill entrypoint hashes |
| Consolidated lessons | Private grouped notes; selected lessons may enter reviewed Git memory | Recurring patterns, confidence, priority, proposed actions, resolution |
| Active skills | Version-controlled skill files | Instructions changed deliberately and validated |

## Completion hook

One call records one skill/task observation:

```console
pixi run feedback-local record duct --task build-validation --outcome success
```

From another project, invoke the installed feedback skill's `scripts/usage.py` with Python and the same arguments.
No registration, dependencies beyond the standard library, or network calls are needed.
A host integration can call this CLI directly; there is no implied automatic subscription to Codex events.
The current user instruction supplies the agent-driven completion convention.

`--outcome` concerns the skill's intended role.
`--task-outcome` independently describes the surrounding task.
Use `unknown` where evidence is absent.
For measured duration, specify both `--duration-seconds` and `--duration-scope task|skill`.
Omit duration when unavailable; future host adapters can supply clock measurements without changing the schema.
A task duration may appear on several skills' observations and must not be summed across them.
It measures elapsed time with the skill, not time caused or saved by the skill.

Optional `--skill-path` hashes the SKILL.md bytes without recording the path or content; this is an entrypoint digest, not a complete artifact identity.
Optional `--model` preserves a known model identifier; missing values remain null.
Use a random `--event-id` for safe retries.
A repeated ID with identical content is a no-op; different content is rejected.
Use one observation per task/skill, even if the skill wraps many commands.

The default store is `${XDG_STATE_HOME:-~/.local/state}/skills-workshop/feedback/observations.jsonl`.
An explicit `--store` must also be outside a Git checkout.
Directory/file permissions are 0700/0600; this is access control, not encryption or protection from an authorized local process.
Writers take an advisory file lock and flush completed records to disk.
Malformed or partial history produces an error without silently deleting or repairing evidence.
The hook targets macOS and Linux, matching Workshop's supported platforms.
Schema version 1 distinguishes `usage` and `insight` rows; existing Git memory and its history remain unchanged.

## Aggregate and prioritize

```console
pixi run feedback-local summary --since 2026-09-01
pixi run feedback-local note duct --group sampling-compatibility \
  --summary "Resource sampling failed in a new runtime" \
  --action "Check runtime support and add a regression case" \
  --priority 1 --confidence medium
pixi run feedback-local insights
```

Summaries group skill, task category, entrypoint digest, and model, reporting sample counts, outcomes, and separate task/skill duration medians with their sample sizes.
Unknown outcomes are explicitly excluded from the known-outcome success denominator.
Missing observations cannot be counted; these statistics are conditional on reported usage and cannot prove efficacy.
Use stable categories such as `build-validation`, `document-editing`, or `release-review` to avoid fragmenting groups.
Do not backfill invented observations or durations into the baseline from old prose reports.

Qualitative notes are exceptional: a new failure, workaround, cost, ambiguity, improvement, or newly demonstrated capability.
Reuse a stable skill/group name and link actual baseline IDs with `--usage-id`. Append a note with `--status resolved` or `deferred` to remove a group from the open queue; append `open` to reopen it. The latest note defines the current action, confidence, and priority; prior notes remain intact. Priority 0 is immediate harm/data loss, 1 is blocking or recurring material failure, 2 is a useful improvement, and 3 is a minor refinement.
Within a priority, distinct linked uses determine ordering.
Repeated notes about one use do not inflate that count.
Frequency is evidence of recurrence, not confidence in a diagnosis.

Before revising a skill, inspect its relevant open groups and supporting observations.
Make a bounded change, record how it was validated, and resolve or defer the group with the outcome.
A proposed action is not an instruction to execute it or authorization to publish it.
Routine collection and the recorder's own bookkeeping never trigger recursive qualitative reports.

## Public promotion

Collection, consolidation, and publication are separate decisions.
Neither baseline observations nor grouped notes are auto-committed or pushed.
Promote only necessary reusable knowledge after inspecting the exact record and all generated metadata, and confirming publication authorization.
The [publication policy](../../.agents/skills/workshop-feedback/references/publication.md) defines exclusions and the existing curated-memory workflow.
There is deliberately no automatic raw-log export or claim that a secret scanner certifies disclosure suitability.

## Relationship to WikiSkill

[WikiSkill, sections 3.1–3.2](https://arxiv.org/html/2608.27454) separates immutable execution traces, a persistent knowledge wiki, and active skill instructions.
Its wiki consolidates successful strategies and failures; proposed skill changes are accepted only through validation, with failed skill changes rolled back while accumulated knowledge survives.

Workshop adopts those boundaries and the importance of preserving proposal outcomes from the outset.
Our baseline is intentionally much smaller than the paper's full execution traces: no reasoning, conversations, tool outputs, or raw logs are collected here.
Existing evaluation scaffolds can support controlled comparisons, but this hook does not implement the paper's benchmark harness, automated wiki maintainer, skill proposer, or validation-driven rollback loop.
Observational task outcomes are not substitutes for held-out evaluation scores.
A future extension should link patterns to exact skill artifacts and evaluation results, retain rejected proposals, and introduce automated changes only with appropriate validation and rollback.
