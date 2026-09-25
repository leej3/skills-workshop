# Structured feedback and learning

Routine records are useful shared evidence.
Sensitive details belong in a private overlay, rather than making all observations private.

## Recording is explicit

**The command does not trigger automatically.** An agent calls it under the user-level instructions, or a future host adapter can call it on completion.
No runtime callback, completion listener, or timer is installed today.

```console
pixi run feedback-local record duct --task build-validation --outcome success
```

The command validates each written and read record against the bundled [JSON Schema draft 2020-12 contract](../../controls/skills/workshop-feedback/schemas/observation-v2.schema.json).
Run `pixi run feedback-local schema` to print the contract.
Unknown fields and invalid types are rejected; dates, UUIDs, nonnegative costs and counts, and duration scope are checked.
Python and jsonschema are provided by the existing Pixi environment; the installed skill includes its own schema and helpers.

The three required arguments remain skill, task category, and skill outcome.
Generated fields identify and date the observation.
Optional groups cover context, execution, resources, quality, evidence, and evaluation; see [reporting examples](../../controls/skills/workshop-feedback/references/reporting.md).
Use `--details file.json` for richer concise reporting rather than a long list of flags.
No environment details are guessed or automatically scanned.

Record the skill's success separately from the surrounding task result.
Measure elapsed duration with an explicit task/skill scope; an elapsed task duration shared across skills must not be summed. Missing metrics remain unknown, not zero. Cost or time saved requires a comparison, not just an elapsed duration. `summary` reports counts, known-outcome success fractions, and median durations/resources with sample sizes.
Groups distinguish task categories, models, and skill entrypoint digests; full artifact digests and exact revisions can also be supplied for evaluations.
These are observational statistics over reported uses, not evidence that a skill caused a result.

## Two matching trees

```text
<workshop>/memory/observations/
  records/YYYY/MM/<uuid>.json       # shareable projection

<local-state>/skills-workshop/feedback-overlay/
  records/YYYY/MM/<uuid>.json       # full record + sensitivity decision
```

Each observation is one immutable JSON file, avoiding concurrent Git edits to one large JSONL file.
The private overlay mirrors the path and ID, so local readers merge it with the shareable tree without double counting.
Private-only records have no shareable projection.
`--store` and `--overlay` override the roots; they must be disjoint, and the overlay is rejected inside a Git checkout.
Without a configured Workshop checkout, the shareable tree falls back beside the private tree in local state.
Private directories/files use restrictive permissions; no encryption or secret-vault claim is made.

For sensitive optional fields, provide JSON pointers through `--private-fields` plus a category and reason.
The public projection removes those fields and the sensitivity decision itself; the overlay retains the complete record, reason, classifier, confidence, and policy version.
If a required field is sensitive, choose `--visibility private` for the entire observation.
Fields are classified by the caller; the recorder enforces the split but does not infer sensitivity.
Keep credentials out of both trees.

Writers use a file lock and atomic no-overwrite file creation.
A UUID reused with identical content is idempotent and repairs a missing projection after an interrupted split write; different content is rejected.
Malformed records are reported without silently rewriting them.
Existing v1 JSONL files remain untouched outside Git; they are not silently migrated, reclassified, or published.

## Read, consolidate, publish

```console
pixi run feedback-local validate
pixi run feedback-local summary --since 2026-09-01
pixi run feedback-local summary --public-only
pixi run feedback-local insights
pixi run feedback-local sensitivity
```

Default reads merge both trees locally.
Use `--public-only` for a shareable view.
`sensitivity` groups the private classification decisions by category and affected fields, retaining reasons for review.
Repeated or uncertain decisions can motivate policy changes, but frequency alone does not justify weakening disclosure rules.
Keep sensitive examples and corrections in the overlay while sharing generalized lessons.

Exceptional notes group novel failures, workarounds, ambiguities, costs, and improvement proposals.
Use a stable group and link baseline IDs; priorities, confidence, and proposed actions let agents inspect relevant findings efficiently.
Append notes with resolved, deferred, or rejected status to preserve what was tried.
Do not generate a narrative about routine successful execution.

Before completing each task, inspect and validate its shareable records and commit them in the configured Workshop checkout, even when the main task is in another project.
Batch within the task; never defer valid records to a later task.
An explicit Workshop sync also includes reviewed pending records from earlier tasks.
Stage exact reviewed paths, follow repository provenance requirements, and push under standing publication authorization.
Report validation or Git blockers and remaining paths explicitly.
No per-record commit, approval request, or external message is required.
The recording command itself does not execute Git or network writes.
Never publish the overlay or merged output without separately assessing the content.
See the [classification and publication policy](../../controls/skills/workshop-feedback/references/publication.md).

## Autonomous optimization

See [the WikiSkill implementation plan](skill-optimization-loop.md) for what can be reused and what remains to build.
