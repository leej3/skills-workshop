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

Initial ordinary clone times were 0.718 seconds shared and 1.443 seconds sensitive.
After annex initialization, Git reported pack sizes of 8 KiB and 4 KiB respectively, plus small loose-object stores.
This tiny, warm-network test does not establish large-scale clone, indexing, or transfer performance.

## Implications and remaining work

The two-store and immutable-batch design works end to end on the selected Hub.
Different writers do not contend for a common memory-ref tip.
Git-annex still merges shared location metadata and maintains local databases and journals.

The trial simulates two writers using separate clones and the same account; it does not test onboarding a second person's credentials or contribution flow.
The sensitive destination relies on Hub authentication and private-repository access controls; client-side encryption was not configured.

Before migration, implement schema-preserving routing from the existing sensitivity judgment, record-level indexing, and interrupted-publication recovery.
Measure larger batches and many refs.
Preserve all memory refs in retention scans; do not use branch-only cleanup rules.
Back up both Git metadata and annex content.
No automatic cleanup, production migration, Entire installation, or fork was made.
