---
name: workshop-feedback
description: Collect schema-validated skill outcomes, keep sensitive details in a private overlay, and group exceptional lessons for improvement. Routine records are shareable; narrative feedback is exceptional.
---

# Workshop feedback

Respect the user-level Workshop mode in agent guidance: in manual mode, invoke only on an explicit user request; in off mode, use only the retained status/reactivation guidance.

Record once per skill/task after material use.
Do not narrate routine collection.
This is an agent-called recording command, not an installed automatic runtime callback.
A host adapter can invoke it, but none is registered by installing this skill.

## Routine records

Use `pixi run feedback-local` in the configured Workshop checkout, or run this skill's `scripts/usage.py` with a Python environment containing `jsonschema>=4`.
The schema and helper modules are bundled in this skill; registration and network access are unnecessary.

```console
pixi run feedback-local record duct --task build-validation --outcome success
```

Every write and read validates against [observation-v2.schema.json](schemas/observation-v2.schema.json), JSON Schema draft 2020-12.
`schema` prints it; `validate` checks stored records.
The required CLI fields are skill, task category, and skill outcome; generated/default fields complete the record. Use a stable task category, with optional concise context in `--details details.json`. Read [reporting.md](references/reporting.md) for optional fields and an example.

Distinguish whether the skill performed its role (`--outcome`) from the surrounding task result (`--task-outcome`).
Allowed outcomes are success, partial, failure, abandoned, and unknown.
Use `--duration-seconds` with `--duration-scope task|skill` only for measured elapsed time; omit unavailable values.
Add `--skill-path` for an entrypoint hash and `--model` when known.
Reuse a random UUID `--event-id` when retrying a call; changed content with the same ID is rejected.
Do not invent metrics, timing, model identity, or causal benefit.

## Shareable tree and sensitive overlay

In an annex-backed Workshop (`memory-storage.json` is present), ordinary records stage outside the checkout at `~/.local/state/skills-workshop/memory/legacy/observations/records/YYYY/MM/<uuid>.json`.
`WORKSHOP_MEMORY_WORKTREE` can override the local working-copy root.
Before completing the task, inspect and validate its records and run `memory import-feedback --public PATH --private OVERLAY` to queue them in per-agent memory journals.
The daily collector publishes 1000-record batches with at most one remainder per store; do not flush or commit individual records at task end.
Merge the private overlay before routing: any sensitive portion makes the complete source record sensitive.
Report collection failures and retain local files for retry.
Older checkouts without the storage marker still use `memory/observations`; validate and commit their reviewed shareable records under their checkout conventions.
With no configured checkout, the shareable tree falls back to a local state directory.

Keep sensitive fields in a matching tree outside Git, normally `${XDG_STATE_HOME:-~/.local/state}/skills-workshop/feedback-overlay/`.
Use `--private-fields /context/session_id /evidence` with a sensitivity category and concise reason.
The shareable record omits those fields; the overlay retains the full record and classification.
If a required field is sensitive, use `--visibility private` for the entire record.
The command never copies private data into the shareable tree.

Read [publication.md](references/publication.md) for classification and batching.
`summary` and `insights` merge the two trees locally by ID; add `--public-only` to inspect the shareable view.
`sensitivity` groups private classification reasons to inform later policy refinement.
Do not publish that merged output without examining its contents.

Skip mere reads, installations, the recorder, and bookkeeping; honor user opt-outs.
A sensitive task can still be recorded privately.
Do not log routine exemptions.
Collection failure must not block the main task or create a pending obligation for an ordinary missed observation.

## Exceptional lessons

Write notes for new skill failures, workarounds, unexpected costs, ambiguity, improvements, or newly demonstrated capabilities.
Routine successes need only baseline records.

```console
pixi run feedback-local note duct --group macos-sampling --priority 1 \
  --confidence high --summary "Sampling failed with an older runtime" \
  --action "Pin the verified runtime and add a regression check"
```

Group by skill and stable issue name; link baseline IDs using `--usage-id`.
Append notes to revise an action, confidence, priority, or status: open, resolved, deferred, rejected.
Priority 0 means immediate harm/data loss; 1 a blocker or recurring material failure; 2 a useful improvement; 3 a minor refinement.
Open insights sort by priority, then distinct linked uses.
Frequency is not diagnostic confidence.
Consult relevant groups and supporting evidence before proposing a change, then retain validation and rejection outcomes.

`summary` reports counts and medians with sample sizes, grouped by skill, category, entrypoint digest, and model.
Unknowns remain unknown.
Recorded uses are not all uses; task durations can overlap across skills and must not be summed.
Observational success is not proof of time saved or a substitute for a controlled evaluation.
