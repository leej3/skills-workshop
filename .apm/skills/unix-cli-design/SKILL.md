---
name: unix-cli-design
description: Design or review command-line interfaces for Unix composition, including pipes, stream formats, arguments, exit status, and interruption. Use when building or changing a CLI's public behavior or reviewing its scripting compatibility; not for ordinary CLI usage or full-screen terminal interfaces.
---

# Unix CLI design

Make each command useful both at a terminal and inside a shell pipeline.
Preserve the project's established interface unless the task authorizes a change.
Distinguish a demonstrated defect, a missing capability, and a deliberate convention; do not claim formal POSIX conformance for an arbitrary application.

## Start with real invocations

Inspect the parser, command dispatch, stream readers and writers, subprocess boundaries, help, and relevant tests.
Identify which commands transform a stream, which manage files or a workspace, and which run a service.
Only stream-oriented operations need to behave as filters: a directory tree or a multi-file build cannot be represented by pretending its path is stdout.

Write a few representative invocations showing actual consumers, such as a JSON parser, another command, or an early-exiting reader.
For a review, report findings with source locations and observed behavior; do not implement changes solely because the skill suggests them.
For implementation, use the existing parser and upstream libraries' stream support before adding an adapter.
Keep the CLI boundary thin and share transformation logic between file and stream paths.

## Input and arguments

- For file arguments where streams are meaningful, support and document `-` as stdin or stdout.
  Resolve this sentinel before normalizing a filesystem path.
  Keep `./-` available for a literal file named `-`.
- Preserve established file defaults; adding `--output -` need not change the default destination.
  For a new filter, stdin and stdout are natural defaults when no file is given.
- State how multiple inputs are ordered and reject attempts to consume the same stdin stream twice unless the command explicitly supports that behavior.
- Read streams without assuming seekability, a known size, or a regular file.
  Buffer or spool only when the algorithm requires it; disclose material limits.
  Do not close process-owned standard streams in reusable functions.
- Distinguish record streams from filename lists.
  Use an explicit NUL-delimited mode when filenames with newlines must be transported; do not invent NUL output for structured records that already have unambiguous framing.
- Use the parser's `--` support for operands beginning with a hyphen.
  Test option values beginning with a hyphen using the parser's documented syntax, such as `--output=-name`.
- Use consistent option meanings across commands.
  Reserve short options for frequent actions, and avoid implicit option abbreviations that become ambiguous when new options are added.

## Output and framing

- Put requested result data on stdout; put diagnostics, progress, and status messages on stderr.
  A human-readable report can itself be the requested result.
- Define machine output explicitly: one JSON document for a bounded result, JSONL for independent records, or another documented format.
  Specify encoding, delimiters, and meaningful ordering; terminate text records with newlines.
- A parent and its subprocesses share stdout unless redirected.
  Check the entire process tree for extra JSON documents, banners, and progress; rendering clean JSON in the parent is insufficient.
- Provide an explicit machine-readable mode when scripts would otherwise scrape decorative or truncated prose.
  Keep full values in that mode; make any filtering or limits explicit and explain their effect on exit status.
- Let TTY detection control presentation, not result selection or schema.
  Avoid automatically switching between JSON and prose solely because stdout is redirected.
- Keep redirected output free of unsolicited ANSI sequences and paging.
  Apply color and progress decisions to the stream they actually use; honor established color overrides when color is supported.
- Keep quick commands quiet where appropriate.
  Flush useful progress to stderr for slow work, following the project's timing convention; do not require a progress library, immediate chatter, or new quiet/verbose flags without a use case.

## Failures, signals, and unattended use

- Document a small set of exit statuses callers can use.
  Zero means the command's defined success; nonzero may mean a domain result, such as differences found, rather than an execution error.
  Preserve established `diff`-style distinctions.
- Render expected input, filesystem, and operational failures concisely on stderr.
  Preserve debugging causes internally; do not expose tracebacks for routine mistakes.
- Treat broken pipes as an expected pipeline condition.
  Handle both writes and final buffered flushing without a traceback.
  Choose and test the platform-appropriate status; do not universally convert broken pipes to success or hide unrelated I/O errors.
- Handle interruption at the process boundary, propagate cancellation to owned child processes, and bound cleanup.
  Preserve meaningful nonzero cancellation status for interrupted work; distinguish a service's documented normal shutdown.
- Do not require a prompt when stdin is a pipe or closed.
  Provide explicit arguments for unattended use, and keep any interactive prompt separate from data input.
  Inspect subprocesses for hidden prompts as well.
- Decide whether partial streamed output is usable after failure.
  Consumers must be able to detect incomplete results through status or documented framing.
  Use atomic replacement for file output when completeness is required; a pipe cannot be rolled back.
- Account for shell pipeline semantics: without `pipefail`, a later successful consumer can hide a producer failure.
  Do not promise that the CLI alone controls the pipeline's final status.

## Help and compatibility

Help and version requests should succeed without workspace validation, credentials, network access, or expensive execution imports.
Explain stdin usage, output format, file defaults, overwrite behavior, and branch-worthy exit statuses where users discover the command.
Use examples that can actually be combined in a pipeline.

Treat arguments, stream contents, formats, defaults, and exit statuses as public behavior.
Prefer additive stream and machine-output options when existing scripts rely on file output.
Do not make scripts consume progress messages to discover generated paths.
Avoid adding a command registry, wrapper framework, or duplicated interface specification merely to make the review easier.

## Verify the process boundary

Use temporary fixtures and capture stdout, stderr, and status independently.
Choose cases that prove the changed behavior and its important failure boundaries, rather than snapshotting every help line or private parser structure.

For stream changes, exercise the applicable cases:

- equivalent file and pipe input, and parseable redirected output;
- `-`, a literal `./-`, spaces, and leading-hyphen operands;
- empty input, malformed input after valid records, and non-ASCII data;
- a real OS pipe whose reader exits early, including output large enough to exceed buffering;
- ordinary errors and interruption, with no traceback for expected conditions;
- clean machine output from the full command, including child processes;
- help/version outside a configured workspace and unattended execution with closed stdin.

Use a PTY only when testing terminal-specific behavior; a captured subprocess is not a terminal.
For timing and streaming claims, check when output becomes available, not just its final bytes.
Report which cases ran, which findings follow from source inspection, and what remains unverified.

## Reference baseline

This skill is original guidance informed by these sources; the operating method above is self-contained.
Consult the relevant source when a convention is disputed or a platform-specific detail matters:

- [POSIX utility syntax](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap12.html): options, operands, `--`, and documented uses of `-`.
- [Command Line Interface Guidelines](https://clig.dev/): human use, composition, output, errors, and signals.
- [GNU command-line conventions](https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces.html): help, version, and option behavior.
