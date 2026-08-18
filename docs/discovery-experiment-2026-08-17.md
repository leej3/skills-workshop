# Discovery experiment: three real intents

Date: 2026-08-17.

This is a small operational check, not a benchmark. The same three task-shaped
queries were sent through workshop memory, ASM 2.14.0, `gh skill` from GitHub
CLI 2.97.0, and Vercel `skills` 1.5.22. No result was installed or promoted to
memory merely because a provider returned it.

| Intent | Local memory | ASM | `gh skill` | Vercel `skills` |
| --- | --- | --- | --- | --- |
| DataLad dataset maintenance | No remembered match | Returned broad dataset skills, with weak DataLad precision | No result in this run | Found `datalad-log` and `datalad-credentials`, but below broader results |
| BIDS App development | No remembered match | Eventually surfaced K-Dense's BIDS material behind generic app results | No result in this run | Found relevant BIDS material, but advertising “bids” polluted the ranking |
| Co-authored commit provenance | Found the exact remembered `commit-provenance` skill | Returned generic conventional-commit alternatives | Provider returned HTTP 503; other providers continued | Found `commit-coauthor-footer` among many weaker matches |

The useful evidence is not that one public provider “won.” It is that their
failure and ranking modes differ:

- source-agnostic memory was the highest-precision path when the skill had been
  encountered before;
- provider scores should not be merged into a fictitious common ranking;
- a failed provider must not erase local or other-provider results;
- task-language search still needs inspection of the complete candidate tree;
  and
- search results are transient discovery observations, not adoption, trust, or
  usage evidence.

The current CLI therefore searches memory by default, fans out only when
requested, limits and labels each provider independently, and uses `gh skill
preview` for exact GitHub candidates. A candidate enters durable memory only
after an explicit `remember` and `consider` decision.

Repeat this exercise with future versions before drawing ecosystem-wide
conclusions. Provider indexes, authentication, ranking, and availability are
all time-dependent.
