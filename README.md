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
pixi run --locked setup-skills
pixi run configure-upstreams
pixi run setup-agent
pixi run setup-agent --apply
pixi run workshop doctor
pixi run workshop validate
```

`setup-agent` previews changes; `--apply` makes them:

- Restores the two control skills through a dedicated user-owned APM manifest and lock in `~/.local/share/skills-workshop/control-install/`.
- Links those deployed controls into user discovery, migrating recognized legacy links.
- Sets this checkout as the memory destination in `~/.config/skills-workshop/config.json`.
- Adds a marked workflow block to `~/.codex/AGENTS.md`, respecting `CODEX_HOME` when set.

Setup preserves unrelated settings and refuses conflicting skill installations or a different configured checkout.
Keep the checkout at this location: the installed skills link to it.
The tooling uses this checkout's locked Pixi environment; APM installs skill content, not the tooling runtime.
Setup installs no runtime hooks and publishes nothing.
The first setup pins `leej3/skills-workshop/controls` at this checkout's HEAD, which must already be published; later setups restore the existing user lock.
To update deliberately, pass `--source leej3/skills-workshop/controls#FULL_COMMIT_SHA`.
`configure-upstreams` configures the catalog remotes listed in [registry.toml](registry.toml), including the maintainer's forks; it does not create forks for you.

For your own ongoing history, clone your fork or private copy instead.
Existing memory records describe the maintainer's experience, not your own use.

## User activation modes

From the checkout, run:

```console
pixi run workshop enable
pixi run workshop manual
pixi run workshop disable
pixi run workshop status
```

On enables proactive discovery and feedback guidance.
Manual keeps the controls discoverable but instructs agents to invoke them only when explicitly requested, including feedback collection.
Off removes only owned control links and retains a small instruction block with working status and reactivation commands.
Memory, tooling, runtime, the user APM installation, and project dependencies stay intact in every mode.
This is an agent-guidance policy, not a runtime permission boundary; start a new task or reload the client after changing mode.
Previously loaded instructions cannot be removed from an active conversation.

`setup-agent --apply` preserves the saved mode (on for a first installation).
Use `--mode on`, `--mode manual`, or `--mode off` to choose it explicitly.
Default setup is a read-only preview.
Foreign skill directories or links are never replaced; conflicts are reported before activation changes.
The managed block supersedes older Workshop lifecycle advice elsewhere in user guidance without rewriting unrelated instructions.
The adapter currently supports Codex user guidance and the shared `.agents/skills/` discovery directory; it does not configure other clients' private instruction files.

For a different working directory, use `pixi run --manifest-path /path/to/skills-workshop/pixi.toml workshop status` (substitute the desired command).
APM's shared `--global` install is deliberately separate: toggles change only discovery links, so an off-mode user installation still passes APM audit.
Project installations keep using their own manifest, lock, and frozen setup; they do not inherit the Workshop controls or user mode.

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
| The two Workshop control skills | `controls/skills/` source; APM installation and activation at user scope |
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

## Reproducible project skills

This checkout uses APM 0.31.0 through the locked Pixi environment.
Run `pixi run --locked setup-skills` before opening an agent task, and `pixi run --locked audit-skills` to verify it.
User setup is independent: `setup-agent` does not restore or change project dependencies.
First setup needs network access; private packages additionally need suitable Git credentials.

Reusable source is tracked in `.apm/skills/`: `duct`, `commit-provenance`, and `build-github-app`.
The root `apm.yml` publishes this collection and declares what APM may deploy.
Workshop's own setup generates ignored copies under `.agents/skills/` and records their hashes in `apm.lock.yaml`.
The Workshop controls live in the separate `controls/` APM package and are activated only at user scope.
Repo-specific working skills may still live directly under `.agents/skills/` as the fallback.
Existing user-level links keep pointing to their established `.agents/skills/` locations.

Other projects can select skills from this repository at an exact published commit:

```console
apm install leej3/skills-workshop#FULL_COMMIT_SHA --skill duct --target agent-skills --dry-run
apm install leej3/skills-workshop#FULL_COMMIT_SHA --skill duct --target agent-skills
```

Replace `FULL_COMMIT_SHA` with a reviewed 40-character commit SHA and run APM through the consumer's pinned environment.
Track its manifest, generated lock, environment/setup metadata, and instructions; ignore `apm_modules/` and the selected deployment directories.
Restore with `apm install --frozen`, then check `apm audit --ci`.
Bootstrap before opening an agent task; an AGENTS.md note cannot load missing skills automatically.

Edit reusable source only in this Workshop repository's `.apm/skills/`, then run `pixi run apm install` to regenerate the working copies and lock.
Downstream projects update only the requested source ref and generated dependency metadata.
Never patch or commit their installed copies.
`pixi run check-apm` tests full and selective consumption, fresh metadata-only restoration, and tamper detection.
CI also restores Workshop's own working copies and checks audit and Git cleanliness on each push.
A separate pinned `security` environment scans reusable source and audits its Python dependencies on pushes, PRs, and weekly.
Run `pixi run --locked -e security scan-skills` and `pixi run --locked -e security audit-dependencies` locally; that optional environment requires macOS 14+ or Linux with glibc 2.28+.

## Update and troubleshoot

After pulling changes into an existing checkout:

```console
git submodule update --init --recursive
pixi install --locked
pixi run --locked setup-skills
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
