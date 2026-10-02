# Shareable records with a private overlay

Ordinary concise observations can be versioned and shared; sensitivity is a property of particular fields or records, not of all telemetry.
Classify while recording, then inspect and validate the task's records.
For an annex-backed Workshop, queue them through the overlay-aware importer and let the daily collector publish batches; do not create task-end Git commits for records.
Legacy Git-backed checkouts still require a reviewed task-end commit.
Shared-thread posting still follows its own approval rules.

## Classification

Consider whether a value exposes personal information, credentials, confidential project work, private conversations, internal locations, or uncertain disclosure rights.
Project names, conversation IDs, paths, links, and failure details are contextual decisions rather than universally forbidden fields.
Keep credentials out of both trees; the overlay is ordinary local storage, not a secret vault.
Public code does not make a private discussion public.

For optional sensitive fields, specify JSON pointers:

```console
pixi run feedback-local record example --task analysis --outcome partial \
  --details details.json --private-fields /context/session_id /evidence \
  --sensitivity-category private-conversation \
  --sensitivity-reason "Links and session identify a private discussion"
```

The private overlay retains the full record, affected field pointers, category, reason, classifier (agent/human/tool), confidence, and policy version.
The shareable projection contains none of the classification explanation, which may itself be sensitive.
Redact an array as a whole.
If identity or another required field is sensitive, record the whole observation with `--visibility private`.
The two roots must be disjoint and the overlay must be outside Git.

## Learn from decisions

Use `sensitivity` locally to group recurring reasons and fields.
Review uncertain and repeated classifications, record refinements as exceptional notes, and adjust guidance based on specific examples.
Human corrections should inform policy; mere frequency must not automatically relax it.
Store sensitive correction examples in the overlay too.
Classification records are evidence for improving policy, not proof that a classifier was correct.

## Batch publication

Inspect the exact shareable files and `summary --public-only` before collection.
Schema validation checks structure, not disclosure suitability.
The annex collector merges overlays first and routes the complete source record to its classified store.
It publishes daily, with 1000 records per batch and at most one remainder per store.
Keep classification reasons and original sensitive fields private; publish generalized insights only after examining their content.
Already-published records cannot be made private by writing an overlay: suspected past disclosure requires a separate remediation decision, not silent history rewriting.
