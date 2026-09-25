---
name: skills-workshop
description: Coordinate systematic agent-skill discovery, native project skill creation, reusable dependency installation, cross-project recall, use tracking, evaluation, and upstream contribution. Use when asked to find or compare skills, create or manage a project's skills, install or audit reusable skills with APM, remember a skill or source, record outcomes or ratings, see where a skill was used, or test whether a skill helps. This skill keeps workshop memory separate from project-native and project-local APM state and delegates public discovery to ASM, GitHub gh skill, and Vercel skills.
---

# Skills Workshop

Respect the user-level Workshop mode in agent guidance: in manual mode, invoke only on an explicit user request; in off mode, use only the retained status/reactivation guidance.

Use the workshop as a source-agnostic memory and a transparent interface to existing tools.
Do not turn it into another installer, registry, or project lock.

## Scope and bootstrap

This is the user-level control skill for discovery and adoption.
The separate `workshop-feedback` control skill handles lightweight post-task observations across projects.
When an agent is asked to find, create, install, audit, record, or evaluate a skill, it should invoke this skill first.
That does not make discovered skills user-global: keep a new project-owned skill directly in the active project's `.agents/skills/`, or install an independently maintained reusable skill through the project's APM state, then record the relationship and any later real use in workshop memory.
A project's reproducible skill set must remain usable if this user-level control skill or the workshop checkout is unavailable.

## Start here

Run commands from the workshop checkout:

```console
pixi run workshop doctor
pixi run workshop validate
```

The doctor names each external tool, its pinned version, and its authority.
Every delegated command is printed before execution.

An explicit request to install a named skill authorizes that installation after the normal preview and compatibility checks.
Continue a fresh alternative search and offer worthwhile alternatives alongside the result; do not make that search or a second selection gate block the named choice.
Never substitute an alternative without the user's agreement.
For an open-ended request, search and recommend a shortlist before adopting a candidate unless the user has authorized you to choose or create it.

## Find and consider a skill

Search remembered skills and the locally tracked upstream inventory first.
The local phase searches every registered upstream, the Workshop native skills, and configured installed skill roots, including full entrypoint contents.
It reports pinned upstream revisions and distinguishes installed observations from remembered use:

```console
pixi run workshop find "capability or remembered task"
```

At the start of each new consultation, inspect the registered-source status.
When network access is available, fetch status so newly published candidates or changes can be reported.
This is a read-only freshness check: never update a registered checkout as a side effect of discovery.

Updating a source is explicit; it never happens as a side effect of search:

```console
pixi run upstream-status --fetch
pixi run upstream-update <registered-source>
```

Apply a reviewed update only with `pixi run upstream-update <registered-source> --apply`, then commit the resulting Workshop gitlink change before relying on that revision.

Then query all configured discovery providers unless the user explicitly narrows the sources.
The default order keeps remembered and local community sources first, but still returns public candidates that may be worth considering or improving upstream:

```console
pixi run workshop find "capability"
```

Use `--provider` only when the user requests a narrower search or the default command cannot query a configured source.
A named installation can proceed while the broader search supplies advisory alternatives.

If you skip or narrow a discovery step, omit the freshness check, or substitute a web search, disclose that decision when you make it.
Name the affected sources or steps, explain the concrete constraint or reason, and identify the fallback.
In the final results, distinguish sources actually searched through Workshop from separately searched sources and sources not queried; state any freshness limitation.
Do not describe an unqueried provider as failed or claim it would miss a candidate without evidence from an actual search.

### Present choices without blocking an explicit choice

Keep searching fresh sources even when a named skill is already known: newer alternatives can be valuable on the next project.
Summarize worthwhile alternatives with source links, differences, and any freshness or provider limitations.
An exact installation request supplies the choice; alternatives are advisory.
For open-ended discovery, include adapting a candidate or creating a project-owned skill when appropriate, and ask for a choice only if the user has not delegated it.
A failed provider should not block an otherwise verified named installation.
Report the incomplete search and continue the authorized work.

Inspect a GitHub candidate's complete tree without installing it:

```console
pixi run workshop preview <owner/repository> <skill-or-path@commit>
```

Do not install reusable dependencies with ASM, `gh skill`, or Vercel `skills` when APM manages the project.
Searching or previewing a candidate is not consideration evidence.
Record a candidate only after the user has directed a decision about it (for example, adopt, defer, or reject), or after it is installed or used.
Do not create unreviewed memory merely from an agent recommendation:

```console
pixi run workshop remember <name> --summary "..." \
  --source <canonical-location> --source-kind git --source-role canonical
pixi run workshop consider <name> --decision adopted --reason "..." \
  --asserted-kind human --asserted-by <person>
```

Use `--asserted-kind agent` and record the actual agent identity when an agent, not a person, makes an observation.
Never attribute an agent judgment to the user.

## Install and audit in a project

APM alone owns the downstream manifest, lock, external dependency graph, deployment, update, and drift state.
Use the metadata-only consumer workflow for every reusable skill APM can install.
Develop reusable source in a dedicated skill repository, normally `con/skills`; never develop or commit its deployed copies in a consumer.
Add a pinned APM setup/development dependency through the project's existing environment manager, a frozen-install setup task, targeted ignores for `apm_modules/` and APM-owned deployment paths, a concise additive root `AGENTS.md` instruction, and a README/development setup note.
Track the manifest, generated lock, and setup metadata; validate a fresh metadata-only consumer with frozen restoration and audit.
Use `install-apm-skills` when available for the full consumer workflow and `author-apm-skills` for explicit APM distribution or collection-maintenance requests; the latter must not take over generic skill creation.
These workflows are maintained in `con/skills`; downstream setup must not require the Workshop or either skill to be preinstalled.

It does not own project-authored skills that live directly under `.agents/skills/`.
Before touching downstream APM state, require the selected reusable source at the intended ref to be a valid APM package that publishes the selected skill.
Do not use a raw skill directory, virtual-subdirectory import, or downstream manifest workaround to compensate for missing upstream packaging.
When the source is not APM-ready, improve the canonical repository first; if that is not possible, use a deliberate maintained fork and offer the packaging change upstream.
The first command is a preview:

```console
pixi run workshop install <apm-package> --project <project>
pixi run workshop install <apm-package> --project <project> --apply
pixi run workshop audit <project>
```

Review the printed APM command and preview before applying.
Never pass APM `--force` through the workshop.
Edit an external skill in its canonical Git source rather than its APM-deployed `.agents/skills` copy.
If organization-policy discovery would cause an unwanted login or network lookup in a personal project, explicitly add `--no-policy`; do not make that bypass invisible.

For a genuinely project-specific experiment that is not intended as a reusable skill, author the canonical tree directly at `.agents/skills/<name>`.
Do not copy it into `.apm/skills` or declare it as a local APM dependency.
Do not initialize APM, a lock, or a bootstrap while every skill remains project-owned.
When the first promoted external dependency is adopted, let the project choose its dependency and agent-agnostic setup mechanism at that time.
When reuse or APM distribution is intended from the outset, start in the dedicated source repository instead.
Promote a project-specific experiment there when it gains that scope.

Before installation, verify that the skill is self-contained.
Every operating instruction, reference, script, template, and asset needed to use the skill must live inside its skill directory, except for explicitly declared and available tool or package dependencies.
Do not make `SKILL.md` depend on parent project documentation, absolute host paths, or undeclared sibling skills.
Project files may be task inputs, but they are not a substitute for portable skill instructions.
Check links from the canonical tree and verify it works without reaching outside its own skill directory for operating instructions or resources.
For an external dependency, install its package into an isolated temporary consumer, confirm the selected skill is deployed, and run `apm audit` before changing the real downstream.
Read [references/workflow.md](references/workflow.md) for the boundary and verification checklist.

## Record evidence after real use

Use `workshop-feedback` for one schema-validated baseline record per skill/task after material use.
Its policy owns collection exemptions, exceptional qualitative notes, grouping, priority, and publication review.
Routine successes require no narrative, memory registration, or per-record commit.
Batch shareable records under user authorization; keep sensitive fields and classification reasons in the private overlay.
Installation and project membership are not evidence of use.

`feedback-local summary` reports observed outcomes and measured durations; `feedback-local insights` prioritizes grouped exceptional lessons.
Keep raw observations separate from consolidated knowledge and active skill instructions.
Consult relevant open lessons when revising a skill; record a proposed change and its validation before treating it as an improvement.
Retain rejected findings so later work does not repeat an unsuccessful intervention.

The existing `workshop feedback`, `use`, `insights`, `history`, and `recall` commands operate on Git-backed memory.
They remain available for deliberately curated records after the feedback skill's publication review.
Validate and commit intentional authorized memory changes under the checkout conventions, and batch routine shareable observations without generating extra prose reports.
Agent observations remain unreviewed assertions; counts and ratings do not establish causal benefit.

## Evaluate important claims

For important, repeated, or disputed skills, scaffold an explicit with-skill versus without-skill comparison:

```console
pixi run workshop eval init <skill> --hypothesis "..." \
  --fixture <fixture-uri> --prompt "..." --expected "..." \
  --metric "rubric score"
```

Treat one pair of stochastic agents as exploratory.
A controlled claim needs the same fixture, runtime, tools, permissions, isolation, an exact treatment artifact, and explicit grading.
Record that artifact's immutable source revision and scoped digest with `workshop artifact add` before selecting a controlled design.
Record a shared time, token, or turn budget (or explain the equivalent ambient limit).
A replicated claim needs repeated trials.
A planned scaffold may have unassigned fields; it must not be reported as a completed result.
The v0 CLI scaffolds and validates evaluation records; it does not yet execute or grade the runs.

## Contribute rather than accumulate forks

When a change is generally useful, work in the skill's ordinary Git source and offer it upstream.
Use a durable fork only for contribution or intentional divergence.
Keep project-local adaptations in the project unless repeated use justifies a reusable upstream skill.

After opening an externally useful issue, pull request, discussion, or release, attach it to the logical skill with `workshop contribution add`.
Do not add self-referential records for routine Workshop commits or memory bookkeeping.
Record a new event when its observed state changes; do not rewrite the earlier event.

Read [references/workflow.md](references/workflow.md) when choosing between tools or deciding what evidence to record.
