# Skills workshop

This repository is a Git-backed, source-agnostic memory of skills encountered across projects.
It remembers where a skill came from, why it was considered, where it was declared or actually used, how it worked, and whether it was evaluated or improved upstream.

## Quickstart (Codex, macOS or Linux)

With Git and Pixi installed:

```console
git clone --recurse-submodules https://github.com/leej3/skills-workshop.git
cd skills-workshop
pixi install --locked
pixi run configure-upstreams
pixi run setup-agent
pixi run setup-agent --apply
pixi run workshop doctor
```

`setup-agent` previews the changes; `--apply` installs the complete agent workflow:

- **Discover and adopt:** links `skills-workshop` into your user-level skill directory.
- **Learn from use:** links `workshop-feedback` and configures this checkout as its memory destination.
- **Connect the two:** adds a small marked block to your global Codex `AGENTS.md` instructing the agent to use discovery and record feedback after meaningful skill use.

The setup preserves unrelated instructions and configuration, reuses existing links, and refuses conflicting installations.
Keep this checkout at its installed location: both skills link to its maintained sources.
No runtime hooks, working skills, or uploads are enabled by setup.
For your own ongoing history, use a fork or private copy; existing memory is the maintainer's recorded experience, not evidence of your own use.

Start a new Codex task in the project you want to work on, then ask:

> Use $skills-workshop to find a skill for reviewing this project's releases.

After a skill participates in the work, the agent uses `workshop-feedback` to retain a short observation; you do not need to request a rating each time.
To check that the two halves are working, ask:

> Use $skills-workshop to recall which skills helped with release reviews.

From this checkout, `pixi run workshop insights --since YYYY-MM-DD` shows recorded outcomes and proposed improvements.
For other agents, install both control directories in that host's user-level skill location, configure the checkout as described under [feedback](#lightweight-feedback-across-projects), and add the equivalent post-task instruction to that host's global guidance.
The automated setup currently targets Codex.

## How it fits together

`skills-workshop` and `workshop-feedback` may be installed as user-level agent control skills.
That installation routes skill-lifecycle requests through this repository; it does not make the skills it discovers user-global.
Each project-owned experimental skill lives directly in that project's `.agents/skills/` tree.
Independently maintained reusable skills are installed through the active project's APM manifest and lock, while the workshop retains cross-project memory for both kinds.

It is not another package manager or public registry.
Projects need no package manager while all their skills are project-owned.
When a project first consumes an independently maintained promoted skill, it may introduce [Microsoft APM](https://microsoft.github.io/apm/) for reproducible installation, update, and audit.
Public discovery is delegated to [ASM](https://github.com/luongnv89/asm), [`gh skill`](https://cli.github.com/manual/gh_skill), and [Vercel `skills`](https://github.com/vercel-labs/skills).
The workshop provides one concise human/agent interface and retains only information those tools do not know across projects.

The concise architecture and recommendations are in the [skill-management executive summary](docs/skill-management-executive-summary.md).
Detailed, agent-maintained research lives under [`docs/agents/`](docs/agents/).
Earlier reconciliation code remains as a frozen prototype, not the default project lifecycle.

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
This includes aliases, source locations, prior task summaries, outcomes, and rationales, plus all registered source trees: K-Dense, NiPreps, `con/skills`, Anthropic, and OpenAI.
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

## Lightweight feedback across projects

[`workshop-feedback`](.agents/skills/workshop-feedback/SKILL.md) is the feedback half of the standard Workshop workflow, installed alongside discovery by `pixi run setup-agent --apply`.
It records one short observation after actual skill use.
For manual installation or another host, install both control skill directories at user scope and configure the checkout in `~/.config/skills-workshop/config.json`:

```json
{"workshop_root": "/absolute/path/to/skills-workshop"}
```

A global agent instruction to invoke it after meaningful skill use makes the process explicit; implicit skill selection alone is not a guaranteed hook.
The skill and its launcher are portable, with Pixi and the configured Workshop CLI as declared dependencies.
No external posting or push is automatic.

```console
pixi run workshop feedback example-skill \
  --task "Reviewed a release" --rationale "Found a missing checksum" \
  --outcome success --benefit avoided-error \
  --next-step "Cover detached signatures" \
  --project-path ../project --asserted-kind agent --asserted-by codex
pixi run workshop insights --since 2026-09-18
```

Ratings are optional.
Unknown outcomes remain unknown; failures and unclear benefit belong in memory too.
`--skill-path` can remember a newly used skill and record an entrypoint digest.
`--project-path` links an already remembered project by remote identity when unambiguous.
`--session` makes retries idempotent for the same skill/task; later milestones or corrections use a distinct task summary.
Evidence links and proposed improvements can be added without creating an evaluation or an upstream issue.

`insights` reports observed benefits, outcomes, review/evidence coverage, and proposed follow-ups over a chosen period.
Use it over the next few weeks to assess discovery breadth, new capabilities, repeat usefulness, and recording effort.
These observations do not establish causality.

### Skill or hook?

Use the skill for the feedback process and, when added, a host hook for the trigger.
The agent must judge whether a skill materially participated and what changed; a file read or completed tool call does not establish that.
The CLI validates and stores the resulting observation.

Codex currently supports a `Stop` hook that can request another agent pass, with a `stop_hook_active` flag to identify a continuation.
Its documented events do not include a dedicated skill-use event, and transcript format is not a stable hook interface; see the [official hook reference](https://learn.chatgpt.com/docs/hooks).
A future adapter should prompt at most once per relevant task milestone, retain duplicate protection, and let the task finish if feedback fails.
It should not assign ratings or infer successful use from tool calls.

The current default is the global instruction plus the portable feedback skill.
No lifecycle hook is shipped or installed yet.
Measure missed feedback during the trial before choosing a host-specific trigger; an unconditional stop reminder can add cost and latency to every response.

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

- `skills-workshop`: discovery and adoption, backed by the same tested CLI used by humans.
- `workshop-feedback`: lightweight post-task observations, installed globally as a second control skill.
- `commit-provenance` and `build-github-app`: currently project-owned native skills; promote either to an independent source when another project needs its versioned lifecycle.

The project-local and user-global `commit-provenance` copies currently have the same name.
Codex can show both rather than merging them.
Remove the old global copy only after confirming the project deployment serves the desired scope.

## Development

```console
pixi run validate
pixi run format
python /Users/johnlee/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/skills-workshop
```

`pixi run validate` runs lint, formatting checks, compilation, tests, legacy prototype metadata checks, and the new memory validator.
APM remains available to the Workshop as a delegated tool for projects that have actual promoted dependencies; it is not initialized speculatively in this repository.
Neither changes the workshop's ownership boundary.

The workshop code is available under the [MIT License](LICENSE).
Imported or upstream skills retain their own terms.

## Design and research

- [Skill-management executive summary](docs/skill-management-executive-summary.md)
- [Documentation policy](docs/README.md)
- [Detailed agent references](docs/agents/README.md)
