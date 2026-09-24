---
name: commit-provenance
description: Resolve the exact active Codex Desktop and agent-runtime versions, model identifier, and reasoning effort for commit provenance. Use immediately before every Codex-authored git commit or whenever a commit trailer requires model, tool, or reasoning-effort attribution. Also use when choosing the original repository or a fork for a GitHub push, opening a pull request, or changing its draft status.
---

# Commit Provenance

Run `scripts/resolve.sh` immediately before creating the commit.
Do not reuse a previous result after a model or effort switch.

The script resolves the current task from `CODEX_THREAD_ID`, then reads the latest `turn_context` in that task's local session transcript.
If no transcript exists (as observed for side conversations), it reads the local `logs_2.sqlite` database in read-only mode using the bundled Python 3 helper.
The fallback requires matching thread and turn metadata from the last five minutes, selects the newest matching record, and reports its turn ID on stderr.
It never borrows a parent thread's settings.
Missing, stale, or unrecognized metadata causes failure; do not substitute saved defaults.
Runtime logs are an internal format: revalidate this fallback after format changes.
Treat the resolved per-turn evidence as authoritative for model and reasoning effort.
Never infer either from prose or use `config.toml` as the current-turn value.

## Commit trailer

Use the script's two output trailers unchanged:

```text
Co-Authored-By: Codex Desktop <desktop-version> (runtime codex-cli <runtime-version>) / <model> <codex@openai.com>
Codex-Reasoning-Effort: <effort>
```

If the script cannot identify every required value, stop and ask the user; do not create the commit with guessed provenance.
Preserve any stricter repository commit-message requirements.

## Pull request draft status

Always open pull requests as drafts, using `gh pr create --draft` or the equivalent API or UI setting.
The user is responsible for deciding when a pull request is ready to merge or should no longer be a draft.
Promote a draft only in response to an explicit human instruction for that pull request.
Completed implementation, passing checks, favorable reviews, and general instructions to finish or publish work do not authorize promotion.
Keep the pull request in draft status when reporting completion unless that explicit instruction has been given.

## GitHub write transport

Prefer a branch in the original repository for an authorized push or pull request, unless the user explicitly requests a fork.
Identify that repository from the remote URLs and PR target; do not assume a remote named `origin` is the original repository.
Attempt the authorized branch push there over SSH before creating or selecting a fork, unless current evidence already shows that the active credential lacks push access to that exact repository.
Use a fork only after that repository's push permission is denied or a permission check confirms that push access is absent.
An existing fork, or denied access to another repository in the same organization, is not evidence that a fork is required here.
Do not treat network failures, branch protection, or non-fast-forward rejection as missing repository push access; address the actual cause instead.

Use this provenance procedure together with the user-level Git transport instruction.
For GitHub Git writes—publishing a branch, pushing a commit, or updating a ref—use the configured SSH credential and an SSH remote such as `git@github.com:OWNER/REPO.git` whenever available.

Before a write:

1. Inspect the fetch and push URLs with `git remote -v` or `git remote get-url --push <remote>`.
2. If the push URL is HTTPS, use the equivalent SSH URL explicitly or configure a local SSH push URL when that is appropriate for the repository.
3. Do not retry an HTTPS write after an authentication or scope failure merely because the commit itself is valid.
4. If SSH authentication is unavailable, stop and report the write blocker; do not silently fall back to a credential known to lack write scope.

This transport rule does not authorize pushing, opening a pull request, or changing a remote when the user did not request that operation.
It prevents a requested GitHub write from wasting retries against the wrong credential.
