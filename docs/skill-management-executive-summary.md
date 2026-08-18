# Skill management: landscape and recommendations

## Recommendation

Use the workshop as a thin, Git-backed memory and coordination layer over existing skill tools.
It should remember what those tools do not share across projects: skills considered, alternate sources, decisions, actual use, ratings, evaluations, and upstream contributions.

Do not make the workshop another package manager, public registry, installer, or project lock.
Prefer replaceable integrations, and reduce workshop-owned code whenever an external component can take over without losing portable memory.

## Functional layers

| Need | Current authority | Recommendation |
| --- | --- | --- |
| Portable skill contents | [Agent Skills](https://agentskills.io/specification) | Keep canonical skills conformant; isolate vendor extensions where practical. |
| Skill source and contribution | Git repositories and forks | Develop ordinary skill trees and contribute general improvements upstream. |
| GitHub discovery and publication | [`gh skill`](https://cli.github.com/manual/gh_skill) | Use for search, whole-tree preview, pinned revisions, and publication. |
| Cross-provider discovery | [ASM](https://github.com/luongnv89/asm) | Use its catalog and machine-readable search; do not duplicate the catalog. |
| Broad source and `.well-known` discovery | [Vercel `skills`](https://github.com/vercel-labs/skills) | Use for discovery and trials; let APM own accepted project dependencies. |
| Project reproducibility | [Microsoft APM](https://microsoft.github.io/apm/) | Keep each project's manifest, lock, deployment, update, and audit in that project. |
| Cross-project experience | Workshop memory | Retain only source-agnostic context and evidence missing from the other layers. |
| Human and agent workflow | Workshop CLI and skill | Explain and delegate exact operations through one stable interface. |

The workshop must not be required to reproduce a downstream project.
Conversely, its memory must not pretend it can reconstruct project state when the project's APM manifest and lock are gone.

See the detailed reviews of [existing tools](agents/skill-management-landscape.md#alternative-approaches-and-existing-tools), [emerging discovery and packaging proposals](agents/skill-management-landscape.md#emerging-packaging-and-discovery-proposals), and [vendor compatibility](agents/skill-management-landscape.md#vendor-compatibility).

## What the workshop adds

Public catalogs can find skills and APM can reproduce one project.
Neither answers cross-project questions such as:

- What was the skill I used before, even if I forgot its name or source?
- Which source, mirror, or fork did I consider?
- Was it merely installed, or did it participate in a real task?
- What worked, failed, or warranted an upstream contribution?

The workshop records this as strict, versioned JSON with stable logical skill identities and append-only evidence events.
This is the smallest custom layer that currently appears justified, and its open schema provides an export path to a future community tool.

See [durable metadata and replaceable components](agents/skill-management-landscape.md#durable-metadata-and-replaceable-components).

## Operating recommendations

1. Search workshop memory first, then query external discovery providers.
2. Preview and validate a complete candidate before adopting it.
3. Put project-owned experimental skills under `.apm/skills/`.
4. Put reusable skills in ordinary Git sources and declare them through the downstream project's APM manifest.
5. Record membership separately from actual use, and treat ratings as contextual observations rather than efficacy claims.
6. Use controlled with-skill/without-skill evaluations only for consequential or disputed claims.
7. Prefer an upstream fix, project-local change, or explicit fork before adding an overlay or reconciliation mechanism.

The [current direction](agents/current-direction.md) explains the authority boundaries and near-term experiments.
The [evaluation protocol](agents/evaluation-protocol.md) defines evidence levels beyond ordinary ratings.

## Potential additions

Add capabilities only after real use demonstrates a repeated gap:

- trial SkillNote-like ratings and evaluation interfaces without making a proprietary database authoritative;
- consume the `/.well-known/agent-skills/index.json` draft through existing tools before writing a parser;
- evaluate tags or bundles only after accumulated memory becomes difficult to retrieve by name, description, and evidence;
- revisit overlays or two-way reconciliation only after repeated projects need the same non-upstreamable divergence;
- replace the workshop interface or memory layer when a portable external tool can round-trip its identities, provenance, and evidence.

Detailed assessments and source links live under [`docs/agents/`](agents/).
Those files are working material for agents and maintainers.
Documents promoted into `docs/` should be concise and explicitly human-approved.
