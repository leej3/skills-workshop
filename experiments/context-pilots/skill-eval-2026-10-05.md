# Waza and native Luna skill evaluation checkpoint — 2026-10-05

## Status: blocked before model execution

Today's bounded milestone selected the Monday Waza/native Luna comparison.
The scheduled fixture is `waza/tasks/cli-stream.yaml`, with the native CLI trial protocol in `native_trial.py`.
The recorded baseline on October 1 used Waza 0.38.8's mock executor; it checked harness plumbing only and did not measure skill effectiveness.
The account-backed Luna trials on that date were separate native agent runs, not Waza's Copilot executor.

Today's checkout has no `waza` executable on `PATH`, and Waza is not declared in the locked Pixi tasks or dependencies.
The native trial journal has no unresolved attempts.
A valid repeated comparison also requires fresh isolated Luna executor contexts with matched model, effort and budget.
This scheduled turn does not expose a way to create or address those contexts, so neither condition was run.
No Luna requests were made.
No quality, timing, token, or cost result is claimed.

The next discriminating step is to restore the pinned Waza 0.38.8 binary using its verified digest and provide two fresh account-backed Luna contexts for the matched frozen conditions.
Preserve the executor identity: Waza mock output cannot stand in for Luna, and native Luna output cannot be labeled a Waza run.

Daily collection completed successfully before this checkpoint.
Duct capture evidence: `1f304e89-e88d-5e45-8e82-887787791489`.
The account-backed model request count for this milestone is zero.
No experimental output artifacts were produced.
