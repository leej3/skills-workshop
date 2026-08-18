# Current direction: memory plus composed tools

Decision date: 2026-08-17.

## Decision

Use existing tools for the jobs they already do well, and keep one small custom layer for information none of them owns across projects.

The workshop is now:

> A Git-backed, tool-neutral memory of skills considered, used, evaluated, and
> improved across projects, plus a transparent interface that teaches and
> invokes the existing tools.

It is not the downstream package manager.
Every project should keep its own reproducible skill intent and resolution in APM.
It is not a public catalog; ASM, `gh skill`, Vercel `skills`, and emerging discovery formats already serve that role.
It is not the canonical skill editor or runtime; skill content stays in ordinary Git.

This supersedes the earlier recommendation to justify the project primarily by parent-held two-sided synchronization.
That mechanism is implemented and well tested, but its demand has not been demonstrated.

## Why the remaining workshop is useful

Package managers and registries know packages.
They generally do not know:

- “I used a skill like this six months ago; where did it come from?”
- which moved source, mirror, or fork is the same logical skill;
- why one candidate was selected and another rejected;
- which projects merely declared a skill versus actually used it;
- what task it helped, under which agent/runtime, and with what outcome;
- whether a 1–5 rating was a casual impression or a controlled evaluation;
- which upstream issue, pull request, or contribution resulted; or
- personal tags and recommendations spanning unrelated sources and managers.

That is durable personal knowledge, not package state.
A logical skill therefore receives an opaque UUID independent of its source.
Source candidates and exact observed artifacts have their own identities.
Moves and forks do not erase history.

The canonical records are strict JSON plus append-only evidence events.
This is less pleasant to hand-edit than prose, but avoids an unstructured notebook that cannot later migrate into a better third-party service.
Humans and agents use the CLI; Markdown, SQLite, embeddings, or a web interface can be generated or replaced without changing the evidence.

## One authority per concern

| Concern | Authority | Workshop behavior |
| --- | --- | --- |
| Skill directory format | [Agent Skills](https://agentskills.io/specification) | Preserve portable `SKILL.md` trees; do not add workshop runtime fields |
| Project dependency intent, exact resolution, lock, targets, deployment, update, and drift | [APM](https://microsoft.github.io/apm/) | Invoke it transparently; store only evidence pointers |
| GitHub search, preview, and publication | [`gh skill`](https://cli.github.com/manual/gh_skill) | Use as a discovery/publication provider |
| Broad cross-provider catalog search | [ASM](https://github.com/luongnv89/asm) | Use machine-readable search; do not let it install into APM paths |
| skills.sh and domain discovery | [Vercel `skills`](https://github.com/vercel-labs/skills) | Use search and its existing `.well-known` consumer |
| Skill body and contribution history | Git source/fork | Record the source; change and contribute there |
| Cross-project experience and judgments | Workshop memory | Own this information because no downstream lock can |

The invariants are:

1. A project remains reproducible if the workshop disappears.
2. The workshop cannot recreate a project after its APM manifest and lock are deleted.
3. Discovery providers never write into APM-managed target paths.
4. Search results are not mirrored into a second public catalog; only deliberate consideration creates durable memory.
5. Every external command, version, working directory, and mutation class is visible before execution.

## APM and ASM together

APM and ASM overlap, so assigning both installation authority would create the very ambiguity this project is meant to prevent.

Use ASM for broad catalog discovery, provider inspection, and optional advisory signals.
Use APM for every accepted downstream dependency.
This preserves ASM's strong human and agent search experience while giving collaborators one project-local `apm.yml` and `apm.lock.yaml`.

This repository now dogfoods that model.
It pins APM 0.28.0 in Pixi, tracks the canonical `skills-workshop` and `commit-provenance` sources, and asks APM to deploy them to `.agents/skills`.
The manifest, lock, and deployed ordinary files are project state; the workshop memory merely records that APM resolved the two skills here.

Both skills are project-owned primitives under `.apm/skills`.
The root manifest's `includes: auto` deploys them without pretending that each experimental tree is already an independent package.
A skill graduates to a Git/APM dependency when another project needs it or it gains an independent versioned lifecycle.

Three APM observations shape the current safeguards:

- policy discovery attempted to inspect `leej3/.github-private`, producing an authentication/scope warning even for this personal repository; the human CLI exposes `--no-policy` only as an explicit choice; and
- `audit --ci` reports a false configuration-consistency failure for the alternative raw local-dependency layout, because it expects a nested `apm.yml`; the adopted root `.apm/skills` layout passes all CI checks; and
- a positional-package `install --dry-run` can say it would add a package, omit that candidate from the displayed plan, and then say it would install no changes.
  The workshop warns on that contradiction and treats the preview as insufficient approval to apply.

Neither justifies a second local lock.
Both reproducible defects have been reported upstream; this repository retains only the operational safeguards, not a parallel issue ledger.

## GitHub and Vercel discovery

`gh skill` is particularly useful for structured GitHub-wide search, repository preview, exact Git provenance, and publication.
It remains public preview and may require GitHub authentication, so its output is a discovery observation, not the workshop's identity or trust decision.

Vercel `skills` provides an independent search index and broad source support.
Its skills.sh model is repository-oriented, which is useful for transport but not sufficient for the source-agnostic memory: a skill may move, be mirrored, or be remembered before its source is known.
The workshop stores that logical continuity; APM records what a particular project accepted.

A bounded three-intent discovery experiment found complementary failure modes: ASM and Vercel produced useful but noisy results, GitHub returned no candidates or a transient provider error, and local memory immediately recovered the one previously encountered skill.
That supports memory-first search, provider isolation, and complete-tree preview; it does not establish a universal ranking of the tools.

The Cloudflare [`/.well-known/agent-skills/index.json` proposal](https://github.com/cloudflare/agent-skills-discovery-rfc) is a promising domain-owned discovery input.
It is still a v0.2 draft with a breaking v0.1 predecessor, but Vercel already consumes it and verifies artifact digests.
Trial it through Vercel rather than writing another parser now.

## SkillNote: useful interface, wrong canonical store for now

[SkillNote](https://github.com/luna-prompts/skillnote) demonstrates several valuable ideas:

- a strong web editor and cross-project browsing interface;
- project collections and live synchronization;
- skill version history;
- usage events, agent comments, and contextual 1–5 ratings; and
- a workflow that asks for feedback while task context is fresh.

Those are worth borrowing or integrating.
Ratings and usage history are especially valuable because a fire-and-forget installer never develops local intuition about what helps.

Making SkillNote the canonical store would currently lose too much:

- its PostgreSQL schema is the authority for skills, versions, ratings, comments, usage, and collections;
- its ZIP export writes current `SKILL.md` files, but there is no documented complete, portable export of the structured history, ratings, provenance, and collection relations;
- ratings are keyed to SkillNote slug/version and use records to SkillNote identifiers, which couples historical interpretation to that service;
- the validator accepts underscores and namespace colons in names, requires a collection, and the renderer adds a nonstandard top-level `collections` array, so “works in SkillNote” is not Agent Skills conformance;
- it imposes a 15-skill collection maximum based on a Claude capacity claim that is not a universal current limit; and
- the local service is a comparatively heavy frontend, API, PostgreSQL, and Docker Compose stack with no authentication by default outside localhost.

The current main branch does contain a Codex adapter and plugin even though the README still says Codex is on the roadmap.
The CLI's user install targets `~/.agents/skills`, while the collection-sync plugin has its own project materialization and hook lifecycle.
That mismatch between shipped code and public guidance deserves a real Codex trial before relying on it.

The appropriate strategy is to retain tool-neutral events now, then build a SkillNote import/export or UI integration only if it can round-trip the workshop IDs and evidence without making its database canonical.
Using its UI today would otherwise risk losing source identity, controlled-evaluation semantics, and portable history when the service is replaced.

## The Claude description-budget claim

SkillNote's README says Claude Code shares roughly 8,000 description characters and that past about 15 skills, skills silently become invisible and forbidden.
That is not a reliable current invariant.

Current Claude Code documentation says skill descriptions receive 1% of the active model context by default, with 8,000 characters as a fallback; the fraction and per-description budget can be configured.
On overflow, less-used descriptions may be omitted while skill names remain available for manual invocation.
`/doctor` and debug logging provide diagnostics, although an ordinary startup warning was removed.
There is no documented universal 15-skill cliff.
See Anthropic's current [environment-variable reference](https://code.claude.com/docs/en/env-vars), [settings reference](https://code.claude.com/docs/en/settings), and [troubleshooting guidance](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short).

The practical lesson survives the correction: keep descriptions concise, scope active skills for relevance, and measure implicit triggering under a realistic competing inventory.
The memory stores observed listing state as `full-description`, `name-only`, `manual-only`, `off`, or `unknown`; it does not encode a hard skill-count cap.

## SkillPort and other managers

Rejecting all of [SkillPort](https://github.com/gotalab/skillport) would be premature.
Its local search and stdio MCP layer can operate over ordinary standard skills without rewriting them.
However, its documented nested `metadata.skillport` arrays, objects, and booleans violate Agent Skills' string-to-string `metadata` rule, and its validator accepts that shape.
It must not be the conformance authority or metadata writer.

There is no reason to normalize canonical skills to SkillPort and strip the metadata on export.
A later bounded trial may use SkillPort read-only over a generated view, with disposable indexes and no metadata mutation, if ASM and simple workshop recall prove insufficient.

`skills-registry` has a good fuzzy personal TUI, but its supported CLI is backed by a GitHub repository and its user-facing MCP service is hosted.
Its server source is not a lightweight supported local-on-demand mode.
Do not adopt it under the current local-service requirement; borrow concepts instead.

SkillHub and MCP Gateway Registry solve organizational governance and gateway problems that are out of scope for one person.
ComeOnOliver/skillshub and other young managers remain observation candidates, not stack dependencies.

## Ratings versus evaluation

Recording an optional rating after real use should be cheap.
It is explicitly observational and requires a rationale:

- 1: harmful or clearly worse;
- 2: unhelpful, substantial correction required;
- 3: mixed or no clear effect;
- 4: useful, minor correction required;
- 5: decisive and reliably helpful.

Important, repeated, or disputed skills can graduate to a paired evaluation.
Two fresh agents receive the same pinned fixture and prompt, one with the exact skill artifact and one without it.
Match model, reasoning effort, tools, permissions, and resource budget; isolate the contexts; predeclare grading and metrics.
One pair remains exploratory.
Controlled and replicated labels require stronger evidence.
See [the evaluation protocol](evaluation-protocol.md).

## What happens to two-way synchronization

The earlier source/project reconciliation implementation is frozen.
Its safety engineering remains useful evidence and its code is not being deleted during this transition, but an unaddressed niche is not automatically a real need.

The simpler operating modes are:

1. **Project is authoritative:** develop the skill in the project, then export a generally useful change to an ordinary Git source and contribute it.
2. **Shared source is authoritative:** develop there, then let APM update each project under its normal lock and drift rules.

Only revisit automatic two-sided reconciliation after repeated real episodes show both sides must evolve independently and continual import/export is materially error-prone.
The same evidence rule applies to generic overlays: first prefer an upstream fix, a fork, or a project-local change.

## Near-term experiments

The implementation is still a `v0` experiment.
The next evidence should come from use, not more infrastructure:

1. Repeat the completed three-intent trial as providers change; remember only deliberately considered candidates.
2. Use APM in this repository and one unrelated downstream project, including frozen replay and ordinary audit.
3. Record actual skill uses, negative outcomes, and ratings from agents without attributing them to the user.
4. Run one exploratory paired evaluation of a consequential skill.
5. Trial one `.well-known` source through Vercel.
6. Decide whether SkillNote's UI merits an export-safe integration only after the Git-native memory has real data to round-trip.
7. Promote the memory schema to `v1` only after a second project exposes the mistakes in `v0`.
