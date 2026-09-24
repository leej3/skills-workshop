# Promote lessons, not activity histories

Baseline records and exceptional notes are local by default, including aggregates.
Publish only a reusable lesson whose necessary details are already public or explicitly authorized for disclosure.
Authorization to collect feedback is not authorization to publish it.

Before creating a Git-backed record:

1. Distill the lesson and proposed action.
   Remove incidental task context.
2. Exclude credentials, private conversations, participant or personal data, confidential work, raw logs, local paths, machine names, internal URLs, and conversation identifiers.
3. Include a public project link only when necessary to support the lesson.
   Public code does not make private discussions public.
4. Inspect the full serialized record and staged diff, including generated source, project, actor, artifact, and extension fields.
   A summary can be safe while its metadata is not.
5. Confirm the intended destination and applicable publication authorization.
   If uncertain, retain the local note; do not publish or create an automatic approval request.

The legacy `feedback.py` launcher no longer injects a conversation ID.
Explicit `--session`, `--project-path`, and `--skill-path` may still add metadata; omit them unless appropriate after inspection.
Secret scanning can supplement this review but cannot establish that an unpublished plan or personal detail is suitable for publication.

For an authorized public record, use the configured Workshop CLI's `feedback` command, then validate memory, inspect all changed records, and commit only those reviewed paths under the repository conventions.
No automatic commit or push follows baseline collection or exceptional local notes.
Do not rewrite old Git history as part of this policy change.
A suspected past disclosure needs separate assessment and appropriate remediation.
