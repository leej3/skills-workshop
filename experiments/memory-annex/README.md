# Annex memory storage trial

This is an executable synthetic experiment, not the Workshop memory backend.
Existing Workshop readers, writers, and records are unchanged.

## Storage contract under test

- Each immutable JSON batch has a versioned envelope, a UUID, writer identity, visibility, and complete records with their own UUIDs.
- A batch contains only shared or only sensitive records.
  A sensitive part makes its entire record sensitive; a mixed batch is rejected before any write.
- Each batch is one SHA256 annex object.
  Its pointer lives in an orphan Git commit referenced by `refs/workshop/memory/v1/<batch-uuid>`.
- The shared and sensitive stores are separate Git repositories and annexes.
  Sensitive pointers and annex location logs stay with the sensitive store.
- Upload content before publishing its ref.
  Synchronize annex location metadata separately with `git annex sync --only-annex --no-content origin`.
- Readers explicitly fetch memory refs, resolve their annex keys, and retrieve payloads.
  Neither Entire nor a hosted search service is involved.

The current envelope is deliberately synthetic; it is not a replacement for the existing observation schema.
The classification adapter, production validation, indexing, migration, batch sealing policy, and compaction remain future work.

## Reproduce

The adjacent Pixi lock pins the runtime tested on macOS Apple Silicon.
This trial writes new synthetic batches to these already initialized stores:

- Shared: <https://hub.datalad.org/leej3/skills-workshop>
- Sensitive: <https://hub.datalad.org/leej3/skills-memories-sensitive>

The credential directory must contain `workshop-shared` and `workshop-sensitive`, each containing its repository access token.
Tokens are read at runtime by a scoped credential helper and are never stored in Git configuration, command arguments, result files, or URLs.
Run the commands through the duct wrapper required by project guidance.
From this directory:

```console
pixi install --locked
pixi run python trial.py \
  --workspace /absolute/path/to/new-trial-directory \
  --credential-dir /absolute/path/to/skills-workshop/.git/info \
  --provenance-script /absolute/path/to/commit-provenance/scripts/resolve.sh
pixi run python recovery.py \
  --workspace /absolute/path/to/new-trial-directory \
  --credential-dir /absolute/path/to/skills-workshop/.git/info
```

The workspace must be new.
Rerunning the first command with a different workspace adds new synthetic batches; it never replaces or deletes previous remote data.
The recovery check drops one local synthetic payload per store after annex verifies an available remote copy, then retrieves and verifies it again.
It also tests anonymous denial for sensitive content.

For an empty destination, initialize an annex repository, add a README on `main`, and push `main` and `git-annex` first.
The harness expects that bootstrap to exist.
Forgejo-aneksajo's `/owner/repo.git/config` endpoint initializes the server annex when an authenticated writer sends a `git-annex/` User-Agent.
The harness uses that endpoint and configures the returned UUID and native annex HTTPS URL.
The server may return repeated `[annex]` sections, so parsing permits them.

The harness creates explicit commits with freshly resolved provenance trailers.
Git-annex itself also maintains its automatically generated metadata commits.

## Results: 2026-10-01

The main trial completed in 44.6 seconds with DataLad 1.6.5 and git-annex 10.20260901.
Two independent clones each packed 100 synthetic shared memories into one 11,442-byte batch, then pushed their distinct refs concurrently.
One 308-byte batch held a complete synthetic sensitive record.
A preceding transport probe added another shared batch containing 20 records.
All these synthetic batches remain in their respective remote stores.

Verified:

- Both concurrent ref pushes succeeded without rebasing or changing `main`.
- Annex metadata synchronization reconciled the writers' location records.
  These sync operations were sequential; concurrent metadata-sync contention has not been measured.
- Ordinary clones did not fetch the custom memory refs or annex payloads.
- Explicit ref fetch discovered the appropriate batches in each store.
- Fresh readers retrieved all main-trial records and verified SHA256 hashes.
  Shared Git cloning and shared payload retrieval worked anonymously.
- The private Git repository and annex payload retrieval refused anonymous access.
- Mixed-visibility batches were rejected before writing.
- Default `annex unused` recognized custom refs.
  A deliberately branch-only refspec marked their payloads unused; restoring `+refs/*:+HEAD` retained them.
- Git bundles restored the custom refs and exact commit IDs independently of Entire.
  Payload backup remains separate from the Git bundle.
- Safe local payload eviction followed by remote retrieval restored the same content hashes in both stores.

Initial ordinary Git metadata clone times were 0.718 seconds shared and 1.443 seconds sensitive.
These did not transfer annex payloads; payload retrieval was a separate operation.
After annex initialization, Git reported pack sizes of 8 KiB and 4 KiB respectively, plus small loose-object stores.
This tiny, warm-network test does not establish large-scale clone, indexing, or transfer performance.

## Implications and remaining work

The two-store and immutable-batch design works end to end on the selected Hub.
Different writers do not contend for a common memory-ref tip.
Git-annex still merges shared location metadata and maintains local databases and journals.

The trial simulates two writers using separate clones and the same account; it does not test onboarding a second person's credentials or contribution flow.
The sensitive destination relies on Hub authentication and private-repository access controls; client-side encryption is not required for that access-control boundary and was not configured.
It would add protection against the storage operator, with additional key-management costs.

Before migration, implement schema-preserving routing from the existing sensitivity judgment, record-level indexing, and interrupted-publication recovery.
Measure larger batches and many refs.
Preserve all memory refs in retention scans; do not use branch-only cleanup rules.
Back up both Git metadata and annex content.
No automatic cleanup, production migration, Entire installation, or fork was made.


## Separate private payload store

`split_store.py` uses the sensitive repository for memory refs and <https://hub.datalad.org/leej3/test-store> for payloads, using `workshop-test` in the same credential directory.
Pass the same three arguments as `trial.py`.
It initializes the test repository if needed, and writes only synthetic data.

The successful run stored 1,000 records in a 909,055-byte object:

- Batch creation and upload: 2.792 seconds.
- Ordinary Git clone: 2.627 seconds; explicit memory-ref fetch: 1.880 seconds.
- Separate authenticated payload retrieval: 1.966 seconds, SHA256 verified.
- The metadata remote did not contain that payload; the payload remote did not contain its memory ref.
- Cloning and fetching refs did not download content; anonymous payload retrieval failed.

This demonstrates independently configured repositories and authenticated access, not isolation between two human identities: the supplied tokens belong to the same owner.
Sensitive metadata remains in the private metadata repository.
The extra setup is a second remote, its annex UUID/transport, and credentials.
Clients must retain both remote mappings for recovery.

Two earlier attempts remain as synthetic remote state: bootstrap succeeded before an annex metadata push conflicted, and a second run published one batch before a harness assertion failed.
Initialization now reconciles the server-created `git-annex` branch instead of pushing over it.
The assertion exposed a useful API detail: `annex get --from=origin --key=...` returned zero without content when origin had no known copy.
Retrieval success must include a content-location/hash check, not just the exit code.
No force pushes or remote cleanup were performed.

## Scaling for a few busy contributors

`scale.py` takes the same arguments but performs local operations only.
It uses 100,000 accumulated synthetic assessments, approximately 99 MB total, with varied hash evidence.
This is a history-size fixture, not an assumed daily workload.
Each case has the same records and a different immutable batch size.

| Records per batch | Objects / refs | Annex add | Explicit ref fetch | Unused scan | SQLite rebuild |
| --- | --- | --- | --- | --- | --- |
| 100 | 1,000 | 5.455 s | 0.890 s | 33.956 s | 0.798 s |
| 1,000 | 100 | 1.013 s | 0.126 s | 1.206 s | 0.572 s |
| 10,000 | 10 | 0.596 s | 0.057 s | 0.178 s | 0.594 s |

At 1,000 records per batch, annex content occupied 100 files and 284 directories, and ordinary clone metadata was approximately 56 KB, growing to 124 KB after fetching memory refs.
Payloads remained absent until explicitly retrieved.
The disposable SQLite index was approximately 35 MB.
A warm structured query returning the failure records for one skill had a median of 0.5 ms.
The FTS query was below this harness's 0.1 ms timing resolution; do not interpret its stored rounded zero as a zero-cost query.

A smaller one-record-per-batch baseline (only 1,000 records) already needed 1,000 objects, 2,355 content directories, and a 34.005-second unused scan.
Object/ref count is more important here than raw JSON size.
Explicit commit generation also has overhead: for 1,000 batches it took 78.329 seconds, including 64.497 seconds of mandatory provenance resolution; for 100 batches, 8.010 and 6.557 seconds.

These are one-run local measurements on this Mac with warm filesystem caches, not Hub throughput guarantees.
Clone used `--no-local` to avoid hardlink shortcuts.
Indexing starts from already available payloads and excludes download time.
The script does not simulate realistic prose search relevance, network failures, long-term annex-log growth, compaction, or multiple human accounts.

Use batches of 1,000 records and one daily flush per store, aggregating across agents before emitting a smaller remainder.
See the [accepted policy and Entire evaluation](entire-evaluation.md) for staging, recovery, and integration details.
A local durable queue should acknowledge individual assessments before sealing and uploading a batch.
Keep batches immutable and separated by visibility; rebuild a local SQLite index from accessible content.
Do not scan all history or run retention maintenance on every assessment.
Later compaction can bound the cost of many small time-flushed batches.
Larger batches trade fewer objects for coarser downloads and eviction.

`burst.py` uses the same arguments and a local bare annex destination.
Four independent clones each published five 100-record batches concurrently: all 2,000 records, 20 refs, and 20 payloads were present after 5.739 seconds of burst work.
Four of 20 concurrent annex metadata sync commands returned nonzero; subsequent sequential reconciliation succeeded for every writer.
The test checks final refs and content presence, not crash recovery or network retry behavior.
Production publication needs a durable retry queue and bounded backoff for annex metadata synchronization even though memory refs have independent tips.

## Reusing existing tools

Independence from Entire is an exit-path result, not a goal to rebuild its tools.

- [Entire CLI](https://github.com/entireio/cli/blob/main/docs/architecture/ref-checkpoint-backend.md) already implements capture/checkpoints, independent refs, queued publication, retry, and remote discovery.
  Those are useful integration candidates.
  Its current primary backends read Git contents; non-Git backends are write-only mirrors.
  An annex mirror alone therefore does not move canonical payloads out of Git.
  Annex-aware reads would need an adapter or upstream change; a fork is not yet justified.
- [Entire Brain](https://github.com/entireio/entire-brain) offers local retrieval, indexing, and evidence-linked facts.
  Evaluate it as an optional consumer after annex hydration, with explicit control over model-backed extraction and egress.
  It has not been installed or benchmarked here.
- [DataLad RIA siblings](https://docs.datalad.org/en/stable/generated/man/datalad-create-sibling-ria.html) already separate Git and annex storage, with publication dependencies.
  Its optional archive storage can reduce cold-storage inode use.
  RIA writes use SSH/local access, so it is a design reference or future backend, not a drop-in replacement for the tested Hub HTTPS transport.
- SQLite supplies the rebuildable structured and full-text index used in this benchmark.
  APM, existing discovery integrations, and AutoHarness can retain their current installation/discovery/improvement roles.

The next implementation should be a small storage adapter around the existing observation schema and sensitivity decision, then compare Entire capture and Brain retrieval against that boundary.
These experiments do not migrate current Workshop memory or establish a hosted service dependency.
