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
Multiple hosts must deliver to that aggregator; independent host aggregation is not a global daily coordinator.

The collector seals yesterday in America/New_York, using receive time to avoid including late deliveries retroactively. It groups all eligible agents' records into 1000-record batches, with at most one remainder per day/store.
Identical records deduplicate by ID.
A local SQLite transaction persists the exact batch bytes and IDs before transport.
Retries reuse them after ambiguous failures.
Late records wait for the next day; missed days catch up at the next run.
No empty batches are published.

The annex transport uploads content, checks presence, publishes an immutable `refs/workshop/memory/v2/<batch UUID>` ref, verifies it, and syncs annex metadata.
Each ref contains only its batch pointer.
The shared repository stores shared metadata/content; sensitive metadata uses its separate repository and content uses the private test-store annex.
Tokens remain in `.git/info` files and are read by a scoped Git credential helper.
Local configuration contains paths, never token values.
Encryption is not configured.

Ordinary clones do not retrieve custom refs or annex content.
`memory restore` explicitly fetches the refs and payloads, verifies SHA-256, validates classification and reconstructs the ledger.
`memory index` and `memory export` rebuild per-store disposable projections.
Recovery works without Entire, qmd or a model.
Backup must include the refs, annex payload remote and unflushed local journals; a regular code clone alone is insufficient.
Current retention is indefinite: no automatic pruning or source deletion.
Remote restore does not recover never-uploaded staging data.

## Commands and local activation

Run `pixi run memory --help`.
The account-backed Luna automation **Workshop daily memory and Luna pilot** runs at 10 a.m. local time in this checkout.
It follows [the scheduled protocol](../../experiments/context-pilots/scheduled-protocol.md).
The computer must be available; completion requires a successful run, not merely the scheduled time.

```sh
pixi run memory daily \
  --public memory/observations \
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
Each store has `metadata` and optionally `payload`, each with `url`, `username`, and `token_file`.
The payload endpoint defaults to metadata.
The tested annex runtime is the existing isolated DataLad/Pixi trial environment.
Every explicit batch commit resolves fresh Codex provenance; missing provenance blocks publication with the outbox retained.

## Initial evidence and limits

- Imported 386 shared and 3 whole-record sensitive legacy observations without removing originals.
  Further daily imports are idempotent.
- Regression tests exercise 2452 records from four concurrent agents, 1000/1000/452 aggregation, daily sealing, duplicate/conflicting IDs, private routing, artifact integrity, ambiguous upload retry, recovery, delivery provenance and CLI error streams.
- A live synthetic roundtrip through the private test-store annex recovered the exact envelope in a fresh checkout.
  `experiments/context-pilots/check_transport.py` retains an opt-in reproduction harness; it writes a new test ref and requires explicit test configuration.
- Initial real records were staged on October 1; their first eligible daily publication is October 2.
  Scheduler creation is not evidence that production publication has completed.

The journals and outbox currently retain all history and aggregation scans retained staging.
This is suitable for the initial few-person trial, not a claim of unbounded throughput.
Migration of other curated Workshop memory families and replacing the feedback recorder's Git compatibility path remain separate work.
First collect reliable evidence; use observed costs before adding compaction or distributed coordination.

## Duct captures as on-demand evidence

Duct is now a Workshop control installed with discovery and feedback.
A finished capture becomes a small evidence envelope containing command, outcome, measured resources and a content-addressed external-artifact descriptor.
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
