# Skills workshop

This repository is the control plane for developing, installing, and
contributing agent skills without mixing local work with upstream code.

## Layout

- `skills/`: skills authored or substantially adapted here
- `upstreams/`: read-only, commit-pinned upstream collections
- `profiles/core.toml`: small host-wide selection linked into `~/.agents/skills`
- `clusters/`: related selections copied into individual projects
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
python3 scripts/manage_skills.py configure-upstreams
python3 scripts/inventory.py
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
python3 scripts/manage_skills.py link-core
```

A cluster is a reusable selection, not an installation. Applying one copies
complete skill directories into a project's `.agents/skills` directory:

```console
python3 scripts/manage_skills.py apply-cluster project-maintenance ../my-project
python3 scripts/manage_skills.py apply-cluster datalad-core ../my-dataset
```

The target project receives `.agents/skills.lock.json` with source paths,
content hashes, upstream URLs, and pinned revisions. Commit both `.agents/skills/`
and the lock file in that project. It can then use the skills without this
workshop checkout. Reapply with `--replace` to update a copied cluster after
reviewing upstream changes.

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
