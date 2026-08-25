---
name: build-github-app
description: Build, deploy, debug, and verify GitHub Apps that use user authorization, repository installations, Actions artifacts, or a hosted service. Use when registering or configuring an App, choosing permissions, implementing OAuth callbacks and sessions, deploying a GitHub-backed web application, diagnosing 401/403/redirect/runtime failures, rotating client secrets, or proving an end-to-end flow. Do not use for an ordinary GitHub Action or a non-App OAuth integration.
---

# Build GitHub App

Treat a GitHub App as several independently testable layers:

1. registration and callback configuration;
2. App permissions and repository installation selection;
3. user authorization and short-lived session handling;
4. GitHub API access;
5. hosted runtime and static assets;
6. any explicit repository write; and
7. live evidence and credential cleanup.

Do not debug the whole stack as one opaque login failure. Establish the first
failing boundary and retain distinct, non-sensitive error codes for it.

## Establish the contract

Before implementing, identify:

- the repositories and account or organization installations in scope;
- each GitHub REST or GraphQL endpoint the App must call;
- whether calls use an installation token, user access token, or no credential;
- the exact callback and public origins;
- which state is durable product data and which is short-lived operational
  authentication state;
- every requested external write and the human action that authorizes it; and
- the hosting platform's secret, redirect, static-asset, and deployment
  behavior.

Derive permissions from the endpoints and operations. Public App visibility,
installation, signed-in user authority, and token permissions are different
conditions; none substitutes for the others. A user access token can reach
only resources allowed by the intersection of App permissions, installation
selection, and the user's own access.

Read [OAuth, permissions, and credentials](references/oauth-permissions.md) in
full when implementing authentication, changing permissions, diagnosing an
authorization failure, or rotating a secret.

## Preserve authority boundaries

- Keep GitHub repository content, pull requests, and authenticated comments as
  the durable record when that is the product contract.
- Do not turn a stateless authentication or presentation service into a second
  data store.
- Treat PR Markdown as human-facing content unless the specification explicitly
  makes it a protocol.
- Use Actions artifacts only as ephemeral, reproducible transport when Git
  remains authoritative.
- Execute trusted writes from trusted code and re-read exact repository, ref,
  head, and source coordinates immediately before mutation.
- Derive actor identity from GitHub's authenticated context, not a browser
  field.
- Grant a write permission only for an explicit supported operation. Enforce
  approved paths, repository identity, exact Git coordinates, and
  compare-and-swap behavior in the service or trusted workflow.
- Never log or retain access tokens, refresh tokens, client secrets,
  authorization codes, signed download URLs, or arbitrary OAuth error bodies.

## Implement in observable layers

Use focused adapters around platform fetch, session sealing, GitHub API calls,
artifact retrieval, and writes. Give each boundary a safe diagnostic that
distinguishes authentication required, permission denied, resource missing,
stale coordinates, malformed upstream data, and hosting misconfiguration.

Test in both a normal application runtime and the actual deployed runtime.
Node-based mocks do not reproduce every Worker, edge-runtime, redirect, cookie,
or static-asset behavior.

For artifact-backed or hosted review flows, read
[Artifacts, deployment, and live proof](references/artifacts-deployment.md) in
full. It includes the redirect credential boundary, canonical asset routing,
iframe readiness, and immutable deployment evidence.

## Verify without manufacturing product state

Prefer a real isolated repository and an existing harmless proposal over a
synthetic production write. A useful read-only proof normally establishes:

- a fresh OAuth flow reaches the expected GitHub identity;
- the App installation selects the intended repository;
- repository discovery returns only relevant resources;
- artifact metadata and content bind to the expected run and coordinates;
- the actual hosted UI paints meaningful controls rather than merely firing a
  load event;
- stale or incomplete input remains blocked; and
- the target ref, pull request, comments, and other durable state are unchanged.

Exercise an actual write only when the user authorized that specific outcome.
Do not create a demonstration pull request, comment, approval, merge, or source
write merely to prove that code exists.

## Rotate credentials safely

Create or replace a client secret only with the required authorization. Move it
through a protected channel, never command output or tracked files. Do not
assume a browser's **Copy** affordance updated the clipboard; verify only
non-secret shape or destination status without revealing the value.

Update the hosting secret before deploying the revision that will use it.
Complete a fresh OAuth flow, then verify the new credential shows recent use
while the superseded credential does not. Permanently delete the old credential
only after explicit confirmation at deletion time and after proving the new
one. Report that deletion is irreversible without recording secret values or
suffixes.

## Record reproducible evidence

Record only coordinates and outcomes needed to reproduce or audit the result:

- App and installation identifiers, repository selection, and permission set;
- source commit and tree, build commands, test results, and runtime versions;
- deployment identifier, immutable URL, timestamps, source revision, and dirty
  flag;
- artifact identifier, name, producer run, expiry, and non-secret digest;
- exact repository, pull request, head, and source coordinates used for live
  proof; and
- durable state intentionally not created or changed.

Never record credentials, signed URLs, cookie contents, authorization codes,
or secret suffixes. Preserve repository-specific attribution, provenance,
approval, and publication rules.
