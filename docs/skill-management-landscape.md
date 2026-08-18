# Skill management landscape and standards comparison

> **Research ledger, not current operating policy.** Tool observations remain
> useful, but the reconciliation-first recommendations in this dated review
> are superseded by [the current direction](current-direction.md) and its
> [executive summary](skill-management-executive-summary.md).

Original research snapshot: 2026-08-14; ecosystem discovery expanded
2026-08-17. The implementation stocktake was updated on the workshop branch
after commit `c042277`, including the materialization-lock compatibility fix.
The Agent Skills repository was assessed at commit
[`69ef37e`](https://github.com/agentskills/agentskills/commit/69ef37e9424c0a7ea9dd2293b559e43ec8176379).
The standard currently has no tagged release, so claims in this report should
be rechecked as its documentation and client implementations evolve.
Source-code links are pinned where implementation details matter; product
documentation otherwise reflects the research date.

## Research status and maintenance method

The original pass was deep but targeted: it began with the three supplied
upstreams, the Agent Skills specification, major vendor clients, GitHub CLI,
and Vercel `skills`. It did not record reproducible ecosystem searches or an
inclusion ledger. Consequently, its earlier phrase "among the tools reviewed"
must not be read as an exhaustive market claim. Community registries,
resolvers, and retrieval research were materially underrepresented.

This report is a **dated decision ledger**, not a claim of completeness. A new
feature proposal or pilot review may trigger another bounded landscape pass;
that pass should record:

1. exact queries, dates, result sources, and pagination limits;
2. candidate projects, canonical repository, forks, aliases, and review state;
3. reasons for inclusion, exclusion, or deferred review;
4. license, governance, self-hostability, export path, telemetry, and hosted
   dependencies;
5. artifact identity, metadata model, search method, install/update behavior,
   local-edit handling, and supported clients;
6. release maturity, maintenance activity, tests, and evidence for important
   claims.

Candidate discovery must cover GitHub repository, code, and topic searches for
synonyms including `agent skills`, `skill registry`, `skills hub`, `catalog`,
`resolver`, `marketplace`, `package manager`, `corpus`, and `MCP registry`;
language package indexes; Agent Skills issues and discussions; vendor
directories; research indexes; and references or competitors named by each
candidate. Discovery and in-depth review are separate states so an immature or
unreviewed project remains visible without being endorsed.

The 2026-08-17 expansion searched combinations of `agent skills registry`,
`SKILL.md search`, `semantic skill search`, `skill resolver`, and `MCP skill
registry`; inspected the GitHub topics
[`skill-registry`](https://github.com/topics/skill-registry),
[`agent-skills`](https://github.com/topics/agent-skills),
[`ai-agent-skills`](https://github.com/topics/ai-agent-skills), and
[`agentskills`](https://github.com/topics/agentskills); followed references
from the Agent Skills repository; searched recent papers; and then reviewed
the primary repositories or documentation for the systems included below.
This substantially broadened candidate generation, but it is still a bounded
pass rather than proof that every project was found.

A follow-up reuse review also compared the Agent Skills package-manifest,
recipe, OCI, and `.well-known` discovery proposals with the metadata and
grouping models used by SkillPort, SkillHub, SkillsHub, and SkillNote. That
review supplies the provisional tag decision below; it does not promote any
single draft or registry into an accepted standard.

The prose snapshot is sufficient as a dated decision ledger for now. A
machine-readable candidate inventory would add another maintained product
surface and should be created only after several active integrations make
manual cross-checking unreliable or automation is actually required.

## Standards and reuse policy

Use the following preference order for every new capability:

1. an accepted, openly documented standard with independent implementations;
2. an official or credible emerging proposal that can be pinned and tested;
3. an open de facto convention already implemented by several clients;
4. an existing open component through a pinned, removable integration;
5. only then, the smallest workshop-specific extension needed to preserve the
   missing lifecycle behavior.

"Emerging" does not mean "copy the latest draft into canonical state." Record
the proposal URL and revision, preserve its native fields, isolate the
experiment from canonical state, add conformance fixtures, and retain an
export path. Extract a common adapter interface only after two real
integrations duplicate a stable contract. If a proposal changes or loses
adoption, remove its integration without rewriting skill identities, tags,
bundles, reviews, or project baselines.

Before implementing a new subsystem, its design note should name the open
alternatives examined and explain the residual gap. Favor upstream
contribution, protocol compatibility, and thin removable integrations over
local forks.
Hosted services may be useful providers, but an undocumented API, unavailable
export, proprietary identity, or mandatory hosted state disqualifies one from
being the workshop's authority.

## Scope and central finding

The workshop and the [Agent Skills standard](https://agentskills.io/home)
operate at different layers:

- the standard defines the portable **skill artifact**: a directory containing
  `SKILL.md` and optional resources;
- this workshop is a **lifecycle control plane** around those artifacts: it
  discovers upstreams, groups skills, records provenance and review state,
  materializes copies, detects two-sided changes, reconciles them, and keeps
  recovery backups;
- each agent product is a **runtime/client, and sometimes an installer**, that
  decides where to discover skills, how to activate them, and what tools or
  execution environment they receive.

Most workshop metadata is therefore an extension outside the standard, not a
competing format. Bundles, locks, trust reviews, and backups remain in this
repository, while downstream projects receive ordinary skill directories.
Tags and broader profiles are still design concepts rather than implemented
state. That boundary is sound. The principal standards gap is that the
workshop currently does not fully validate the ordinary skill directories it
manages.

The defining architectural rule is **reuse before invention**. Accepted
standards are preferred, but credible emerging specifications are also better
alignment targets than an unnecessary workshop-specific alternative. Because
drafts can still change or compete, they should first be tested through pinned,
removable experiments with lossless source metadata and an explicit exit path.
Extract an adapter only after two integrations reveal a stable shared
contract. The workshop should implement only the durable coordination behavior
not already supplied by an open component.

The viability conclusion is narrower than the architectural possibility. The
workshop is conditionally worth maintaining for parent-held, two-sided
reconciliation of independently editable project copies. It is not justified
as a general skill platform. The [project viability decision](project-viability.md)
defines the current promotion boundary, adoption defaults, 60-day pilot, and
stop criteria.

## Standards alignment

### What the standard defines

The [format specification](https://agentskills.io/specification) requires a
skill directory with a `SKILL.md` containing valid YAML frontmatter followed by
Markdown instructions. Its required fields are:

- `name`: 1 to 64 lowercase letters, numbers, and hyphens; no leading, trailing,
  or consecutive hyphens; it must match the parent directory name;
- `description`: 1 to 1,024 characters explaining both what the skill does and
  when it should be used.

Standard optional fields are `license`, `compatibility`, a string-to-string
`metadata` map, and the experimental `allowed-tools` string. Conventional
resource directories are `scripts/`, `references/`, and `assets/`, although
other files and directories are allowed. File references are relative to the
skill root. Shallow reference chains, a concise `SKILL.md`, and moving detailed
material into on-demand resources are recommendations supporting the
progressive-disclosure loading model.

The current specification does **not** mandate installation roots and does not
define package registries, package versioning or version selection, dependency
resolution, profiles, tags, bundles, overlays, trust-review records, conflict
resolution, or backups. Its
[client implementation guide](https://agentskills.io/client-implementation/adding-skills-support)
describes `.agents/skills` as a widely adopted interoperability convention,
not a normative location.

### Conformance and extension table

| Area | Agent Skills requirement or guidance | Workshop behavior | Assessment |
| --- | --- | --- | --- |
| Artifact | Directory containing `SKILL.md` | Copies complete skill directories | Aligned |
| Project location | Not standardized; `.agents/skills` is recommended for interoperability | Materializes into `.agents/skills` | Good convention, not universal |
| Frontmatter | Valid YAML with opening and closing delimiters | Extracts a simple `name:` line | Conformance gap |
| `description` | Required, nonempty, at most 1,024 characters | Not parsed or validated | Conformance gap |
| `name` | Exact syntax, no trailing or consecutive hyphens | Current regular expression permits both and accepts ASCII only | Looser about hyphens and narrower than the pinned reference implementation about non-ASCII names |
| Directory identity | Parent directory must match `name` | Manifest name must match declared name, but the source directory basename need not match | Conformance gap |
| Optional fields | Defined types and limits | Preserved but not validated or inventoried | Conformance gap |
| Body and resources | Markdown plus optional relative resources | Complete tree is copied | Aligned |
| Nested symlinks | No portable semantics specified | Refused during materialization | Deliberate safety restriction |
| Core-profile links | Client-specific | Top-level directory symlinks into `~/.agents/skills` | Useful local extension; test per client |
| Progressive disclosure | Runtime loads metadata, then instructions, then resources | Delegated to the agent runtime | Appropriate; workshop is not a client |
| Collisions | Client should behave deterministically | Bundle duplicate install names are refused | Appropriate manager policy |
| Trust | Client guide recommends considering a trust gate | Hash-bound advisory review ledger | Strong extension; not an enforcement gate |
| Distribution and version resolution | Out of scope | Forks, submodules, remotes, revisions, and update plans | Workshop extension |
| Selection and grouping | Out of scope | Core profile and bundles implemented; tags and broader profiles are design concepts | Workshop extension with evidence-gated additions |
| Reconciliation | Out of scope | Two baselines and four explicit conflict policies | Workshop extension |
| Recovery | Out of scope | Verified content-addressed backups with explicit 30-day cleanup | Workshop extension |
| Overlays | No accepted mechanism | Not implemented | Evidence-gated design only |

Profiles and bundles select sets of independent skills; they are not runtime
skill composition. Tags are nonexclusive discovery facets and do not select or
install anything by themselves. Skill-to-skill dependency and invocation
semantics are also not standardized.

The distinction between `validate-metadata` and skill validation matters.
[`validate_metadata.py`](../scripts/validate_metadata.py) protects bundle,
lock, and trust contracts used by workshop operations. It is not a complete
Agent Skills validator. Likewise, the runtime checks in
[`manage_skills.py`](../scripts/manage_skills.py) are intentionally focused on
safe paths, names, real directories, and stable content before destructive
operations.

### Current catalog portability

A research pass using the pinned official reference validator over the 216
upstream skills produced this result. The method discovered each upstream
`SKILL.md`, ran `skills-ref validate <skill-directory>` from the reference
checkout named above, and counted runs that returned no problems.

| Collection | Pinned `skills-ref` passes | Total | Main source of failures |
| --- | ---: | ---: | --- |
| K-Dense scientific skills | 161 | 161 | None in this snapshot |
| NiPreps skills-comm | 22 | 42 | Nonstandard vendor activation fields and some strict-YAML values |
| CON skills | 3 | 13 | Mainly `user-invocable`; one missing required `name` |

The official [`skills-ref`](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref)
README explicitly calls the library demonstrational rather than production
ready. It also does not enforce every detail of the written specification.
These counts should therefore be treated as a pinned compatibility
measurement, not an infallible conformance judgment. They nevertheless expose
a real difference between “loads in a particular client” and “returns no
problems from the pinned reference checks.”

The issue reaches the current bundles. Their selected NiPreps and CON skills
use nonstandard activation keys such as `argument-hint`, `user-invocable`, and
`disable-model-invocation`, and comma-delimited `allowed-tools` values. These
may be meaningful to particular clients, but the shared format does not define
the activation keys and defines `allowed-tools` as an experimental
space-separated string.

Portability should consequently be reported in three separate dimensions:

1. **Format portability:** a specification-conformant `SKILL.md` and resource
   tree.
2. **Discovery portability:** whether the host scans the chosen location and
   supports the chosen link or copy method.
3. **Behavioral portability:** whether tools, dependencies, permissions,
   network access, invocation behavior, and runtime semantics are available.

A skill can pass the first test and fail the other two.

## Tags, bundles, and profiles

The organization model distinguishes descriptive metadata from curated
selection:

| Concept | Cardinality | Meaning | Installation effect |
| --- | --- | --- | --- |
| Tag | A skill has zero or more; a tag applies to zero or more skills | Stable descriptive or operational facet used for filtering and retrieval | None |
| Bundle | A skill belongs to zero or more; a bundle contains zero or more skills | Named, curated selection intended to be reused or materialized together | Selects its members when explicitly applied |
| Profile | A named host or project policy | Chooses default bundles, individual skills, targets, or policy settings | Applies only through an explicit profile operation |

Tags should describe durable facts or intentional local curation, such as a
domain, task family, required runtime, maturity state, or reviewed
compatibility. Provider-supplied tags must retain their namespace and source.
Generated aliases, hypothetical task descriptions, embeddings, popularity,
and search scores are rebuildable index observations rather than canonical
tags.

The current Agent Skills specification has no tag field, and its optional
`metadata` field is strictly a string-to-string map. Arrays or nested tag maps
inside `SKILL.md` are therefore not a portable solution. The closest reusable
contract found is
[packaging discussion #302](https://github.com/agentskills/agentskills/discussions/302).
It defines one external recipe per skill, optional free-form lowercase tags
with at most eight entries, and version records containing a Package URL (PURL)
and required SHA-256 content hash. It explicitly leaves TOML, JSON, or YAML
serialization as a separate decision. It is an early community discussion,
not a ratified specification or independently implemented contract, so this is
an alignment hedge rather than a production dependency.

If real usage requires curated tags, the workshop should align with that
**logical contract**, not invent another serialization:

- keep zero to eight lowercase curation tags outside the portable skill tree;
- associate them with the stable workshop skill identity, and retain the PURL
  and content hash of each observed version when they can be expressed;
- preserve provider-native tags, labels, and categories under their provider
  namespace with evidence and an observation time;
- require explicit promotion before a provider observation becomes a workshop
  curation tag;
- prefer an accepted recipe or an existing manager's exportable representation
  when one is available; and
- use a minimal, losslessly exportable sidecar only if the pilot demonstrates
  a concrete need before a shared format stabilizes.

Tag persistence is intentionally not implemented. With two bundles and no
tracked materializations, names, descriptions, and bundle membership have not
yet proved insufficient. The tag vocabulary remains useful, but a sidecar,
schema, and CLI are evidence-gated rather than the next automatic feature.

| Existing model | Where grouping lives | Compatibility finding | Workshop treatment |
| --- | --- | --- | --- |
| Agent Skills specification | `SKILL.md` string-map `metadata` | No standard tag field or nested values | Keep curation tags external |
| Packaging discussion #302 | External recipe | Lowercase free-form tags, maximum eight; PURL and SHA-256 bind versions | Provisional logical contract and future adapter target |
| SkillPort | Nested `metadata.skillport` category and tag arrays | Useful management API, but the nested values do not conform to the current standard's string map | Import as namespaced observations, not portable frontmatter |
| SkillHub | Registry-managed labels | Useful organizational facets tied to one registry | Preserve issuer and timestamp; promote explicitly |
| SkillsHub | Catalog tags, including keyword-generated tags | Useful search fields, not curated local facts | Store as provider or derived-index observations |
| SkillNote | Nonstandard `collections` frontmatter | Bundle-like project scoping that is not portable Agent Skills metadata | Treat as a provider extension and map only through an adapter |

A bundle is a selection, not a packaging format. It may later export to a
Vercel Pack, vendor plugin, registry collection, or an emerging standard
manifest, but none of those provider formats should become the internal source
of truth. Bundle membership remains many-to-many so one skill can participate
in several project workflows without being copied in the workshop.

Bundle manifests live in `bundles/*.toml`; materialization locks and the
`apply-bundle` command use the same identity. The
[feature disposition](project-viability.md#feature-disposition) defines the
trigger that would justify tag persistence.

## Lessons from the pinned upstreams

The three upstreams are complementary rather than interchangeable models.

### K-Dense scientific-agent-skills

The pinned [K-Dense collection](https://github.com/K-Dense-AI/scientific-agent-skills/tree/13385c7c4db02fdcc84a020752c07cce91ef780e)
has the strongest portable-format and repository-quality model of the three.
Its
[contribution guide](https://github.com/K-Dense-AI/scientific-agent-skills/blob/13385c7c4db02fdcc84a020752c07cce91ef780e/CONTRIBUTING.md)
requires exact standard naming and frontmatter, repository-level tests for
script-bearing skills, reference validation, and additional CI checks. Its
[security policy](https://github.com/K-Dense-AI/scientific-agent-skills/blob/13385c7c4db02fdcc84a020752c07cce91ef780e/SECURITY.md)
combines recurring automated scans with explicit warnings that scan output is
not an audit.

This is the best upstream to emulate for structural validation, test layout,
and portable frontmatter. Its breadth also means dependencies, credentials,
and network behavior vary substantially by skill; the workshop's selective
bundles and hash-bound review remain valuable.

### NiPreps skills-comm

The pinned [NiPreps collection](https://github.com/nipreps/skills-comm/tree/ded6d5ea77cdae0c01f384fc306e12fe5973f00d)
has the strongest domain-operational model. Its
[contribution process](https://github.com/nipreps/skills-comm/blob/ded6d5ea77cdae0c01f384fc306e12fe5973f00d/CONTRIBUTING.md)
starts with an issue, emphasizes reproducible environments, BIDS/DataLad
provenance, quality control, and requires manual end-to-end evidence. Its
`skill-iterations/` examples show how a rough domain skill is progressively
hardened.

The current pin explicitly says it has no CI test harness, and many skills use
Claude plugin packaging and vendor activation keys. It is therefore a strong
source for neuroimaging behavior and contribution practice, but not yet the
best portability baseline. Workshop validation and target classification
should surround it without erasing useful Claude behavior.

### CON skills

The pinned [CON collection](https://github.com/con/skills/tree/493d7e83865ed5c21a8f4e5b02e72fc47bce5bb3)
contains focused maintenance, triage, compliance, and repository-health
workflows closely aligned with this workshop. Its small size and direct fork
relationship make upstream contribution straightforward.

At this pin, its [README](https://github.com/con/skills/blob/493d7e83865ed5c21a8f4e5b02e72fc47bce5bb3/README.md)
documents Claude installation, declares licensing as unresolved, and many
skills use vendor activation keys. Automated tests are concentrated in the
`issue-triage` skill rather than enforced across the collection. The workshop
adds material value here through conformance diagnostics, licensing review,
bundle selection, and safe project reconciliation.

## Alternative approaches and existing tools

No reviewed tool covers the workshop's whole intended workflow, and that is no
longer the criterion for reuse. A component that provides only discovery,
ranking, registry transport, validation, or installation may still be the
correct implementation behind a stable workshop interface. The strongest
approach is to compose specialized open tools at clear boundaries.

### Comparison at a glance

| Approach | Strongest use | Advantages over the workshop | Advantages of the workshop |
| --- | --- | --- | --- |
| Agent Skills `skills-ref` | Format validation and prompt catalog examples | Closest reference interpretation of the standard | Production safety, lifecycle state, reconciliation, trust, and recovery |
| Microsoft APM | Reproducible project-local agent packages, dependencies, and deployment | Manifest and integrity lock, transitive resolution, frozen replay, many clients and primitives, packaging, integrity/drift/hidden-Unicode audit, and provenance SBOMs | Parent-held two-sided baselines, independent project copies, back-propagation, fork coordination, and hash-bound human review |
| GitHub CLI `gh skill` | GitHub discovery, preview, install, update, pin, and publish | First-party GitHub workflow, many host destinations, format/release checks, release and SHA pins | Bundles, external locks, fork coordination, two-sided changes, back-propagation, review ledger |
| Vercel `skills` / skills.sh | Broad multi-agent discovery and one-way installation | Many sources and hosts, search, packs, copy/symlink choices, local and global state, advisory audit signals | Conservative local-edit handling, independent project development, hash-bound review and backup policies |
| ASM | Cross-provider catalog, TUI, install, validation, evaluation, and advisory scans | Broad existing catalog, structured CLI, provider coverage, and publication flow | Durable local curation and the parent-held reconciliation model |
| `skill-manager` | Personal canonical store, profiles, project manifests, symlinks, and TUI | Closest existing profile/TUI precedent, source sync, hashes, history, and backups | Independently editable project copies rather than links to one global canonical store |
| SkillPort | Cross-client management, its own lint, search-first loading, and MCP delivery | Existing CLI, Python library, full-text search, metadata commands, and MCP `search_skills`/`load_skill` tools | Exact source pins, external two-sided locks, hash-bound human review, and recovery |
| `skills-registry` | Personal GitHub-backed inventory, fuzzy browsing, and on-demand MCP access | Existing TUI with metadata/description preview, sync/publish flow, cache, and simple search/read tools | Exact upstream pins, hash-bound review, bundles, fork coordination, and two-sided project reconciliation |
| SkillHub | Self-hosted organizational registry and governance | Versions, namespaces, review, RBAC, audit logs, ratings, filtered full-text search, and CLI | Lightweight local operation, Git-native upstream work, independent project copies, and back-propagation |
| SkillsHub resolver | Open task-to-skill lookup over a large aggregated catalog | Agent-facing API, BM25-based ranking, tags, and raw skill retrieval | Durable local selection, review state, exact sources, and source/project baselines |
| SkillNote / SkillsGo | Emerging self-hosted or desktop registry workflows | Collections, synchronization, source inspection, local inventory, and reusable protocol work | Current maturity, pinned upstream contribution flow, conservative local-edit handling, and recovery |
| SkillCorpus | Large-scale corpus curation, retrieval, and evaluation research | Quality facets, task matching, benchmark evidence, and ecosystem-scale perspective | Available implementation today and durable personal control-plane state |
| Open search components | Fuzzy, full-text, vector, or hybrid ranking | Mature retrieval primitives without a vendor-specific skill model | Skill identity, provenance, trust, bundles, and lifecycle semantics |
| Native vendor installers and plugins | Product-specific distribution | Best integration with each product's UI, MCP, hooks, and policies | One portable source of truth and vendor-neutral development workflow |
| Git submodules and forks alone | Exact upstream pins and contribution branches | Standard Git primitives and full history | Skill-level inventory, bundles, project materialization, status, and safe conflict policies |
| Plain copies | Small, stable project sets | Minimal tooling and maximum downstream independence | Provenance, updates, drift detection, reconciliation, and recovery |

### Official reference tooling

The standard's reference repository supplies `skills-ref` to validate a skill,
read properties, and generate an `<available_skills>` catalog. It is the most
useful compatibility oracle, but its
[own warning](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref/README.md)
means it should be pinned and used in CI alongside workshop-owned tests rather
than trusted as the sole production parser.

The [official evaluation guidance](https://agentskills.io/skill-creation/evaluating-skills)
also fills a gap the workshop's current 98 management tests do not address. It
recommends realistic prompts, clean contexts, runs with and without the skill,
machine-checkable assertions where possible, blind comparisons, and human
review. Management correctness and skill effectiveness are different test
layers; both are needed.

### Existing agent-facing helper skills

There are useful agent-facing helpers, but none reviewed is a portable manager
for this full lifecycle. The
[Codex documentation](https://developers.openai.com/codex/skills) describes a
bundled `skill-installer` for curated skills and Git repository paths. It is a
convenient local installation interface, not a bundle, lock, reconciliation,
overlay, or upstream-contribution system.

The Agent Skills evaluation guide points to `skill-creator`, which supports
authoring, realistic evaluation prompts, graders, comparisons, and iterative
improvement. That is a strong basis for testing individual skills and the
future workshop-manager skill, but it does not manage an inventory of
independently versioned sources and project copies. The gap is therefore not
“another installer”; it is a thin, well-evaluated agent interface over this
workshop's deterministic lifecycle commands.

### Microsoft APM

[Microsoft APM](https://github.com/microsoft/apm) is the strongest current
argument against expanding the workshop into a general package manager. Its
documented `apm.yml` and `apm.lock.yaml` model already covers direct and
transitive dependencies, exact commits and content hashes, selective skills,
frozen installation, cache integrity, update previews, many Git and local
sources, and deployment to major agent clients. It also supplies compile,
pack, publish, marketplace, integrity, drift, hidden-Unicode, JSON/SARIF, and
CycloneDX/SPDX workflows. Its policy and external-scanner integrations are
early-preview features, and its SBOM output is provenance inventory rather
than a compliance attestation.

APM should therefore be the first integration trial when the need is dependency
resolution, integrity locks, generic target placement, packaging, audit, or
SBOM output. It is not automatically the first replacement candidate for the
personal reconciliation workflow; plain Git, `skill-manager`, and ASM overlap
that workflow more directly and should be tested cheapest and closest first.
The workshop should not implement competing package capabilities unless a
bounded trial fails a documented requirement.

There is one important architectural difference. APM normally commits its
manifest, lock, and deployed context in the downstream project so every
collaborator can reproduce them. The workshop deliberately keeps coordination
state in a parent repository and permits a downstream copy to evolve without
the workshop. APM detects drift, but its documented remediation does not offer
the workshop's separate source/project baselines, `record` and
`back-propagate` choices, or fork-to-canonical contribution workflow. Use APM
when project-local reproducibility is the goal; add the workshop only when the
parent-held two-sided lifecycle is genuinely needed.

APM's
[OpenAPM v0.1 specification](https://microsoft.github.io/apm/specs/openapm-v01/)
is an editor's Working Draft under semantic-version-zero, not an accepted
ecosystem standard. Its current manifest and registry contracts should be
treated as versioned implementation interfaces. An APM lock must remain
derived package/deployment state rather than become a second authority for the
workshop's reconciliation lock.

### GitHub CLI `gh skill`

GitHub CLI 2.90 and later includes `gh skill` in public preview. It can
[search, preview, install, pin, and update skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills),
choose among many agent destinations, and
[perform format/release checks or publish skill releases](https://cli.github.com/manual/gh_skill_publish).
It records source and tree provenance in installed `SKILL.md` metadata. These
checks are not a safety review: GitHub warns that third-party skills remain
unverified and can contain malicious instructions or scripts.

The workshop's locked Pixi environment currently provides GitHub CLI 2.97, so
this preview can be evaluated without adding another runtime dependency.

Its strengths are ecosystem discovery, pre-install inspection, GitHub-native
version selection, host path knowledge, and release transport. Its model is
still principally one way: upstream to installed copy. A
[normal or forced refresh](https://cli.github.com/manual/gh_skill_update) may
replace local modifications rather than reconcile them. It does not document
bundle/profile composition, a separate two-sided lock,
back-propagation, a hash-bound review ledger, or verified recovery backups.
Before installation, it recognizes embedded upstream provenance in republished
skills, and `install --upstream` can redirect to that source. Installing the
republished copy replaces that field with the republisher's provenance, and
neither path provides fork/branch contribution coordination.

This makes `gh skill` a good candidate **import and publication backend**, not a
replacement for the workshop when project copies are expected to evolve and
contribute changes back. An import adapter should read the recorded upstream
ref/tree or strip `metadata.github-*` installer fields rather than treating an
installer-mutated `SKILL.md` as the canonical source.

### Vercel `skills` and skills.sh

The [Vercel `skills` CLI](https://github.com/vercel-labs/skills) is a broad
multi-agent installer reviewed here. It supports GitHub, GitLab, arbitrary Git
and local sources, project and global installs, many agent path mappings,
skill selection, copy or symlink installation, one-off use, search, list,
remove, check, update, and initialization. It has both a project
[`skills-lock.json`](https://github.com/vercel-labs/skills/blob/c6f69c631292444cc541ac6d91e2226b0ff247da/src/local-lock.ts)
and global installation state, plus a substantial automated test suite.

It is optimized for convenient distribution and one-way refresh. Its update
path does not provide the workshop's “record both,” “back-propagate,” or
two-sided divergence workflow for a locally developed project copy. Its
project lock is intended to live in the downstream project, whereas this
workshop deliberately keeps coordination metadata in the parent control
plane. skills.sh does offer account-managed
[Packs](https://www.skills.sh/docs/packs) for grouped installation, but these
are not repository-native, version-controlled, hash-bound workshop bundles or
profiles. In workshop terminology they are export targets for bundles, not the
canonical bundle record. The system also lacks canonical-versus-fork remotes,
hash-bound human reviews, and the workshop's conservative prune and backup
policy.

skills.sh aggregates
[advisory signals from external audit providers](https://www.skills.sh/audits).
Those signals are useful discovery cues, but they do not replace a human
review bound to the exact tree digest being materialized.

The two systems can interoperate: use `skills` for commodity discovery and
multi-host installation, then import selected skills into the workshop when
they require curation, modification, review, or bidirectional project work.
Path maps must still be checked against current vendor documentation because
vendor locations evolve independently.

### Adjacent personal and cross-provider managers

Two additional projects overlap enough with the workshop to deserve an
adopt-or-contribute decision before related work:

- [ASM](https://github.com/luongnv89/asm) is an active, MIT-licensed
  cross-provider CLI and TUI with a large catalog, structured output, search,
  installation, bundles, validation, evaluation, advisory security scans, and
  publication. It is a stronger starting point than a workshop-built catalog,
  scanner, or cross-provider installer.
- [`skill-manager`](https://github.com/omrikais/skill-manager) is a smaller but
  unusually close UX precedent. It has a canonical store, named profiles,
  project manifests, source synchronization, hashes, history, backups, a TUI
  with diffs, MCP access, and symlink deployment. Its canonical-store model is
  intentionally different from independently editable copied project skills,
  but its profile and UI patterns should be evaluated or improved upstream
  before expanding equivalent workshop features.

Other package approaches include npm-oriented
[`skillpm`](https://github.com/sbroenne/skillpm), historical
[`OpenSkills`](https://github.com/numman-ali/openskills), registry-oriented
[`Paks`](https://github.com/stakpak/paks), and multi-artifact
[`OpenPackage`](https://github.com/enulus/OpenPackage). They are lower-priority
than APM for the current requirements, but they reinforce the same conclusion:
do not build another generic package, registry, or target-deployment layer.

### Community registries and resolvers

Several open community systems cover meaningful portions of the registry and
search problem. Their existence changes the workshop's implementation
strategy even where none is adopted wholesale.

MIT-licensed [`SkillPort`](https://github.com/gotalab/skillport) is a
particularly relevant reusable component. It validates skills; adds, updates,
lists, and removes them; provides metadata commands and full-text search; and
offers MCP `search_skills` and `load_skill` tools for search-first loading. Its
documented category and tag convention uses nested `metadata.skillport`
values in `SKILL.md`. That shape conflicts with the current Agent Skills
requirement that `metadata` be a string-to-string map, so the workshop should
evaluate SkillPort's CLI, library, and MCP surfaces without copying that
serialization into canonical skills. An adapter can retain those values as
`skillport` observations and still reuse the open implementation.

[`skills-registry`](https://skills-registry.dev/) is an Apache-2.0,
pre-1.0 personal registry backed by a GitHub repository. Its Go TUI scans
vendor skill locations, synchronizes and publishes skills, fuzzy-filters the
inventory with a metadata and description preview, and can add skills from
another person's registry. Its separate native macOS app, rather than the Go
TUI, provides rich Markdown rendering. Its hosted MCP surface exposes
`search_skills` and
`get_skill`; search uses an fzf-style scorer over the skill slug, name, and
description. This is the closest existing implementation to the personal
browsing experience previously proposed for the workshop. Adopt it when that
experience is the need. Add the workshop only for exact upstream pins,
hash-bound review, bundle intent, or two-sided project reconciliation; do not
rebuild its TUI or search merely to keep all behavior local.

[`iflytek/skillhub`](https://github.com/iflytek/skillhub) is an Apache-2.0
self-hosted registry with semantic versions and release tags, filtered
full-text search, namespaces, membership roles, review gates, audit logs,
ratings, and CLI installation. It is a strong candidate when a team needs an
organizational registry. Its PostgreSQL, Redis, object-storage, web, and
governance stack is disproportionate for a small personal inventory, but its
API and data model deserve evaluation before comparable registry machinery is
built here.

[`ComeOnOliver/skillshub`](https://github.com/ComeOnOliver/skillshub) is a
separate MIT-licensed project whose agent-facing resolver accepts a task and
ranks an aggregated catalog. Its current technology summary names BM25, while
its feature description calls the weighting IDF-based across names,
descriptions, and tags. It also generates tags from keywords during import,
exposes raw Markdown retrieval, and supports self-hosting. These are useful
search-provider outputs, not authoritative provenance or curated workshop
tags.

Two other open projects broaden the design space. MIT-licensed
[`SkillNote`](https://github.com/luna-prompts/skillnote) provides a self-hosted
registry with per-project collections, live synchronization, and usage
feedback. Its example writes a nonstandard `collections` array into
`SKILL.md`; that is useful provider behavior but should be mapped as an
external bundle-like observation rather than copied into a portable core.
Apache-2.0 [`SkillsGo`](https://github.com/skillsgo/skillsgo) is developing a
desktop app, CLI, Hub, and shared executable protocol around source evidence,
immutable releases, and local inventory; its own status says it is still
preparing first releases. Re-evaluate either only when a concrete requirement
makes it a plausible replacement or integration.

The Apache-2.0
[`MCP Gateway & Registry`](https://github.com/agentic-community/mcp-gateway-registry)
also indexes skills alongside MCP servers and agents and exposes
natural-language discovery with governance and access control. It is an
enterprise gateway rather than a personal skill workshop. It is evidence that
the workshop should not expand into a general agent-context registry.

### Retrieval research and reusable search components

[SkillCorpus](https://arxiv.org/abs/2607.15557) is the most directly relevant
research effort found so far. It reports crawling roughly 821,000 skills,
curating 96,401 of them using utility, robustness, and safety facets, and
pairing the corpus with a fine-tuned retrieval-and-selection stack evaluated
across three benchmarks. Its authors say the dataset, models, and code will be
released upon acceptance, so it cannot yet be adopted or independently
verified as an implementation. Revisit it if the search evidence gate is met;
it is not a reason to start local retrieval work now.

The workshop should not implement a search engine. Fuzzy search, SQLite full
text search, local vector extensions such as
[`sqlite-vec`](https://github.com/asg017/sqlite-vec), and hybrid engines such as
[`Qdrant`](https://qdrant.tech/documentation/search/hybrid-queries/) already
provide the underlying retrieval primitives. Use an existing registry or
manager now.

Only after the numeric search trigger in the viability decision is met, use
this staged model to compare existing candidates:

1. exact identity and lexical search over names, descriptions, tags, and
   sources;
2. optional fuzzy and full-text ranking;
3. optional semantic retrieval over ordinary descriptions and generated task
   examples;
4. provider-independent filtering for license, review, compatibility, source,
   and bundle membership;
5. reranking and explanations, measured against a versioned query set.

Hypothetical task descriptions and embeddings belong in a rebuildable index,
not canonical skill classification. This preserves the useful insight behind
hypothetical-document retrieval without allowing generated text to become a
fact about the skill.

### Native installers and plugins

[OpenAI's skill guidance](https://developers.openai.com/codex/skills) recommends
standalone directories for local or repository authoring and plugins for
reusable distribution bundles. An OpenAI plugin may include multiple skills,
MCP servers, connectors, hooks, and assets, and a skill can add
`agents/openai.yaml` for OpenAI-specific UI and dependency metadata. Claude
plugins and other vendor packages use different manifests.

The portable core should therefore remain the ordinary skill directory. A
vendor plugin is a distribution adapter around that core, not its canonical
source. This avoids letting one vendor's packaging format determine the
workshop's internal model.

### Emerging packaging and discovery proposals

Several efforts in and around the Agent Skills repository are relevant but are
not standards:

- [Discussion 210](https://github.com/agentskills/agentskills/discussions/210)
  proposes external `skills.json` and `skills.lock` files, Git URL identity,
  dependency resolution, and content integrity while leaving `SKILL.md`
  untouched;
- [Discussion 302](https://github.com/agentskills/agentskills/discussions/302)
  defines a serialization-neutral recipe with lowercase tags, PURL identity,
  required content hashes, versions, and dependencies;
- [Discussion 292](https://github.com/agentskills/agentskills/discussions/292)
  explores OCI distribution, signatures, provenance, and layer-based
  packaging, including possible overlay benefits;
- [Issue 255](https://github.com/agentskills/agentskills/issues/255) and the
  [MCP Skills interest group](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2460)
  are converging on `/.well-known/agent-skills/index.json` for discovery, with
  name, description, artifact type, URL, and SHA-256 digest. That proposal
  currently has no tag field.

They could eventually offer interoperable package and supply-chain machinery.
Today they do not cover the workshop's two-sided project development, bundles,
review state, or conflict menu, and their schemas should not yet be treated as
settled standards. That does not justify inventing an incompatible package
schema. The workshop should track their fields and identity rules, keep its own
extension surface minimal, and prefer an adapter or experimental export using
extension surface minimal, and prefer a pinned experimental integration or
export. Discussion #302 supplies the provisional tag
semantics, while the `.well-known` index is a future discovery adapter rather
than a new local authority. The workshop already records enough URL, revision,
identity, and digest information to support both paths.

The proposed package lock and the existing workshop locks solve different
problems. A package lock would record dependency resolution and installation
integrity. A workshop materialization lock is a per-project reconciliation
receipt with separate source and project baselines. A future common package
lock would complement rather than replace the workshop lock.

## Durable metadata and replaceable components

The workshop should be the durable record of its narrow decisions, not a
monolithic implementation of every operation. The following separation is a
boundary for integrations, not a commitment to implement every layer locally:

| Layer | Durable contents | Replacement rule |
| --- | --- | --- |
| Canonical artifact | Exact skill tree, content digest, source identity, revision, and license evidence | Never reconstructed from a provider ranking or generated summary |
| Workshop curation | Stable local identity, bundles, trust review, and reconciliation baselines; tags and overlays only if later justified | Versioned and exportable; changed only through explicit workshop operations |
| Provider observation | Provider-native identifier, raw metadata, source URL, revision, score, audit signal, and observation time | Namespaced, refreshable, and removable without damaging canonical state |
| Derived index | Normalized search documents, tokens, fuzzy keys, embeddings, hypothetical task examples, and reranking features | Fully rebuildable from artifacts, curation, and recorded provider observations |
| Materialized output | Vendor or project copy plus a receipt linking it to the source and rendered digest | Regenerable where unchanged; independently editable where project policy permits |

Provider metadata should be preserved losslessly under a provider namespace
before any cross-provider normalization. A GitHub star count, Vercel rank,
registry rating, automated audit, and workshop human review are different
claims with different issuers and timestamps. Combining them into one
unqualified `quality` or `trust` field would destroy information and create
lock-in to the current ranking model.

When an external discovery or retrieval tool is integrated, use the following
conceptual vocabulary to keep its responsibilities clear:

```text
discover(query, filters, cursor) -> provider candidate references
fetch(reference, revision)       -> immutable artifact plus provenance
inspect(reference)               -> namespaced provider observations
index(records, configuration)    -> reproducible index snapshot
search(query, filters)           -> ranked results plus match evidence
```

Scores remain provider-local unless a documented calibration combines them.
Search results should expose the provider, native identity, retrieval method,
matched evidence, artifact revision where known, and index timestamp. Import,
installation, publication, and update are separate capabilities rather than
assumptions attached to every search provider.

A chosen integration needs focused contract tests for the operations actually
used. Implement the first two integrations directly and extract an adapter
interface only after both demonstrate a stable common contract. A ranking
benchmark is justified only when a concrete tool-selection decision requires
one; it is not a reason to build a workshop search subsystem.

## Overlays

### When overlays may be justified

Overlays are a plausible response to repeated small specializations, not a
current requirement. Do not implement them until the same non-upstreamable
transformation has recurred at least three times across at least two projects.
Until then, prefer a project edit, a general upstream fix, or a distinct fork.

The current choices are too coarse for a small, durable specialization:

- edit the project copy, which creates whole-tree divergence;
- back-propagate the entire project tree into the workshop;
- fork and maintain a nearly identical skill;
- put local detail into an ad hoc project prompt.

The Agent Skills format does not define inheritance, tree merging,
skill-to-skill imports, or overlay behavior. Its client guide treats same-name
skills as collisions resolved through deterministic precedence, so portable
tooling must not assume that installing two same-name skills composes them. An
overlay must therefore be a workshop build input, not a new artifact that the
agent is expected to understand.

| Specialization strategy | Benefits | Costs and risks |
| --- | --- | --- |
| Full fork | Ordinary Git history; easy to develop and contribute substantial changes | Duplicates the whole skill and accumulates upstream drift |
| Edited downstream copy | Maximum project independence; no extra format | The reusable intent is hidden inside whole-tree divergence |
| Wrapper skill delegating to a base | Leaves the base untouched | Skill-to-skill invocation and dependency availability are not standardized |
| Runtime-loaded overlay support file | Fits progressive disclosure and avoids generation | Requires overlay-aware instructions or clients and has no shared precedence semantics |
| Workshop-rendered overlay | Produces one ordinary portable artifact; can be hashed, previewed, and tested | Requires a renderer, conflict model, and rebase workflow |

```mermaid
flowchart LR
    A["Pinned base skill<br/>identity + revision + hash"] --> B["Apply ordered overlays<br/>in a staging tree"]
    B --> C["Validate format,<br/>resources, and policy"]
    C --> D["Complete ordinary<br/>skill tree + result hash"]
    D --> E["Copy to one<br/>vendor destination"]
```

### Existing overlay precedents

There is no accepted overlay standard, but two precedents are informative:

- an independent [draft Skill Overlays RFC](https://gist.github.com/nibzard/dc79fe1f3954a0594fc8414d6f8cea28)
  treats overlays as optional support files loaded after activation; clients
  that do not know the convention ignore them. This preserves the base but
  requires overlay-aware runtime behavior and does not solve deterministic
  project materialization;
- the [Vercel plugin's upstream sync](https://github.com/vercel/vercel-plugin/blob/11c32588786a9d49791372657433b88d49561874/README.md#upstream-skill-sync)
  keeps an upstream subtree, an `overlay.yaml`, and a generated complete
  `SKILL.md`, with CI checking that generated output is current. This is closer
  to the workshop's needs as a precedent for build-time composition. It is not
  a general patch system: it replaces upstream frontmatter, appends the body,
  copies a fixed resource set, and records no base digest or rebase state. Its
  metadata and injection model are Vercel-specific.

### Contract if the evidence gate is met

Store overlay inputs only in the workshop and render a complete standard skill
before materialization. A first version should record:

- immutable base identity, source URL, revision, and tree digest;
- ordered overlay files and their digests;
- an optional target vendor or compatibility profile;
- a deliberately small operation set, initially append or replace a named
  managed section plus explicit file add/delete operations;
- the rendered tree digest and validation result.

Apply overlays in an isolated staging tree, refuse a stale base or failed
patch, show the composed diff, validate the result, and only then materialize
it.
When upstream changes, re-render against the new base and expose conflicts as
a rebase operation. Do not attempt semantic Markdown merging.

Small vendor companion files are a good first use case. Generic corrections
should still be made in the fork and contributed upstream. A large or
independently versioned change should remain a fork rather than an overlay.

## Vendor compatibility

### Shared location and syntax

`.agents/skills` is the broadest common project and user convention among the
clients reviewed: Codex, GitHub Copilot, Gemini CLI, Cursor, and OpenCode all
document it. Claude Code remains the important exception: its documented roots
are `.claude/skills` and `~/.claude/skills`. This makes the workshop's current
destination broadly interoperable, but not universal.

| Host | Project roots relevant here | User roots relevant here | Notable differences |
| --- | --- | --- | --- |
| [OpenAI Codex](https://developers.openai.com/codex/skills) | `.agents/skills` from working directory to repository root | `~/.agents/skills` | Follows directory symlinks; optional `agents/openai.yaml`; plugin distribution is separate |
| [Claude Code](https://code.claude.com/docs/en/skills) | `.claude/skills` from the start directory through repository parents, plus descendant roots on demand | `~/.claude/skills` | Does not support/document `.agents`; adds vendor frontmatter and runtime features; local rules can be more lenient than the standard |
| [GitHub Copilot](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) | `.github/skills`, `.agents/skills`, `.claude/skills` | `~/.copilot/skills`, `~/.agents/skills` | Product-specific invocation fields; Copilot CLI documents first-found precedence, while other surfaces do not; symlinks are not a safe portability assumption |
| [Gemini CLI](https://geminicli.com/docs/cli/skills/) | `.gemini/skills`, `.agents/skills` | `~/.gemini/skills`, `~/.agents/skills` | Explicit activation consent; deterministic tier precedence; supports a symlink-linking workflow; parser and depth rules are more lenient than the standard |
| [Cursor](https://cursor.com/docs/skills) | `.cursor/skills`, `.agents/skills`, `.claude/skills`, `.codex/skills` | `~/.cursor/skills`, `~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills` | Recursive discovery and `paths`/invocation extensions; duplicate and symlink behavior are not fully documented |
| [OpenCode](https://opencode.ai/docs/skills) | `.opencode/skills`, `.claude/skills`, `.agents/skills` | `~/.config/opencode/skills`, `~/.claude/skills`, `~/.agents/skills` | Recognizes the standard core fields except experimental `allowed-tools`, ignores unknown keys, and controls access with separate host permissions |

Primary vendor sources are the
[Codex skill guide](https://developers.openai.com/codex/skills),
[Claude Code skill guide](https://code.claude.com/docs/en/skills),
[GitHub Copilot skill overview](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills),
[Gemini CLI skill guide](https://geminicli.com/docs/cli/skills/),
[Cursor skill guide](https://cursor.com/docs/skills), and
[OpenCode skill guide](https://opencode.ai/docs/skills).

These rows describe filesystem discovery by coding agents. OpenAI documents
the roots in the table for Codex; it does not describe them as a raw local
installation path for ChatGPT on web or mobile. Reusable ChatGPT and Codex
distribution across surfaces uses plugin packaging.

Claude Code's lack of `.agents/skills` support is not merely an omitted example:
the official [compatibility request was closed as not planned](https://github.com/anthropics/claude-code/issues/66352).
Gemini CLI is more permissive than the shared format: its
[troubleshooting guide](https://geminicli.com/docs/cli/tutorials/skills-getting-started/)
describes the frontmatter name as authoritative, normalizes forbidden
characters, and limits discovery to `SKILL.md` at a skills root or one level
below it.

Symlink portability also needs explicit testing. A reported
[Copilot/VS Code issue](https://github.com/microsoft/vscode/issues/315979)
shows a linked skill visible in the UI but unavailable to the agent, while an
[OpenCode issue](https://github.com/anomalyco/opencode/issues/18848) reports
linked project roots failing in worktree sandboxes. Neither report establishes
a universal limitation, but both make copies the conservative default.

Do not install the same skill blindly into both `.agents/skills` and
`.claude/skills` in one project. Copilot, Cursor, and OpenCode scan both roots,
so this can create duplicates or host-specific precedence surprises. Ensure
that each intended host sees exactly one effective copy, reusing a shared
`.agents/skills` destination where supported and adding a native-path adapter
only when required.

### Portable core and vendor adapters

Use this compatibility rule:

- canonical top-level frontmatter contains `name`, `description`, and the
  standard optional fields `license`, `compatibility`, and string-valued
  `metadata`;
- use the standard but experimental `allowed-tools` only when its
  client-specific semantics are understood, and never treat it as a portable
  security boundary;
- put vendor configuration in companion files or workshop overlays rather
  than nonstandard top-level frontmatter where possible;
- use relative resource paths and conventional `scripts/`, `references/`, and
  `assets/` directories;
- describe runtime, package, network, credential, and tool requirements in
  `compatibility` and the trust inventory;
- avoid embedding vendor invocation syntax in canonical instructions;
- test every host or surface for which behavioral compatibility is claimed.

OpenAI's separate `agents/openai.yaml` illustrates a companion-file adapter
that leaves `SKILL.md` unchanged. Nonstandard top-level frontmatter is rejected
by the pinned `skills-ref` validator and may be ignored or interpreted
differently by other clients.

## A tested manager skill

The workshop has a well-tested management implementation, but not yet a
portable skill that teaches an agent when and how to operate it. These should
remain distinct:

- deterministic Python commands own path validation, locking, copying,
  backups, conflict policy, and mutation;
- a `skills-workshop-manager` skill provides discovery, task routing,
  previews, explanations, and the human approval sequence;
- the skill never reimplements destructive behavior in prose.

Do not create the manager skill before the pilot stabilizes the useful command
surface. If the evidence gate is met, its first version should cover only the
operations actually exercised: inventory and trust inspection, project import,
bundle selection, status and diff, upstream checks, and explicit conflict
resolution. Its instructions should default to preview and status operations
and require a clear user choice before mutation. Overlay routing belongs in a
later version only if overlays independently clear their own evidence gate.

Its test strategy needs four layers:

1. **Format tests:** specification-conformance and resource-link checks.
2. **Management tests:** the existing deterministic CLI suite, including
   atomicity and recovery behavior.
3. **Agent evaluations:** realistic positive and negative trigger prompts,
   with-versus-without baselines, correct plan selection, and safe refusal.
4. **Host compatibility tests:** discovery, explicit and implicit invocation,
   resource access, dependencies, permissions, copy versus symlink behavior,
   and at least one run on every claimed host.

Any eventual manager skill should be small enough to include in the core
profile, but bootstrapping must not depend on it already being installed.
Direct Pixi commands remain the recovery interface.

## Recommendations

### Recommended operating pattern

Use a promotion boundary rather than a universal layered platform:

1. Discover, preview, validate, and try ordinary skills with existing tools.
2. Leave unchanged, one-way installations under those tools.
3. Promote only skills that will be curated, reviewed at an exact revision,
   modified across projects, or contributed upstream.
4. Keep workshop authority limited to bundle intent, fork/source attribution,
   hash-bound human review, and source-versus-project baselines.
5. Materialize ordinary complete skill trees so downstream projects remain
   usable without the workshop.
6. Reconcile deliberate divergence and contribute general changes upstream.

### Evidence-gated roadmap

1. Keep the version 1/2 → version 3 migration and compatibility tests green.
2. Run pinned external conformance checks before the first pilot promotion;
   classify rather than claim portability for nonstandard vendor skills.
3. Dogfood a complete apply, project edit, status/diff, record or
   back-propagate, and reapply cycle in a real downstream project.
4. Test the same seven residual cases against plain Git, `skill-manager`, ASM,
   and APM, cheapest and closest first. APM must use disposable staging if the
   downstream is to remain workshop-independent.
5. Run the 60-day proof-of-value pilot in the committed
   [usage ledger](usage-pilot.md).
6. Continue only the features attached to observed unique-value events.

Tag persistence, overlays, broad target adapters, search infrastructure,
generic provider interfaces, and a manager skill are frozen during the pilot.
Each has a concrete trigger in the
[feature disposition](project-viability.md#feature-disposition). Package
resolution, dependency locks, generic deployment, packaging, registry
transport, provenance SBOMs, APM's integrity/Unicode audit, and third-party
security scans should be delegated to established tools rather than added to
this roadmap.

### Decision rules

| Situation | Preferred pattern |
| --- | --- |
| One to three stable skills with no update workflow | Commit plain copies or use the vendor installer |
| Reproducible dependency state should live in the downstream project | Use APM |
| GitHub-native discovery, pinning, update, or release | Use `gh skill` |
| Useful unchanged skill needed across sources or agents | Use Vercel `skills` or another broad installer |
| Search-first or MCP access to a large local inventory | Use SkillPort |
| Personal canonical store and symlinked profiles | Use `skill-manager` |
| GitHub-backed fuzzy inventory with metadata/description preview | Use `skills-registry` |
| Small project-specific change | Edit and commit the project copy |
| Repeated small non-upstreamable change | Consider an overlay only after its evidence trigger |
| General correction | Change the fork and contribute upstream |
| Large independent evolution | Maintain a fork as a distinct source |
| Multiple independently edited projects need a shared source and parent-held coordination | Use the workshop |
| Project copy changed under workshop management | Inspect status/diff, then explicitly record, back-propagate, overwrite, or abort |
| Claiming cross-vendor support | Validate the core and test each claimed host |

The decision is conditional: continue the reconciliation kernel, pivot every
commodity capability to reuse, and stop active development if the pilot does
not demonstrate repeated value. The full continue, pivot, stop, and safe-exit
criteria are in the [project viability decision](project-viability.md).

## Source index

### Standard and evaluation

- [Agent Skills overview](https://agentskills.io/home)
- [Agent Skills specification](https://agentskills.io/specification)
- [Client implementation guide](https://agentskills.io/client-implementation/adding-skills-support)
- [Evaluating skills](https://agentskills.io/skill-creation/evaluating-skills)
- [Official repository](https://github.com/agentskills/agentskills)
- [Pinned reference validator](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref)

### Managers, distribution, and overlays

- [Microsoft APM](https://github.com/microsoft/apm)
- [APM package types](https://microsoft.github.io/apm/reference/package-types/)
- [APM manifest schema](https://microsoft.github.io/apm/reference/manifest-schema/)
- [APM lockfile specification](https://microsoft.github.io/apm/reference/lockfile-spec/)
- [APM policy preview](https://microsoft.github.io/apm/enterprise/apm-policy/)
- [APM audit command](https://microsoft.github.io/apm/reference/cli/audit/)
- [OpenAPM v0.1 Working Draft](https://microsoft.github.io/apm/specs/openapm-v01/)
- [GitHub CLI skill workflow](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [GitHub CLI skill update](https://cli.github.com/manual/gh_skill_update)
- [GitHub CLI skill publish](https://cli.github.com/manual/gh_skill_publish)
- [Vercel `skills` CLI](https://github.com/vercel-labs/skills)
- [skills.sh Packs](https://www.skills.sh/docs/packs)
- [skills.sh audit signals](https://www.skills.sh/audits)
- [ASM](https://github.com/luongnv89/asm)
- [`skill-manager`](https://github.com/omrikais/skill-manager)
- [`skillpm`](https://github.com/sbroenne/skillpm)
- [`OpenSkills`](https://github.com/numman-ali/openskills)
- [`Paks`](https://github.com/stakpak/paks)
- [`OpenPackage`](https://github.com/enulus/OpenPackage)
- [Vercel plugin overlay/upstream model](https://github.com/vercel/vercel-plugin/blob/11c32588786a9d49791372657433b88d49561874/README.md#upstream-skill-sync)
- [Draft Skill Overlays RFC](https://gist.github.com/nibzard/dc79fe1f3954a0594fc8414d6f8cea28)
- [Agent Skills package manifest discussion](https://github.com/agentskills/agentskills/discussions/210)
- [Agent Skills recipe and PURL discussion](https://github.com/agentskills/agentskills/discussions/302)
- [Package URL specification](https://github.com/package-url/purl-spec)
- [Agent Skills OCI distribution discussion](https://github.com/agentskills/agentskills/discussions/292)
- [Agent Skills `.well-known` discovery proposal](https://github.com/agentskills/agentskills/issues/255)
- [MCP Skills interest-group discovery notes](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2460)

### Community registries, resolvers, and retrieval

- [`skills-registry`](https://github.com/nikships/skills-registry)
- [SkillPort](https://github.com/gotalab/skillport)
- [SkillHub](https://github.com/iflytek/skillhub)
- [SkillsHub resolver](https://github.com/ComeOnOliver/skillshub)
- [SkillNote](https://github.com/luna-prompts/skillnote)
- [SkillsGo](https://github.com/skillsgo/skillsgo)
- [MCP Gateway & Registry](https://github.com/agentic-community/mcp-gateway-registry)
- [SkillCorpus](https://arxiv.org/abs/2607.15557)
- [`sqlite-vec`](https://github.com/asg017/sqlite-vec)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)

### Pinned upstream collections

- [K-Dense scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/13385c7c4db02fdcc84a020752c07cce91ef780e)
- [NiPreps skills-comm](https://github.com/nipreps/skills-comm/tree/ded6d5ea77cdae0c01f384fc306e12fe5973f00d)
- [CON skills](https://github.com/con/skills/tree/493d7e83865ed5c21a8f4e5b02e72fc47bce5bb3)

### Vendor behavior

- [OpenAI Codex and ChatGPT skills](https://developers.openai.com/codex/skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [GitHub Copilot skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/)
- [Cursor skills](https://cursor.com/docs/skills)
- [OpenCode skills](https://opencode.ai/docs/skills)
