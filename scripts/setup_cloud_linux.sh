#!/usr/bin/env bash
# Install pinned Pixi and restore Workshop environments and skills. No sign-in.
set -euo pipefail

if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    printf '%s\n' 'This setup supports Linux x86_64 only.' >&2
    exit 1
fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bin_dir="${SKILLS_WORKSHOP_BIN_DIR:-${SKILLS_MANAGER_BIN_DIR:-$HOME/.local/bin}}"
cache_root="$(dirname -- "$repo_root")/.cache/skills-workshop"
export PIXI_CACHE_DIR="${PIXI_CACHE_DIR:-$cache_root/pixi}"
export APM_CACHE_DIR="${APM_CACHE_DIR:-$cache_root/apm}"
export XDG_CACHE_HOME="$cache_root"

case "$bin_dir" in
    /*) ;;
    *) printf '%s\n' 'The installation bin directory must be an absolute path.' >&2; exit 1 ;;
esac
mkdir -p -- "$bin_dir" "$PIXI_CACHE_DIR" "$APM_CACHE_DIR" "$cache_root"
if ! mkdir -p -- "$HOME/.apm"; then
    printf '%s\n' 'APM requires a writable ~/.apm during installation; run this in the environment Install script before task sandboxing.' >&2
    exit 1
fi

pixi_version=0.83.0
archive_sha256=064f371e692aaa3400ac581c89da2843c91437f20c2d9155395a5d0037f33551
binary_sha256=50571451e96f4a82cf675cd83baaf66fff9b718f0aaf153900b9faf4c29bd401
archive_name=pixi-x86_64-unknown-linux-musl.tar.gz
archive_url="https://github.com/prefix-dev/pixi/releases/download/v$pixi_version/$archive_name"
pixi_bin="$bin_dir/pixi"

has_digest() {
    [[ -f "$1" ]] && [[ "$(sha256sum -- "$1" | cut -d ' ' -f 1)" == "$2" ]]
}

if ! has_digest "$pixi_bin" "$binary_sha256"; then
    bootstrap_cache="$PIXI_CACHE_DIR/bootstrap/v$pixi_version"
    mkdir -p -- "$bootstrap_cache"
    archive="$bootstrap_cache/$archive_name"
    temp_dir=$(mktemp -d "$bootstrap_cache/install.XXXXXXXX")
    trap 'rm -rf -- "$temp_dir"' EXIT
    if ! has_digest "$archive" "$archive_sha256"; then
        curl --fail --show-error --silent --location \
            --connect-timeout 20 --max-time 180 \
            "$archive_url" --output "$temp_dir/$archive_name"
        has_digest "$temp_dir/$archive_name" "$archive_sha256" || {
            printf '%s\n' 'Official Pixi archive checksum mismatch; refusing installation.' >&2
            exit 1
        }
        mv -- "$temp_dir/$archive_name" "$archive"
    fi
    tar -xzf "$archive" -C "$temp_dir" pixi
    has_digest "$temp_dir/pixi" "$binary_sha256" || {
        printf '%s\n' 'Extracted Pixi checksum mismatch; refusing installation.' >&2
        exit 1
    }
    install -m 0755 -- "$temp_dir/pixi" "$pixi_bin"
fi
export PATH="$bin_dir:$PATH"
"$pixi_bin" --version

"$pixi_bin" install --locked --manifest-path "$repo_root/pixi.toml"
# Source checkout uses the host's existing Git credentials and TLS trust.
# The workflow tools themselves are installed and verified through Pixi below.
git -C "$repo_root" submodule update --init --recursive
"$pixi_bin" run --locked --manifest-path "$repo_root/pixi.toml" setup-skills
"$pixi_bin" run --locked --manifest-path "$repo_root/pixi.toml" audit-skills
"$pixi_bin" run --locked --manifest-path "$repo_root/environments/archive/pixi.toml" agentsview version --json

# A setup subprocess cannot change its parent's PATH. Leave a sourceable,
# Git-ignored activation file for subsequent task shells instead of editing profiles.
mkdir -p -- "$repo_root/.pixi"
{
    printf 'export PATH=%q:"$PATH"\n' "$bin_dir"
    printf 'export PIXI_CACHE_DIR=%q\n' "$PIXI_CACHE_DIR"
    printf 'export APM_CACHE_DIR=%q\n' "$APM_CACHE_DIR"
    printf 'export XDG_CACHE_HOME=%q\n' "$XDG_CACHE_HOME"
} > "$repo_root/.pixi/cloud-env.sh"
printf 'Ready. In subsequent shells: source %q\n' "$repo_root/.pixi/cloud-env.sh"
