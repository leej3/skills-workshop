# Shareable records with a private overlay

Ordinary concise observations can be versioned and shared; sensitivity is a property of particular fields or records, not of all telemetry.
Classify while recording, then batch inspect and commit the shareable tree under the user's standing publication authorization.
Avoid a separate approval exchange or commit for every routine record.
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

Before committing a batch, inspect the exact shareable files and `summary --public-only`.
Check text and metadata for accidental omissions in classification; schema validation guarantees structure, not disclosure suitability.
Publish that tree only, never the merged view or overlay.
Do not copy raw logs or transcripts merely because a record references them.
If uncertain, keep the specific data in the overlay while sharing the remaining useful record.

The recorder performs no Git writes or network calls.
Batch commit/push follows normal user authorization and repository conventions.
Already-published records cannot be made private by writing an overlay: suspected past disclosure requires a separate remediation decision, not silent history rewriting.
