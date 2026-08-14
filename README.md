# Skills workshop

This repository is the control plane for developing, installing, and
contributing agent skills without mixing local work with upstream code.

## Layout

- `skills/`: skills authored or substantially adapted here
- `upstreams/`: read-only, commit-pinned upstream collections
- `profiles/core.toml`: small host-wide selection linked into `~/.agents/skills`
- `clusters/`: related selections copied into individual projects
- `materializations/`: workshop-owned locks coordinating downstream skill copies
- `registry.toml`: upstream purpose, policy, and local skill roots
- `scripts/inventory.py`: reproducible inventory of installed and upstream skills
- `scripts/manage_skills.py`: apply the core profile or materialize a cluster
- `docs/stamped-use-cases.md`: candidate work for stamped-agent-skills issue #2

The upstream checkouts are Git submodules. This preserves exact provenance and
makes it possible to compare or contribute changes in the source repository
instead of silently copying and diverging.

## Start here

Clone with upstreams:

```console
git clone --recurse-submodules <this-repository>
```

For an existing checkout:

```console
git submodule update --init --recursive
pixi install --locked
pixi run configure-upstreams
pixi run inventory
```

The scientific collection is large; its first checkout can take longer than
the other two. The inventory still reports the pinned revision when a submodule
has not been initialized and marks that source with `initialized: false`.

The inventory is written to `inventory/installed-skills.json`. It is a local
report and is intentionally ignored because installed skills and absolute host
paths vary between machines.

## Profiles and clusters

Keep `profiles/core.toml` intentionally small. Link its skills globally:

```console
pixi run link-core
```

A cluster is a reusable selection, not an installation. Applying one copies
complete skill directories into a project's `.agents/skills` directory:

```console
pixi run apply-cluster project-maintenance ../my-project
pixi run apply-cluster datalad-core ../my-dataset
```

The target receives only standard `.agents/skills/<name>` directories and can
develop those copies independently. This workshop writes the coordination lock
to `materializations/<project-id>--<cluster>.lock.json`, recording the cluster,
downstream Git remote, content hashes, upstream URLs, and pinned revisions.
Commit that lock here, not in the downstream project. Separate locks allow a
project to use multiple clusters. The project ID defaults to its `origin` remote;
use `--project-id <name>` when the project has no remote or needs a stable
override.

When project and workshop copies differ, choose one of four explicit policies:

- `--conflict abort` (default): report every conflict and change nothing;
- `--conflict record`: preserve both copies and update the workshop lock with
  separate source and project hashes marked `diverged`;
- `--conflict back-propagate`: copy project changes into the workshop source and
  update the lock—review and commit the resulting first-party or submodule work;
- `--conflict overwrite`: replace the project copy from the workshop and update
  the lock.

For example:

```console
pixi run apply-cluster datalad-core ../my-dataset --conflict record
```

Locks retain both fork (`origin`) and canonical (`upstream`) URLs and mark a
workshop source dirty after back-propagation until its changes are committed in
the appropriate first-party repository or upstream fork.

## Development environment

Pixi owns the workshop's Python and command-line dependencies. `pixi.lock` is
committed so every checkout resolves the same environment. Common tasks are:

```console
pixi run inventory
pixi run configure-upstreams
pixi run validate
pixi run format
```

Use `pixi add <package>` when a helper script gains a runtime dependency, then
commit both `pixi.toml` and the updated `pixi.lock`.

## Working agreement

1. Search the upstream collections before starting a new skill.
2. Prefer contributing a generally useful improvement to its original project.
3. Put genuinely personal or cross-upstream experiments in `skills/`.
4. Record provenance when adapting an upstream skill; do not copy code without
   checking its license.
5. Keep only selected skills installed. Review `SKILL.md` and bundled scripts
   before enabling third-party skills.
6. Validate and forward-test skills on realistic tasks before proposing them
   upstream.

Update one upstream deliberately with:

```console
git -C upstreams/<name> fetch
git -C upstreams/<name> switch --detach <tag-or-commit>
git add upstreams/<name>
```

This makes every upstream update visible as a single pinned commit change.

Each tracked collection follows the usual fork workflow:

- `origin` is the `leej3` fork used for development branches;
- `upstream` is the canonical community repository used to fetch updates;
- `.gitmodules` points to the fork so a new workshop clone follows your copy;
- `registry.toml` records both URLs, and `configure-upstreams` restores the
  two-remote layout after cloning.

Develop a contribution inside the relevant submodule, push its branch to
`origin`, and open the pull request against `upstream`. After the upstream
change merges, update the submodule pin to the canonical merged commit.
