# Portable memory collection

Implemented 2026-10-01.
The daily collector is a transitional capture path: existing feedback files remain intact while immutable annex batches accumulate.
Entire is not required for ingestion, publication, recovery, or SQLite projection.

## Evidence contract

`schemas/memory-envelope-v1.schema.json` separates source payload, provenance, classification, artifacts and relations.
Preserve native fields in `payload`; retain exact original bytes in hashed base64 artifacts.
Unknown runtime/model/skill/task context is null and listed in `context.missing`, not inferred from the collecting agent. Each batch embeds its envelope and observation schemas and delivery timestamps/agent labels.

Evaluation collectors should retain the complete prompt, fixture, rubric, treatment artifact, protocol, native response/transcript, source/tool versions, runtime/model settings, budget, isolation and grading conditions.
Record digests *and bytes*: a digest alone cannot reconstruct a lost source.
Distinguish proposed, attempted, failed, completed and graded trials in native payloads.
The generic envelope does not establish experimental validity.
The native pilot freezes those inputs and leaves grading unset.
Preserve measurement scope and explicit unknowns; never equate subscription access with measured zero cost.

A classification applies to the whole envelope, artifacts included.
The legacy importer validates observation-v2 and merges the private overlay before routing.
Missing private trees fail closed.
Shared records cannot carry classification reasons.
Once accepted, an ID's content and classification are immutable; corrections require a new ID with a relation to the previous record.
Changing classification after publication needs explicit remediation of the original publication, not an automatic rewrite.

## Aggregation and recovery

Each agent stages in its own SQLite file outside Git.
An identity registry rejects conflicting IDs across agents and stores.
A designated aggregator per store seals one day at a time under an OS lock.
All agents use the local staging area.
Multi-host support is an explicit non-goal; do not design host-to-host transfer or distributed coordination.

When a sealed batch must be replaced without rewriting its original evidence, use `memory supersede-batch --manifest PATH` to append a `memory-batch-supersession-v1` event to that store's `batch-supersessions.jsonl`.
The command verifies the held source batch, replacement batches and receipts, complete source-record accounting, and explicit IDs retained local-only.
The original batch and artifacts remain unchanged.
Resolved batches are historical: the collector excludes them from pending publication, indexes, and exports even if a hold is later removed.
The event retains replacement refs/digests and local-only record IDs.
If a previously local-only record is later corrected and published, use `memory amend-supersession --manifest PATH` to append a `memory-batch-supersession-amendment-v1` event.
The amendment must link the record through `reclassified-from` in a durably published replacement batch; it removes that source ID from the local-only list without editing the original resolution or source batch.
Never clear a hold as a substitute for recording a supersession.

The collector seals yesterday in America/New_York, using receive time to avoid including late deliveries retroactively. It groups all eligible agents' records into 1000-record batches, with at most one remainder per day/store.
Identical records deduplicate by ID.
A local SQLite transaction persists the exact batch bytes and IDs before transport.
Retries reuse them after ambiguous failures.
Late records wait for the next day; missed days catch up at the next run.
No empty batches are published.

The annex transport uploads content, checks presence, publishes an immutable `refs/workshop/memory/v2/<batch UUID>` ref, verifies it, and syncs annex metadata.
Each ref contains only its batch pointer.
The project's GitHub repository (`git@github.com:leej3/skills-workshop.git`) stores shared memory refs, artifact refs, and the `git-annex` branch.
Shared payload bytes live on the DataLad Hub annex at `https://hub.datalad.org/leej3/skills-workshop.git`.
GitHub is the canonical shared Git store; the Hub is its content server.
Sensitive metadata uses its separate private repository and content uses the private test-store annex.
Tokens remain in `.git/info` files and are read by a scoped Git credential helper.
Local configuration contains paths, never token values.
Encryption is not configured.

Ordinary clones do not retrieve custom refs or annex content.
`memory restore` explicitly fetches the refs and payloads, verifies SHA-256, validates classification and reconstructs the ledger.
`memory index` and `memory export` rebuild per-store disposable projections.
Recovery works without Entire, qmd or a model.
Backup must include the GitHub memory/artifact refs and `git-annex` branch, annex payload remote and unflushed local journals; a regular code clone alone is insufficient.
Current retention is indefinite: no automatic pruning or source deletion.
Remote restore does not recover never-uploaded staging data.

## Commands and local activation

Run `pixi run memory --help`.
The account-backed Luna automation **Workshop daily memory and Luna pilot** runs at 10 a.m. local time in this checkout.
It follows [the scheduled protocol](../../experiments/context-pilots/scheduled-protocol.md).
The computer must be available; completion requires a successful run, not merely the scheduled time.

```sh
pixi run memory daily \
  --private "$HOME/.local/state/skills-workshop/feedback-overlay" \
  --config "$HOME/.local/state/skills-workshop/memory/transport.json"
pixi run memory status --store shared
pixi run memory restore --store sensitive --config /path/to/transport.json
pixi run memory index --store shared --output /path/to/shared.sqlite
pixi run memory export --store sensitive --output /private/path/sensitive.jsonl
```

Default state is `~/.local/state/skills-workshop/memory`; override using `memory --state PATH COMMAND`.
Keep it outside Git.
Output is JSON; failures use stderr and nonzero status without echoing evidence.
Agent-native envelopes enter via `memory ingest - --agent LABEL`.

Local transport configuration has `annex_bin`, `provenance_script`, and `stores`.
Each store must explicitly specify `metadata` and `payload`.
`metadata` is an ordinary Git endpoint with a `url`; SSH uses the configured SSH credential.
An authenticated HTTPS metadata endpoint additionally supplies `username` and `token_file`.
`payload` supplies the Hub `url`, `username`, and `token_file` for annex endpoint discovery and content access.
Only the payload server is queried for annex configuration; GitHub is configured with `annex-ignore=true` for content while still synchronizing Git metadata.
There is no fallback from payload to metadata and no compatibility mode for the previous shared Hub Git store.
The root Pixi environment pins the git-annex wheel; use `pixi run git annex`.
Its supported platforms require macOS 14 on Apple Silicon, macOS 15 on Intel, or glibc 2.34 on Linux.
The active configuration's `annex_bin` selects the project's `.pixi/envs/default/bin`, not a host installation or the earlier trial environment.
Every explicit batch commit resolves fresh Codex provenance; missing provenance blocks publication with the outbox retained.

Shared endpoint configuration (the token file contains only the content-server token):

```json
{
  "metadata": {
    "url": "git@github.com:leej3/skills-workshop.git"
  },
  "payload": {
    "url": "https://hub.datalad.org/leej3/skills-workshop.git",
    "username": "leej3",
    "token_file": "/path/to/workshop-shared-token"
  }
}
```

The collector uses a separate working checkout of this same GitHub repository so publishing evidence does not change the developer's index or code branch.
Local journals and indexes are working state outside Git; their published records are carried by the repository's annex refs.
To inspect those refs in an ordinary code clone:

```sh
git fetch origin 'refs/workshop/*:refs/workshop/*'
pixi run git annex init
git config annex.used-refspec '+refs/*:+HEAD'
git for-each-ref refs/workshop refs/remotes/origin/git-annex
```

Use `memory restore --store shared --config /path/to/transport.json` with a fresh `--state` directory to recover records from GitHub and fetch their batches from the annex server.
Artifact downloads remain explicit through `memory fetch-artifact`.

## GitHub storage correction: 2026-10-02

The initial shared transport put Git history on DataLad Hub instead of this project's GitHub repository.
That deployment was incorrect for the intended repository-backed storage design.
The migration published shared records and artifact refs to GitHub, with annex location metadata on its `git-annex` branch.
Its historical counts included synthetic evaluation records and are withdrawn as evidence of real-memory coverage.
The October 7 cleanup replaces affected batches while preserving genuine record bytes.
The active collector now uses this GitHub destination, and the development checkout is annex-enabled with these refs fetched.
Old batch commits were not imported and the previous shared Hub Git history is not used for recovery or ongoing publication.
Sensitive records remain on their private endpoints.

## Initial evidence and limits

- Imported 386 shared and 3 whole-record sensitive legacy observations without removing originals.
  Further daily imports are idempotent.
- Regression tests exercise 2452 records from four concurrent agents, 1000/1000/452 aggregation, daily sealing, duplicate/conflicting IDs, private routing, artifact integrity, ambiguous upload retry, recovery, delivery provenance and CLI error streams.
- Initial real records were staged on October 1; their first eligible daily publication is October 2.
  Scheduler creation is not evidence that production publication has completed.

The journals and outbox currently retain all history and aggregation scans retained staging.
This is suitable for the initial few-person trial, not a claim of unbounded throughput.
The curated v0 working tree now lives outside the checkout and uses lossless annex snapshots; feedback staging also lives outside Git.
First collect reliable evidence; use observed costs before adding compaction.

## Duct captures as on-demand evidence

Duct is now a Workshop control installed with discovery and feedback.
A finished capture becomes a small evidence envelope containing command, outcome, measured resources and a content-addressed external-artifact descriptor.
All collected logs, regardless of size, use this one external-artifact path and are fetched only on demand.
Small measurements and artifact references stay in the memory record; there is no inline small-log tier.
The complete exact capture files are stored in a deterministic compressed archive in annex under `refs/workshop/artifacts/v1/<SHA-256>`.
They are not embedded in the 1000-record batches.

`memory capture-duct RUN --store STORE --agent LABEL --config CONFIG` stages the assessment and uploads the archive immediately; `--related UUID` links its assessment, and sensitive captures require `--reason`.
Daily batch publication verifies referenced content is uploaded first.
Without `--config`, collection stages locally for daily publication.
No capture is deleted.

Ordinary restore fetches memory batches only.
Explicit `memory fetch-artifact REFERENCE_JSON --config CONFIG --output ARCHIVE` retrieves a referenced archive and verifies its content hash and size.
Backup/retention must cover both memory and artifact refs plus annex payloads. Do not instrument capture/upload commands with duct: doing so would create recursive capture obligations.

The associated record and its artifacts share classification; a sensitive capture is kept in the sensitive store.
A public trial may have a separate private supporting capture containing local execution paths; that private record points to the public trial without exposing its details in the shared store.


## Retiring the repository memory directory

`memory-storage.json` selects the annex-backed layout and identifies the initial curated snapshot.
The compatibility working copy is `~/.local/state/skills-workshop/memory/legacy`, overridable with `WORKSHOP_MEMORY_WORKTREE`.
It contains curated skills, projects and events plus feedback staging; it is not tracked in the code branch.
The collector imports feedback with its private overlay and snapshots changed curated files as one compressed annex artifact.
Curated snapshots exclude observations, preserving whole-record private routing.
This is a compatibility adapter for the existing v0 commands, not a replacement for per-agent journals and 1000-record assessment batches.
Local working copies still contain individual files; durable snapshots do not.
Curated source records remain shareable; sensitive evidence belongs in the classified collector.

Snapshots preserve exact JSON bytes and relative paths.
Their content-derived identity deduplicates unchanged trees; an epoch sentinel explicitly marks an unknown source event time, while batch delivery provenance records collection time.
Use `memory snapshot-curated DIRECTORY` to stage a snapshot without flushing.
The daily collector does this automatically before its usual seal/upload step.

To recover the initial curated working copy, save the `curated_snapshot` descriptor from `memory-storage.json` to a file, then run:

```sh
pixi run memory fetch-artifact descriptor.json --config /path/to/transport.json --output curated.tar.gz
pixi run memory restore-curated curated.tar.gz --output /path/to/new-working-copy
```

Recovery requires a new destination and never overwrites local work.
For later snapshots, restore/export the shared memory batches and select the `workshop-curated` record from the desired batch delivery date, then fetch its external artifact.
Feedback records remain independently recoverable from the classified memory batches.
The one-time migration retains a verified complete local backup, including previously untracked observations; deleting the repository directory does not delete those records.
An ordinary clone carries the initial snapshot descriptor, not its payload.

## Linked skill-use records — October 7, 2026

The existing `feedback-local record` command accepts `--capture REQUEST.json` alongside a schema-validated `assessment` in `--details`.
It calls `memory capture-feedback`, retaining the original observation, explicit transcript snapshot, selected finished duct logs, optional pinned APM skill reference, and hashed manifest in one external annex artifact.
The envelope links back to the observation UUID and embeds its self-assessment for indexing.
The source observation remains independently importable through the existing daily collector.

`memory show-capture UUID --store STORE --output NEW_DIRECTORY --config CONFIG` resolves either the observation or capture ID, including captures still in journals, retrieves annex bytes when necessary, and verifies every member before extraction.
A retry of the same recording uses the first snapshot; transcript appends do not silently change an earlier capture.
The full supplied transcript is captured through the collection byte boundary.
The recorder does not install a hook, fetch external attachments, or infer which old duct runs belong to a session.
Agent utility/efficiency judgments remain self-assessments; later independent evaluations should be linked records.

`memory catalog --store shared --output NEW_DIRECTORY` exports JSON envelopes under `captures/<shard>/<uuid>/metadata.json` with `index.json` at the root.
This is a Workshop catalog suitable for a separate `workshop/captures/v1` Git branch in this repository, not an Entire checkpoint store.
It contains metadata and annex descriptors, not transcript or log payloads.
Exports include staged records; ensure their artifact uploads succeeded before advertising remote availability.
The exporter does not push or mark records published.
Sensitive catalogs must remain on a private store; never combine them into the shared branch.
A fresh checkout can run `memory import-catalog DIRECTORY` followed by `show-capture` with the transport configuration.
The existing daily batches remain the canonical envelope publication path.

Verification on October 7 exercised the real recorder on a private task conversation and ten explicitly selected duct runs.
The configured sensitive transport accepted the 761,861-byte archive; a fresh memory state imported its catalog, downloaded the artifact from the configured remote, and recovered all 55 members with archive and member digest checks.
The catalog used for this recovery was copied locally; GitHub catalog publication was not established by that test.
The synthetic acceptance capture was removed on October 7; it is not collection evidence.

## Synthetic evidence removal — October 7, 2026

Synthetic memory generators, authored evaluation corpora and their derived findings were retired at the user’s request.
Isolated software unit-test inputs remain permitted and must not enter memory stores.
Evaluations now use collected records and existing annex evidence under the [scheduled protocol](../../experiments/context-pilots/scheduled-protocol.md).

The cleanup removed 73 synthetic or dependent records from local journals and replicas, along with 45 exclusively associated artifacts.
Six older synthetic v1 batches and two isolated transport/retrieval test batches were also removed.
Mixed published batches were replaced with genuine records preserved byte-for-byte before deleting their old refs and payloads.
Direct annex checks verified absence of 60 selected keys across current and legacy endpoints.

Hash checks preserved all 841 shared and 238 sensitive source envelopes in the removal plan.
These local counts include unpublished records and retained historical classification sources; they are not publication counts.
A fresh remote restore recovered 683 shared records in seven batches and 69 sensitive records in three batches, with no selected synthetic IDs.
Twenty-one generator-owned local workspaces/files and 26 raw generator-run directories were removed.

The cleanup receipts contain IDs, hashes, ref changes and verification results in the local `synthetic-removal-20261007` state directory.
They retain no synthetic payloads.
Repository history was not rewritten; prior source commits are historical, not active tooling or evaluation evidence.
Original genuine conversations remain unmodified, including any historical discussion of retired experiments.

## Collection health

`pixi run memory health --store shared` prints one JSON report for recorded skill uses in the last seven days, newest first, limited to 50 uses.
Select the private report with `--store sensitive`.
`--days` and `--limit` are positive integers.
The report states the total matching count, returned count and whether it was truncated; summary counts cover returned uses only.
It cannot detect skill uses that were never recorded.

The report reads source observations, private overlays, journals and active batches, including observations not yet queued.
Both feedback trees must be available so a missing private overlay cannot silently expose a shared placeholder.
Private fields never enter the shared report.
`--public` and `--private` override the source trees.
It neither imports nor publishes records.

Each use lists presence of the agent assessment, captured conversation, duct logs and pinned APM reference.
Explicitly linked duct evidence counts as present and is listed by ID; unattached logs are not guessed from timestamps.
Declared evidence gaps remain visible.
Missing components describe available evidence, not an automatic policy violation: older minimal observations and tasks with no command execution may legitimately lack them.

Storage status distinguishes unqueued, journaled, pending, held and published records.
For rich captures, local payload status verifies archive size/hash.
Upload receipts and batch publication receipts are historical evidence, not a current availability guarantee.
Older immediate uploads without saved receipts are reported as unknown.
New immediate uploads save their receipt for future reports.
Storage status describes the rich capture when present, otherwise the observation; separately linked duct IDs do not imply that their payloads were checked.

To check current metadata refs and annex payload presence, run:

```console
pixi run memory health --store sensitive --verify-remote --config /absolute/path/to/transport.json
```

This may initialize/update the local transport cache and contact its configured remotes, but does not download evidence payloads.
Remote metadata absence, payload absence and check failures remain distinct.
`retrievable` means both the metadata ref and content-addressed payload are present; it is not a fresh byte-for-byte download test.
Configuration or initial connectivity failures fail the command rather than reporting a healthy store.

Every use includes an `inspect_command`.
For a rich capture it prints the full envelope using `show-capture`; add `--output NEW_DIRECTORY` and `--config CONFIG` to recover the complete archive.
For an observation without a capture it uses `health --id UUID`, which includes the complete observation regardless of age.
Evidence gaps return exit status 0 with issue fields; invalid inputs or operational failures return 1.
CLI syntax errors return 2.
