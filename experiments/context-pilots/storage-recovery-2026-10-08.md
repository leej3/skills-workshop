# Storage and recovery checkpoint — October 8, 2026

## Status: daily publication blocked; no recovery trial

Today's Thursday slot covered storage/recovery. The documented daily command started through duct 0.22.0, imported/sealed work reached publication, then was interrupted after 134 seconds.
The stack trace shows the collector in `memory.publish`, publishing an annex artifact through `git push origin <ref>`.
No daily command result was returned, so publication and projection rebuilds are unconfirmed.
No fresh-checkout recovery was attempted.

This repeats the unresolved publication boundary observed October 6.
The earlier attempt stalled in `git annex copy --to=payload`; today's attempt stalled during a Git push from the annex publisher.
Do not retry the daily command until the SSH/annex transport state changes.
This run does not establish whether the interrupted artifact ref was accepted remotely.

## Current local state

The daily command's duct run is `20261008T140026.906729Z-cac1762625124069b690a6c0a4f24cf1`; captured raw streams and resource data remain in the central duct store.
Its shared assessment record `82424dd2-1125-5a47-9c8f-69cd26fde959` was staged locally.
The external archive has SHA-256 `dcaf0c70a0c83eee850932abff410422774627e6b38c1c15cc214de7980dc07a`, size 5,368 bytes; immediate remote publication was not requested and is pending the daily collector.

An idempotent follow-up import check on the documented public feedback tree and private overlay returned 0 shared, 10 sensitive, and 10 duplicates.
This is a post-run source-tree check, not the interrupted daily run's import count.
The check's duct run is `20261008T140316.912347Z-65ba0848b0374933ab124b22ef900e6b`; its shared assessment `dbf1af80-b857-5106-b1b2-32233da0cc6e` was staged locally.

Read-only status after interruption reported 859 sealed shared records, 656 active shared records, six published batches and one pending batch.
Sensitive status reported 69 sealed/active records and three published batches.
These are local status values, not counts imported or published by this run.
No new feedback-tree import count was returned by the interrupted command.

## Evidence and next step

- Duct run: `20261008T140026.906729Z-cac1762625124069b690a6c0a4f24cf1`.
- Local shared duct assessment: `82424dd2-1125-5a47-9c8f-69cd26fde959`.
- Idempotent import-check duct assessment: `dbf1af80-b857-5106-b1b2-32233da0cc6e`; Snapper duct assessment: `9f4bcfcb-522b-583a-9eab-8c622b309b78`.
- Skill-use observations `4c0822f2-55ec-4dc7-80f0-931a7563260c` (duct) and `cee4cb8d-ac89-43fe-84c5-a2a78e321c54` (skills-workshop) passed feedback validation.
  The open duct insight is `5032011f-2bf3-48c2-ae89-1da477220ce3`.
- Existing October 6 checkpoint documents two interrupted attempts at the same publication boundary; it remains the prior evidence, not a recovery result.
- Account-backed model requests: 0.
  Candidate executions and recovery checks: 0.

Next discriminating step: establish a changed SSH/annex transport state and then run one daily collection. Confirm each publication receipt and projection rebuild before using a fresh state to test restore. Do not infer success from local sealed/pending counts or a push timeout.
