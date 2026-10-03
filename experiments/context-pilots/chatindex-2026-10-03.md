# ChatIndex account-backed adapter checkpoint — 2026-10-03

## Candidate pin and source review

- Candidate: ChatIndex, conversation trees.
- Upstream: `VectifyAI/ChatIndex` at `7df2c9208db6f113f85a6c09295bec7f0f2114e7`.
- Pinned checkout: `/tmp/workshop-chatindex-20261003`.
- Reviewed source digests (SHA-256):
  - `ctree/ctree.py`: `9fe8a4a6b165dba71fd292d9ffdc3d2b34662aa2f884f7fee75516ac477713a3`
  - `ctree/utils.py`: `818d1bd0d0e6b0bf09e80b4b8258af5d12d0db764ebeb55b7b04e789f5afef12`
  - `retrieval/llm_tools.py`: `39be990b1b415d2f2e4e1cc4a74867dd7cd1d4ee440af1fe4cae6a21daaea2be`
- Frozen fixture/protocol: not yet constructed; no fixture digest.

## Exact adapter boundary

Tree construction calls `ctree.utils.ChatGPT_API(model, prompt, api_key, chat_history, temperature, max_tokens)`.
That function creates an `openai.OpenAI` client and calls Chat Completions.
The tree methods expect plain text and parse selected responses as JSON.

Non-streaming retrieval in `retrieval.llm_tools.query_ctree` separately creates an `anthropic.Anthropic` client and calls Messages with tool schemas.
It expects `end_turn` or `tool_use`, SDK content blocks, tool IDs, and serializes local tree results back into `tool_result` messages.
Streaming retrieval has an additional Anthropic event-stream contract.
Retrieval is therefore not covered by an indexing-only completion shim.

## Status and evidence limits

- Status: `blocked` at the account-backed transport boundary.
- Adapter revision: none; no adapter code was added because no callable account-backed Luna interface is exposed to this execution environment.
- Attempted approach: reviewed the pinned indexing and retrieval call sites and the available execution tools for a credential-free bridge.
  The available runtime is an agent/CLI turn, while this scheduled execution exposes no Luna invocation handle that accepts preserved upstream prompts and returns Chat Completions text or Anthropic-style structured tool-use responses.
- Account-backed model requests: 0.
  Product indexing/retrieval execution: none.
- Native conversation-tree baseline is separate and is not a ChatIndex result.
- No quality, citation, update, removal, latency, or resource result is claimed.
- Provider/API credentials, paid API accounts, and hosted subscriptions remain unconfigured.
- Portable assessment envelope: `c4dada34-e7a0-4595-9eb2-7f998628eb70`.
- Pinned source annex evidence: `7bc492e6-d5a6-480b-a03b-b3c60bdbca6b`; source tarball SHA-256 `9fcaffe0a22b2c57a50256aaaa82a9d203e7660fdfc65e8fc058382bd2a48190`.
- Daily collection duct capture: `bad28ad3-36f2-594d-96e1-50ca4a2d6ca3`.
- Pinned checkout duct capture: `73114c12-cd47-5db3-a220-a2a675435ab3`.
- Documentation formatting attempt and successful rerun captures: `ea2b16fc-7848-5c26-8ede-1a8fe93c597a` and `1afc8449-80fe-50e2-906e-482c8e275fb3`.
- The records above are queued in the shared journal; their annex objects were uploaded and verified.
  The daily collector published yesterday's two shared and two sensitive batches: 35 shared and 54 sensitive records for October 2.

## Next discriminating step

Provide a credential-free local bridge that can service both Chat Completions text/JSON calls and Anthropic-style structured tool-use turns through the account-backed Luna runtime while preserving the upstream prompt and tool semantics.
The bridge must persist exact requests, responses, identities, and checkpoints so upstream execution can resume across runs.
Then run the actual ChatIndex constructor and `query_ctree` on the same frozen conversation used by the explicitly named native baselines.
Do not treat a staged request or a hand-built tree as product execution.
