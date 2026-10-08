# Evaluation using collected memory

Use real collected Workshop memories, native conversations and actual duct logs from annex.
Synthetic memories, authored benchmark conversations, simulated outcomes and generated evaluation corpora are prohibited.
Isolated unit-test inputs are allowed only within software tests and must never enter memory stores or evaluation results.

## Daily collection

Run the documented `memory daily` command in [memory collection](../../docs/agents/memory-collection.md).
Import both feedback trees, aggregate yesterday’s records in 1000-record batches, retry publication and rebuild each store’s projections.
Preserve source IDs, classifications and bytes.
Report failures without claiming publication succeeded.
Use the command defaults for both feedback trees; a feedback root is `observations`, never its `records` child.
Daily stdout is one JSON result, including per-store errors on partial failure; stderr carries phase and transport progress.
Allow each transport operation its built-in 180-second timeout.
A quiet interval or a stack sampled inside `git push` does not establish a stall.
The ten-minute milestone budget below applies to evaluation, not the total collection backlog.
On failure, retain the result and completed duct log; do not repeatedly rerun publication in the same task.
The collector still attempts the other store and rebuilds local projections after a publication failure.
A publication failure does not block analysis of already available, verified evidence.

Read automation notes from `${CODEX_HOME:-$HOME/.codex}/automations/workshop-daily-memory-and-luna-pilot/memory.md`.
Resolve user-level controls from the current skill catalog; do not look for Workshop controls in project `.agents/skills`.
Run `memory health --store shared` and `memory health --store sensitive` after collection and report queued/pending records separately from missing evidence.
Refresh the automation notes with the actual result, evidence IDs and next actionable step; mark superseded blockers explicitly.

## Daily candidate rotation

Use America/New_York weekdays: Friday PageIndex, Saturday ChatIndex, Sunday SQLite/qmd/Brain retrieval, Monday skill utility assessment, Tuesday native context selection, Wednesday native capture, Thursday storage/recovery.
Take one bounded milestone, at most ten minutes and eight account-backed Luna requests.
Use only the existing account-backed runtime; do not configure paid providers, subscriptions or copied account credentials.

Select existing accessible records before evaluating a candidate.
Record the selection query, IDs, content hashes and inclusion criteria.
Prefer available shared annex content; do not invent a privacy restriction on content already classified as shared.
Preserve actual sensitivity boundaries for other records.
If suitable evidence is absent, report the data gap and stop that milestone without generating substitutes.

Measure source-linked retrieval, capture completeness, recovery correctness, review effort and available runtime/resource costs.
Keep agent self-assessments separate from measured efficiency.
Unknown outcomes remain unknown; retrospective observations do not establish causal skill benefit.
Preserve failed operations and missing evidence.

PageIndex and ChatIndex require compatible account-backed adapters before product execution.
Source review or a native baseline is not execution of those products.
Entire integration is deferred until a concrete unmet capability justifies its maintenance cost.
Do not recreate retired native-trial, synthetic transport or checkpoint generators.

Retain original outputs and classified duct captures in annex.
Update the existing cumulative assessments in `docs/agents` with source revision, roles, evidence level, data boundary, dependencies, decision and next discriminating test.
Follow repository validation, commit provenance and publication rules.
Report evidence IDs and meaningful changes; do not repeatedly probe an unchanged blocker.


## Productive fallback and reporting

If today's candidate is blocked on an unchanged adapter or missing runtime, choose one bounded review of collected evidence: inspect a real rich capture, check missing evidence with `memory health`, or verify recovery of an existing annex artifact.
State that this is a fallback and not execution of the blocked candidate.
Do not make another dated checkpoint or Git commit solely to repeat an unchanged blocker.
Update cumulative assessments only for new evidence or a changed decision.
Use `--details PATH` for feedback JSON, not inline JSON; rich assessments belong under the schema's `assessment` field.
Stage the task's real conversation and finished duct runs using the installed recorder and its actual APM pin.
Never claim that source counts are new imports: `shared` and `sensitive` count inspected source records, while `duplicates` counts already-present records.
