# Skills Workshop

Skills Workshop remembers which agent skills you considered, installed, and used across projects—and what helped or failed.
It searches local catalogs and public providers, delegates external skill installation to APM, and stores observations as versioned JSON in Git.

## Install for Codex

Prerequisites: Git and [Pixi](https://pixi.sh).
The lockfile supports macOS (Apple Silicon and Intel) and Linux x86-64.
Native Linux ARM64 and Windows are not currently included.

```console
git clone --recurse-submodules https://github.com/leej3/skills-workshop.git
cd skills-workshop
pixi install --locked
pixi run configure-upstreams
pixi run setup-agent
pixi run setup-agent --apply
pixi run workshop doctor
pixi run workshop validate
```

`setup-agent` previews changes; `--apply` makes them:

- Links the `skills-workshop` and `workshop-feedback` control skills into `~/.agents/skills/` (or reuses matching links under `~/.codex/skills/`).
- Sets this checkout as the memory destination in `~/.config/skills-workshop/config.json`.
- Adds a marked workflow block to `~/.codex/AGENTS.md`, respecting `CODEX_HOME` when set.

Setup preserves unrelated settings and refuses conflicting skill installations or a different configured checkout.
Keep the checkout at this location: the installed skills link to it.
Setup installs no runtime hooks and publishes nothing.
`configure-upstreams` configures the catalog remotes listed in [registry.toml](registry.toml), including the maintainer's forks; it does not create forks for you.

For your own ongoing history, clone your fork or private copy instead.
Existing memory records describe the maintainer's experience, not your own use.

## Use it

Start a new Codex task in the project you are working on and ask:

> Use $skills-workshop to find a skill for reviewing this project's releases.

The agent searches remembered skills, pinned local catalogs, and public providers.
After material skill use, `workshop-feedback` writes a schema-validated concise baseline record.
Routine records are shareable; a private overlay holds sensitive fields and classification reasons.
Exceptional lessons are grouped and prioritized, with shareable records committed in batches.
See [local feedback and learning](docs/agents/local-feedback.md) for the hook, aggregates, and publication boundary.
The installed instruction asks the agent to do this, but it is not an automatic runtime hook.

> Use $skills-workshop to recall which skills helped with release reviews.

You can also use the CLI from this checkout:

```console
pixi run workshop find "release review"
pixi run workshop find "release review" --offline
pixi run workshop recall "release review"
pixi run workshop insights --since YYYY-MM-DD
```

Replace `YYYY-MM-DD` with a date.
Public discovery uses pinned ASM and Vercel commands through `npx`, plus `gh skill`; it requires network access and GitHub search may require `pixi run gh auth login`.
Offline search needs neither.
`doctor` reports tool versions; it does not verify provider authentication or network access.
Only the supplied public query is sent to discovery providers.

## Where skills and memory live

| Item | Owner and location |
| --- | --- |
| The two Workshop control skills | This checkout, linked at user scope |
| A project's own working skills | That project's `.agents/skills/` |
| External reusable skill dependencies | That project's APM manifest and lock |
| Decisions, use, outcomes, and contribution links | This checkout's `memory/` |
| Search catalogs | Pinned Git submodules under `upstreams/` |

Workshop is not a package manager.
Projects with only their own skills need no APM setup.
External dependencies use APM for installation and audit; Workshop retains cross-project evidence.
Removing Workshop leaves project skills usable.
Searching or installing a skill does not count as evidence that it helped.

The catalogs cover [OpenAI](https://github.com/openai/skills), [Anthropic](https://github.com/anthropics/skills), [K-Dense](https://github.com/K-Dense-AI/scientific-agent-skills), [NiPreps](https://github.com/nipreps/skills-comm), and [CON](https://github.com/con/skills).
They are discovery sources, not a set of skills automatically installed in your projects.

## Update and troubleshoot

After pulling changes into an existing checkout:

```console
git submodule update --init --recursive
pixi install --locked
pixi run configure-upstreams
pixi run setup-agent
pixi run setup-agent --apply
pixi run workshop doctor
pixi run workshop validate
```

- **Setup conflict:** inspect the reported path and reconcile the existing installation or configured checkout before retrying.
  Setup will not overwrite it.
- **Catalog missing:** run the submodule command above.
- **Public search unavailable:** use `--offline`, then check network access and GitHub authentication.
  Successful results survive individual provider failures.
- **Another agent host:** install both control skill directories at user scope, configure the checkout, and add equivalent global guidance as described in the [feedback reference](docs/agents/workshop-reference.md#lightweight-feedback-across-projects).
  The setup command currently targets Codex.

## Development and reference

```console
pixi run hooks-install
pixi run validate
```

`validate` runs lint, formatting checks, compilation, tests, and metadata/memory validation.
The Snapper pre-commit hook formats documentation.
Use `pixi run format` to format Python code.

- [Clean-container installation check](docs/agents/clean-install.md)
- [CLI and workflow reference](docs/agents/workshop-reference.md)
- [Skill-management executive summary](docs/skill-management-executive-summary.md)
- [Documentation policy](docs/README.md) and [research notes](docs/agents/README.md)

Workshop code is [MIT licensed](LICENSE).
Upstream skills retain their own terms.
