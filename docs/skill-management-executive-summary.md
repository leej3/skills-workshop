# Executive summary: a recommended skill management pattern

Research snapshot: 2026-08-14. This summary condenses the findings in the
[full landscape and standards report](skill-management-landscape.md).

## Recommendation

Keep this workshop, but define it explicitly as a **curation and development
control plane**, not as a new skill format or a universal installer.

Use a layered pattern:

| Layer | Recommended responsibility |
| --- | --- |
| Portable core | A specification-conformant Agent Skills directory with `SKILL.md` and relative resources |
| Workshop | Upstream forks and pins, inventory, clusters, trust reviews, project locks, reconciliation, and backups |
| Overlay | A small, deterministic workshop-side transformation bound to a base digest |
| Project copy | A complete, ordinary skill tree committed and editable with the project |
| Vendor adapter | One effective copy and optional companion configuration for each intended host |
| Distribution | `gh skill`, Vercel `skills`, or vendor plugins for one-way installation; `gh skill` or vendor packaging for publication |

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
not specify installation roots, locks, profiles, clusters, overlays, trust
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

### Existing managers are complements, not replacements

Two substantial pre-existing efforts should be integrated selectively:

- GitHub CLI's public-preview `gh skill` is strong for GitHub search, preview,
  host-aware install, exact pins, update, format/release checks, and publishing.
  Its checks do not establish that a skill is safe, and refreshes may replace
  local modifications.
- Vercel's `skills` CLI and skills.sh are strong for multi-source discovery,
  many agent destinations, copy or symlink installation, project/global state,
  Packs, advisory audit signals, and convenient one-way updates.

Neither provides the workshop's full two-sided development model: separate
source and project baselines, explicit record/back-propagate/overwrite/abort
choices, fork-to-canonical coordination, hash-bound reviews, clusters, and
verified recovery backups. Use these tools as discovery, import, installation,
or publication adapters. Keep workshop locks authoritative when project copies
are expected to evolve and contribute back.

See
[Alternative approaches and existing tools](skill-management-landscape.md#alternative-approaches-and-existing-tools).

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

1. Add a separate strict `validate-skills` task and portability diagnostics.
   Keep `validate-metadata` focused on workshop contracts.
2. Add the thin manager skill and an evaluation suite with positive and
   negative triggers, with/without-skill baselines, and safe conflict plans.
3. Implement hash-bound, deterministic overlays that render ordinary complete
   skill trees.
4. Add explicit `.agents/skills` and `.claude/skills` target adapters with
   duplicate-root detection.
5. Add optional `gh skill` and/or Vercel `skills` adapters for discovery,
   preview, import, installation, and update. Use `gh skill` or vendor
   packaging for publication.
6. Continue gradual trust review and upstream contribution. Track proposed
   package-lock and OCI standards without adopting an unstable schema.

The detailed sequencing and rationale are in the
[Prioritized implementation roadmap](skill-management-landscape.md#prioritized-implementation-roadmap).
