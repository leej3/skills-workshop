# Skills workshop

This repository is a Git-backed, source-agnostic memory of skills encountered across projects.
It remembers where a skill came from, why it was considered, where it was declared or actually used, how it worked, and whether it was evaluated or improved upstream.

`skills-workshop` itself may be installed once as a user-level agent control skill.
That installation routes skill-lifecycle requests through this repository; it does not make the skills it discovers user-global.
Each selected skill is installed into the active project's APM manifest, lock, and agent-skill target, while the workshop retains cross-project memory.

It is not another package manager or public registry.
Downstream projects use [Microsoft APM](https://microsoft.github.io/apm/) for their own reproducible manifest, lock, installation, update, and audit.
Public discovery is delegated to [ASM](https://github.com/luongnv89/asm), [`gh skill`](https://cli.github.com/manual/gh_skill), and [Vercel `skills`](https://github.com/vercel-labs/skills).
The workshop provides one concise human/agent interface and retains only information those tools do not know across projects.

The concise architecture and recommendations are in the [skill-management executive summary](docs/skill-management-executive-summary.md).
Detailed, agent-maintained research lives under [`docs/agents/`](docs/agents/).
Earlier reconciliation code remains as a frozen prototype, not the default project lifecycle.

## Responsibility model

| Concern | Authority |
| --- | --- |
| Portable skill contents | [Agent Skills](https://agentskills.io/specification) |
| Project dependencies, exact resolution, deployment, lock, update, and audit | APM in that project |
| GitHub discovery, preview, source provenance, and publication | `gh skill` |
| Cross-provider catalog discovery | ASM |
| skills.sh and `.well-known` discovery | Vercel `skills` |
| Skill content and contribution history | Ordinary Git source and forks |
| Cross-project recall, decisions, use, ratings, evaluations, and contribution links | This workshop |

The boundary is testable:

- deleting this workshop must leave an APM-managed project reproducible;
- deleting a project's APM files must leave the workshop unable to recreate its dependency state.

## Set up

```console
git clone --recurse-submodules https://github.com/leej3/skills-workshop.git
cd skills-workshop
pixi install --locked
pixi run workshop doctor
pixi run memory-validate
pixi run apm-install-frozen
pixi run apm-audit
```

Pixi pins Python, Node, APM, and the helper dependencies.
The workshop CLI pins the npm discovery commands it delegates and prints every external command, working directory, and mutation class before execution.

This repository's project-owned canonical skill sources are under `.apm/skills/`.
APM's `includes: auto` deploys ordinary copies to `.agents/skills/`, records them in `apm.lock.yaml`, and uses `apm_modules/` only as an ignored cache.
Edit the canonical source and rerun APM; do not edit the deployed copy.

Start a project-specific experimental skill in `.apm/skills/<name>`.
Do not also declare it as a local dependency.
Promote it to an independent Git/APM package only after another project needs it or it acquires its own release lifecycle.

## Find and remember skills

Search local memory and every registered, checked-out upstream source first.
This includes aliases, source locations, prior task summaries, outcomes, and rationales, plus the K-Dense and `con/skills` source trees declared in `registry.toml`.
Results show each local source's pinned revision; newly added registered sources automatically participate in the same search:

```console
pixi run workshop find "something I used to verify commit trailers"
```

For a candidate where freshness matters, inspect the latest verified remote state before choosing it.
The status command fetches only when requested; updating a checkout always begins with a plan and requires an explicit apply:

```console
pixi run upstream-status --fetch
pixi run upstream-update scientific-agent-skills
```

The same default search then queries the pinned public discovery tools, after the local results.
Use `--provider` only when a narrower or specially composed search is useful:

```console
pixi run workshop find "neuroimaging dataset review" --dry-run
```

Preview a GitHub candidate's full tree without installing it:

```console
pixi run workshop preview owner/repository skill-name@commit-sha
```

Search results are not mirrored wholesale.
Record a skill only after the user has directed consideration, or after it is installed or used; an agent search or preview alone is not durable evidence:

```console
pixi run workshop remember example-skill \
  --summary "When and why this is useful" \
  --source https://github.com/example/skills.git \
  --source-kind git --source-role canonical \
  --subpath skills/example-skill

pixi run workshop consider example-skill \
  --decision adopted --reason "Why this candidate was selected" \
  --asserted-kind human --asserted-by john
```

A logical skill has a stable UUID independent of any source.
Add a mirror, fork, moved origin, or remembered local location without changing that ID:

```console
pixi run workshop source add example-skill \
  --source https://github.com/me/example-skills.git \
  --source-kind git --source-role fork
```

## Install and observe a project

Installation is an APM operation.
The workshop defaults to an APM preview and requires `--apply` before mutation:

```console
pixi run workshop install owner/repository --project ../project
pixi run workshop install owner/repository --project ../project --apply
pixi run workshop audit ../project
```

APM 0.28.0 currently emits contradictory output for some positional-package dry runs: it announces a package addition, omits the candidate from the plan, then says nothing would change.
The wrapper detects and warns about that specific contradiction.
Defer the apply when it appears; the preview is not a sound approval artifact.

APM may discover organization policy from the repository remote and therefore perform a network/authentication check.
The workshop exposes `--no-policy` as an explicit personal-project choice; it never silently adds the bypass.

Remember a project by its durable repository identity, not a host path, and record APM-resolved membership without pretending it proves actual use:

```console
pixi run workshop project add my-project \
  --repo-url https://github.com/example/my-project.git
pixi run workshop project scan my-project --project-path ../my-project
```

After a skill participates in a real task, record a sanitized observation:

```console
pixi run workshop use example-skill \
  --task "Reviewed a dataset release" \
  --invocation explicit --outcome success --rating 4 \
  --rationale "Found two missing release checks; one correction was needed" \
  --project my-project --project-path ../my-project \
  --asserted-kind agent --asserted-by codex
```

Ratings use `workshop-overall-v1`: 1 harmful, 2 unhelpful, 3 mixed, 4 useful, and 5 decisive.
They are contextual observations, not controlled efficacy evidence.
Agent assertions remain visibly distinct from human review.

```console
pixi run workshop show example-skill
pixi run workshop history example-skill
pixi run workshop where-used example-skill
```

When work produces an upstream issue, pull request, commit, release, or discussion, keep the durable link with the same logical skill:

```console
pixi run workshop contribution add example-skill \
  --kind pull-request --direction upstream --state open \
  --url https://github.com/example/skills/pull/123 \
  --summary "Generalized the release check" \
  --asserted-kind human --asserted-by john
```

## Evaluate an important skill

For a repeated or consequential claim, create an explicit with-skill versus without-skill scaffold:

```console
pixi run workshop eval init example-skill \
  --hypothesis "The skill improves release-review completeness" \
  --fixture fixtures/release-review-v1 \
  --prompt "Review this release" \
  --expected "Identify every seeded defect" \
  --metric "Defects found without false positives"
```

One stochastic pair is exploratory.
Controlled evidence additionally requires an exact treatment artifact, identical fixture/runtime/tools/permissions, isolation, and explicit grading; replicated evidence requires repeated trials.
Record the exact source revision and a named, scoped digest with `workshop artifact add` before creating a controlled evaluation:

```console
pixi run workshop artifact add example-skill \
  --revision <immutable-revision> \
  --digest-scheme <producer-scheme> --digest-algorithm sha256 \
  --digest-scope skill-tree --digest-value <digest>
```

The v0 CLI creates and validates the evidence scaffold; it does not execute or grade agents.
A record cannot validate as complete without assigned grading, runtime and budget controls, complete condition/case coverage, declared metrics, and retained evidence. See [the evaluation protocol](docs/agents/evaluation-protocol.md).

## Canonical memory

The initial schema is intentionally `v0`:

```text
memory/
  skills/<uuid>.json
  projects/<uuid>.json
  events/YYYY/MM/<timestamp>-<uuid>.json
  evaluations/<uuid>.json
  tags/<uuid>.json
  bundles/<uuid>.json
schemas/memory/
```

Records are strict JSON Schema 2020-12 objects.
Events are append-only.
SQLite, Markdown, and search indexes may later be generated views, never canonical state.
The schema will become `v1` only after this repository and another real project have generated enough evidence to expose poor assumptions; there is no reason to maintain compatibility among abandoned `v0` experiments.

Tags and bundles are source-agnostic recommendations.
They never contain versions, install paths, hashes, dependency graphs, or target state—those are APM concerns.

## Tracked skills

- `skills-workshop`: this workflow, backed by the same tested CLI used by humans.
- `commit-provenance`: the existing co-commit trailer skill, promoted from the host into ordinary Git and installed in this project through APM.

The project-local and user-global `commit-provenance` copies currently have the same name.
Codex can show both rather than merging them.
Remove the old global copy only after confirming the project deployment serves the desired scope.

## Development

```console
pixi run validate
pixi run format
python /Users/johnlee/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .apm/skills/skills-workshop
```

`pixi run validate` runs lint, formatting checks, compilation, tests, legacy prototype metadata checks, and the new memory validator.
APM 0.28.0 frozen replay and `apm audit --ci` both pass the project-owned `.apm/skills` layout.
Two independently reproduced APM limitations have been reported upstream: local raw-skill dependencies fail the CI configuration check, and positional-package dry runs omit their prospective install plan.
Neither changes the workshop's ownership boundary.

The workshop code is available under the [MIT License](LICENSE).
Imported or upstream skills retain their own terms.

## Design and research

- [Skill-management executive summary](docs/skill-management-executive-summary.md)
- [Documentation policy](docs/README.md)
- [Detailed agent references](docs/agents/README.md)
