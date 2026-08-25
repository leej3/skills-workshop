# OAuth, permissions, and credentials

Read this reference for GitHub App registration, installation, user-to-server
OAuth, permission diagnosis, or secret rotation.

## Permission and identity model

Build a small endpoint matrix before changing App permissions:

| Operation | Credential | Typical repository permission |
| --- | --- | --- |
| Identify the signed-in curator | user access token | no repository permission beyond App/user authorization |
| Read repository metadata | user or installation token | Metadata read |
| Read blobs, refs, or commits | user or installation token | Contents read |
| Read workflow runs or artifacts | user or installation token | Actions read |
| Post a pull-request comment | user or installation token | Pull requests write |
| Create a branch or commit | user or installation token | Contents write |
| Open a pull request | user or installation token | Pull requests write |

Confirm every endpoint against current GitHub documentation; permission labels
and endpoint behavior can change. Request only the operations the product
actually implements.

After a permission change, inspect each relevant installation. An App setting
may be correct while an existing installation still awaits updated permission
approval or selects the wrong repositories. Verify account, installation ID,
repository selection, and the signed-in user's collaborator role separately.

## Callback and exchange invariants

- Configure the exact HTTPS callback origin and path used by the deployment.
- Bind state to a short-lived, encrypted, host-only cookie and compare it in
  constant time where practical.
- Use PKCE when supported by the selected GitHub App flow.
- Accept only the callback fields GitHub actually sends. If GitHub supplies an
  issuer field, accept one exact trusted value; reject duplicates, untrusted
  values, and unrelated parameters without weakening state or redirect checks.
- Exchange the code server-side with an explicit JSON response format.
- Validate the successful token shape, expected token type, scope behavior, and
  expiration. Discard refresh data unless refresh is an explicit requirement.
- Detect GitHub's OAuth error object before treating the response as a token.
  Map known failures to fixed safe messages and never reflect or log arbitrary
  descriptions, URIs, response bodies, codes, or tokens.
- Do not retry or reload an OAuth callback code. Start a fresh authorization
  flow because codes are single-use and short-lived.

Useful safe diagnostics include distinct fixed messages for a rejected code,
invalid access-token shape, missing or invalid expiry, unexpected token type,
unexpected scope, missing state cookie, and state mismatch.

## GitHub API request invariants

Every request to GitHub's REST API, including specialized paths that bypass a
shared helper, should deliberately set:

- `Accept: application/vnd.github+json` or the endpoint's required media type;
- `Authorization: Bearer ...` when the endpoint is authenticated;
- a valid, stable `User-Agent`; and
- the selected `X-GitHub-Api-Version`.

A helper-level header test is insufficient when artifact downloads, GraphQL,
uploads, or other paths construct requests separately. Assert headers at each
credential-bearing boundary.

When injecting `fetch`, test its calling convention in the target runtime.
Edge runtimes can expose receiver-sensitive platform functions that fail when
stored or invoked differently from Node mocks. Wrap or bind the platform fetch
according to the runtime rather than assuming all implementations are freely
detachable.

## Diagnose in order

Locate the first failing boundary:

1. callback URL and callback parameter validation;
2. state cookie and PKCE verification;
3. authorization-code exchange and token shape;
4. authenticated `/user` lookup;
5. App installation and repository selection;
6. collaborator permission;
7. endpoint-specific repository permission; and
8. resource coordinates or stale state.

Do not broaden permissions until the failing endpoint proves the existing set
is insufficient. A 403 from `/user`, repository metadata, artifact download,
or a storage redirect represents a different defect even if the browser shows
the same generic message.

## Secret rotation

Use a two-secret overlap when the provider permits it:

1. generate the replacement without exposing it to logs, transcripts, or
   tracked files;
2. update the hosting secret through stdin or another non-echoing channel;
3. deploy a known source revision after the secret update;
4. start a completely fresh OAuth flow;
5. verify the new secret is marked recently used and the old one is not;
6. obtain confirmation immediately before irreversible deletion; and
7. delete only the identified superseded entry, then verify one working entry
   remains.

If a UI reports **Copied**, do not infer the system clipboard changed. Prefer a
provider-supported CLI or secret manager. If the UI is the only source, keep
the value in protected process memory, validate only length/character shape,
pipe it directly to the destination, restore the prior clipboard if touched,
and clear temporary variables immediately.

Authoritative starting points:

- <https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app>
- <https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api>
- <https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps>
