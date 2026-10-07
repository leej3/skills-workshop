# Daily aggregation and Entire integration evaluation

## Accepted storage policy

The durable batch target is **1,000 records**, with **one daily flush per store**.
Do not flush on agent completion or a short timer.
At the daily cutoff, gather all available staged records for that store, emit full 1,000-record batches, and emit at most one smaller remainder.
For example, 2,450 records from four agents become batches of 1,000, 1,000, and 450, not four independently rounded batches.
A store with fewer than 1,000 records that day necessarily produces a smaller file; daily visibility and exclusively full batches cannot both be guaranteed.
No empty batches are published.

Each agent writes its own local append-only staging stream, separated by store.
Records retain their existing schema and stable UUIDs.
A durable local append acknowledges collection; upload is a later state.
A flush snapshots complete records up to a cutoff while agents continue in new segments.
Never truncate an active agent file or treat an incomplete final JSONL line as a complete record.

A designated aggregator per store combines sealed segments across agents, deduplicates identical record IDs, and rejects conflicting contents for the same ID.
Agents share a local spool, with a local lock per store preventing overlapping daily aggregation runs.
Records arriving after the cutoff join the next daily flush.

The aggregator persists a manifest mapping record IDs and source offsets to batch IDs, uploads annex content, publishes the independent batch refs, and retries annex metadata synchronization.
Source segments are acknowledged only when publication is confirmed.
Recovery must reuse existing batch IDs and manifests so a crash or ambiguous network result cannot create a second logical copy.
No automatic staging deletion is enabled by this design document.

Sensitivity applies to each entire record and its supporting evidence.
A sensitive record enters only the sensitive spool and aggregation.
Classification reasons, staging files, and publication manifests inherit the relevant store's visibility.
Local retrieval and synthesis may combine shared and sensitive evidence; derived insights are classified on their own publishable content.
The separate private payload remote remains a transport choice for the sensitive store, not a third assessment classification.

This records the accepted policy; it does not migrate the current recorder or install a daily scheduled job.
Production implementation still needs schema validation, recovery tests, and an explicit daily cutoff configuration.

## Executed integration probe: 2026-10-01

`entire_probe.py` uses synthetic data in a new isolated repository.
Tested checksum-verified macOS arm64 release assets:

| Tool | Release asset | SHA256 |
| --- | --- | --- |
| Entire CLI 0.11.3 | `entire_darwin_arm64.tar.gz` | `ad8de534e985ca2f4f6ba98dea810ab4c88cd06e81dccd04d38d68c1021b28cf` |
| Entire Brain 0.1.0 | `entire-brain_0.1.0_darwin_arm64.tar.gz` | `8c4e9eb6f4a5d962af88d39b05c3f6213ad24639f2416ccc863b3164a124ce46` |

Sources: [CLI release](https://github.com/entireio/cli/releases/tag/v0.11.3) and [Brain release](https://github.com/entireio/entire-brain/releases/tag/v0.1.0).
Binaries were extracted into an evaluation directory, not registered globally.
The probe redirects XDG and plugin data/config/state/cache directories, disables Brain egress and model use, and skips backfill and daemon registration.
The fixture has no Git remote.
No Entire login was used.
These are application-level controls, not a packet-capture proof that every dependency made zero network calls.

Verified with the released binaries:

- Codex transcript import works without an account.
  Repeating import reports the turn already imported instead of duplicating it.
  Imported checkpoints are read-only and cannot resume the original agent session.
- An unconfigured repository's import used `entire/checkpoints/v1`.
  An explicit `checkpoints.primary.type = git-refs` setting produced an independent `refs/entire/checkpoints/<shard>/<id>` ref.
  The final probe disables live capture and telemetry in fixture settings; it does not install agent hooks.
- Brain setup with `--no-backfill --no-daemon --agent none` indexed the session, documents, and history without login.
  An explicitly classified fact was recorded and retrieved with `--agent none`.
- Graph-dependent semantic and entity indexing reported unavailable.
  This was a degraded but queryable setup, not a successful semantic-search evaluation.
- Brain did not install a launchd watcher.
  Its local memory coordinator was reported running: `--no-daemon` must not be interpreted as prohibiting every internal worker process.

### Reproduced transcript compatibility gap

CLI import compacted the transcript into lines shaped like:

```json
{"v":1,"agent":"codex","type":"assistant","content":[{"type":"text","text":"Synthetic evidence..."}]}
```

Brain reported one captured session but zero conversation exchanges.
A keyword query for an exact transcript term returned no conversation results.
This is a retrieval failure despite successful import and setup exit codes.

The diagnostic adapter saved the compact export, replaced only Brain's generated transcript copy with the original Codex `response_item` JSONL, and ran `entire-brain refresh history`.
The same query then returned the expected exchange with session ID, source path, and line range.
Neither Entire source nor the canonical checkpoint was changed.
A normal session refresh can overwrite this projection, so this is a demonstrated adapter seam, not a production fix.

Source inspection is consistent with the result: Brain's conversation parser reads assistant text from `message.content` for an `assistant` record, whereas the compact export has top-level `content`.
Source snapshots inspected were CLI `30fa2a79ffe2c269914b036df62084ba25c94921` and Brain `f423963df61fe70077234170567055aa88cb3e62`; runtime findings above refer to the released binaries, not an assumption that main equals a release.

## Provisional integration boundary

**Superseded recommendation:** the [context-stack landscape](../../docs/agents/context-stack-landscape.md) keeps Brain as one retrieval candidate alongside other providers.
The diagram below describes this experiment, not a selected Workshop-wide architecture.
The probe findings remain valid within their stated scope.

```text
agent observations and captured evidence
                 |
     existing schema + sensitivity routing
                 |
       per-agent, per-store durable spool
                 |
       daily aggregation: 1000 records
                 |
       annex payloads + independent refs  (canonical)
                 |
       retrieve authorized batches locally
                 |
       disposable projection/normalization
                 |
       Brain keyword search and source references
                 |
       synthesize across shared + sensitive evidence
                 |
       obscure sensitive details in derived insights
                 |
       publish the resulting insight store
```

Keep assessment records distinct from captured transcripts: a successful checkpoint capture is not a skill assessment.
Preserve raw evidence and provenance alongside assessments, rather than converting everything into Brain facts.
Brain-authored facts worth retaining must flow back through the normal classification and record path; the Brain directory must remain rebuildable.
Aggregate across shared and sensitive evidence locally to produce the overall insights.
Sensitive evidence may inform a shareable insight when its sensitive details are obscured or omitted in the published result.
Publish that derived insight store; raw sensitive facts, identifying details, and revealing source excerpts remain private.
Keep full evidence links locally so insights remain traceable without requiring private evidence to be generally retrievable.
A derived insight is not automatically sensitive merely because some supporting evidence is private; apply the existing sensitivity judgment to the insight itself.
The local combined index is a working input to synthesis, while the published store contains the resulting publishable insights.

Entire is useful as a capture/import component, but its current primary storage contract is Git-backed.
Non-Git plugins are write-only mirrors, and annex pointer hydration is not a built-in primary read path.
Full Entire lifecycle operations would still expect Git checkpoint contents.
Start with a private local capture cache and a normalized export into our storage path, or use transcript import only in a disposable retrieval projection.
Do not push that cache as our durable memory store.
Live hook capture and cache cleanup have not yet been tested here.

Brain is the more immediately demonstrated reuse opportunity: account-free, model-free keyword retrieval with inspectable source references.
The transcript format gap needs a versioned adapter or an upstream fix.
An upstream parser fix is preferable to a maintained fork; no issue or PR has been posted.

Both projects currently use the MIT license.
Hosted search, publishing, model extraction, and semantic/code indexing are optional capabilities, not required for this tested path. Pin compatible releases and keep JSON/JSONL plus annex keys and ref manifests as the exit format.
No hosted service purchase or production adoption occurred in this experiment.

## Reproduce

Download the two release assets above, verify against their release checksums, and extract `entire` and `entire-brain` into a dedicated directory.
From the Workshop root, run through the project's duct wrapper:

```console
pixi run python experiments/memory-annex/entire_probe.py \
  --workspace /absolute/path/to/new-evaluation-directory \
  --bin-dir /absolute/path/to/verified-binaries \
  --provenance-script /absolute/path/to/commit-provenance/scripts/resolve.sh
```

The script saves command results and both transcript dialects outside the repository.
It asserts successful retrieval after the diagnostic conversion.
The fixture covers one session, one authored fact, and one document; it does not establish ranking quality, ingestion throughput, or end-to-end annex integration.

References:

- [Entire primary/mirror and independent-ref design](https://github.com/entireio/cli/blob/30fa2a79ffe2c269914b036df62084ba25c94921/docs/architecture/ref-checkpoint-backend.md)
- [Brain configuration, privacy, and retrieval](https://github.com/entireio/entire-brain/blob/f423963df61fe70077234170567055aa88cb3e62/docs/reference.md)
- [Brain conversation parser](https://github.com/entireio/entire-brain/blob/f423963df61fe70077234170567055aa88cb3e62/internal/cli/conversation.go)

## Annex round-trip: October 7, 2026

Decision: align at the checkpoint metadata/export boundary and retain annex as canonical payload storage.
Do not make Entire's current primary backend the Workshop storage contract.
An annex pointer is not a transparent replacement for a transcript Git blob.

The new [round-trip fixture](entire_annex_roundtrip.py) used the prior synthetic checkpoint and the same pinned Entire CLI 0.11.3 binary.
It placed an exact checkpoint-tree archive in git-annex, indexed it on `workshop/captures/v1` in an isolated local bare metadata repository, and cloned that repository without local object sharing.
The clone initially had no payload.
Fetching from the directory annex remote reproduced the archive byte for byte.

The fixture then built an Entire checkpoint with ordinary metadata but annex pointers at the transcript paths.
`entire checkpoint explain ID --transcript` returned exit status 0 and the literal annex pointer, not the transcript, even though annex content was present locally.
Readers use Git tree blobs rather than hydrated working-tree files.
After constructing a disposable checkpoint ref with the retrieved original bytes as blobs, its Git tree hash exactly matched the original checkpoint.
Both Entire's JSON metadata read and exact transcript export succeeded.

The first probe attempt left Entire disabled and received a disabled-status message with exit 0; it did not prove a transcript read.
The corrected fixture enables the isolated repository's read path without installing hooks, then asserts content equality in addition to exit status.
Local evidence is retained under `~/.local/state/skills-workshop/entire-evaluation/annex-roundtrip-20261007-02/`, including `result.json`, all commands, pointer output, and the recovered transcript.
Its source checkpoint is `c5a9c4b050fb`; the archive key is `SHA256-s10240--e1f9a93254eafea39865cefa457860a36a84bfe1f553e64e3b71ae4df75eb66c`.

This proves local read compatibility after hydration, using a synthetic fixture.
It does not test Entire hosted services, Brain retrieval, live agent capture, resume, or cross-project discovery.
The October 1 Brain parser mismatch remains unresolved by this test.
The current upstream [backend contract](https://github.com/entireio/cli/blob/main/docs/architecture/ref-checkpoint-backend.md), reviewed October 7, still documents Git-backed primary stores and write-only non-Git mirrors.
The tested release remains the prior pin; this is not a claim that latest upstream behavior was executed.
No hosted account, model invocation, or credential was needed for this local probe.

Reproduce after running the earlier synthetic import probe:

```console
pixi run python experiments/memory-annex/entire_annex_roundtrip.py \
  --source-repo /absolute/path/to/earlier-probe/repo \
  --entire /absolute/path/to/pinned/entire \
  --workspace /absolute/path/to/new-roundtrip \
  --provenance-script /absolute/path/to/commit-provenance/scripts/resolve.sh
```

Run through duct, as with the earlier probe.
Every authored fixture commit resolves fresh provenance.
Next discriminating test: import a recovered real Workshop capture into a disposable Entire repository, normalize its transcript for Brain if needed, and verify source-linked retrieval.
Only consider changing Entire's primary storage implementation if that adapter proves too costly or loses required lifecycle functionality.
