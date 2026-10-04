# Retrieval milestone — 2026-10-04

Status: **completed for lexical retrieval; semantic Brain retrieval remains blocked/unmeasured**.
This reran the scheduled shared-corpus comparison using the exact six-file, six-query public fixture from October 1–2.
It is a reproducibility check of that narrow fixture, not a new held-out or semantic quality result.

## Frozen inputs and versions

- Corpus record: `47f48700-a9d9-4b78-bd78-9df66beba76f`
- Pilot run: `482620c9-6039-440a-9360-d448912cf411`
- Frozen input SHA-256: `2ec357fd31010925b3b587a02dde9995175f87d62ee41f8b5dc4c00d04c901d7`
- Query fixture SHA-256: `6f148e97b11e2ed78b19caf4272bd2c0819aec27273c7cf243ebccc23435b847`
- Runner SHA-256: `23d4576bae44afdac5e55e8c657752dee3c2eda6795945415a8ce29760f24133`
- SQLite 3.53.4; qmd 2.8.3 (`facd35e`); Entire Brain 0.1.0 from `entire-brain` source revision `f423963df61fe70077234170567055aa88cb3e62`.
- Account-backed model requests: 0.
  No embedding or hosted service was used.
- qmd collection construction indexed 6 documents in 0.373 s.
  Brain setup took 0.849 s and reported degraded components; SQLite database-build time was not measured.
  Query time includes process startup for qmd/Brain but not SQLite.
  Duct measured the whole driver at 3.180 s, 145.5 MB peak RSS and 68.3 MB average RSS; per-provider resource use is unknown.

## Observed result

Each provider returned the labeled source among its top five for all five positive queries.
For the absent-term query, SQLite and qmd returned no hits; Brain returned `README.md`, so it failed that coarse abstention check.
Brain also returned repeated document paths on several positive queries.
These fixture checks are not a relevance gold standard, and repeated output does not independently validate the earlier trial.

Median process-level query times were about 0.171 s for qmd and 0.047 s for Brain.
SQLite's in-process query times were about 0.000064 s.
These timings are not directly comparable because only the qmd/Brain measurements include CLI startup.
No latency score is assigned.

The Brain setup stayed local and disabled egress, but its report says it could not establish a complete readable local checkpoint catalog and its semantic/entity components require the missing Entire graph plugin. The lexical keyword command still ran. qmd reported six missing vectors and no embedding command was run. Therefore semantic retrieval, setup recovery, incremental update/removal, citations beyond file paths, and held-out questions remain unmeasured.

## Retained evidence

The corpus and all 18 query outcomes are in the shared memory journal, linked to the corpus record above.
In particular, SQLite's absent-term result is `0dc58c7d-4009-4fc0-ab5c-4a1b556c7d99`, qmd's is `f7e00e49-9adb-47df-8304-6ad506651bf7`, and Brain's false positive is `c3bce4de-02dd-4910-bb8f-8208a30fdf75`.

Annex-backed duct captures:

- Daily collection: `4ee9dff8-0684-55d8-b5dd-6d9cd0b438c9`
- Retrieval execution: `f31800f6-ec3c-53f9-982b-f80b88f16b86`

The runner also retained the frozen inputs, setup output, and each native query output in separate annex artifacts.
Local workspace: `/Users/johnlee/.local/state/skills-workshop/pilots/retrieval-2026-10-04`.

Next discriminating step: resolve whether the scheduled environment can provide the graph plugin and a complete local checkpoint catalog without egress.
If not, keep Brain's lexical-only boundary explicit and move the comparison to held-out questions plus incremental update/removal behavior for SQLite and qmd.
Do not repeat this fixture unchanged.
