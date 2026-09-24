# Discovery and feedback trial

Historical trial report.
Routine collection now uses [private baseline records](local-feedback.md); the Git-backed feedback examples below are for curated, publication-reviewed lessons.

This iteration preserves fresh discovery, project-local working skills, and the existing prototype workflows.
The user reports that finding more skills and using them more is already a substantial benefit.
The next few weeks should evaluate that benefit alongside repeat usefulness and recording effort.

## Changes to try

- Named installation requests authorize that choice after preview and compatibility checks; fresh alternatives remain advisory.
- Two additional pinned catalogs, Anthropic and OpenAI, join the registered upstreams.
  At introduction they contain 20 and 44 `SKILL.md` files respectively.
  They are discovery inputs; their licenses, compatibility, and packaging still need candidate-specific review before installation.
- Local search includes full skill entrypoints, Workshop native skills, and the configured installed roots.
  Installed presence remains distinct from use.
- Ranking uses weighted text fields, inverse document frequency, saturated term counts, query coverage, and a limited prefix/typo fallback.
  Query filler words no longer eliminate otherwise relevant matches.
  Results explain matching fields and show recent observations without treating ratings as rank endorsements.
- `recall` defaults to memory only.
  `find --offline` avoids public providers.
  TSV output can feed `fzf`; selecting a row executes nothing.
- Local text results appear before public searches complete.
  Provider failures remain visible without discarding other results.
- The global `workshop-feedback` control skill records optional benefit, evidence, and improvement notes after meaningful use.
  No rating or controlled evaluation is required.
  `insights --since` makes those observations reviewable together.

## Initial verification

The eight remembered-task queries in `tests/fixtures/recall_queries.json` were checked against the memory present before this iteration's feedback was recorded.
The previous matcher retrieved the intended skill in its top three for 3/8 queries. The new matcher ranked the intended skill first for 8/8, including the README's natural-language example and a misspelled skill name.

This is a small, change-authored regression set, not an independent relevance benchmark.
It tests remembered items, not the precision of the public catalogs.
Add real missed or misleading queries as they occur rather than tuning only these examples.

A local full-content search took approximately 0.29 seconds on the development machine during one run.
This is a smoke measurement, not a latency guarantee.
There is currently no persistent index or embedding dependency.

## Why no vector compression yet

[Google's TurboQuant article](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/) concerns compressing high-dimensional vectors for model caches and vector search.
Workshop currently has no vector index and no demonstrated vector-memory bottleneck.
Compression would not itself produce semantic representations or solve the existing all-terms matching problem.

[Fzf](https://github.com/junegunn/fzf) is useful as an optional interactive selector over exported candidates.
It complements the CLI's retrieval and evidence display.
If real queries repeatedly fail because of semantic vocabulary differences, compare a disposable embedding index with the lexical baseline before considering index compression.
Canonical memory should remain ordinary JSON.

## Observation prompts for the next few weeks

Use short feedback after actual work, including negative or uncertain experiences:

- Did discovery enable a new capability or lead to a better alternative?
- Did recalling prior experience save rediscovery or prevent a repeated mistake?
- What did the skill change in the actual task?
- What specific improvement would help next time?
- Was recording the observation quick enough to keep doing?

Review with `pixi run workshop insights --since 2026-09-18`.
Counts are observations, not independent task trials; all historical missing benefits remain unknown.
Follow-ups are proposals and are not automatically resolved, implemented, or posted externally.

Global installation and a short agent instruction make the feedback workflow available across projects.
They do not supply deterministic host telemetry: activation and quality of observations still need to be assessed in real tasks.
User-specific checkout configuration belongs outside the repository.
Preserve the existing commit and privacy conventions, and batch feedback bookkeeping at task completion.
