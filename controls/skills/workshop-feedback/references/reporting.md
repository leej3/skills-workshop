# Concise reporting schema

The complete contract is [observation-v2.schema.json](../schemas/observation-v2.schema.json).
Both record kinds reject undeclared fields and invalid types, outcomes, UUIDs, timestamps, and negative resource values.
Duration requires an explicit scope; absent measurements remain null or omitted.

| Group | Optional information |
|---|---|
| Top-level flags | Task outcome, measured duration/scope, model, SKILL.md digest, measurement source |
| context | Opaque task/session IDs, project and revision, short summary, type, complexity, tags, related skills |
| execution | Trigger, host/runtime/version, provider/effort, OS/architecture, skill source/revision/full artifact digest, attempts, calls, errors, retries, exit code, start/end times, timing method |
| resources | Input/output/cached tokens, USD cost, peak RSS bytes, CPU seconds |
| quality | Verification method, tests passed/failed, human interventions, rework seconds, optional 1–5 rating, observed benefit, failure stage/code, confidence, notes |
| evidence | Typed URL/path/digest/evaluation/log references; no automatic copying of their contents |
| evaluation | Experiment/case, condition, split, metric/score, time/token budget |

Example `details.json` (illustrative values, not actual observations):

```json
{
  "context": {"task_summary": "Validate a release", "tags": ["testing"]},
  "execution": {"trigger": "agent", "attempts": 1, "tool_calls": 3, "retries": 0, "duration_method": "clock"},
  "resources": {"input_tokens": 1500, "output_tokens": 250},
  "quality": {"verification": "tests", "tests_passed": 12, "tests_failed": 0, "human_interventions": 0}
}
```

```console
pixi run feedback-local record duct --task build-validation --outcome success \
  --task-outcome success --duration-seconds 42 --duration-scope skill \
  --details details.json
```

Optional fields should make collection comprehensive when evidence exists, not require agents to fill every slot.
Host adapters can supply measured timestamps, tokens, runtime identity, and exit status; agents supply role-specific outcomes and short context.
A process exit code alone does not establish skill success.
Do not put unknowns in numeric fields as zero.

The minimal command runs only when called.
There is no automatic task-completion listener, timer, or implicit environment scan.
Existing v1 JSONL files remain untouched outside Git and are not silently reclassified or published.
