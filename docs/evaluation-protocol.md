# Skill evaluation protocol

This protocol separates inexpensive observations from claims that a skill
caused a better outcome.

## Ordinary use

A use event records what happened in one task. It may include a 1–5 contextual
rating, but it is observational: the task, agent, environment, and expectations
were not controlled. These events are valuable for recall, deciding what to
investigate, and detecting repeated failure patterns.

## Exploratory pair

Run two fresh, isolated agents against the same pinned fixture and prompt. Give
one the exact skill artifact and keep it from the other. Match model, reasoning
effort, tools, permissions, and resource budget. Grade both outputs against a
predeclared rubric. One stochastic pair is exploratory even when the treatment
wins.

## Controlled and replicated evidence

A controlled-paired evaluation requires:

- an immutable task fixture and exact treatment artifact;
- identical runtime and permission configuration;
- isolation from the other condition's context and output;
- predeclared cases, metrics, expected behavior, and grading;
- complete retained outputs or evidence digests;
- a stated conclusion and limitations.

A replicated evaluation repeats conditions enough times to characterize
variation. Randomize run order when order could matter. Do not silently discard
errors or adverse results.

The v0 CLI creates a planned scaffold; it does not run or grade agents. Before
marking a record complete, the semantic validator requires assigned grading,
concrete and matched runtime/budget controls, complete condition-by-case
coverage, every declared metric, and retained evidence. Controlled records also
require digests for the protocol, fixture, rubric, and treatment artifact.

## Triggering evaluations

Behavioral quality and discoverability are distinct. To test implicit
activation, include realistic competing skill names and descriptions and record
whether the host exposed the full description, only the name, manual invocation
only, or no listing. Do not assume a universal fixed skill-count limit.
