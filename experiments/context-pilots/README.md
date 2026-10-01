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
| PageIndex / ChatIndex | No model-backed execution | Native heading-tree fixtures establish a comparison baseline; they do not test either product. Compatible account-backed adapters remain unimplemented. |

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
