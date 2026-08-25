# Artifacts, deployment, and live proof

Read this reference for Actions-artifact transport, stateless hosted services,
edge or Pages deployments, embedded applications, and end-to-end acceptance.

## Ephemeral artifact transport

An Actions artifact can carry reproducible presentation or editor input without
becoming durable authority. Bind it to authoritative Git facts before use:

- repository and pull-request number;
- exact proposal or head SHA;
- source revision when applicable;
- producer workflow and run conclusion;
- expected artifact name, ID, creation time, and expiry; and
- complete candidate or input fingerprints derived from trusted code.

Before any write, regenerate authoritative facts from trusted default-branch
code and reject stale, incomplete, duplicate, unknown, or mismatched input.
The artifact should not replace repository content, an authenticated comment,
or another durable product record.

Treat the artifact archive as untrusted input. Bound compressed and expanded
size, entry count, paths, filenames, encoding, and schema. Reject traversal,
symlinks, ambiguous entries, unsupported compression, malformed coordinates,
and decompression expansion beyond the declared limit.

## Redirect credential boundary

GitHub's artifact-download endpoint commonly returns a redirect to short-lived
storage. Handle it as two requests:

1. send GitHub API headers and the bearer token to the GitHub endpoint with
   automatic redirect following disabled;
2. require the expected redirect status and validate the HTTPS destination
   against a narrow storage-host policy; and
3. fetch the signed storage URL without forwarding GitHub credentials.

Bound response size while streaming as well as through `Content-Length`. Never
log the signed URL. Test this specialized request independently so it cannot
omit headers required by the shared GitHub client.

## Stateless hosted service

Keep OAuth state and short-lived encrypted sessions as operational state. Do
not retain repository blobs, artifacts, candidate sets, submitted decisions,
or generated bundles unless the product explicitly requires a durable store.
Make the public origin configurable so the same code can serve a central or
self-hosted deployment.

For edge runtimes, verify:

- cookie flags and size under the actual public origin;
- request and response redirect semantics;
- platform fetch invocation;
- subrequest, CPU, body, and archive limits;
- secret and variable binding behavior; and
- absence of unintended databases, object stores, queues, analytics stores, or
  other persistent bindings.

Changing a hosting secret may not change an existing deployment. Set or rotate
the secret first, then deploy or redeploy the exact source revision that should
use it. Record the deployment's source SHA and clean/dirty state.

## Static assets and embedded applications

Static hosts may canonicalize `/path/index.html` to `/path/` with a 301 or 308.
When server code fetches its own immutable assets with manual redirects and
fail-closed status checks, request the host's canonical URL instead of assuming
the filesystem path returns 200.

Do not treat an iframe `load` event as evidence that the embedded application
started. Error responses and empty documents also fire it. A live smoke test
should assert meaningful painted content, such as the framework root plus a
known visible control, and confirm required JavaScript, CSS, schema, and data
requests return 200 with correct MIME types.

Keep executable code and schema pinned to trusted released assets. Do not load
runtime code from the pull request or an external data artifact merely because
the surrounding wrapper is trusted.

## Live proof ladder

Use the smallest non-destructive progression that reaches the real boundaries:

1. production origin and anonymous session return expected status and headers;
2. a synthetic callback lacking the state cookie reaches `missing state`, not a
   generic invalid-callback branch;
3. a fresh OAuth flow identifies the expected GitHub user;
4. repository-only discovery returns the intended open resources and artifacts;
5. an exact link loads the real artifact and authoritative Git blobs;
6. stale-head and incomplete-submission controls remain active;
7. embedded or dynamic UI content visibly paints; and
8. repository refs, pull-request commits, comments, approvals, and merge state
   remain unchanged.

Perform a write proof only when the user authorized its exact target and
result. A product that creates comments, commits, branches, or pull requests
should still support a read-only acceptance path for deployments and demos.

## Immutable evidence

Record:

- source commit and tree;
- build/runtime versions and exact verification commands;
- deployment ID, immutable URL, environment, timestamps, source revision, and
  dirty flag;
- App ID, installation ID, repository selection, and permission names;
- artifact ID, expected name, producer run, expiry, and digest;
- exact repository, pull request, head, and source coordinates used; and
- counts and state observed before and after the proof.

Do not record tokens, cookies, authorization codes, secret suffixes, or signed
storage URLs. Update earlier evidence through a new attributed record when the
repository's history rules prohibit rewriting it.

Provider references:

- <https://docs.github.com/en/rest/actions/artifacts>
- <https://developers.cloudflare.com/pages/functions/bindings/>
- <https://developers.cloudflare.com/workers/runtime-apis/request/>
