# Workshop reference

For installation and first use, see the [README](../../README.md).

## Responsibility model

| Concern | Authority |
| --- | --- |
| Portable skill contents | [Agent Skills](https://agentskills.io/specification) |
| Project-owned experimental skill source | That project's tracked `.agents/skills/` tree |
| External dependencies, exact resolution, deployment, lock, update, and audit | APM in that project |
| GitHub discovery, preview, source provenance, and publication | `gh skill` |
| Cross-provider catalog discovery | ASM |
| skills.sh and `.well-known` discovery | Vercel `skills` |
| Skill content and contribution history | Ordinary Git source and forks |
| Cross-project recall, decisions, use, ratings, evaluations, and contribution links | This workshop |

The boundary is testable:

- deleting this workshop must leave native project skills usable and APM dependencies reproducible;
- deleting a project's native skills and APM files must leave the workshop unable to recreate its skill state.

## Project-owned skills and dependencies

Pixi pins Python, Node, APM, and the helper dependencies.
The workshop CLI pins the npm discovery commands it delegates and prints every external command, working directory, and mutation class before execution.

This repository's project-owned canonical skill sources are ordinary tracked trees under `.agents/skills/`.
Edit them there directly; they need no APM installation or startup hook.
This repository has no APM manifest, lock, deployment, or bootstrap because all of its current skills are project-owned.

Start a project-specific experimental skill in `.agents/skills/<name>`.
Do not duplicate it under `.apm/skills` or declare it as a local dependency.
Promote it to an independent Git/APM package only after another project needs it or it acquires its own release lifecycle.
Only after consuming a promoted external skill should a project choose dependency infrastructure and, if useful, expose an agent-agnostic bootstrap through Pixi or its preferred setup hook.

## Find and remember skills

Search local memory and every registered, checked-out upstream source first.
Memory search includes aliases, source locations, prior task summaries, outcomes, and rationales.
### Local catalogs

The following catalogs are included as pinned Git submodules and searched locally:

| Skill source | Focus |
| --- | --- |
| [OpenAI skills](https://github.com/openai/skills) | Codex skill catalog, including curated and experimental workflows |
| [Anthropic skills](https://github.com/anthropics/skills) | Creative, document, and developer workflow examples |
| [K-Dense scientific skills](https://github.com/K-Dense-AI/scientific-agent-skills) | Scientific tools and research workflows |
| [NiPreps skills](https://github.com/nipreps/skills-comm) | Neuroimaging workflows and operational guidance |
| [CON skills](https://github.com/con/skills) | Software maintenance, triage, and automation |

[registry.toml](../../registry.toml) lists their checkout locations and upstream URLs.
These are discovery sources; individual skills are installed only when selected for a project.
For an existing checkout, run `git submodule update --init --recursive` after pulling to initialize newly added catalogs.

### Public discovery tools

A normal `workshop find` searches memory, the local catalogs above, and configured installed-skill directories, then queries all three public discovery tools:

| Tool | How Workshop uses it | Select just this provider |
| --- | --- | --- |
| [ASM (Agent Skill Manager)](https://github.com/luongnv89/asm) | Cross-provider catalog search through `agent-skill-manager search --available --machine` | `--provider asm` |
| [Vercel `skills`](https://github.com/vercel-labs/skills) | Public candidate discovery through `skills find` | `--provider vercel` |
| [GitHub `gh skill`](https://cli.github.com/manual/gh_skill) | GitHub skill search; `workshop preview` also delegates whole-tree candidate preview | `--provider github` |

These tools expand discovery beyond the five checked-out catalogs.
ASM and Vercel run through version-pinned `npx` commands; GitHub discovery uses the Pixi-managed `gh` CLI.
Workshop uses these integrations for discovery and preview, while accepted external project dependencies are installed through APM.
GitHub publication and Vercel's broader source support are available in the underlying tools; the current Workshop CLI does not wrap publication or implement its own `.well-known` crawler.

### Other tools in the skill workflow

| Tool | Role in this project | Entry point |
| --- | --- | --- |
| [Microsoft APM](https://microsoft.github.io/apm/) | External project skill dependencies: installation preview/apply and audit; Workshop also reads manifests and locks for membership evidence | `workshop install`, `workshop audit`, `workshop project scan` |
| Git | Pins catalog revisions as submodules, manages upstream/fork history, and versions skills and Workshop memory | `configure-upstreams`, `upstream-status`, `upstream-update` |
| Pixi | Provides the reproducible runtime and commands for the skill workflow, including Python, Node, GitHub CLI, and APM | `pixi install --locked`, `pixi run workshop doctor` |
| `fzf` (optional, separately installed) | Interactive filtering of exported skill candidates; selecting a result does not install it | Pipe `workshop find --offline --tsv` output into `fzf` |
| VisiData | Interactive browsing of generated skill inventory and trust-signal tables | `pixi run inventory-vd`, `pixi run trust-vd` |
| Textual | Terminal interface for the retained project-skill import/reconciliation prototype | `pixi run import-project --help` |
| Workshop CLI and control skills | Cross-project recall, source identity, observations, contribution links, and evaluation scaffolds; `skills-workshop` guides discovery and `workshop-feedback` guides post-task recording | `workshop recall`, `feedback`, `insights`, `contribution`, `eval` |

The retained prototype also provides `inventory`, `skill-status`, `link-core`, `apply-bundle`, `import-project`, backup cleanup, and legacy metadata migration/validation. Its copy/link/reconciliation operations are optional experiments, not the default APM dependency workflow.
`trust-inventory` and `review-skill` expose source signals and recorded review state; they do not establish that a skill is safe or effective.
Tools discussed only in the research notes, such as SkillNote and SkillPort, are not active integrations.

### Search and recall examples

Local discovery searches full `SKILL.md` contents and configured installed skill roots as well as names and descriptions.
Ranking favors meaningful query coverage and specific matches, tolerates minor typos, and explains its matches.
Recall results include recent outcomes and caveats with their assertion and review status.
Results show each local source's pinned revision; newly added registered sources automatically participate in the same search:

```console
pixi run workshop find "something I used to verify commit trailers"
```

Use memory alone for a quick recollection, or keep all discovery local:

```console
pixi run workshop recall "something I used to verify commit trailers"
pixi run workshop find "hippocampal segmentation" --offline
```

An empty offline query lists candidates.
TSV output supports an optional `fzf` picker without executing or installing the selected result:

```console
pixi run workshop find "" --offline --limit 1000 --tsv | fzf
```

Public searches remain part of fresh discovery.
Text output shows local results immediately, and a failed provider does not discard successful results.
`--json` includes provider errors for agents.
Only the supplied query goes to public providers; local memory and installed contents stay local.

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

A request to install a named skill authorizes that choice after the normal preview and compatibility checks.
Search for fresh alternatives and offer useful ones alongside the result, without making another selection a prerequisite or silently substituting them.
Open-ended requests still benefit from a shortlist before adoption.

Installation is an APM operation.
The workshop defaults to an APM preview and requires `--apply` before mutation:

```console
pixi run workshop install owner/repository --project ../project
pixi run workshop install owner/repository --project ../project --apply
pixi run workshop audit ../project
```

APM 0.29.0 still emits contradictory output for some positional-package dry runs: it announces a package addition, omits the candidate from the plan, then says nothing would change.
The wrapper detects and warns about that specific contradiction.
The upstream fix merged after 0.29.0 in [microsoft/apm#2664](https://github.com/microsoft/apm/pull/2664); retain the guard until a release containing it is pinned.
Defer the apply when the warning appears; the preview is not a sound approval artifact.

APM may discover organization policy from the repository remote and therefore perform a network/authentication check.
The workshop exposes `--no-policy` as an explicit personal-project choice; it never silently adds the bypass.

Remember a project by its durable repository identity, not a host path, and record native and APM-resolved membership without pretending either proves actual use:

```console
pixi run workshop project add my-project \
  --repo-url https://github.com/example/my-project.git
pixi run workshop project scan my-project --project-path ../my-project
```

For a deliberately curated, publication-reviewed observation, the Git-backed memory interface remains available:

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

## Lightweight feedback across projects

[`workshop-feedback`](../../controls/skills/workshop-feedback/SKILL.md) is the feedback half of the standard Workshop workflow, installed alongside discovery by `pixi run setup-agent --apply`.
It records schema-validated baseline outcomes in a shareable tree with a private sensitivity overlay, with grouped qualitative notes only for exceptional lessons.
The bundled `scripts/usage.py` hook needs Python and jsonschema on macOS or Linux; it can be called directly by an agent or a host completion adapter.
It does not automatically register a host callback.

```console
pixi run feedback-local record example-skill --task release-review --outcome success
pixi run feedback-local summary --since 2026-09-01
pixi run feedback-local insights
```

The user-level instruction delegates collection exemptions and publication policy to that skill.
Routine collection requires no registration, prose report, or per-record commit; schema validation is automatic and shareable records are batched.
Use the separate Git-backed `workshop feedback` interface only after reviewing the full record for publication and confirming authorization.
The launcher no longer automatically inserts conversation IDs.
See [local feedback and learning](local-feedback.md) for measurement semantics and the relationship to WikiSkill.

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
A record cannot validate as complete without assigned grading, runtime and budget controls, complete condition/case coverage, declared metrics, and retained evidence.
See [the evaluation protocol](evaluation-protocol.md).

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

- `skills-workshop`: discovery and adoption, backed by the same tested CLI used by humans.
- `workshop-feedback`: lightweight post-task observations, installed globally as a second control skill.
- `commit-provenance` and `build-github-app`: currently project-owned native skills; promote either to an independent source when another project needs its versioned lifecycle.

The project-local and user-global `commit-provenance` copies currently have the same name.
Codex can show both rather than merging them.
Remove the old global copy only after confirming the project deployment serves the desired scope.

