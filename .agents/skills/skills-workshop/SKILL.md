---
name: skills-workshop
description: Coordinate systematic agent-skill discovery, self-contained project skill creation, project installation, cross-project recall, use tracking, evaluation, and upstream contribution. Use when asked to find or compare skills, create or manage a project's skills, install or audit skills with APM, remember a skill or source, record outcomes or ratings, see where a skill was used, or test whether a skill helps. This skill keeps workshop memory separate from project-local APM state and delegates public discovery to ASM, GitHub gh skill, and Vercel skills.
---

# Skills Workshop

Use the workshop as a source-agnostic memory and a transparent interface to existing tools.
Do not turn it into another installer, registry, or project lock.

## Scope and bootstrap

This is the one user-level control skill for the skill lifecycle.
When an agent is asked to find, create, install, audit, record, or evaluate a skill, it should invoke this skill first.
That does not make discovered skills user-global: install every selected skill into the active project through its APM state, then record the relationship and any later real use in workshop memory.
A project's reproducible skill set must remain usable if this user-level control skill or the workshop checkout is unavailable.

## Start here

Run commands from the workshop checkout:

```console
pixi run workshop doctor
pixi run workshop validate
```

The doctor names each external tool, its pinned version, and its authority.
Every delegated command is printed before execution.

## Find and consider a skill

Search remembered skills and the locally tracked upstream inventory first.
The local phase searches every source registered in `registry.toml` (including K-Dense `scientific-agent-skills` and `con/skills`) and reports its pinned revision, so it covers new registered sources without a workflow change:

```console
pixi run workshop find "capability or remembered task"
```

For a freshness-sensitive choice, first refresh the registered upstream status and review the update plan.
Updating a source is explicit; it never happens as a side effect of search:

```console
pixi run upstream-status --fetch
pixi run upstream-update <registered-source>
```

Apply a reviewed update only with `pixi run upstream-update <registered-source> --apply`, then commit the resulting Workshop gitlink change before relying on that revision.

Then query the existing discovery providers.
The default order keeps remembered and local community sources first, but still returns public candidates that may be worth considering or improving upstream:

```console
pixi run workshop find "capability"
```

Use `--provider` only to narrow or compose a specialized search.

### Human decision gate

When the user asks for a skill to provide a capability, discovery is a separate decision phase.
Do not create, install, adopt, or record a candidate in the same turn unless the user already selected an exact skill or explicitly asked to skip discovery.

After searching:

1. Present a concise shortlist of plausible matches.
   For each, state its name, relevant capability, important limitation or difference, and a link to its canonical source.
   Use a clickable local path when the canonical source is local and a canonical web URL when it is remote.
2. If no candidate is a good fit, say which sources were searched and propose creating a new project-owned skill.
   If partial matches exist, explain why a new skill or adaptation may still be preferable.
3. Ask the user to choose among adopting a candidate, adapting one, creating a new skill, or stopping.
   End the turn and wait for that human decision.

Do not treat the original capability request as approval of the agent's later selection or creation proposal.
Do not scaffold files, change APM state, or record an adoption decision while waiting.
A later user choice supplies the authority to proceed with the selected path.

Inspect a GitHub candidate's complete tree without installing it:

```console
pixi run workshop preview <owner/repository> <skill-or-path@commit>
```

Do not install with ASM, `gh skill`, or Vercel `skills` when APM manages the project.
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

After opening an externally useful issue, pull request, discussion, or release, attach it to the logical skill with `workshop contribution add`.
Do not add self-referential records for routine Workshop commits or memory bookkeeping.
Record a new event when its observed state changes; do not rewrite the earlier event.

Read [references/workflow.md](references/workflow.md) when choosing between tools or deciding what evidence to record.
