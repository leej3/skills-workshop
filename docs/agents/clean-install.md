# Clean installation check

Run the quickstart in a disposable Debian container with an empty, unprivileged user home.
No host home directory, credentials, Pixi environment, or package cache is mounted.
Docker must support Linux x86-64 containers (emulation is sufficient on Apple Silicon).

From the Workshop checkout, run:

```bash
docker run --rm --platform linux/amd64 \
  --mount "type=bind,src=$PWD/scripts/check_clean_install.sh,dst=/check.sh,readonly" \
  debian:bookworm-slim bash -c '
    set -euo pipefail
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends ca-certificates curl git
    useradd -m -s /bin/bash tester
    su tester -c '\''
      set -euo pipefail
      cd "$HOME"
      curl -fsSL https://github.com/prefix-dev/pixi/releases/download/v0.76.2/pixi-x86_64-unknown-linux-musl.tar.gz -o /tmp/pixi.tar.gz
      mkdir -p "$HOME/.local/bin"
      tar -xzf /tmp/pixi.tar.gz -C "$HOME/.local/bin"
      export PATH="$HOME/.local/bin:$PATH"
      git clone --recurse-submodules https://github.com/leej3/skills-workshop.git
      cd skills-workshop
      git rev-parse HEAD
      cp /check.sh scripts/check_clean_install.sh
      bash scripts/check_clean_install.sh
    '\''
  '
```

This tests the published default branch.
To test another published revision, check it out and run `git submodule update --init --recursive` before the check.
It does not include uncommitted local edits.
The script requires a fresh home; it intentionally fails if Workshop user configuration already exists.

The check covers locked dependency installation, submodule remote setup, read-only setup preview, both skill symlinks, memory configuration, the managed instruction block, byte-identical configuration after a second apply, tool reporting, offline discovery, feedback launcher resolution from another working directory, and the complete validation suite.
It also checks that installation has not modified tracked repository files.

## Verified on 2026-09-18

- Debian 12 x86-64 container under Docker on Apple Silicon, Pixi 0.76.2; public clone at `8d008c8d45062ddaba78789207a6e7d51168f638`.
- Recursive clone and `pixi install --locked` succeeded without credentials.
- Setup preview, apply, repeat apply, offline search, and memory validation passed.
- Pinned ASM 2.14.0 and Vercel skills 1.5.22 downloaded and ran through `npx`; `gh skill --help` and APM 0.29.0 also ran successfully.
  Provider search and authenticated operations were outside this installation check.
- All 163 tests passed, as did lint, formatting, compilation, and metadata checks.
  The host macOS checkout also passed the same validation suite.
- The original feedback example failed outside Pixi because no system `python` was installed.
  The corrected skill command uses `pixi run --manifest-path`.
  Running it from `/tmp` successfully recorded and validated a disposable observation in the container; that observation was not copied to real memory.

The tested revision has the same installer, runtime code, lockfile, and tests as the local review baseline; subsequent local commits only added memory records.
The feedback instruction correction was checked separately in that container.
This does not establish fresh macOS installation, native Linux ARM64 support, Codex UI skill discovery, authenticated GitHub search, or agent behavior.
No Codex runtime or lifecycle hook is installed in this test.
