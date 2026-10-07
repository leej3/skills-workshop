# STAMPED assessment of the Workshop workflow

Assessed October 1, 2026, against Workshop commit `61eba1f6d864186455e395853694fc0fb09ea211`.
Assessor: Codex, using the local `stamped-assess` skill at `cda6aa85d5c41b63176032240e5da8a1d3934d7f` and its declared assessment tool revision `e367080f40e5f99e9cad31e885c9549d37e21b42`.
Reference bundle: `stamped-2026-09-25`, principles 0.2.0, checklist 0.3.1.
The prior structured assessment and scores were withdrawn on October 7 because their evidence included retired synthetic trials.
The source-based design questions below remain open; they are not validated outcome claims.

## Finding

The workflow has a sound preservation and modularity design, but it is not yet demonstrably optimized or independently reproducible end to end.
The largest remaining risks concern incomplete execution provenance and reliance on author-host configuration, rather than the choice of retrieval product.
Before adding more adapters, establish one complete handoff and recovery path and measure the operational burden of collecting useful evidence.
This assessment proposes next actions; it does not implement them.

The use case is a few people running busy agents, retaining reusable evidence and replacing downstream tools without losing data or requiring proprietary paid features.
The assessor selected priorities from the user's stated preferences; the rubric remains provisional and not human-calibrated.
No aggregate STAMPED score is appropriate.
The checklist informs eight selected criteria and does not exhaust each principle.

## Principle findings

| Principle | Finding under this rubric | What works | Remaining gap |
|---|---|---|---|
| **Self-contained** | Partial | Source, schemas, locks and documented external stores form useful building blocks. | No single versioned manifest resolves the complete workflow: annex endpoints/ref namespaces, schema/tool versions, local journals, provenance helper, transport configuration and scheduled execution. |
| **Tracked** | Partial | Immutable identities, hashes, original artifact bytes, Git history and retained captures support audit. | Duct's commit plus dirty flag does not preserve exact uncommitted source. Task-to-capture links are optional; full runtime/environment versions remain incomplete. |
| **Actionable** | Partial | Ingest, flush, publish, restore, index and explicit artifact fetch are executable. Focused regression tests pass. | Capture/classification remain agent-followed procedures; the first production daily cycle and complete recovery independent of this host are not established by these tests. |
| **Modular** | Demonstrated for the selected boundary criterion | Canonical records, large artifacts, derived indexes and shared/sensitive stores are separated. Entire is replaceable. | Keep policy bundling distinct from execution capability; Workshop dependency should not leak into unrelated consumers or the con/duct executable. |
| **Portable** | Partial | Pixi, APM and npm locks describe substantial dependencies. | The annex runtime, provenance helper, local paths and account-backed scheduler still require host setup. A fresh checkout on the same machine is not a fresh-host test. |
| **Ephemeral** | Partial | Temporary test workspaces and rebuildable projections can be discarded. | Complete disposable execution has not been demonstrated. Unflushed journals, originals and annex content must survive worker loss. |
| **Distributable** | Partial | Published code and explicit annex fetch support sharing; earlier same-host archive retrieval succeeded. | A different authorized recipient and complete backup restore have not been tested. Access restrictions are legitimate; the retrieval procedure still needs demonstration. |

The source requirements S.1, T.3/T.5, P.1/P.2 and D.1 remain incompletely established; their normative importance is not reduced by assigning a use-case priority.
An unmet evidence requirement is not automatically a demonstrated implementation failure.

“Self-contained” does not require putting every log in a clone or flattening all stores into one directory.
A single top-level object can reference content-addressed modules, fetched on demand.
Our architecture is compatible with that approach; the missing piece is a complete, versioned description that another recipient can resolve.

“Ephemeral” applies to computation and derived environments, not to the memory we deliberately preserve.
The original evidence should be durable while indexes and workers can be rebuilt.
The agreed daily flush and 1000-record target need not change: backup of unflushed staging is a separate decision from publishing more frequently.

Bundling duct with Workshop is reasonable for this use case.
It centralizes classification and publication policy, while con/duct remains independent and captures remain portable bytes. The portability concern is the operational dependency on local Workshop/Codex configuration, not packaging alone.

## Have we optimized the workflow?

Not demonstrated.
The prior synthetic task comparisons are withdrawn.
Skill benefit must be assessed from collected task evidence, with causal limitations stated.

The current design also introduces work: source/record commits, per-capture annex publication, model-mediated scheduling, classifications and manually prepared evidence relationships.
Those costs may be justified, but we have not compared them against a simpler workflow over representative tasks.
All-history staging scans and retained journals likewise deserve measurement, not premature enterprise machinery.

Duct helps measure local command elapsed time and resources, but those are not total task cost, model compute, user review time or avoided rework.
The useful denominator is a completed task with complete usable evidence, not the number of captured commands or successful tests.

## Highest-value next actions

1. **Preserve exact execution inputs before expanding evaluation.** Capture relevant dirty source bytes or a source snapshot, environment/lock digests, collector version and stable task ID; join command captures, model responses, assessments and artifacts.
   Acceptance: a reviewer can identify the exact code and inputs behind a selected result without consulting the original working directory.
   This is the most urgent protection against having to restart evidence collection later.
2. **Create a small versioned recovery manifest.** Include non-secret store identities/endpoints, ref namespaces, schema versions, environment definitions, tool identities and scheduler procedure; reference credentials by role, never value.
   Acceptance: one documented entrypoint resolves everything an authorized recipient needs, without downloading logs by default.
3. **Perform one independent handoff and disaster-recovery rehearsal.** Rebuild on a clean authorized environment, restore canonical records, rebuild indexes, retrieve one requested capture and recover pending staging from backup.
   Acceptance: the recipient succeeds without using the author's local paths or undocumented state.
   Record non-attempted portions honestly rather than broadening permissions just to obtain a pass.
4. **Make collection completeness observable.** Track expected versus received task/capture IDs, pending publication age, retries, orphaned artifacts and last successful flush.
   Preserve failures and sampled quiet successes.
   Acceptance: a missed upload or recording step is visible without manually reading every log.
5. **Measure operating burden and decision quality.** Use representative tasks, fixed rubrics, repeated baseline/treatment runs and reviewers blinded where practical.
   Measure evidence completeness, citation errors, recovery success, review effort and total latency alongside local resources.
   Then decide whether to simplify per-capture publication, scheduling or retention.
   No additional retrieval product is required for this test.

## Evidence limits

The earlier assessment included isolated regression tests, which remain valid software checks, and synthetic evaluation results, which are withdrawn.
No optimized-workflow or independent-recovery conclusion follows from the retired evaluation.
Reassess using actual collected memories, conversations and duct captures.
