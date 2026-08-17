# Sixty-day workshop usage pilot

This is the auditable ledger for the
[project viability decision](project-viability.md). Do not start the clock when
the template is committed. Start it when the first real downstream project has
a workshop materialization lock and completes an apply or status operation.

## Pilot control

| Field | Value |
| --- | --- |
| Owner | John Lee |
| State | Not started |
| Start condition | First real project lock plus an apply or status operation |
| Start date | TBD |
| Day-30 review | TBD |
| Day-60 decision | TBD |

Use stable project IDs rather than confidential paths. Link to commits, issues,
or pull requests when those records are public; otherwise use a concise local
evidence note.

## Counting rules

A **unique-value event** is one of:

- deliberate `record` or `back-propagate` after source/project divergence;
- a both-sides conflict resolved using the workshop's separate baselines; or
- fork/canonical coordination that produces a submitted upstream pull request
  or issue-backed patch.

One underlying divergence or contribution episode counts as at most one
unique-value event, even if it matches several bullets. Assign one event ID and
one row to the episode; a later pull request from the same change is an outcome
on that row, not another event.

Do not count search, preview, install, copy, link, overwrite, ordinary update,
or routine status with no consequential decision. Those are commodity
operations for this evaluation.

Workshop maintenance time includes workshop-specific engineering, tests,
documentation, ecosystem research, integration spikes, release/PR work, and
manual metadata repair during the pilot. Do not count time spent improving the
content of a skill unless the workshop workflow itself caused extra work.

Estimate the counterfactual against the best existing alternative known on the
operation date, not against an entirely manual process when APM, `gh skill`, Vercel
`skills`, `skill-manager`, ASM, or plain Git would have been credible. Record
both estimates when each operation occurs rather than reconstructing them at
day 60.

## Active projects

| Project ID | First qualifying operation | Last qualifying operation | Operations used | Notes |
| --- | --- | --- | --- | --- |
| _Add rows when the pilot starts_ |  |  |  |  |

An active project has completed at least one real apply, status, or reconcile
operation during the 60-day window. Merely registering a path does not count.

## Promotions and conformance

| Promotion ID | Canonical URL | Subpath | Commit SHA | Tree digest | Validator revision and command | Validator result | Policy checklist result | Classification | Review evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _Add one row before each promoted skill enters the pilot_ |  |  |  |  |  |  |  |  |  |

Use a resolved commit SHA and content digest as evidence. A tag may be recorded
in review notes but is not an immutable identifier. Classification is
`portable`, `vendor-specific`, or `rejected`; only `portable` permits a
cross-vendor claim.

## Unique-value events

| Event ID | Date | Project ID | Skill | Event type | Outcome | Best alternative | Workshop minutes | Alternative minutes | Net minutes | Manual repair | Upstream/reuse result | Evidence |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| _One row per underlying episode_ |  |  |  |  |  |  |  |  |  |  |  |  |

A reusable local result counts only when the same skill change is used by at
least two downstream projects. Creating a workshop feature or an unsubmitted
branch does not prove user value.

## Commodity operations

| Operation ID | Date | Project ID | Operation | Tool used | Best alternative | Workshop minutes | Alternative minutes | Net minutes | Evidence/notes |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| _Log every workshop operation during the pilot_ |  |  |  |  |  |  |  |  |  |

Complete operation logging is required; do not infer the proportion from an
ad hoc sample. At each review, divide commodity rows by all unique-event plus
commodity rows in that review interval. A share of 75% or more is a pivot
signal toward making the relevant external manager primary.

For both event and commodity rows, net minutes equal alternative minutes minus
workshop minutes. Include negative values. Total operation benefit is the sum
of all net minutes, converted to hours before comparison with maintenance.

## Maintenance time

| Date | Category | Work | Hours | Evidence |
| --- | --- | --- | ---: | --- |
| _Add all workshop-specific maintenance during the pilot_ |  |  |  |  |

Categories should distinguish implementation, tests, documentation, ecosystem
review, integration spike, PR/release administration, and metadata repair.

## Alternative replacement checks

Evaluate the seven requirements in
[Replacement test against the closest alternatives](project-viability.md#replacement-test-against-the-closest-alternatives).

| Candidate | Version/revision | Date | Status | Manager-free downstream | Immutable identity | Local edits preserved | Export/removal | No-loss test | Residual cases passed | Integration hours | Switching hours | Decision/evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Plain Git and copies | TBD (`git --version`) | TBD | Pending |  |  |  |  |  |  |  |  |  |
| `skill-manager` | TBD | TBD | Pending |  |  |  |  |  |  |  |  |  |
| ASM | TBD | TBD | Pending |  |  |  |  |  |  |  |  |  |
| Microsoft APM | TBD | TBD | Pending |  |  |  |  |  |  |  |  |  |

Test the cheapest and closest alternative first. Stop evaluating once a
candidate satisfies every safety-critical case and at least six of seven
residual requirements with no more than one day of removable integration.
Before a continue decision, every candidate row must be `Tested` at a pinned
revision or `Disqualified` with linked evidence. Record estimated switching
time separately from integration time so the replacement stop rule is
reviewable. Compare switching hours with three times cumulative 60-day
maintenance hours as the projected six-month workshop-maintenance cost.

## Reviews

| Review interval | Cumulative unique events | Active projects | Submitted upstream patches or two-project skill reuse | Interval operation benefit (hours) | Interval maintenance (hours) | Cumulative operation benefit (hours) | Cumulative maintenance (hours) | Interval commodity share | Replacement rows complete? | Replacement passed? | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| Days 1–30 |  |  |  |  |  |  |  |  |  |  |  |
| Days 31–60 |  |  |  |  |  |  |  |  |  |  |  |

Decision precedence is defined in the viability report: a stop condition wins;
all continue gates are required; every other result means pivot or re-scope.
Continue uses cumulative day-60 economics. The two-consecutive-review stop rule
uses the two interval columns, not overlapping cumulative windows.
