# A `find-skill` interface without another skill installer

This is a proposed alternative for
[CON skills issue #5](https://github.com/con/skills/issues/5). It is a draft for
review, not a posted issue comment.

## Decision

Adopt the interaction proposed in issue #5, but not its installer design.

A single agent-facing `find-skill` entry point is valuable. It should search
remembered skills and existing discovery services, help inspect candidates,
and delegate accepted project dependencies to APM. The only novel persistent
layer should be source-agnostic cross-project memory: what was considered,
used, useful, rejected, evaluated, or contributed upstream.

In short: preserve the interface; replace the hand-maintained catalog and
installer with existing tools.

## What the issue gets right

The issue identifies a coherent workflow:

- ask for a capability in task language;
- search concise “when to use” metadata before loading full instructions;
- inspect promising skills;
- use one temporarily or add it to a project; and
- retain enough source information to find it or update it later.

That staged lookup mirrors the
[Agent Skills progressive-disclosure model](https://agentskills.io/specification):
clients first see names and descriptions, load `SKILL.md` only after selection,
and read supporting resources on demand. A small Markdown index is transparent,
Git-native, editable without special software, useful offline, and entirely
reasonable for a small trusted community.

## Where the lightweight design grows

It remains lightweight only while every entry is trusted, small, single-file,
unambiguous, and manually maintained. Real use introduces familiar
package-manager details:

| Initial operation | Details that eventually appear |
| --- | --- |
| Fetch raw text | Multi-file skill trees, relative resources, executable modes, archives, and symlinks |
| Remember a URL | Renames, forks, subpaths, private sources, redirects, moved origins, and immutable revisions |
| Install into a project | Agent destinations, project/user scope, collisions, ownership, and portable clone behavior |
| Update from source | Revision choice, digests, local edits, conflicts, rollback, and pruning |
| Search an index | Ranking, aliases, duplicates, stale descriptions, provider failures, and authentication |
| Trust a result | Preview, prompt injection, hidden content, scripts, archive traversal, licensing, and provenance |
| Reproduce a project | A committed manifest, transitive resolution, pinned artifacts, and drift detection |

These are not invented edge cases. Existing tools already implement much of
the surface:

- [`gh skill search`](https://cli.github.com/manual/gh_skill_search) returns
  structured GitHub results and
  [`gh skill preview`](https://cli.github.com/manual/gh_skill_preview) inspects a
  complete candidate before installation.
- [ASM](https://github.com/luongnv89/asm) provides catalog search,
  machine-readable output, inspection, cross-provider inventory, and advisory
  checks.
- [Vercel `skills`](https://github.com/vercel-labs/skills) provides keyword
  search, broad source handling, temporary use, and many agent destinations.
- [APM](https://microsoft.github.io/apm/) gives a downstream project a
  committed manifest, content-aware lock, target deployment, frozen replay,
  and integrity/drift audit.

Reimplementing those details behind a small wrapper would still be
reimplementation; the complexity would merely be hidden.

## Proposed boundary

| Concern | Authority |
| --- | --- |
| Intent-oriented interface for agents and humans | Workshop skill and CLI |
| Encountered skills, aliases, judgments, usage, ratings, evaluations, and contribution links | Workshop memory |
| Broad catalog discovery | ASM, `gh skill`, Vercel `skills`, and future providers |
| GitHub candidate preview | `gh skill preview` |
| Domain discovery | `/.well-known/agent-skills/index.json` through a supporting provider |
| Project dependency intent, lock, update, deployment, and audit | APM in the downstream project |
| Skill contents and development history | Ordinary Git repositories and forks |
| Large scientific data transport | DataLad only where the surrounding project already needs it |

There must be one writer per downstream concern. Discovery tools do not install
into APM-managed destinations. The workshop does not maintain a second
dependency lock or copy APM's resolved graph into memory.

Deleting the workshop must not make the APM project unreproducible. Deleting a
project's APM files must not leave enough workshop metadata to reconstruct
them.

## Agent-facing workflow

```text
intent
  -> search workshop memory
  -> query ASM, gh skill, and Vercel when needed
  -> inspect and compare candidates
  -> remember deliberate consideration
  -> delegate accepted dependency to project-local APM
  -> record actual use and outcome
  -> optionally evaluate or contribute upstream
```

The current interface begins with:

```console
pixi run workshop find "review a DataLad dataset for STAMPED compliance"
pixi run workshop find "review a DataLad dataset" --provider all
pixi run workshop preview <owner/repository> <skill-or-path@commit>
pixi run workshop consider <skill> --decision adopted --reason "..." \
  --asserted-kind human --asserted-by <person>
pixi run workshop install <apm-package> --project <project>
pixi run workshop audit <project>
pixi run workshop use <skill> --outcome success --rating 4 \
  --task "..." --invocation explicit --rationale "..." \
  --asserted-kind agent --asserted-by <agent>
pixi run workshop history <skill>
pixi run workshop where-used <skill>
```

Every delegated command is printed before execution. Provider failures remain
isolated so local memory and other providers can still answer. Search output is
not mirrored as another catalog; only a deliberately considered or used skill
enters durable memory.

If a selected source cannot be expressed in the pinned APM version, stop. Find
its Git source, package or fork it into an APM-consumable source, or record it as
blocked. Do not silently install it with a second manager.

## Cross-project memory is the custom value

The memory answers questions public catalogs and project locks cannot:

- “I used something like this before; where did it come from?”
- which fork/source was preferred and why;
- which projects declared or actually used it;
- task context, agent/vendor/version, outcome, and a contextual rating;
- controlled evaluation evidence, kept distinct from informal ratings;
- rejected candidates and reasons; and
- upstream issues, branches, pull requests, and contributions.

Strict versioned JSON and append-only events prevent this from becoming an
unmigratable prose corpus. A logical skill identity remains independent of any
one URL. Markdown, SQLite, or a web UI is a replaceable view.

## DataLad's appropriate role

DataLad can record content URLs and retrieve known content through Git-annex.
That is valuable for scientific datasets and large remote artifacts. See its
[file URL design](https://docs.datalad.org/en/latest/design/file_url_handling.html)
and [`addurls` behavior](https://docs.datalad.org/en/latest/generated/man/datalad-addurls.html).

It does not define skill identity, dependency resolution, agent destinations,
lock semantics, update conflicts, or audit. It should remain optional transport
inside projects that independently need DataLad, not the default installer for
small Git-backed skill trees.

## `.well-known` discovery

The Cloudflare
[Agent Skills Discovery RFC](https://github.com/cloudflare/agent-skills-discovery-rfc)
defines `/.well-known/agent-skills/index.json` with a schema identifier,
artifact URLs, types, and SHA-256 digests. It is a strong non-GitHub source
type. It is also a pre-1.0 draft whose v0.2 shape broke v0.1.

Vercel `skills` already consumes v0.2 and handles digest and archive safety.
Use that implementation now; do not internalize the discovery schema or write
another parser until a second use case requires programmatic access.

## Trade-offs

The composed approach costs more initial orientation than one Markdown index:

- multiple external tools evolve independently;
- formats and ranking differ;
- `gh skill` is public preview;
- Vercel's search output is human-oriented;
- APM may not support every source immediately; and
- useful history requires a deliberate recording habit.

Those costs are bounded with pinned versions, a `doctor` command, dry runs,
transparent delegation, strict portable memory, and provider isolation. They
are smaller than owning another installer indefinitely.

The original lightweight design remains reasonable if its permanent scope is
a small trusted index for one-off reading with no reproducible project state.
Once updates, multiple sources, multi-file skills, or shared projects matter,
the composed approach is safer and cheaper to maintain.

## Issue-ready proposal

Build the proposed `find-skill` skill as an orchestrator:

1. search source-agnostic local memory first;
2. fan out to ASM, `gh skill`, Vercel, and later providers;
3. preview and compare without writing project files;
4. record only considered or used candidates;
5. delegate accepted project dependencies to APM;
6. keep source development and contribution in Git; and
7. use DataLad only when its data-transport semantics are independently useful.

This preserves the simple agent request surface in issue #5 without rebuilding
discovery, installation, locking, and audit underneath it.
