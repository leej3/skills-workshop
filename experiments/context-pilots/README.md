# Replaceable context pilots

The storage boundary is `scripts/memory_store.py`, not any evaluated product.
Public documents and synthetic fixtures only.
See [collection contract](../../docs/agents/memory-collection.md) and [scheduled protocol](scheduled-protocol.md).

## Results on 2026-10-01

| Pilot | Actual execution | Result and limit |
|---|---|---|
| Waza 0.38.8 | Mock executor, two trials per condition, with skill directory and stripped baseline | Both passes completed. Exit 1 means neutral skill impact in this fixture; output-present grader is plumbing only. No model or skill-effectiveness claim. Initial misconfigured attempt skipped baseline and is not paired evidence. |
| SQLite FTS5 | Six literal source-location/empty-result queries over six frozen public docs | 6/6 expected checks. In-process latency excludes CLI startup. |
| qmd 2.8.3 | Same corpus/queries, lexical `search` | 6/6 checks. About 0.15–0.16 seconds including process startup. No embeddings or model download. |
| Entire Brain 0.1.0 | Same corpus/queries, keyword document retrieval, isolated local/no-egress setup | 5/6 checks. Returned a document for an absent nonsense term. About 0.047–0.062 seconds including startup. Duplicate sections differ from qmd's file-level results. |
| Native Luna | Daily local account-backed schedule created, frozen CLI and long-document/conversation fixtures | Three immediate Luna trials completed October 1; scheduled follow-ups remain active. Ambient host context is not isolated; results remain exploratory. |
| PageIndex / ChatIndex | No model-backed execution | Native heading-tree fixtures establish a comparison baseline; they do not test either product. PageIndex uses separate LiteLLM/OpenAI Agents interfaces; pinned ChatIndex uses OpenAI Chat Completions for construction and Anthropic Messages tool calls for retrieval. The Luna runtime exposes neither endpoint here; see the [PageIndex](pageindex-2026-10-02.md) and [ChatIndex](chatindex-2026-10-03.md) checkpoints. |

Six coarse checks do not rank overall retrieval quality.
Keep citation correctness, semantic questions, abstention and exact-ID recall as separate future measurements.
Waza's Copilot executor is not the account-backed Luna scheduler.

## Reproduce

Install lexical qmd locally with `pixi run npm ci --prefix experiments/context-pilots`; package-lock pins dependencies.
No global installation is needed.
Use duct for execution.

```sh
pixi run python experiments/context-pilots/run_retrieval.py \
  --workspace /private/path/new-retrieval-trial \
  --state /private/path/memory \
  --entire-bin /path/to/verified/entire/bin \
  --provenance-script /path/to/commit-provenance/scripts/resolve.sh
waza run experiments/context-pilots/waza/eval.yaml --baseline \
  --output /private/path/waza-results.json \
  --transcript-dir /private/path/waza-transcripts --no-update-check
```

Verified Waza standalone macOS arm64 release: 0.38.8, SHA-256 `f4f36fbdfdd60b6d7c1bd555b25a6c6d33485e57fdf8e67c1c65a82400622601`.
The retrieval runner retains frozen corpus, protocol, native outputs, producer versions and conditions in the memory journal; the query labels are exploratory, not an independently curated gold standard.
Local workspaces and duct logs remain outside Git.

## Luna baseline — October 1, 2026

Executed with `gpt-6-luna`, medium reasoning, three subagents with no inherited conversation.
Only the appropriate frozen agent input was supplied; the rubric was withheld.
Runtime token use and cost were not available.
This uses the native account-backed executor, not Waza's Copilot executor.

| Trial | Evidence ID | Result |
|---|---|---|
| CLI ambient baseline | `79fa1751-06e9-4129-8dcc-105d2f6d6569` | 5/5 basic rubric checks |
| CLI explicit unix-cli-design skill | `ce1d111e-d0f4-4764-b342-c36211c22b6e` | 5/5 basic rubric checks; additionally mentions final flushing and shell pipefail |
| Native heading-tree document/conversation | `dbca0c16-3a00-4dfa-a50a-8f9e41e116f2` | 4/4 checks, including exact D120/T145/T012 citations and abstention on the unspecified cipher |

Grading was performed by the parent agent after the answers, unblinded and not human-reviewed.
The final-flush/pipefail observations are post hoc distinctions, not pre-registered effect measurements.
One trial per condition and a simple fixture do not establish reliable skill benefit.
Raw responses, frozen inputs, artifact hashes, runtime conditions and separate grading records are retained in memory.

PageIndex/ChatIndex are still evaluation candidates, not deployed components.
This run does not test their indexing or traversal implementation.
Their actual adapters remain future work; using Luna through the native agent runtime does not automatically provide an API backend for either project.

## Continuing evaluations

The daily Luna job now follows a [seven-day cross-layer rotation](scheduled-protocol.md#daily-candidate-rotation), with PageIndex on Fridays and ChatIndex on Saturdays, beginning October 2–3, 2026.
Their first work is real-product adapter implementation under the existing account-backed boundary.
Subsequent milestones collect indexing, retrieval, updates, citations, measured resources and recovery evidence against matched baselines.
Enrollment is not a completed benchmark; keep interface blockers and measured outcomes distinct.


## Reliability and replaceability — October 2, 2026

All newly collected logs use external annex artifacts regardless of size.
Duct, native trial responses/runtime output, and lexical pilot command outputs share that policy.
Small measurements, statuses, hashes and references remain in records.
Historical immutable records retain their old representation.

Native preparation now journals an attempted event before execution.
Outcomes are separate immutable records linked by trial ID, including failed, interrupted, blocked and abandoned attempts.
`pending` replays persisted event files after crashes and reports unresolved attempts without guessing that they failed.
Non-completed outcomes can preserve partial output without runtime metadata.

Use `native_trial.py prepare-pair` for the CLI comparison.
Both conditions freeze the same prompt, harder edge-case rubric, skill revision and protocol together; execution order is randomized.
Execute each in a fresh context with the same runtime/budget.
`grading-packet --pair PAIR_JSON --output NEW_DIRECTORY` produces an assignment-free grader input and a separate local answer key.
Wording and ambient host context may still reveal treatment; this is not guaranteed blind or isolated evaluation.
No new model-effectiveness result is claimed here.

`check_replaceability.py` completed a live synthetic test against the private `test-store` annex: publish canonical evidence, restore into a fresh local state, then build independent SQLite FTS5 and qmd 2.8.3 lexical views.
Three positive queries returned identical evidence IDs; one absent-term query returned no hits in either tool.
Results carry canonical text hashes.
The derived statement is a deterministic quotation of evidence, not a model-synthesis quality test.
A one-byte log stayed absent throughout restore and search, then passed hash verification on explicit retrieval.
This proves a small replacement/rebuild path, not semantic-search quality or production throughput.

The first upload failed after staging.
Retrying the same annex key succeeded; `--resume` then reused the original batch and record identities.
No cause for the transient failure was established.
Both failed and successful captures are retained.

Reproduce with a test-only configuration whose shared entry points to the private test repository, and the existing pinned local qmd installation:

```sh
pixi run python experiments/context-pilots/check_replaceability.py \
  --workspace /private/path/new-replaceability-trial \
  --config /private/path/test-only-transport.json
```

Use `--resume` with that same workspace after interrupted publication.
The probe writes synthetic refs and payloads; it never deletes remote evidence.

## PageIndex Luna adapter checkpoint — October 2, 2026

The [pinned-source checkpoint](pageindex-2026-10-02.md) reviewed PageIndex `6d23caf416858f2ca136840305d1f479a86f6ef7` and pinned ChatIndex `7df2c9208db6f113f85a6c09295bec7f0f2114e7` for Saturday.
PageIndex's current local indexer uses LiteLLM chat completions; its tree traversal uses the OpenAI Agents Responses API or provider-specific interfaces.
The scheduled account-backed Luna runtime is available as an agent/CLI invocation, not as either callable provider interface. No account requests or PageIndex product execution occurred, so there are no quality or performance measurements. The adapter checkpoint is blocked pending a local transport bridge that preserves the upstream request/response semantics; indexing and traversal must be demonstrated separately before retrieval is reported.

## ChatIndex Luna adapter checkpoint — October 3, 2026

The [pinned-source checkpoint](chatindex-2026-10-03.md) reviewed ChatIndex `7df2c9208db6f113f85a6c09295bec7f0f2114e7`.
Its tree builder calls OpenAI Chat Completions; retrieval directly requires Anthropic Messages structured tool-use responses.
The account-backed Luna runtime in this execution environment exposes neither provider interface.
No model requests or product execution occurred, and no product quality or performance result is claimed.
The next adapter must preserve both interfaces and persist resumable requests and responses across runs.

## Waza and native Luna checkpoint — October 5, 2026

The scheduled Monday milestone was blocked before model execution.
Waza 0.38.8 is not available on `PATH` or in the locked Pixi environment, and this turn does not provide fresh isolated account-backed Luna contexts for a matched comparison.
No account requests were made and no model-effectiveness result is claimed.
See the [checkpoint](skill-eval-2026-10-05.md) and daily collection duct capture evidence `1f304e89-e88d-5e45-8e82-887787791489`.
