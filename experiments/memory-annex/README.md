# Annex memory storage

Use the production [memory collector](../../docs/agents/memory-collection.md) with existing collected records and their annex artifacts.
Synthetic storage benchmarks, payload generators, Entire transcript probes and their derived results were retired on October 7, 2026 at the user’s request.
They are not evidence for current design decisions.

Future recovery checks must select existing record IDs, fetch their actual artifacts, verify hashes and compare recovered bytes.
Preserve the original records and classification.
Do not manufacture records or publish test inputs.
Isolated software unit tests remain permitted outside memory stores.
