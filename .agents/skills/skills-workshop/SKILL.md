---
name: skills-workshop
description: Coordinate systematic agent-skill discovery, native project skill creation, reusable dependency installation, cross-project recall, use tracking, evaluation, and upstream contribution. Use when asked to find or compare skills, create or manage a project's skills, install or audit reusable skills with APM, remember a skill or source, record outcomes or ratings, see where a skill was used, or test whether a skill helps. This skill keeps workshop memory separate from project-native and project-local APM state and delegates public discovery to ASM, GitHub gh skill, and Vercel skills.
---

# Skills Workshop

Use the workshop as a source-agnostic memory and a transparent interface to existing tools.
Do not turn it into another installer, registry, or project lock.

## Scope and bootstrap

This is the one user-level control skill for the skill lifecycle.
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

For any request to find, create, choose, or install a skill, the first outcome is a discovery consultation, not a filesystem or dependency change.
The user must make a separate choice after seeing the current alternatives.
A request such as "install X" or "I want a skill for Y" does not waive this consultation merely because it names a known skill.
Proceed immediately only when the user explicitly says to skip comparison or confirms a choice from a consultation.

## Find and consider a skill

Search remembered skills and the locally tracked upstream inventory first.
The local phase searches every source registered in `registry.toml` (including K-Dense `scientific-agent-skills` and `con/skills`) and reports its pinned revision, so it covers new registered sources without a workflow change:

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
Do not let a previously remembered or named skill short-circuit the broader search: newer alternatives are part of the consultation.

### Human decision gate

When the user asks about, requests, names, creates, or proposes installing a skill, discovery is a separate decision phase.
Do not create, scaffold, adapt, install, adopt, or record a candidate in that turn unless the user explicitly asked to skip consultation or is confirming a choice from an earlier consultation.
Naming an exact skill is not by itself confirmation because newer alternatives may now be available.

After searching:

1. Summarize which configured sources were searched, their freshness or pinned state, and any source that was unavailable.
2. Present a concise shortlist of plausible matches across those sources.
   For each, state its name, source, relevant capability, important limitation or difference, and a link to its canonical source.
   Use a clickable local path when the canonical source is local and a canonical web URL when it is remote.
3. Always include creating a new project-owned skill as an explicit option, even when matches exist.
   Explain when adapting a candidate may be preferable to either installing it unchanged or starting over.
4. Give a recommendation with its tradeoffs, while keeping the choice with the user.
5. Ask the user to choose among adopting a candidate, adapting one, creating a new skill, broadening or refreshing the search, or stopping.
   End the turn and wait for that human decision.

Do not treat the original capability request as approval of the agent's later selection or creation proposal.
Do not scaffold files, change APM state, or record an adoption decision while waiting.
A later user choice supplies the authority to proceed with the selected path.

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
It does not own project-authored skills that live directly under `.agents/skills/`.
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

For a project-owned experimental skill, author the canonical tree directly at `.agents/skills/<name>`.
Do not copy it into `.apm/skills` or declare it as a local APM dependency.
The project may expose an agent-agnostic bootstrap such as `pixi run agent-deps-bootstrap` for external dependencies; project-owned skills must remain available before that bootstrap runs.
Promote it to an independently sourced dependency only after another project needs it or it requires its own versioned lifecycle.

Before installation, verify that the skill is self-contained.
Every operating instruction, reference, script, template, and asset needed to use the skill must live inside its skill directory, except for explicitly declared and available tool or package dependencies.
Do not make `SKILL.md` depend on parent project documentation, absolute host paths, or undeclared sibling skills.
Project files may be task inputs, but they are not a substitute for portable skill instructions.
Check links from the canonical tree and verify it works without reaching outside its own skill directory for operating instructions or resources.
For an external dependency, also verify its APM deployment.
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
