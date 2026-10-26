# Discovery reference

Run these commands from a Workshop checkout; Pixi prepares the environment automatically.
For installing reusable skills, use [APM directly](../../README.md).

## Search and preview

```console
pixi run workshop find "release review"
pixi run workshop find "release review" --offline
pixi run workshop preview owner/repository skill-name@commit-sha
pixi run workshop doctor
```

`find` searches the pinned catalogs in [registry.toml](../../registry.toml), declared Workshop skill sources, and configured installed-skill directories.
It matches full `SKILL.md` contents and reports source revisions.
Without `--offline`, it also queries ASM, GitHub `gh skill`, and Vercel `skills`.
Only the search query is sent to public providers.
A failed provider does not discard other results.

Use `--provider asm`, `--provider github`, or `--provider vercel` for a narrower search.
`--json` returns structured results, `--tsv` supports table tools, and `--dry-run` prints the external commands without running them.
An empty offline query lists candidates.

`preview` delegates repository inspection to `gh skill`.
`doctor` reports tool versions and responsibilities; it does not verify provider authentication or network access.
Search and preview do not install skills or record usage.

## Sources and review

Initialize catalogs with `git submodule update --init --recursive`, then configure their remotes:

```console
pixi run configure-upstreams
pixi run upstream-status --fetch
pixi run upstream-update scientific-agent-skills
```

`configure-upstreams` sets `origin` and `upstream` from `registry.toml`.
Status fetches remote-tracking refs without moving the checked-out sources.
Updates are previews until `--apply` is supplied; review and commit the resulting gitlink change.

`pixi run inventory` lists sources and installed skills.
`inventory-vd` opens the generated table in VisiData.
`trust-inventory` and `review-skill` expose source signals and review metadata; those signals alone do not establish safety or effectiveness.
Generated inventories and review records stay in the external user state directory, selected by `SKILLS_MANAGER_STATE_HOME` (default: `$XDG_STATE_HOME/skills-manager` or `~/.local/state/skills-manager`).
These legacy names preserve access to existing review records.
