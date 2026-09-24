# Adopting a WikiSkill-style optimization loop

Recommendation: adopt the method as the target architecture, with domain-specific evaluation and constrained promotion.
A passive feedback store is only its first component; more observations alone do not implement autonomous optimization.

[WikiSkill sections 3.1–3.2](https://arxiv.org/html/2608.27454) describe execution traces, a persistent wiki, and active skills; separate maintainer and proposer roles consolidate experience and propose atomic changes.
Validation accepts improvements or rolls back skill changes while retaining accumulated knowledge and proposal history.
The paper's controlled task splits and evaluators matter: ordinary project completion reports do not provide an equivalent objective.

## Concrete implementation work

| Component | Current Workshop support | Needed for an autonomous loop |
|---|---|---|
| Collection | Explicit schema-validated recording command; optional trace/log references; sensitivity overlay | A host-specific completion adapter with reliable task/skill identity, measured timing, runtime/model and resource data; idempotent delivery and crash handling |
| Knowledge consolidation | Grouped notes, priorities, actions, sensitivity review | A bounded maintainer job that samples successes and failures, updates pattern pages and an index, and links observations without flattening private data into public prose |
| Proposal generation | Skill authoring workflow and Git history | A proposer consuming relevant patterns and past accepted/rejected proposals; exact artifact identity, one bounded skill change, rationale and predicted effect |
| Evaluation | Existing with/without-skill evaluation scaffolds | Executable replayable fixtures, deterministic or calibrated graders, train/validation/test separation, matched model/tool/time/token budgets, repeated trials and uncertainty |
| Gating and rollback | Normal tests and Git commits | Isolated candidate checkout, baseline/candidate comparison, quality and cost thresholds, non-regression checks, atomic promotion, reliable rollback |
| Orchestration | Individually callable commands | A durable run state machine, bounded iteration/cost limits, retry and stop rules, scheduled dispatch, and a reviewable impact ledger |

The maintainer and proposer are logical roles, not necessarily simultaneously running agents.
A sequential orchestrator can perform them while preserving the separation of responsibilities.
The proposal ledger should retain the exact diff, motivating patterns, evaluation configuration, scores/costs, decision, and rollback status.
Rejected proposals remain searchable so future runs do not repeat the same failed intervention.

## First useful pilot

Choose one narrow skill with objective checks, such as duct's argument preservation, exit-code handling, log retention, and resource sampling.
Use synthetic or public fixtures and run candidates in isolated environments so the loop cannot modify user projects or globally installed skills during evaluation.
Establish an unchanged-skill baseline, define task quality and resource budgets, and hold some cases out from proposal generation.
Do not optimize solely for a self-reported success flag or prettier instructions.

Start with automatic collection, consolidation, proposals, and evaluation; retain explicit promotion while calibrating the evaluator.
Once its scores agree with reviewed outcomes and rollback is demonstrated, allow promotion within an explicitly authorized narrow skill scope and budget.
A cost cap, maximum iterations, repeated-failure stop, and no-action outcome are part of the loop, not optional afterthoughts.
External publication and shared-thread communication remain separate from local optimization.

The practical bottleneck is reliable evaluation and a task-completion adapter, not writing another prose-feedback prompt.
No optimizer, schedule, model-spending job, or automatic production-skill update is enabled by the current schema/overlay change.
