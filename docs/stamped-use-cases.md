# STAMPED skill use cases

This is a working response to
[stamped-agent-skills issue #2](https://github.com/stamped-principles/stamped-agent-skills/issues/2).
It separates reusable user intents from implementation so each candidate can
be tested before becoming a skill.

## Candidate set

| User intent | Candidate skill | Minimum useful output | Likely composition |
| --- | --- | --- | --- |
| Review a software project against STAMPED | `review-stamped-software` | Evidence-linked findings, gaps, and prioritized remediation | Dispatch to repository-health, licensing, testing, provenance, and citation skills |
| Review a dataset, including a DataLad dataset | `review-stamped-dataset` | Data/provenance inventory, FAIR and reproducibility gaps, actionable fixes | Dispatch to DataLad, BIDS, metadata, licensing, and integrity checks |
| Improve existing project material | `refactor-for-stamped` | Small proposed patch with a principle-to-change trace | Consume either review skill, then invoke focused maintenance skills |
| Decide which STAMPED workflow applies | `apply-stamped` | Scope classification and an explicit dispatch plan | Thin router over the three task skills; no duplicated domain procedure |
| Evaluate an existing scientific skill | `review-stamped-skill` | Trigger, provenance, safety, validation, and contribution-readiness report | Combine skill validation with the relevant software/data reviewer |

## Recommended first vertical slice

Start with `review-stamped-dataset` using a small public DataLad/BIDS dataset.
It is bounded, produces inspectable evidence, and exercises the intersection of
STAMPED principles, scientific practice, and the NiPreps community. A useful
evaluation should include:

1. a clean dataset with strong provenance;
2. a dataset with intentionally incomplete metadata or provenance;
3. expected findings written before forward-testing;
4. an independent run where the agent sees only the skill and dataset;
5. a record of false positives, missed issues, runtime, and unsafe suggestions.

## Design constraints

- Keep `apply-stamped` as a router. Put checks in task-specific skills so the
  dispatcher does not become a large copy of every procedure.
- Require evidence for every assessment and distinguish observed facts from
  inferred risks.
- Produce advisory findings, not compliance or quality certifications.
- Preserve source provenance and upstream licenses when composing other skills.
- Prefer improvements to the originating upstream when the behavior is broadly
  useful; keep STAMPED-specific orchestration in stamped-agent-skills.

## Upstream contribution map

- **scientific-agent-skills:** broad scientific review patterns, interoperability,
  and a STAMPED-aware scientific-skill review where generally applicable.
- **nipreps/skills-comm:** DataLad/BIDS execution, neuroimaging QC, and evaluation
  examples for the dataset-review vertical slice.
- **con/skills:** repository health, maintenance, duplication, licensing, issue
  triage, and pull-request workflows used by the software reviewer.
- **stamped-agent-skills:** the STAMPED vocabulary, principle-to-evidence rubric,
  dispatcher, and cross-domain orchestration.
