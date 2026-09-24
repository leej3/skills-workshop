---
name: workshop-feedback
description: Record minimal local skill-use outcomes, group exceptional lessons, and curate publication-safe feedback. Routine use needs one local call, not a report or Git commit.
---

# Workshop feedback

Separate baseline measurement, qualitative learning, and publication.
Use the bundled standard-library Python hook; it does not need Pixi, a Workshop checkout, registration, Git, or network access.
Do not narrate routine collection or interrupt the main task for it.

## Baseline: one local call

After actual material use, record once per skill and task (not per command).
Resolve `scripts/usage.py` relative to this skill directory:

```console
python /path/to/workshop-feedback/scripts/usage.py record duct \
  --task build-validation --outcome success
```

Use a short, stable task category, without project names or task transcripts.
`--outcome` describes whether the skill performed its intended role: `success`, `partial`, `failure`, or `unknown`.
An expected project test failure can coexist with successful log capture; use optional `--task-outcome` separately.
For measured elapsed time, add `--duration-seconds 120 --duration-scope task` (whole task) or `--duration-scope skill` (measured skill-active interval).
Omit unmeasured durations; never estimate from memory or imply time saved.
Add `--skill-path` to hash the actual SKILL.md when convenient; its path and contents are not stored.
Add `--model` only when known.
Reuse `--event-id` with a random identifier for an uncertain retry; changed content with the same ID is rejected.

Records are private JSONL under `${XDG_STATE_HOME:-~/.local/state}/skills-workshop/feedback/`, outside Git, with restrictive permissions.
No session, conversation, project, environment, command, or log metadata is collected automatically.
A local host may invoke the same CLI with arguments as its completion hook; installation alone does not register an automatic host callback.

Skip mere reads, installation, the feedback recorder, and bookkeeping.
Honor explicit user opt-outs and omit collection when even a task category would be sensitive.
Do not log exemptions or create a pending-work obligation for a missed routine observation.
If collection fails, finish the task; mention it only when it affects requested measurement or suggests a recurring fault.

## Exceptional lessons

Write a qualitative note only for new failures of the skill, workarounds, surprising costs, ambiguities, concrete improvements, or success in a new setting.
Routine success is covered by the baseline; it needs no prose report, rating, commit, or push.
A user-requested evaluation may collect richer evidence for a bounded period.

```console
python /path/to/workshop-feedback/scripts/usage.py note duct \
  --group macos-sampling --priority 1 --confidence high \
  --summary "Older runtime failed to sample resources on macOS" \
  --action "Use the verified runtime and retain a sampling regression check"
```

Link actual baseline records with repeatable `--usage-id` when available.
Use the same skill/group for recurring findings; append a note to refine its action, confidence, priority, or status (`open`, `resolved`, `deferred`).
Never rewrite the historical observations.
Grouping and resolution do not require a new skill or a public report.

Read `summary` for outcomes and median measured durations grouped by skill, task category, skill digest, and model.
Read `insights` for open groups ordered by priority, then distinct linked uses; both accept `--since YYYY-MM-DD`.
Priority is an explicit judgment: 0 immediate harm or data loss; 1 a blocker or recurring material failure; 2 a useful improvement; 3 a minor refinement.
Confidence reflects evidence quality, not frequency.
Check the supporting observations before changing a skill.
Counts describe recorded uses, not all uses; missing outcomes and times remain unknown.
Do not sum overlapping task durations across skills or interpret these observational statistics as causal benefit.

## Publication is separate

Local observations and aggregates are not automatically public.
Read [publication.md](references/publication.md) before promoting a lesson to Git-backed memory or publishing it.
Use the existing `scripts/feedback.py` launcher only for an intentionally curated public-memory record after that review; it requires the configured Workshop checkout and Pixi.
Do not copy the JSONL store into a repository.
The user may authorize publication of a reviewed set; use that authorization without asking again, but inspect the exact staged records and metadata first.
Shared-thread messages still require their separately applicable approval.
