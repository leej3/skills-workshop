# PageIndex Luna adapter checkpoint — 2026-10-02

Status: **blocked before adapter implementation or product execution**.
This is a compatibility assessment, not an indexing or retrieval result.

## Pinned source

- PageIndex: `VectifyAI/PageIndex` at `6d23caf416858f2ca136840305d1f479a86f6ef7`
- ChatIndex, pinned for the next slot: `VectifyAI/ChatIndex` at `7df2c9208db6f113f85a6c09295bec7f0f2114e7`
- PageIndex file digests:
  - `pageindex/client.py`: `b3f25630cf268fab5af48134e3fb2b433dc948dcfe08021554b9eb624d9acd56`
  - `pageindex/local_api.py`: `d5c9804d68f3147c612c81cf82542d961b1cc8682d837c3705c0d59c7202293f`
  - `pageindex/local_chat.py`: `60d2d1a966b5ad614513d6f69768ea5a74be6f5e6f88a1ef9bb72b3d4e23d50e`
  - `pageindex/utils.py`: `2356a2b00155faf1e1bc0628c51cc66320f1c980f9c938abdb7f885cee5681ad`
- ChatIndex file digests:
  - `README.md`: `76ef2eadcd462c3c05defd90d2dc7562796eb1af56d82f43d280bb8267fc2c88`
  - `retrieval/llm_tools.py`: `39be990b1b415d2f2e4e1cc4a74867dd7cd1d4ee440af1fe4cae6a21daaea2be`

## Interface finding

The pinned PageIndex SDK has a local PDF indexer, tree storage, and a local chat agent.
Its indexing lane calls LiteLLM chat completions through `index_backend`; its chat lane uses the OpenAI Agents SDK Responses API or provider-specific Chat Completions/Anthropic adapters.
These are provider interfaces.
The documented `gpt-5.6-luna` model example still requires an OpenAI API key in the SDK's normal setup.

The available account-backed Luna boundary is the Codex agent/CLI runtime.
`codex exec` is an agent invocation, not a callable LiteLLM endpoint or an OpenAI Responses server.
It exposes a final agent response, not the drop-in model and wire-level function-call interface PageIndex's traversal loop expects.
A bridge would need to translate upstream request schemas to Luna turns and convert structured output back into provider response envelopes.
No credentials were copied or provider configured.
No account-backed model requests were made.

## Milestone record

- Candidate: PageIndex, document trees.
- Adapter revision: none; source review only.
- Fixture, protocol, and rubric digests: not created; no product run began.
- Runtime/model/effort: Codex desktop task; underlying model and effort are not surfaced to subprocess integrations.
  Account-backed Luna calls: 0 of 8.
- Status: `blocked` at the model transport boundary.
  No index, response, citation, timing, resource, or performance result exists.
- Evidence IDs: daily collection and projection capture `185dddc1-ef2c-554b-841b-955c9acef4e3`; pinned-source and digest capture `f8223ad9-90e3-571a-b3d8-555b5d7a547c`.
  Both raw duct archives are in the shared annex.

## Next discriminating step

Implement a small local adapter that translates PageIndex's indexing request envelopes into account-backed Luna turns and returns the provider response shape without storing account credentials.
First prove one bounded indexing turn against a synthetic frozen PDF.
Then determine whether the agent host can return structured function calls to PageIndex's actual traversal loop.
Keep the index and chat interfaces as separate checkpoints, enforce the eight-call cap, and do not report retrieval until the upstream traversal ran.

## Scope and missing measurements

This slot was limited to pinning both repositories and reviewing the PageIndex model boundary.
It did not run either product, create a native tree comparison, or make a quality claim.
Build/query/update timing, index size, resources, token use, reconstruction, and data egress remain unmeasured.
