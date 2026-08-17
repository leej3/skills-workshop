# Executive summary: project scope and operating pattern

Decision date: 2026-08-17. This summary condenses the
[project viability decision](project-viability.md) and the supporting
[landscape and standards review](skill-management-landscape.md).

## Decision

Continue the workshop, but pivot it to one narrow job:

> **Two-sided reconciliation for independently editable project skill
> copies.**

The project should not become a general registry, package manager, search
engine, installer, target-path mapper, or governance platform. Existing tools
already cover those jobs, often much more completely. Further feature growth
should pause until a 60-day pilot proves that the reconciliation workflow is
used repeatedly.

See the full [verdict and value proposition](project-viability.md#verdict).

## Why this may still be worth keeping

The intended user is a maintainer who:

- curates skills from several upstream or forked repositories;
- copies selected skills into independent downstream projects;
- expects both source and project copies to change;
- wants an explicit choice between stopping, recording divergence,
  back-propagating the project change, and overwriting the project copy; and
- does not want downstream projects to depend on this workshop or commit its
  coordination lock.

No reviewed manager combines that parent-held, two-baseline model with the
current contribution-back, conservative prune, and verified backup workflow.
The individual mechanisms are not novel; their value is packaging careful Git
and copy discipline into a repeatable skill-aware process.

That value is still hypothetical. The repository currently inventories 216
upstream skills and has 2 bundles with 12 references, but its core profile,
workshop-owned skills, materialization locks, and trust-review ledger are
empty. The implementation has 5,491 Python lines and 98 automated tests. It
has proved implementation care, not workflow demand.

See [Current evidence](project-viability.md#current-evidence) and
[The value that is not already commodity functionality](project-viability.md#the-value-that-is-not-already-commodity-functionality).

## Do not reinvent these capabilities

| Need | Prefer |
| --- | --- |
| Portable skill format | [Agent Skills](https://agentskills.io/specification) |
| Format-conformance differential | Pinned [`skills-ref`](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref) plus explicit workshop policy checks |
| Package manifests, dependency resolution, integrity locks, frozen installs, target deployment, integrity/drift/hidden-Unicode audit, and provenance SBOMs | [Microsoft APM](https://github.com/microsoft/apm) |
| GitHub search, preview, exact pins, updates, and publication | [`gh skill`](https://cli.github.com/manual/gh_skill) |
| Broad source and host support, quick trials, one-way install, and Packs | [Vercel `skills`](https://github.com/vercel-labs/skills) |
| Local management, full-text search, MCP delivery, and its own lint | [SkillPort](https://github.com/gotalab/skillport) |
| Personal canonical store, profiles, symlinks, and TUI | [`skill-manager`](https://github.com/omrikais/skill-manager) |
| GitHub-backed personal inventory, fuzzy TUI with metadata/description preview, and read-only MCP | [`skills-registry`](https://github.com/nikships/skills-registry) |
| Organizational versions, review, RBAC, and audit | [SkillHub](https://github.com/iflytek/skillhub) |

Microsoft APM materially changes the earlier build-versus-adopt decision. It
already implements much of the former roadmap. Its project-local manifest and
lock are preferable when collaborators should reproduce package state from the
downstream repository. The workshop remains relevant only when coordination
must stay in a separate parent and local copies are deliberately editable.

The defaults are not all stable standards: APM is pre-1.0, its policy and
external-scanner features are early preview, OpenAPM is a working draft, `gh
skill` is a public preview, and SkillPort is work in progress. Pin each
integration and keep it replaceable. APM SBOMs are provenance inventories, not
compliance attestations; SkillPort lint is not the exact Agent Skills
conformance oracle.

The recommended hybrid is:

> discover and try with an existing manager → promote only deliberately
> developed skills → reconcile them in the workshop → contribute or publish
> with Git, `gh skill`, APM, or the relevant vendor flow.

See [Adopt, wrap, or build](project-viability.md#adopt-wrap-or-build) and the
full [alternative-tools comparison](skill-management-landscape.md#alternative-approaches-and-existing-tools).

## Scope now

Maintain:

- bundles and exact source identities;
- the small home core profile and existing link reconciliation;
- basic inventory/VisiData views and the hash-bound review ledger, without
  expanding them into search or generic scanning products;
- project import and ordinary copied skill trees;
- source/project baselines, status, diffs, and the four conflict choices;
- conservative prune and verified recovery backups;
- fork/canonical upstream coordination; and
- tests protecting those operations.

Delegate:

- general discovery, search, package resolution, transitive dependencies,
  registries, publication, multi-agent path mapping, SBOMs, generic security
  scans, and one-way installation.

Freeze until a concrete trigger exists:

- tag storage and a tag CLI;
- overlays or patch composition;
- generic provider adapters;
- custom retrieval and ranking;
- broad vendor-target support; and
- the manager skill.

Tags remain a useful concept distinct from bundles, but a new serialization is
not justified by two bundles and no active materializations. Overlays become
worth considering only after the same small, non-upstreamable modification
recurs at least three times across at least two projects. A manager skill
should be a thin interface over stable, tested commands after the pilot, not a
new implementation layer.

See the detailed [feature disposition](project-viability.md#feature-disposition).
The economic test is equally important: workshop engineering competes with
reviewing, evaluating, using, and improving the skills themselves. See the
[opportunity-cost and break-even test](project-viability.md#opportunity-cost-and-break-even-test).

## Decision guide

- Use plain committed copies for a few stable skills with no update workflow.
- Use APM when package intent and a reproducible lock belong in the downstream
  project.
- Use `gh skill` for GitHub-native search, pins, update, and publication.
- Use Vercel `skills` for many sources or agent hosts and for quick trials.
- Use SkillPort for search-first or MCP delivery of a large local inventory.
- Use `skill-manager` for a global canonical store and symlinked profiles, or
  `skills-registry` for a GitHub-backed fuzzy TUI with metadata/description
  preview.
- Use SkillHub for organizational governance.
- Use this workshop only when multiple independently edited projects share a
  source and need parent-held reconciliation and contribution-back.

See [Tool choice by decision criterion](project-viability.md#tool-choice-by-decision-criterion).

## Proof before more development

Run a 60-day pilot. Count only **unique-value events**: deliberate `record` or
`back-propagate` decisions after source/project divergence, both-sides conflict
resolution using separate baselines, or fork/canonical coordination that
produces a submitted upstream pull request or issue-backed patch. Routine
search, install, copy, overwrite, and update do not count.

Continue active development only if the pilot reaches all of these gates:

- two active downstream projects;
- three unique-value events across at least two projects;
- at least one record/back-propagate event;
- at least one submitted upstream pull request or issue-backed patch, or one
  skill change reused in two downstream projects;
- no lost changes and no more than one manual lock repair;
- cumulative operation benefit, including commodity-operation overhead, at
  least twice cumulative maintenance time; and
- every named alternative tested or evidence-backed disqualified, with no
  replacement passing every safety-critical case plus at least six of seven
  residual requirements within one day of removable integration.

Stop conditions take precedence; continue requires every gate; all other
outcomes mean pivot or re-scope. The committed
[pilot ledger](usage-pilot.md) defines the timing, evidence, maintenance-cost
accounting, alternative comparisons, and archive review.

The complete gates, pivot cases, and safe exit path are in the
[60-day proof-of-value pilot](project-viability.md#sixty-day-proof-of-value-pilot).

## Immediate recommendation

1. Keep the version 3 migration and legacy readers as the metadata
   compatibility baseline.
2. Run pinned external conformance checks before the first pilot promotion.
3. Dogfood one complete source → project edit → status/diff → reconcile →
   reapply cycle.
4. Test plain Git, `skill-manager`, ASM, and APM against the same seven residual
   requirements, cheapest and closest first.
5. Run the pilot before implementing tags, overlays, search, target adapters,
   or a manager skill.

This sequence tests the only defensible value proposition before adding more
maintenance surface.
