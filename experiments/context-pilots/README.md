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
| Native Luna | Daily local account-backed schedule created, frozen CLI and long-document/conversation fixtures | First scheduled model trial pending. Ambient host context is not isolated; results remain exploratory and ungraded. |
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
