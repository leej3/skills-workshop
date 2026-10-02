# Ongoing context-stack evaluations

Evaluate the actual candidate tools alongside explicitly named native baselines.
An enrollment or adapter attempt is not a completed product evaluation.
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

## Daily candidate rotation

Use the local date in America/New_York and the table below.
Start with PageIndex on Friday October 2, 2026.
Keep one bounded fixture or adapter milestone per run; do not repeatedly run all tools every day.
Each model-backed trial is exploratory until its execution and grading conditions support a stronger claim.

| Day | Layer and candidates | Work to accumulate |
|---|---|---|
| Friday | Document trees: actual PageIndex against native heading-tree and lexical baselines | Local index construction, page-cited retrieval, index size, build/query resources and reconstruction |
| Saturday | Conversation trees: actual ChatIndex against native tree and lexical baselines | Construction, exact message citations, appended messages, superseded decisions, update cost and removal behavior |
| Sunday | Retrieval: SQLite FTS5, qmd, Entire Brain | Same frozen corpus/queries; precision, recall, abstention, citation correctness and startup-aware latency |
| Monday | Skill evaluation: Waza and native Luna with/without explicit skill | Preserve executor identity; matched prompt/treatment/rubric, repeated trials and failures |
| Tuesday | Context selection: native document/conversation baseline | Harder held-out questions and context-volume measurements; avoid ceiling-only fixtures |
| Wednesday | Capture: Entire CLI and native evidence/duct capture | Coverage, original-byte preservation, missing provenance, export and recovery without the collector |
| Thursday | Storage: canonical journals, annex and disposable projections | Concurrent ingestion, daily batching, retry/recovery, lazy artifact retrieval and operational cost |

Read the latest candidate evidence and `docs/agents/context-stack-landscape.md` before choosing the next milestone.
Work from the existing implementations and pinned local binaries where available.
Keep source checkouts, dependency environments and generated indexes outside the code repository.
Record source revision before execution.
Never silently update a previously measured tool revision.

### PageIndex and ChatIndex enrollment

Both are active evaluation candidates, not deferred selections.
Their first milestone is an actual product adapter compatible with the account-backed Luna boundary.
Inspect pinned upstream code and its model interface; implement and test the smallest reversible adapter in `experiments/context-pilots`, then run a small frozen fixture.
A staged request/response adapter may preserve upstream prompts and resume execution, but it must run the actual indexing/retrieval logic.
Do not replace that logic with a handwritten tree and label it a product result.
Avoid maintaining a fork unless an adapter cannot preserve the required semantics.

A model-backed trial may span runs: retain pending requests, responses and checkpoints with exact identities, and resume instead of restarting.
Cap a daily milestone at ten minutes of experiment execution and eight account-backed model requests; stop earlier when the result or a concrete blocker is established.
Record actual requests and available usage; the cap is not an observed measurement.
Keep API-provider accounts and hosted subscriptions unconfigured.
Do not copy account credentials into third-party providers.

If the runtime cannot supply the required interface, save a `blocked` assessment naming the exact interface, source revision, attempted approach and next discriminating step.
Never give an unrun tool a performance score.
On later visits, advance adapter work or check a materially changed boundary; do not repeat an identical unsuccessful probe just to produce another record.
Use remaining time for a ready comparison in the same layer.
Report any unresolved user decision explicitly.

### Common retained evidence

For every candidate milestone retain candidate/layer, upstream revision, adapter revision and patch, fixture/protocol/rubric digests and original bytes, runtime/model/limits, status (`planned`, `attempted`, `blocked`, `failed`, `completed`, or `graded`), native output and index artifacts, citations, measured timing/resources and missing measurements.
Preserve failures and provider restrictions as operational evidence, separate from retrieval quality.
Record build cost separately from query and incremental-update cost.
Compare within a layer and keep the canonical source corpus identical across candidates.

Use portable memory envelopes for each attempt and separate annex objects for all collected logs and index artifacts, regardless of size; fetch those only when needed.
Whole-record sensitivity applies.
Update cumulative assessments in `docs/agents`; link evidence IDs rather than copying private capture details.
No tool becomes canonical storage as a consequence of an evaluation.
Evaluate exit/rebuild, data egress and dependency/account requirements alongside quality.

## Native baseline execution

The following commands run only the native baseline, not PageIndex/ChatIndex.
Use them on the corresponding baseline or skill-evaluation day, or as a clearly named matched comparison.
Retain failed and incomplete trials as well as successes.
Do not infer model cost from an account subscription or claim zero resource cost.

Before execution, run `pixi run python experiments/context-pilots/native_trial.py pending` to replay persisted events and inspect unresolved attempts.
Do not assume an unresolved attempt is dead; explicitly close a stopped attempt with `finish --workspace PATH --status interrupted --reason TEXT`.
For the CLI comparison, run `native_trial.py prepare-pair` and execute both printed workspaces in the recorded randomized order within the same scheduled milestone.
Use separate fresh executor contexts with the same model, effort and budget; if the host cannot provide those contexts, record the deviation or a blocked outcome rather than claiming isolation.
Never pass one condition's answer into the other condition.
For the tree baseline, run `native_trial.py prepare --kind tree`.
Preparation records an attempted event before any model response is requested.
It freezes the prompt, rubric, complete treatment skill, fixture, protocol, and source digests.
Do not consult earlier trial answers or scores.
Read only `agent-input.json` as the trial input; it contains the prompt and assigned treatment but excludes grading rubrics.
Keep `fixture.json` and previous answers closed until the response is saved.
The host may already expose skill descriptions/instructions, so a baseline is ambient host context, not a clean no-skill condition.
Record that limitation.

For CLI pairs, both conditions share frozen fixture, rubric, skill revision, collector and protocol bytes.
The baseline asks for a response without explicitly reading the skill.
Repeat matched pairs across runs; do not interpret between-day treatment alternation as a controlled comparison.
For tree trials, use the supplied heading outline and inspect the cited document or conversation nodes.
This measures a native heading-tree baseline only.
Actual PageIndex/ChatIndex evaluations follow their candidate slots above; keep their product identities separate from this baseline.

Write your answer verbatim to `response.txt` in that workspace.
Write `runtime.json` with the actual model identifier, reasoning effort and host version if known (otherwise null), elapsed time and token usage only if measured, and any deviations.
Run `native_trial.py finish --workspace PATH`.
This appends a separate immutable completed outcome linked to the attempt.
Exact inputs, logs, raw response and runtime metadata use external annex artifacts; the shared journal contains statuses, hashes and artifact references.
For a failed, blocked, abandoned or interrupted execution, use `finish --workspace PATH --status STATUS --reason TEXT`; missing response/runtime files are allowed and partial output is preserved. Inspect any failure detail before retaining it: these baseline fixtures are public/synthetic, so do not add ambient sensitive text.
Retrying an unchanged event is idempotent.
`pending` replays persisted events after a journal-append interruption without inventing a completion.
After both pair outcomes complete, use `native_trial.py grading-packet --pair PAIR_JSON --output NEW_DIRECTORY`.
Give only `grader-input.json` to a fresh grader.
Keep the separate assignment key closed until grading is saved, and retain the grade, grader identity and deviations as a separate related memory record.
The packet withholds treatment/runtime labels, but answer wording may reveal the treatment; do not claim guaranteed blinding.
Incomplete pairs remain operational evidence, not zero-valued quality scores.
Synthetic fixtures contain no private project data.
Do not put ambient conversation text or secrets in shared evidence.

The fixture rubric supports later independent grading; self-grading is not evidence of effectiveness.
A scheduled execution alone is not a controlled comparison.
Report failures or newly useful findings succinctly; do not announce an unrun product integration as completed.
