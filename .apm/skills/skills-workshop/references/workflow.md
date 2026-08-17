# Workshop workflow reference

## Authority map

| Concern | Authority |
| --- | --- |
| Cross-project recall, decisions, use, ratings, evaluations, contributions | Workshop memory |
| Project dependencies, exact resolution, target deployment, lock, update, audit | APM |
| GitHub search, preview, source provenance, publication | `gh skill` |
| Cross-provider catalog search and inspection | ASM |
| skills.sh and `.well-known` discovery | Vercel `skills` |
| Skill content and development history | Ordinary Git source or fork |

## Project-owned versus reusable skills

Start a project-specific experimental skill under
`.apm/skills/<name>/SKILL.md`. The root `apm.yml` and `includes: auto` make it a
project-owned primitive; do not also list it as a local APM dependency. This
keeps the experiment reproducible without prematurely making it an independent
package.

Promote the skill to an independent Git/APM dependency when another project
needs it or it gains an independently versioned lifecycle. After promotion,
the source repository owns the skill and each downstream project pins it
through APM.

When converting an existing raw local dependency, treat the APM lock and
deployed target as generated state with ownership history. Verify the canonical
tree first, preserve the generated state for recovery, remove the old
dependency declaration, move the source, and regenerate the lock and target
from `.apm/skills`. Do not use `--force` to paper over mixed old/new owners.

Discovery providers never install into APM-managed paths. The workshop never
copies APM's dependency graph or lock. Deleting the workshop must leave an APM
project reproducible; deleting APM state must leave the workshop unable to
reconstruct it.

## Evidence levels

1. **Consideration:** why a candidate was adopted, deferred, rejected, or
   retired.
2. **Membership:** APM declared or resolved a skill for a project. This does not
   prove that an agent used it.
3. **Use:** a skill participated in a real task, with sanitized context,
   invocation mode, outcome, and optional rating.
4. **Assessment:** a reproducible compatibility, trust, license, security,
   quality, or portability check bound to an exact artifact.
5. **Evaluation:** an explicit protocol comparing conditions and retaining run
   evidence, grading, metrics, and limitations.

Keep agent assertions unreviewed until a person reviews them. Do not convert a
provider popularity signal or a skill's self-rating into workshop evidence.

## Rating scale

- **1 — harmful:** clearly worsened the task or created unsafe output.
- **2 — unhelpful:** required substantial correction.
- **3 — mixed:** no clear effect or balanced strengths and weaknesses.
- **4 — useful:** improved the task with only minor correction.
- **5 — decisive:** reliably enabled or materially improved the outcome.

The scale ID is `workshop-overall-v1`. A rationale is required because a number
without context is not migratable evidence.

## Evaluation controls

- Use an exact skill artifact in the treatment arm.
- Give conditions the same fixture, model, reasoning effort, tools, permissions,
  and recorded time, token, or turn budget.
- Isolate contexts so the baseline cannot see treatment output.
- Predeclare task cases, expected behavior, metrics, and direction.
- Prefer blind grading when outputs can be compared without knowing condition.
- Label one treatment/control pair `exploratory`.
- Use `controlled-paired` only when controls and explicit grading are present.
- Use `replicated` only after repeated trials.
- Record failures and limitations; do not retain only favorable runs.

For implicit triggering, evaluate recall in the presence of a realistic set of
competing skill descriptions. Installation alone does not prove discoverability.
