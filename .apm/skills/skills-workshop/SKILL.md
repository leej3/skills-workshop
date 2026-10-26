---
name: skills-workshop
description: Find and compare agent skills, inspect candidate sources, and guide installation with APM. Use for skill discovery, source review, and choosing reusable project skills.
---

# Skills Workshop

Search skill sources and inspect candidates, then use APM directly for installation.
Use the available `skills-workshop` CLI, or run `pixi run workshop` from an existing checkout identified in project or user guidance.
For a checkout elsewhere, use `pixi run --manifest-path /path/to/checkout/pixi.toml workshop`.
APM installs these instructions; the discovery CLI and provider tools must be available separately.
If Workshop tooling is unavailable, use available source tools directly and report the search limits.

## Find candidates

```console
skills-workshop doctor
skills-workshop find "capability"
```

Search covers pinned local catalogs, Workshop skills, configured installed-skill roots, and public providers: ASM, GitHub `gh skill`, and Vercel `skills`.
Only the supplied query goes to public providers.
Use `--offline` for local search and `--provider` to narrow the providers.
Report sources searched, unavailable providers, and freshness limitations; a failed provider does not invalidate other results.

Compare candidates by fit, maintenance, required tools, licensing, and completeness of their instructions and resources.
An explicit request to install a named skill supplies the selection; useful alternatives are advisory and should not replace it silently or block it.
For an open-ended request, recommend suitable choices unless the user has authorized you to choose.

## Inspect the source

```console
skills-workshop preview owner/repository skill-name@commit-sha
```

Read the complete skill and required resources before recommending adoption.
Check whether scripts, sibling skills, or vendor-specific features are required and available in the intended environment.
Popularity or successful installation does not establish that a skill suits the user's work.

For catalog maintenance, run these commands from its Workshop checkout:

```console
pixi run upstream-status --fetch
pixi run upstream-update source-name
pixi run upstream-update source-name --apply
```

The status command refreshes remote-tracking refs without moving catalog checkouts.
Updates are previews until `--apply`; review the plan before applying and commit the gitlink when repository policy requires it.
Do not move a catalog checkout as a side effect of searching.

## Adopt through APM

Point APM at the selected repository and revision in the consuming project's environment.
Read [the adoption reference](references/workflow.md) for installation, restoration, and audit commands.
Keep project-specific skills in that project's tracked `.agents/skills/` and edit reusable skills in their source repository.
Install skills at the project or user scope requested by the user.
