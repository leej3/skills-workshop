# Adopt a skill with APM

Run APM in the consuming project's pinned environment and follow its `AGENTS.md` guidance.
Use the selected repository or package coordinate and a reviewed full commit SHA:

```console
apm install owner/repository#FULL_COMMIT_SHA --skill skill-name --target agent-skills --dry-run
apm install owner/repository#FULL_COMMIT_SHA --skill skill-name --target agent-skills
apm audit --ci
```

Preview the selected skills and target paths before applying.
A named installation request authorizes its normal installation; resolve source or ownership conflicts without replacing unrelated files.
Use the source formats supported by the installed APM version rather than adding a Workshop installer or requiring extra packaging.

Track the consumer's `apm.yml`, generated lock, and setup instructions.
Ignore `apm_modules/` and APM-owned deployment paths; preserve tracked project-authored skills.
Restore dependencies with `apm install --frozen` and verify them with `apm audit --ci`.
Run setup before a new agent session so installed skills can be discovered.

Project-specific skills can remain ordinary tracked `.agents/skills/` trees.
Reusable skill changes belong in their source repository; update consumers through APM rather than editing generated copies.
Each project remains usable without the Workshop discovery tooling.
