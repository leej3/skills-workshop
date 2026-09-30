# A vendor-independent Workshop optimization loop

Workshop is enduring infrastructure for collecting experience, discovering and maintaining skills, and evaluating changes.
Its implementations should remain replaceable as tools improve.
A parent agent in Codex or Claude can orchestrate reflection, proposal, evaluation, and integration through native subagents.
A separate execution service is not a prerequisite.

## Reuse existing implementations

[AutoHarness](https://github.com/tigerless-labs/autoharness) is MIT-licensed and provides useful skill indexing, intent queues, validation, application, and provenance code.
Maintain a small compatibility fork rather than reimplementing those pieces.
Preserve Claude behavior while adding host adapters for Codex.
The initial [fork](https://github.com/leej3/autoharness/tree/codex/native-agent-bridge) provides an explicitly invoked native-agent bridge; automatic Codex event collection and live host parity are not yet verified.
Upstream submission requires John's review of the concrete changes and message.

Keep the responsibilities distinct:

| Responsibility | Replaceable implementation | Shared evidence |
|---|---|---|
| Collection | Host completion/event adapter | Schema-validated observations, task identity, optional measured resources |
| Consolidation | Parent agent delegates a maintainer | Grouped lessons, source observations, sensitivity classification |
| Proposals | AutoHarness reflector/curator or another proposer | Exact candidate diff, motivation, artifact identity |
| Evaluation | Domain-specific tasks and calibrated reviewers | Matched conditions, repeated results, uncertainty and human judgments |
| Integration | Existing validator and Git workflow | Applied/rejected proposals and validation results |

Use frequency and self-reported success describe observed use, not causal benefit.
Structural validation does not establish correctness or skill effectiveness.
Preserve rejected proposals and their evidence so future agents can learn from them.
Routine outcomes remain concise; qualitative reports are for exceptional lessons.
Sensitive details stay in the private overlay rather than forcing all records private.

## Document indexing

[PageIndex](https://github.com/VectifyAI/PageIndex) is a candidate for retrieving page-cited evidence from long text-based PDFs.
Its MIT-licensed local implementation can run with a chosen supported model connection.
Local indexing does not imply that remote model calls are offline.
Its advertised corpus-level File System, OCR/image understanding, and hosted MCP features are cloud-only.

Keep a stable retrieval result contract around source identity, document revision or digest, page/section location, retrieved text, and provider provenance. Compare PageIndex against simpler text search on representative evidence questions before adopting it. Retain schema/metadata queries for structured records and skill catalogs; document retrieval complements those indexes.

## STAMPED relationship

STAMPED assessment remains independently installable and runnable, with its own schemas, rubrics, evidence requirements, and review workflow.
Its urgent assessment work need not wait for Workshop's orchestration or PageIndex adoption.

Share useful retrieval adapters, artifact identities, observation formats, and evaluation lessons through explicit interfaces.
Workshop can use STAMPED cases as one evaluation domain; STAMPED can consume reusable components without importing Workshop's lifecycle controls.
Preserve domain-specific judgments and human calibration instead of turning every task into one generic score.

## Next validation

Exercise the native AutoHarness bridge in a real Codex parent/subagent task and retain a Claude regression case.
Then normalize host events and install a completion adapter with explicit task identity and retry handling.
Compare candidate and baseline skills on matched fixtures, with independent human-calibrated judgments.
The evaluation protocol, rather than an external runner, is the principal gap.
