# Executive summary: a memory layer over existing tools

Decision date: 2026-08-17.

## Recommendation

Keep the workshop, but give it one clear job:

> Preserve source-agnostic cross-project memory—what skills were considered,
> used, useful, rejected, evaluated, or improved—and provide a concise,
> transparent interface to existing discovery and project-management tools.

Use APM in every downstream project for reproducibility. Use ASM, `gh skill`,
and Vercel `skills` for discovery. Keep skill contents and contribution history
in ordinary Git. Do not build a second package manager, installer, public
catalog, lock, or host-path mapper.

See [the current direction](current-direction.md#decision).

## Why the workshop still adds value

APM can reproduce a project and public catalogs can find packages, but neither
retains personal knowledge across unrelated projects:

- remembered capabilities when the original name or source is forgotten;
- aliases, moved sources, mirrors, and forks of the same logical skill;
- selection and rejection reasons;
- declared membership versus actual task use;
- contextual outcomes and 1–5 ratings;
- controlled evaluation evidence; and
- upstream issues and contributions.

The workshop stores this as strict Git-tracked JSON and append-only events.
Logical skill IDs are independent of source URLs. That structure is small
enough to inspect and portable enough to migrate into a future service.

See [why the remaining workshop is useful](current-direction.md#why-the-remaining-workshop-is-useful).

## Tool stack

| Need | Use |
| --- | --- |
| Standard skill contents | [Agent Skills](https://agentskills.io/specification) |
| Project manifest, lock, installation, frozen replay, update, and audit | [APM](https://microsoft.github.io/apm/) |
| GitHub search, preview, provenance, and publication | [`gh skill`](https://cli.github.com/manual/gh_skill) |
| Cross-provider discovery | [ASM](https://github.com/luongnv89/asm) |
| skills.sh and `.well-known` discovery | [Vercel `skills`](https://github.com/vercel-labs/skills) |
| Source development and contribution | Git repository/fork |
| Personal cross-project evidence | Workshop memory and CLI |

ASM and Vercel are discovery providers, not alternate installers in an
APM-managed project. Every external command is printed before it runs.

See [one authority per concern](current-direction.md#one-authority-per-concern).

## SkillNote decision

SkillNote has an excellent interface concept: collections, live sync, version
history, usage, ratings, and agent comments. Its rating loop is worth learning
from.

Do not make its database canonical yet. Its current portable ZIP exports skill
files but not the complete structured history; its relations are coupled to
SkillNote slugs/versions; its validator and renderer accept nonstandard names
and write a top-level `collections` field; and its 15-skill collection limit is
based on an overstated Claude claim. Current main contains a Codex integration
that its README still calls future work, which warrants a real compatibility
trial.

Retain portable workshop events first. Consider SkillNote later as a UI only if
it can round-trip IDs, provenance, use, ratings, and evaluation evidence without
becoming the sole store.

See [the SkillNote assessment](current-direction.md#skillnote-useful-interface-wrong-canonical-store-for-now).

## Evaluation pattern

Keep ordinary feedback cheap: after real use, record a sanitized task summary,
invocation mode, outcome, optional 1–5 rating, rationale, and agent/runtime
context. This is useful observation, not causal proof.

For consequential skills, compare two fresh isolated agents on the same pinned
fixture and prompt, one with the exact skill and one without it. Match model,
reasoning effort, tools, permissions, and budget; predeclare metrics and
grading. One pair is exploratory. Controlled and replicated labels require
stronger evidence.

See [ratings versus evaluation](current-direction.md#ratings-versus-evaluation)
and the [evaluation protocol](evaluation-protocol.md).

## What is not being developed

The earlier two-way source/project reconciliation engine is frozen. It may be
technically differentiated without being useful. Prefer one of two simpler
modes:

- develop in the project and export a generally useful change to Git; or
- develop in shared Git source and let APM update projects.

Revisit reconciliation or generic overlays only after repeated real episodes
show continual import/export is materially error-prone.

SkillPort may later be trialed only as a read-only local search/MCP view; its
nested metadata format and validator are not acceptable conformance authority.
`skills-registry` does not currently provide the supported fully local,
on-demand service desired here. Enterprise registries are out of scope.

See [what happens to two-way synchronization](current-direction.md#what-happens-to-two-way-synchronization)
and [SkillPort and other managers](current-direction.md#skillport-and-other-managers).

## Current implementation

This repository now contains:

- a `v0` source-agnostic memory schema for logical skills, projects,
  append-only events, evaluations, tags, and bundles;
- a tested `workshop` CLI for validation, recall, multi-provider discovery,
  decisions, project membership, use/ratings, contribution links, exact
  artifacts, APM install/audit, and evaluation scaffolds;
- a tracked `skills-workshop` skill that gives agents the same workflow;
- a tracked `commit-provenance` skill promoted from the host; and
- project-local APM manifest, lock, and `.agents/skills` deployments for both.

The schema deliberately remains `v0`. Promote it to `v1` only after a second
real project exposes mistakes. Do not spend effort maintaining compatibility
between discarded experimental layouts.

The dogfood run also found two APM 0.28.0 limitations: positional-package dry
runs can produce a contradictory plan, and `audit --ci` falsely expects nested
APM manifests in standalone raw local-skill dependencies. Project-owned skills
now use `.apm/skills`, which passes frozen replay and every CI audit check. The
workshop keeps the operational safeguards but does not duplicate the upstream
issue tracker or replace APM because of the defects.

## Next evidence

1. Repeat the completed three-intent search trial as provider versions change.
2. Add one unrelated APM-managed project.
3. Record both successful and failed real uses.
4. Run one exploratory paired skill evaluation.
5. Trial `.well-known` discovery through Vercel.
6. Reassess whether a third-party UI can safely round-trip the accumulated
   memory.

The alternative proposed for
[CON skills issue #5](con-issue-5-alternative.md) follows the same pattern:
keep the coherent `find-skill` interface, delegate its installer.
