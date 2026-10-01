# Account-backed Luna pilots

These are exploratory native-agent pilots, not Waza Copilot or PageIndex/ChatIndex executions.
Use the account-backed Luna runtime supplied by the scheduler.
Do not configure an API key, start paid provider jobs, install model weights, or enable Brain network services.

## Daily collection

Run from the Workshop checkout through duct:

```sh
pixi run memory daily \
  --public memory/observations \
  --private "$HOME/.local/state/skills-workshop/feedback-overlay" \
  --config "$HOME/.local/state/skills-workshop/memory/transport.json"
```

This imports both feedback trees before routing whole records, seals yesterday using receive time, retries outstanding uploads, and rebuilds separate SQLite projections.
It does not delete originals.
Never print token files.
If classification/content changed under an existing ID, stop and report the conflict; do not silently publish a new classification or discard the original.

## Rotating exploratory pilot

Alternate CLI evaluation and tree retrieval by local calendar day.
At most one model response per scheduled run.
Retain failed and incomplete trials as well as successes.
Do not infer model cost from an account subscription or claim zero resource cost.

Before answering, run `pixi run python experiments/context-pilots/native_trial.py prepare --kind cli` (or `--kind tree`) and use its printed private workspace.
It freezes the prompt, rubric, complete treatment skill, fixture, protocol, and source digests.
Do not consult earlier trial answers or scores.
Read only `agent-input.json` as the trial input; it contains the prompt and assigned treatment but excludes grading rubrics.
Keep `fixture.json` and previous answers closed until the response is saved.
The host may already expose skill descriptions/instructions, so a baseline is ambient host context, not a clean no-skill condition.
Record that limitation.

For CLI trials, treatment alternates on each CLI trial; the baseline asks for a response without explicitly reading the skill.
For tree trials, use the supplied heading outline and inspect the cited document or conversation nodes.
This measures a native heading-tree baseline only.
PageIndex and ChatIndex model-backed adapters remain pending a compatible account-backed interface.

Write your answer verbatim to `response.txt` in that workspace.
Write `runtime.json` with the actual model identifier, reasoning effort and host version if known (otherwise null), elapsed time and token usage only if measured, and any deviations.
Run `native_trial.py finish --workspace PATH`.
This retains originals, hashes, missing fields, classification, treatment assignment and the raw answer in the shared journal.
Synthetic fixtures contain no private project data.
Do not put ambient conversation text or secrets in shared evidence.

The fixture rubric supports later independent grading; self-grading is not evidence of effectiveness.
A scheduled execution alone is not a controlled comparison.
Report failures or newly useful findings succinctly; do not announce an unrun product integration as completed.
