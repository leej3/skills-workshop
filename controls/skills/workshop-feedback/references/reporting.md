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

## Rich skill-use capture

For substantive use, include an `assessment` in the details file and supply `--capture`.
The assessment is the agent's judgment; it does not establish a causal speedup.
Use `efficiency: "unknown"` when there is no defensible comparison, and explain the observed help or overhead in `rationale`.
Numeric durations remain measured values in the existing fields.

```json
{
  "assessment": {
    "usefulness": "useful",
    "efficiency": "unknown",
    "confidence": "medium",
    "basis": "agent-self-assessment",
    "rationale": "The skill supplied the recovery procedure used after a failed upload. No timed baseline was run.",
    "improvements": ["Return a command that opens the full capture."],
    "evidence_refs": ["duct/0000/run_stderr"]
  }
}
```

The capture request follows [capture-request-v2.schema.json](../schemas/capture-request-v2.schema.json).
Paths are explicit; relative paths resolve against the request file's directory.
The collector never searches unrelated sessions or guesses log ownership from timestamps.
Codex conversation identity is checked against the native `session_meta` record.
Duct runs with a recorded session identity must match it.
Older runs without that field remain explicitly selected inputs, not independently verified associations.

```json
{
  "schema_version": 2,
  "conversation": {
    "path": "/absolute/path/to/rollout.jsonl",
    "format": "codex-jsonl",
    "session_id": "actual-session-id"
  },
  "duct_runs": ["/absolute/path/to/finished-duct-run"],
  "skill_reference": {
    "manager": "apm",
    "package": "leej3/skills-workshop/controls",
    "resolved_commit": "38c9df6cfee8241f1bce9bb2f65d1c083a574757",
    "skill": "duct"
  },
  "missing_evidence": ["External attachments are referenced in the transcript but not copied."]
}
```

Take the package (repository plus virtual path), `resolved_commit`, and skill selector from the APM lock that supplied the skill actually used.
The pin above is illustrative, not a default.
GitHub APM packages are supported; omit the reference and explain `missing_evidence` for a native/unmanaged skill or another host.
Do not substitute the latest commit for the version used.
Resolve in an isolated APM project with `apm install PACKAGE#RESOLVED_COMMIT --skill SKILL --target agent-skills`; access to that repository is still required.
The reference is provenance, not proof of an untampered installation: audit the supplying APM deployment, and use the observation entrypoint digest to identify drift.

Old v1 captures remain readable and exact retries reuse their existing snapshot.
New requests cannot embed a skill, including through v1.

```console
pixi run feedback-local record duct --task implementation --outcome success \
  --details details.json --event-id ACTUAL_UUID \
  --capture capture.json --capture-store sensitive \
  --capture-reason "Conversation contains private project context" \
  --capture-config /absolute/path/to/memory/transport.json
```

`--capture` uses `SKILLS_WORKSHOP_ROOT` or the configured `workshop_root` to invoke the Workshop collector with the recorder's Python environment.
It requires the Workshop checkout and its memory dependencies; it is not an independent portable annex implementation.
`--capture-state` can select an isolated state directory for testing.
Sensitive is the default capture store; give a reason, and classify any sensitive assessment fields with the ordinary overlay options too.
Choose shared only after reviewing the entire conversation, logs and report.
Do not instrument collection itself with duct.

The archive retains the original observation, request, transcript bytes, complete selected finished duct directories, optional pinned APM reference, the reporting/request schemas, and a manifest of member hashes and sizes.
Conversation scope is the whole supplied transcript through the byte boundary at collection; later messages, attachments, and unselected sessions are not silently included.
The manifest marks the boundary and caller-reported missing evidence.
It preserves a partial final line as original bytes rather than silently truncating it.
No separate skill source file is copied.
Skill text already present in the original conversation remains part of that unmodified evidence.

The result contains both the observation ID and capture ID plus an artifact descriptor.
Collection stages locally; `--capture-config` also uploads the artifact immediately.
The envelope joins the existing daily batch; no task-end flush is needed.
On upload failure, retry the same command with the same `--event-id`.
The first snapshot is reused even if the live conversation has grown.
Changed inputs require a new observation ID; collection never rewrites earlier evidence.
If the command fails after saving an observation, it reports that ID and preserves any staged capture.

Open everything using either ID:

```console
pixi run memory show-capture UUID --store sensitive \
  --config /absolute/path/to/memory/transport.json --output /new/capture-directory
```

Without `--output`, the command emits the full envelope as JSON.
With `--output`, it verifies the archive and member hashes before writing into a new directory.
It refuses to overwrite an existing directory.
The result contains `observation.json`, `conversation/transcript`, `duct/`, optional `skill/`, `manifest.json`, and `envelope.json`.
No runtime hook is installed by this option: it expands the existing agent-called recorder.
