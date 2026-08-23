---
name: organize-project-docs
description: Organize project documentation by audience and lifecycle, separating durable human guidance, agent operating context, milestone records, decisions, and temporary working notes. Use when creating, placing, auditing, or reorganizing repository documentation. Do not use merely to edit prose when its location and purpose are already clear.
---

# Organize Project Docs

Compartmentalize documents so readers can tell what is authoritative, what is temporary, and what kind of attention it requires.
Respect an established repository convention when it already communicates those distinctions well.

## Classify before writing

Choose a document's home from its primary future reader and lifecycle, not the tool that generated it or the person writing it.

| Location | Put here | Keep out |
| --- | --- | --- |
| `docs/` | Durable human-facing explanations, guides, architecture, and reference material | Agent transcripts, temporary plans, and implementation diaries |
| `docs/agents/` | Concise operating context for agents: repository constraints, commands, hazards, and task-specific context recovery | General explanations that humans also need and duplicated source truth |
| `docs/milestones/` | Bounded milestone intent, current state, evidence, and completion reports | Project-wide reference material and an unfiltered history of every interaction |
| `docs/decisions/` | Durable decisions, their context, rationale, and consequences | Tentative ideas that have not become decisions |
| `docs/scratch/` | Disposable or not-yet-classified investigations, drafts, notes, and generated working material | The only copy of durable decisions, requirements, or operational instructions |

Create a directory only when it has a real document.
Do not add empty placeholders merely to establish the taxonomy.

When a document serves several audiences, choose the durable canonical home and link to it from the other context.
Do not maintain equivalent copies.

## Preserve instruction discovery

`docs/agents/` does not imply that an agent harness will load its contents.
Keep recognized instruction entry points such as `AGENTS.md` where their scope and discovery rules require them.
Use those entry points for essential instructions or make them explicitly route to relevant files under `docs/agents/`.
Before moving agent instructions, verify how the active tools discover and scope them.

Keep agent-facing documents compact and operational.
Prefer stable constraints and commands over conversational history, speculative advice, or facts easily recovered from the repository.

## Structure milestones around outcomes

Use one directory per substantial milestone when it needs more than one artifact:

```text
docs/milestones/
  003-user-import/
    plan.md
    progress.md
    completion.md
```

Use a short sortable identifier and descriptive slug if the project has no naming convention.
A small milestone may use one file instead.
Do not create all three files unless each will carry distinct information.

- `plan.md` states the intended outcome, boundaries, acceptance evidence, risks, and explicitly deferred work.
- `progress.md` is a compact restart point containing current state, verified facts, blockers, unresolved decisions, and the next useful action; rewrite or compress it rather than appending a running chat log.
- `completion.md` records what shipped, the evidence reviewed, deviations from the plan, and remaining work without claiming that every possible improvement was completed.

Treat specifications as progressive.
Begin with the highest level that is known, let exploration expose missing decisions, and promote settled decisions into the appropriate durable document.
Do not ask an agent to expand a modest specification into exhaustive prose without a concrete need; specification volume is not evidence of understanding.

## Control document lifecycle

For each documentation task:

1. Inspect existing conventions, instruction files, indexes, and links.
2. State the document's purpose, primary reader, expected lifetime, and source of truth.
3. Place it in the narrowest fitting compartment and write only what that compartment needs.
4. Link related durable material instead of duplicating it.
5. Revisit working documents at milestone boundaries: promote useful content, consolidate overlap, and identify obsolete scratch material.

Do not silently delete scratch files or move existing documents solely because the taxonomy suggests another location.
When reorganizing, inventory the affected documents, preserve history with ordinary file moves where practical, update inbound links, and report ambiguous cases.
Never store credentials, private keys, tokens, or other secrets in documentation, including scratch files.

## Keep the boundaries meaningful

Use these tests when placement is unclear:

- If a new human contributor should learn it, prefer durable human docs.
- If an agent needs it to operate safely or efficiently, prefer agent context or a recognized instruction entry point.
- If it answers "what are we delivering and where are we now?", prefer the active milestone.
- If it answers "why did we choose this?", prefer a decision record.
- If its value is uncertain or short-lived, begin in scratch and give it an explicit promotion or disposal point.

Documentation is a context budget.
Optimize for reliable recovery and clear ownership, not completeness measured by file count or word count.
