# Skills Workshop working agreement

Keep reusable skills and discovery tooling here; APM owns dependency installation and locks.
Read applicable nested `AGENTS.md` files before editing.
Explicit user instructions take precedence.

## Development

- Run `pixi run setup-skills`; Pixi prepares the environment automatically.
- Run `pixi run validate` before committing code changes.
  It checks lint, formatting, compilation, tests and REUSE licensing.
- For focused iteration, use `pixi run pytest -q tests/<test_file>.py` and `pixi run format`.
- Run `pixi run check-apm` for reusable package changes.
- Format changed prose with `pixi run pre-commit run snapper --files <paths>`.

The root Pixi environment is for Workshop development.
Use `environments/archive/pixi.toml` for AgentsView, DataLad, git-annex, and rclone.
Keep command examples synchronized with the relevant manifest and CI.
Keep setup and overview material in `README.md`.
Commit intentional changes after validation; stage explicit paths and leave unrelated work untouched.
Push only when authorized.

## Skills and sources

Edit reusable skill source in `.apm/skills/`; APM-owned deployments are generated and Git-ignored.
Refresh the deployment lock with `pixi run apm install` and check it with `pixi run audit-skills`.
Run setup before a new agent session so installed skills can be discovered.

The `skills-workshop` discovery skill is published in the same APM package as the other reusable skills.
Use it when explicitly requested.
Preserve upstream Git submodule pins and their independent licenses; never flatten source collections into this repository.

## Data boundaries

Keep real conversations, archive contents, logs, credentials, indexes, and operation configuration outside this code checkout.
Preserve existing external data, settings, Git refs, and remote payloads when retiring code.
Do not collect feedback or activate capture.
Hook installation or trust changes require an explicit deployment request.

Use actual agent work for analysis and evaluation.
Isolated software fixtures are permitted for tests, but must never enter archives or be presented as evaluation evidence.
