---
name: duct
description: Use con/duct for substantive project commands such as tests, builds, benchmarks, analyses, and batch jobs. Capture execution logs and resource usage in central per-project storage outside Git, inspect failures, and retain classified task captures in Workshop annex. Installed as part of Skills Workshop.
---

# Project execution with con/duct

This control is distributed and activated with Skills Workshop, not as an independent reusable skill.
Respect Workshop mode: in manual mode, capture to memory only when requested; in off mode do not invoke this control.
The con/duct executable itself remains independent.

Use duct by default in every project for tests, builds, analyses, benchmarks, reproductions, and other substantive commands.
Routine reads, navigation, Git inspection, and simple edits do not need wrapping.
Wrap the outer command once; do not instrument each child or nest wrappers.
This is an agent execution convention, not a shell alias or an automatic change to project CI.

## Run

Requires Python 3.9+ and the `duct` executable from `con-duct`.
Prefer an existing project environment; otherwise install the user tool with `uv tool install --python 3.12 con-duct`.
Check `duct --version` and `duct --help` for the installed version.
On macOS, use a release with Darwin sampling support (verified with 0.22.0).
An older Python may resolve 0.17.0, which invokes Linux `ps` flags on macOS and yields no resource samples; upgrade the tool environment rather than treating those missing measurements as successful monitoring.
The helper also finds the user executable at `~/.local/bin/duct`.
Optional plotting and inspection commands require `con-duct[all]`.

Resolve `scripts/run.py` relative to this skill directory.
Run from the intended working directory; the helper preserves it, argument boundaries, and duct's exit status by replacing itself with duct:

```bash
python /path/to/duct/scripts/run.py --message "Focused regression test" -- pixi run pytest -q
python /path/to/duct/scripts/run.py --message "Production build" -- npm run build
python /path/to/duct/scripts/run.py -- bash -o pipefail -c 'producer | consumer'
```

Use the project's Python launcher where `python` is unavailable.
A shell is only needed for shell syntax; never interpolate untrusted values into shell code.
The helper uses `--fail-time 0` so immediate failures remain inspectable, captures and forwards both streams, and prints the run directory on stderr.
Inspect `run_info.json` and relevant output after a failure.
Report the command result and log location; resource numbers are useful when relevant to the task.
Do not rerun a mutating command merely because monitoring failed or a summary is missing.
Establish whether the command started before choosing a recovery.

## Storage and identity

Default root: `${XDG_STATE_HOME:-~/.local/state}/con-duct/projects/`.
Each project has a directory containing unique UTC/UUID run directories. Each run contains `context.json`, duct's `run_info.json`, `run_usage.jsonl`, and captured `run_stdout`/`run_stderr` when produced.
No repository files or ignores are changed.
Logs stay until the user requests cleanup.
Retain completed task captures in the configured Workshop annex under standing task-log publication authorization; do not commit raw logs to the code repository.

The default project key is a readable name plus a hash of its resolved Git root (or working directory outside Git).
Worktrees and separate clones are distinct.
`context.json` records the original root, working directory, commit, and dirty state, not a source snapshot.
A commit plus a dirty flag cannot reproduce uncommitted code.
No remote URL or full environment dump is added by the helper.
The helper records `session_id` from `CODEX_THREAD_ID` (or `--session-id`) and optional `task_id` from `WORKSHOP_TASK_ID` (or `--task-id`) to support explicit capture linkage.
Unset identities remain null; timestamps and project paths alone do not prove ownership.

Use `--project /path/to/root` to group a non-Git project's subdirectories.
For a durable identity across relocated checkouts or machines, set `--project-id my-project` (or `DUCT_PROJECT_ID`) consistently.
This deliberately groups clones/worktrees under that identifier while each run keeps its original context.
Without an explicit ID, relocation creates a new bucket; the old logs remain discoverable by their context.
Use `--store /absolute/path` (or `DUCT_STORE_ROOT`) to relocate central storage.
The helper's explicit prefix overrides `DUCT_OUTPUT_PREFIX` and duct configuration.

## Export or migrate

Copy complete, finished run directories, including `context.json`, to a chosen destination.
Use `shutil.copytree(source, destination)` with a new destination, or an equivalent non-overwriting copy; keep the originals until verified.
Compare relative filenames and SHA-256 digests after copying.
For full migration, copy the central tree, verify it, then select the new root with `DUCT_STORE_ROOT`.
Preserve project IDs and run directory names.

Historical absolute paths inside JSON are provenance; do not rewrite them just to make an export look local.
Read the copied files directly if a viewer follows old paths.
A project-local export remains untracked by default: use the local Git exclude file if needed, and track or publish only explicitly selected, reviewed artifacts.
Export is not permission to commit raw logs.

## Exceptions and interpretation

- Commands and captured streams can contain sensitive data.
  Keep secrets out of arguments and messages.
  `--capture none` disables stream files but duct still records command metadata; skip instrumentation if metadata itself is sensitive.
  Review logs before sharing.
  Central directories are private on creation.
- Interactive programs, authentication flows, and terminal-dependent commands may need plain execution.
  Duct uses pipes and normally a new session; changing session mode does not turn pipes into a terminal.
  Explain a necessary bypass.
- Sampling can miss short peaks; missing samples are unknown, not zero.
  Do not rerun expensive work just to obtain samples.
  Session-detached children, remote jobs, and containers may not be fully measured, and monitoring ends when the primary process exits.
  Avoid claiming complete accounting in those cases.
- If duct is unavailable or breaks command semantics, report the limitation and use an appropriate execution path.
  Do not silently claim a captured run.

CLI semantics: [con/duct](https://github.com/con/duct).
Consult installed help before using version-specific options or optional inspection commands.

## Retain task evidence in Workshop

Before completing a task, collect its finished duct runs, including failed attempts relevant to the outcome.
Read `~/.config/skills-workshop/config.json` for `workshop_root`; this installation must supply the Workshop memory CLI and configured transport.
Keep source captures until explicit cleanup.
Do not instrument the capture/upload operation itself: that would recursively create logs requiring capture.

Classify the complete capture with the assessment using Workshop sensitivity rules.
Inspect commands, stdout/stderr and metadata without echoing sensitive values.
If any portion is sensitive, use the sensitive store and a private reason.
Never add secrets deliberately to a capture.
A missing configuration or upload failure leaves local evidence intact and must be reported; never claim it was uploaded.

Run from the configured checkout, substituting paths and record IDs:

```sh
pixi run memory capture-duct /path/to/finished-run \
  --store shared --agent AGENT --related ASSESSMENT_UUID \
  --config /path/to/memory/transport.json
```

For sensitive captures, use `--store sensitive --reason "classification reason"`.
Omit `--related` if no assessment exists yet; retain the returned evidence ID for later relations.
`--config` uploads the artifact immediately, while its small evidence record joins the daily 1000-record batch.
Without transport configuration, omit that option to stage locally and report publication pending.

The archive includes exact capture files, is content-addressed, and lives separately in annex.
Normal memory restore/index operations do not download it.
`memory fetch-artifact REFERENCE_JSON --config CONFIG --output ARCHIVE` explicitly retrieves it with integrity verification.
Follow the host's configured memory state location; the default is `~/.local/state/skills-workshop/memory`.

Record missing measurements as unknown.
Duct measures local process work and elapsed waiting; remote model compute, token use and charges require separately reported provider evidence.
