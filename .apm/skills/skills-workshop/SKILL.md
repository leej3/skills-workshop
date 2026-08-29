---
name: skills-workshop
description: Coordinate systematic agent-skill discovery, self-contained project skill creation, project installation, cross-project recall, use tracking, evaluation, and upstream contribution. Use when asked to find or compare skills, create or manage a project's skills, install or audit skills with APM, remember a skill or source, record outcomes or ratings, see where a skill was used, or test whether a skill helps. This skill keeps workshop memory separate from project-local APM state and delegates public discovery to ASM, GitHub gh skill, and Vercel skills.
---

# Skills Workshop

Use the workshop as a source-agnostic memory and a transparent interface to existing tools.
Do not turn it into another installer, registry, or project lock.

## Start here

Run commands from the workshop checkout:

```console
pixi run workshop doctor
pixi run workshop validate
```

The doctor names each external tool, its pinned version, and its authority.
Every delegated command is printed before execution.

## Find and consider a skill

Search remembered skills first.
This includes prior task summaries, outcomes, aliases, and old sources, so it supports vague recall:

```console
pixi run workshop find "capability or remembered task"
```

If memory does not resolve the need, query the existing discovery providers:

```console
pixi run workshop find "capability" --provider all
```

Inspect a GitHub candidate's complete tree without installing it:

```console
pixi run workshop preview <owner/repository> <skill-or-path@commit>
```

Do not install with ASM, `gh skill`, or Vercel `skills` when APM manages the project.
Remember only a candidate that was deliberately considered:

```console
pixi run workshop remember <name> --summary "..." \
  --source <canonical-location> --source-kind git --source-role canonical
pixi run workshop consider <name> --decision adopted --reason "..." \
  --asserted-kind human --asserted-by <person>
```

Use `--asserted-kind agent` and record the actual agent identity when an agent, not a person, makes an observation.
Never attribute an agent judgment to the user.

## Install and audit in a project

APM alone owns the downstream manifest, lock, dependency graph, deployment, update, and drift state.
The first command is a preview:

```console
pixi run workshop install <apm-package> --project <project>
pixi run workshop install <apm-package> --project <project> --apply
pixi run workshop audit <project>
```

Review the printed APM command and preview before applying.
Never pass APM `--force` through the workshop.
Edit canonical skill sources rather than deployed `.agents/skills` copies.
If organization-policy discovery would cause an unwanted login or network lookup in a personal project, explicitly add `--no-policy`; do not make that bypass invisible.

For a project-owned experimental skill, author the canonical tree at `.apm/skills/<name>` and let the root package's `includes: auto` deploy it.
Do not declare that same tree as a local APM dependency.
Promote it to an independently sourced dependency only after another project needs it or it requires its own versioned lifecycle.

Before installation, verify that the skill is self-contained.
Every operating instruction, reference, script, template, and asset needed to use the skill must live inside its skill directory, except for explicitly declared and available tool or package dependencies.
Do not make `SKILL.md` depend on parent project documentation, absolute host paths, or undeclared sibling skills.
Project files may be task inputs, but they are not a substitute for portable skill instructions.
Check links from the canonical tree, deploy with APM, and verify the deployed tree works without reaching back into `.apm/` or elsewhere in the source repository.
Read [references/workflow.md](references/workflow.md) for the boundary and verification checklist.

## Record evidence after real use

Project membership is not usage.
Record a `use` event only after the skill participated in a task:

```console
pixi run workshop use <skill> --task "sanitized task summary" \
  --invocation explicit --outcome success --rating 4 \
  --rationale "Useful because ..." \
  --asserted-kind agent --asserted-by <agent-id>
```

Ratings are cheap contextual observations, not efficacy evidence.
The scale is 1 harmful, 2 unhelpful, 3 mixed, 4 useful, and 5 decisive.
Record enough task, runtime, and project context to interpret the observation without storing secrets or private task content.

Recall the evidence later with:

```console
pixi run workshop show <skill>
pixi run workshop history <skill>
pixi run workshop where-used <skill>
```

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

After opening an issue, pull request, discussion, commit, or release, attach it to the logical skill with `workshop contribution add`.
Record a new event when its observed state changes; do not rewrite the earlier event.

Read [references/workflow.md](references/workflow.md) when choosing between tools or deciding what evidence to record.
