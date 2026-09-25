# Workshop workflow reference

## Authority map

| Concern | Authority |
| --- | --- |
| Cross-project recall, decisions, use, ratings, evaluations, contributions | Workshop memory |
| Project-owned skill source and history | Project `.agents/skills/` and Git |
| External dependencies, exact resolution, target deployment, lock, update, audit | APM |
| GitHub search, preview, source provenance, publication | `gh skill` |
| Cross-provider catalog search and inspection | ASM |
| skills.sh and `.well-known` discovery | Vercel `skills` |
| Skill content and development history | Ordinary Git source or fork |

## User-level control skills

`skills-workshop` may be installed once in an agent's user-level skill directory so agents can invoke the Workshop whenever a request concerns the skill lifecycle.
`workshop-feedback` is the separate global control skill for post-task observations.
These are control-plane exceptions; working skills remain project-owned or project-local dependencies.

Every discovered or created working skill belongs to the active project.
A project-owned experiment lives directly in that project's `.agents/skills/`; an independently maintained reusable dependency is declared, locked, and deployed by APM.
Do not create empty APM state in anticipation of a future promotion.
The Workshop records cross-project recall, consideration, membership, and actual-use evidence, but never substitutes for the project's dependency state.
This keeps a project reproducible without the Workshop and keeps the Workshop from pretending it can recreate a project's dependencies.

## Fresh discovery alongside explicit choices

Keep discovery current: inspect registered-source freshness and search memory, local trees, installed skill roots, and the public providers.
Report worthwhile alternatives with source links and limitations, even when a user names a known skill.

An explicit named installation authorizes installing that choice after preview and compatibility checks.
Alternatives are advisory and must not block it or silently replace it.
For an open-ended request, compare plausible candidates and ask for a selection unless the user has delegated the choice or creation.
Provider failures should be visible and isolated.

Use `workshop recall` for memory-only retrieval and `workshop find --offline` for a local-only search.
Full searches still query public providers, but never send remembered event text or installed file contents as part of their query.

## Project-owned versus reusable skills

Reusable skills are authored in a dedicated skill repository, normally `con/skills`.
Use APM for any selected reusable skill it can manage.
Consumers track `apm.yml`, `apm.lock.yaml`, the pinned APM environment dependency, setup task, targeted ignores, and concise AGENTS.md/README setup guidance.
Ignore package caches and generated deployment paths as part of every downstream installation; never ignore canonical source in its source repository.
`workshop install --apply` adds targeted ignores from the APM deployment ledger automatically.
For direct APM installation, add equivalent entries and verify with `git check-ignore`.
Organization-policy discovery is separate from Git tracking and is not a prerequisite for these ignores.
Run setup before starting the agent so discovery sees installed skills.
Prove restoration and audit from tracked metadata without requiring a Workshop checkout.
Normal downstream updates change pins, hashes, and deployment metadata, keeping skill-development history upstream.
Use the separately distributed `install-apm-skills` workflow when available; explicit authoring for distribution uses `author-apm-skills`.
A generic request to create a skill does not imply APM distribution.


Only for a genuinely project-specific experiment with no intended reusable distribution, start a skill under `.agents/skills/<name>/SKILL.md`.
That tracked tree is both canonical and directly visible to compatible agents; do not duplicate it under `.apm/skills` or list it as a local APM dependency.
This keeps the experiment usable without a bootstrap and avoids pretending it already has an independent package lifecycle.

Promote the skill to an independent Git/APM dependency when another project needs it or it gains an independently versioned lifecycle.
After promotion, the source repository owns the skill and each downstream project pins it through APM.

### Upstream APM packaging gate

A selected reusable source must publish the skill as a valid APM package before any downstream declares it.
Packaging belongs with the reusable source, not as a compensating layer in each consumer.

When a selected source lacks APM packaging:

1. Stop before creating or editing downstream APM state.
2. Add the smallest valid source-owned APM package that publishes the selected skill from its canonical tree.
3. Validate that package by installing it into an isolated temporary consumer, checking the deployed skill, and running `apm audit`.
4. Contribute the packaging to the canonical source.
   Use a maintained fork only when the canonical repository cannot accept the change.
5. Install downstream only from the reviewed APM-ready source and ref.

Do not treat APM's ability to import an arbitrary raw skill subdirectory as a substitute for upstream packaging.
A monorepo package subpath is acceptable only when that subpath is itself an intentional source-owned APM package.

When converting an APM self-deployed project skill, first reconcile the canonical and deployed trees.
Choose the reviewed content, make `.agents/skills/<name>` canonical, and remove the `.apm/skills` source and its local deployment ledger.
If no promoted dependencies remain, remove the APM manifest, lock, bootstrap, and runtime dependency as well.
Do not use `--force` to paper over mixed old/new owners.

Discovery providers never install into APM-managed paths.
The workshop never copies APM's dependency graph or lock.
Deleting the workshop must leave native skills usable and APM dependencies reproducible; deleting project-native and APM state must leave the workshop unable to reconstruct the project.

## Self-contained skill boundary

A skill must remain usable when its directory is copied or deployed without the surrounding source repository.
Keep all required operating knowledge and resources within that directory:

- shared instructions and routing in `SKILL.md`;
- conditional or detailed guidance under `references/`;
- deterministic helpers under `scripts/`;
- output templates and reusable media under `assets/`;
- UI metadata and declared integrations under the skill's supported metadata directories.

The skill may inspect project files, user attachments, repositories, or remote resources as inputs to a task.
It must not rely on them to explain how the skill itself works.
In particular, avoid:

- links from `SKILL.md` to `../../docs`, another project directory, or an absolute host path;
- required guidance stored only beside, rather than inside, the skill;
- undeclared dependencies on sibling skills or host-installed tools;
- scripts, templates, or references present in the canonical project but absent from the deployed skill tree;
- instructions that only work from a particular repository-relative skill location.

Before installation or promotion:

1. Read the full canonical `SKILL.md` and every resource it requires.
2. Resolve each local link from the skill directory and confirm the target remains inside that directory.
3. Validate the canonical tree with the skill validator.
4. For a native project skill, test the tracked `.agents/skills` tree directly.
5. For an external dependency, deploy through APM, compare required resources, and run `apm audit`.
6. Treat missing external context as a realistic portability test: the skill should still provide its method, constraints, and workflow.

This boundary applies equally to project-owned experiments and reusable packages.
Project ownership changes where a skill is versioned, not whether it must be internally complete.

## Evidence levels

1. **Consideration:** why a candidate was adopted, deferred, rejected, or retired.
2. **Membership:** a project tracked a native skill or APM declared or resolved a dependency.
   This does not prove that an agent used it.
3. **Use:** a skill participated in a real task, with sanitized context, invocation mode, outcome, and optional rating.
4. **Assessment:** a reproducible compatibility, trust, license, security, quality, or portability check bound to an exact artifact.
5. **Evaluation:** an explicit protocol comparing conditions and retaining run evidence, grading, metrics, and limitations.

Keep agent assertions unreviewed until a person reviews them.
Do not convert a provider popularity signal or a skill's self-rating into workshop evidence.

## Rating scale

- **1 — harmful:** clearly worsened the task or created unsafe output.
- **2 — unhelpful:** required substantial correction.
- **3 — mixed:** no clear effect or balanced strengths and weaknesses.
- **4 — useful:** improved the task with only minor correction.
- **5 — decisive:** reliably enabled or materially improved the outcome.

The scale ID is `workshop-overall-v1`.
A rationale is required because a number without context is not migratable evidence.

## Evaluation controls

- Use an exact skill artifact in the treatment arm.
- Give conditions the same fixture, model, reasoning effort, tools, permissions, and recorded time, token, or turn budget.
- Isolate contexts so the baseline cannot see treatment output.
- Predeclare task cases, expected behavior, metrics, and direction.
- Prefer blind grading when outputs can be compared without knowing condition.
- Label one treatment/control pair `exploratory`.
- Use `controlled-paired` only when controls and explicit grading are present.
- Use `replicated` only after repeated trials.
- Record failures and limitations; do not retain only favorable runs.

For implicit triggering, evaluate recall in the presence of a realistic set of competing skill descriptions.
Installation alone does not prove discoverability.
