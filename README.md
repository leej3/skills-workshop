# Skills Workshop

Agent skills, discovery, and review of how those skills work in practice.
Keep the custom layer thin: use APM for installation, AgentsView for reviewing agent work, and small tools where they help.

Install a [skill](.apm/skills/) with [APM](https://microsoft.github.io/apm/): `apm install leej3/skills-workshop --skill skills-workshop --target agent-skills`.

## Development

```console
pixi run setup-skills
pixi run validate
```

AgentsView and the archive tools use their own [Pixi environment](environments/archive/pixi.toml).

See [development guidance](AGENTS.md) and the [discovery reference](docs/agents/workshop-reference.md).

Workshop-owned files are [MIT licensed](LICENSE), with licensing metadata in [REUSE.toml](REUSE.toml) and [LICENSES/](LICENSES/).
Upstream skills retain [their own licenses](THIRD_PARTY_NOTICES.md).
