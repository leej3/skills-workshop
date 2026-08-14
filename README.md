# Skills workshop

This repository is the control plane for discovering, reviewing, organizing,
developing, and contributing agent skills. Upstream code stays pinned and
traceable here; downstream projects receive ordinary skill directories and do
not need this workshop's tooling or metadata.

## Organization model

| Layer | Purpose | Tracked where |
| --- | --- | --- |
| Upstream collection | Search and contribute to existing work | `upstreams/` submodules plus `registry.toml` |
| Workshop skill | Author or substantially adapt a skill | `skills/` |
| Core profile | Small host-wide set linked into `~/.agents/skills` | `profiles/core.toml` |
| Cluster | Reusable, topic-oriented selection | `clusters/*.toml` |
| Project copy | Independently editable standard skills | `<project>/.agents/skills/` |
| Coordination lock | Separate workshop/project baselines and provenance | `materializations/*.lock.json` |

The important boundary is the last one: locks remain in this repository.
Projects can commit their copied skills, use them without the workshop, and
develop them independently. The workshop uses its own locks to recognize and
reconcile later changes.

These locations follow
[Codex's documented discovery scopes](https://developers.openai.com/codex/skills):
user skills live under `$HOME/.agents/skills`, while repository skills live
in `.agents/skills` from the working directory up to the repository root.

## Set up the workshop

Clone the repository and its pinned upstreams:

```console
git clone --recurse-submodules https://github.com/leej3/skills-workshop.git
cd skills-workshop
pixi install --locked
pixi run configure-upstreams
pixi run validate
```

For an existing checkout, initialize any missing submodules first:

```console
git submodule update --init --recursive
```

The scientific collection is large, so its first checkout can take longer.
Pixi owns the helper dependencies, and the committed `pixi.lock` keeps them
reproducible on macOS and Linux.

## Discover and review skills

Build the inventory, create a flattened table, or explore it in VisiData:

```console
pixi run inventory
pixi run inventory-table
pixi run inventory-vd
```

The table connects each skill to its collection, source, revision, clusters,
materialized projects, and synchronization state. Generated inventory files
are host-specific and intentionally ignored.

Before selecting a third-party skill, inspect its trust and licensing signals:

```console
pixi run trust-inventory
pixi run trust-inventory --format tsv --output inventory/trust.tsv
pixi run trust-vd
pixi run review-skill <source> <name> --state reviewed --reviewer <reviewer>
```

`policy/trust.toml` keys reviews by the stable identity `<source>#<name>` and
binds a completed review to the skill tree hash. A later content change makes
that review stale. License, executable, network, and credential results are
review cues, not security findings or compliance conclusions.

## Organize a core profile and clusters

Keep `profiles/core.toml` intentionally small: it is for skills useful in
nearly every project. Reconcile its links with:

```console
pixi run link-core
```

Clusters are reusable selections, not installations. They let the inventory
grow by topic while each project chooses only what it needs. Applying a cluster
copies complete skill directories into a project:

```console
pixi run apply-cluster project-maintenance ../my-project
pixi run apply-cluster datalad-core ../my-dataset
```

Materialization refuses skill trees containing symlinks. This prevents a link
from silently copying or exposing content outside the selected skill tree.
Codex supports the top-level skill-folder links made by `link-core`; the
restriction applies to links nested inside a copied skill tree.

## Import and organize project work

Use the terminal UI to bring independently developed project skills under
workshop coordination:

```console
pixi run import-project ../my-project
pixi run import-project ../my-project --project-id stable-project-name
```

The UI supports filtering, source-path suggestions, zero or more clusters per
skill, creation of a new cluster, and a scrollable project/diff preview. It
tracks mappings by source and name, so an unrelated skill with the same install
name is not silently removed from another cluster. On differing workshop and
project content, the import policy can stop, record both baselines, or
back-propagate the project copy.

The project ID normally derives from its `origin` remote. Use `--project-id`
when there is no remote or when the same stable identity must be retained after
a move.

## Inspect and reconcile changes

Inspect all workshop and project copies represented by the project's locks:

```console
pixi run skill-status ../my-project
pixi run skill-status ../my-project --diff
pixi run skill-status ../my-project --format json
pixi run skill-status ../my-project --plan overwrite --prune
```

Status distinguishes synchronized content, project-only changes,
workshop-only changes, changes on both sides, recorded divergence, missing
copies, lock collisions, obsolete selections, and fetched upstream updates.
Plans and diffs are always read-only.

Applying a cluster offers four explicit conflict policies:

- `abort`: do not proceed;
- `record`: preserve both copies and update the workshop metadata;
- `back-propagate`: replace the workshop source from the project copy;
- `overwrite`: force-update the project copy from the workshop.

For example:

```console
pixi run apply-cluster datalad-core ../my-dataset --dry-run --prune
pixi run apply-cluster datalad-core ../my-dataset \
  --conflict back-propagate --show-diff --prune
```

Omit `--conflict` for the interactive menu. Non-interactive use stops rather
than guessing. Normal reapplication never overwrites changed downstream
skills. Pruning only removes a previously managed skill that is no longer in
the cluster and still matches its recorded project baseline; changed, symlink,
and non-directory paths are refused.

Before replacement or pruning, the workshop makes a content-addressed local
backup under `.backups/`. Backups are ignored by Git and are an emergency
recovery aid rather than durable project history; review and commit intended
skill changes in their owning repository.

## Track forks and canonical upstreams

Each collection uses the same contribution layout:

- `origin` is the `leej3` fork used for development branches;
- `upstream` is the canonical community repository;
- `.gitmodules` points to the fork for reproducible clones;
- `registry.toml` records both URLs and the collection's role.

Inspect fork, canonical, and pinned revisions:

```console
pixi run upstream-status
pixi run upstream-status --fetch
```

Plan an update from the canonical upstream, then apply it only after review:

```console
pixi run upstream-update nipreps-skills-comm --fetch
pixi run upstream-update nipreps-skills-comm --apply
```

Updates are dry runs by default. Applying requires verified remotes, a clean
submodule, matching checkout/index/pin, an unchanged selected remote ref, and a
fast-forward target. It moves only the submodule checkout; the resulting
superproject gitlink still needs explicit review and commit.

Develop broadly useful changes on a branch inside the relevant submodule, push
that branch to its `origin`, and propose it to the canonical `upstream`. After
merge, advance this workshop's submodule pin to the canonical commit.

## Metadata and development

Cluster manifests use schema version 1. Materialization locks use version 2,
with separate source and project hashes and a `<source>#<name>` identity.
Schemas live under `schemas/`; runtime validation also protects every path and
field used by destructive operations.

```console
pixi run migrate-metadata          # report legacy locks
pixi run migrate-metadata-apply    # rewrite v1 locks to v2
pixi run validate-metadata
pixi run validate                  # lint, format check, compile, tests, metadata
pixi run format
```

GitHub Actions runs the same locked Pixi validation. When a helper gains a
dependency, use `pixi add <package>` and commit both `pixi.toml` and
`pixi.lock`.

## STAMPED work

[The STAMPED use-case map](docs/stamped-use-cases.md) turns
[stamped-agent-skills issue #2](https://github.com/stamped-principles/stamped-agent-skills/issues/2)
into bounded software-review, dataset-review, refactoring, dispatch, and skill-
evaluation candidates. This workshop supplies the discovery, composition,
provenance, trust, and forward-testing workflow around those skills without
making that coordination pattern a downstream requirement.

## Working agreement

1. Search the upstream collections before starting a new skill.
2. Review provenance, licensing, scripts, and external access before selection.
3. Prefer contributing generally useful behavior to its original project.
4. Keep personal or cross-upstream experiments in `skills/`.
5. Keep the core profile small and organize project needs into clusters.
6. Forward-test on realistic tasks before proposing a skill upstream.
