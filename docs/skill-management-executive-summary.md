# Executive summary: a recommended skill management pattern

Original research snapshot: 2026-08-14; ecosystem discovery expanded
2026-08-17. This summary condenses the findings in the
[full landscape and standards report](skill-management-landscape.md).

## Recommendation

Keep this workshop, but define it explicitly as a **curation and development
control plane**, not as a new skill format or a universal installer.

Make **reuse before invention** a governing rule. Prefer accepted standards,
and follow credible emerging specifications through versioned adapters rather
than creating a competing format while consensus is still forming. Existing
open registries, resolvers, search engines, and installers should be pluggable
components; none should own the durable workshop record.

Use a layered pattern:

| Layer | Recommended responsibility |
| --- | --- |
| Portable core | A specification-conformant Agent Skills directory with `SKILL.md` and relative resources |
| Workshop curation | Upstream forks and pins, tags, bundles, profiles, trust reviews, project locks, reconciliation, and backups |
| Provider observation | Namespaced, timestamped source metadata, audit signals, and rankings retained without becoming canonical facts |
| Derived index | Rebuildable fuzzy, full-text, semantic, or provider-backed search data and generated task examples |
| Overlay | A small, deterministic workshop-side transformation bound to a base digest |
| Project copy | A complete, ordinary skill tree committed and editable with the project |
| Adapter | Replaceable discovery, registry, search, installation, publication, and vendor-materialization integrations |

This preserves the current design's most important property: a downstream
project can use and develop its copied skills without installing the workshop,
while the workshop retains enough information to reconcile deliberate changes
later.

See [Recommended operating pattern](skill-management-landscape.md#recommended-operating-pattern)
for the full model and
[Decision rules](skill-management-landscape.md#decision-rules) for concrete
choices.

## Principal findings

### The workshop complements the standard

The Agent Skills standard specifies the contents of a skill directory. It does
not specify installation roots, locks, profiles, bundles, overlays, trust
reviews, upstream contribution, reconciliation, or backups. The workshop's
metadata is therefore a legitimate higher-level extension because it remains
outside materialized skill directories.

The main deviation is validation. The workshop copies ordinary skill trees,
but its validators do not yet parse complete YAML frontmatter or enforce the
full `name`, `description`, directory-name, and optional-field contracts. A
pinned reference-validator pass returned no problems for all 161 K-Dense
skills, but only 22 of 42 NiPreps skills and 3 of 13 CON skills in the assessed
snapshot. The reference implementation is demonstrational and not a complete
conformance oracle, but the result exposes useful vendor-specific activation
fields that are outside the shared format.

See [Standards alignment](skill-management-landscape.md#standards-alignment)
and
[Current catalog portability](skill-management-landscape.md#current-catalog-portability).

The upstreams offer different models worth preserving: K-Dense for structural
validation and CI, NiPreps for reproducible domain practice and manual
evidence, and CON for focused maintenance workflows that benefit from added
workshop governance. See
[Lessons from the pinned upstreams](skill-management-landscape.md#lessons-from-the-pinned-upstreams).

### Existing systems are components, not authorities

The expanded review found several substantial pre-existing efforts that should
be evaluated as components:

- GitHub CLI's public-preview `gh skill` is strong for GitHub search, preview,
  host-aware install, exact pins, update, format/release checks, and publishing.
  Its checks do not establish that a skill is safe, and refreshes may replace
  local modifications.
- Vercel's `skills` CLI and skills.sh are strong for multi-source discovery,
  many agent destinations, copy or symlink installation, project/global state,
  Packs, advisory audit signals, and convenient one-way updates.
- MIT-licensed SkillPort already provides validation, lifecycle commands,
  full-text search, metadata operations, and MCP search/load tools. Reuse those
  interfaces, but do not copy its nested tag arrays into portable `SKILL.md`
  metadata because the current specification permits only string values.
- Apache-2.0 `skills-registry` already provides a personal GitHub-backed
  registry, fuzzy TUI, live preview, synchronization, and MCP search/read
  tools.
- Apache-2.0 SkillHub provides a self-hosted organizational registry with
  versions, filtered full-text search, namespaces, review, RBAC, and audit
  logs.
- MIT-licensed SkillsHub provides a task resolver, BM25-based ranking, and
  keyword-generated tags over a large aggregated catalog. SkillNote, SkillsGo,
  and the MCP Gateway & Registry cover additional self-hosted, desktop,
  protocol, and governed discovery patterns.
- SkillCorpus is directly relevant retrieval-and-evaluation research, although
  its implementation and data are not yet released.

No one system needs to provide the workshop's full two-sided development
model. Use each for the part it implements well, while retaining separate
source and project baselines, explicit conflict choices, fork-to-canonical
coordination, hash-bound reviews, bundles, and verified recovery backups in
portable workshop state.

See
[Alternative approaches and existing tools](skill-management-landscape.md#alternative-approaches-and-existing-tools).

### Durable metadata enables replacement

Keep canonical skill artifacts and workshop curation separate from provider
observations and derived indexes. A GitHub star count, Vercel rank, registry
rating, automated audit, and workshop human review are different claims with
different issuers and timestamps; they must not collapse into one provider-
defined quality field.

Tags are many-to-many descriptive facets and have no installation effect.
Bundles are many-to-many curated selections applied explicitly to projects.
Generated aliases, embeddings, hypothetical task descriptions, and search
scores belong in rebuildable indexes rather than canonical tags.

Do not invent a workshop tag format. The current Agent Skills specification
has no tag field and restricts `SKILL.md` metadata to string values. Follow the
logical contract in emerging packaging discussion #302 instead: keep zero to
eight lowercase tags outside the skill tree and associate them with exact
skill identity; record each observed version with a PURL and content hash when
possible. Because that early proposal intentionally leaves serialization open,
use a small, versioned `metadata/tags.yaml` sidecar in the interim. Retain
provider labels and auto-tags as namespaced observations, keep the temporary
format losslessly exportable, and migrate at the earliest opportunity to an
accepted replacement.

Define stable adapter contracts for discovery, immutable fetch, inspection,
index construction, and ranked search. Require source identity, revision,
provider, retrieval method, evidence, and observation time in results. Then
fuzzy search, `skills-registry`, GitHub, Vercel, SkillHub, SkillsHub, or a local
hybrid index can be compared and replaced without rewriting workshop metadata.

See
[Durable metadata and replaceable components](skill-management-landscape.md#durable-metadata-and-replaceable-components)
and [Tags, bundles, and profiles](skill-management-landscape.md#tags-bundles-and-profiles).

### Overlays belong in the control plane

The Agent Skills format defines no overlay mechanism, and its client guide
treats same-name skills as collisions resolved through precedence. Portable
tooling must not assume that installing two same-name skills composes them.

The recommended overlay is a reproducible build:

> pinned base tree + ordered, hash-bound overlay inputs -> validated complete
> skill tree

Keep the base, overlay metadata, and rendered digest in the workshop. Apply
changes in staging, fail on a stale base or conflict, show the composed diff,
and materialize only the complete result. Begin with append or managed-section
replacement and explicit file add/delete operations; avoid semantic Markdown
merging. Contribute general corrections upstream, use overlays for genuinely
small project/vendor adaptations, and use a fork for large independent
changes.

See [Overlays](skill-management-landscape.md#overlays) and the
[Recommended overlay contract](skill-management-landscape.md#recommended-overlay-contract).

### Format portability is not behavioral portability

`.agents/skills` is the broadest common location among the clients reviewed:
Codex, GitHub Copilot, Gemini CLI, Cursor, and OpenCode. Claude Code remains the
notable exception and uses `.claude/skills`. Vendors also differ in
duplicate-name precedence, symlink support, activation fields, tool
permissions, package availability, network access, and invocation UI.

Maintain a conservative portable core with standard frontmatter and relative
resources. Put vendor-specific behavior in companion files or rendered
adapters, ensure each host sees exactly one effective copy, describe
environment and tool requirements in `compatibility`, and test every host for
which behavioral compatibility is claimed. Do not treat `allowed-tools` as a
portable security boundary.

See [Vendor compatibility](skill-management-landscape.md#vendor-compatibility)
and
[Portable core and vendor adapters](skill-management-landscape.md#portable-core-and-vendor-adapters).

### The manager should be a skill over tested code

The workshop has 85 deterministic management tests but no standard skill that
teaches an agent to operate the workflow, and it does not yet test whether the
managed skills improve real tasks.

Create a small `skills-workshop-manager` skill as a procedural interface over
the existing commands. It should route inventory, trust, import, status,
preview, overlay, upstream, and conflict tasks; default to read-only inspection;
and request a clear policy choice before mutation. The Python implementation,
not prose, must remain responsible for paths, locks, atomicity, backups, and
destructive actions.

Test four layers independently: format conformance, management correctness,
agent behavior on realistic prompts, and claimed-host compatibility. Keep
direct Pixi commands as a bootstrapping and recovery path.

See [A tested manager skill](skill-management-landscape.md#a-tested-manager-skill).

## Recommended next steps

1. Create a machine-readable ecosystem candidate inventory and record the
   reproducible discovery method, review state, evidence, and rejection reason.
2. Define the minimal provider-neutral skill record, namespaced observation
   model, bundle contract, and adapter interfaces. Adopt discussion #302's
   external, lowercase, maximum-eight tag semantics provisionally. Implement a
   tracked, versioned `metadata/tags.yaml` sidecar with validation, inventory
   joins, minimal list/add/remove commands, and tests. Preserve provider tags
   and labels losslessly without promoting them automatically, and migrate the
   sidecar to the earliest suitable standard format.
3. Build a versioned relevance set of realistic requests. Compare exact,
   fuzzy, full-text, semantic, hypothetical-description, and external-provider
   retrieval before selecting a default backend.
4. Add a separate strict `validate-skills` task and portability diagnostics.
   Keep `validate-metadata` focused on workshop contracts.
5. Add the thin manager skill and an evaluation suite with positive and
   negative triggers, with/without-skill baselines, and safe conflict plans.
6. Implement hash-bound, deterministic overlays that render ordinary complete
   skill trees, but first recheck emerging overlay and packaging proposals.
7. Add explicit `.agents/skills` and `.claude/skills` target adapters with
   duplicate-root detection.
8. Implement discovery and registry integrations only as contract-tested
   adapters. Begin with `gh skill`, Vercel `skills`, and one open self-hosted or
   personal registry; preserve workshop artifacts and locks as the authority.
9. Continue gradual trust review and upstream contribution, and monitor
   emerging packaging, PURL, `.well-known` discovery, OCI, and MCP work through
   dated compatibility notes and experimental adapters rather than competing
   formats.

The detailed sequencing and rationale are in the
[Prioritized implementation roadmap](skill-management-landscape.md#prioritized-implementation-roadmap).
