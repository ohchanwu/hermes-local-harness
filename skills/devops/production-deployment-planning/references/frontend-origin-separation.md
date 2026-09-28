# Frontend Origin Separation

Use this recipe when extracting a public static frontend from an application server while keeping APIs, forms, admin routes, authentication, analytics, or persistence on the existing backend.

## 1. Establish the real boundary

Separate three concerns explicitly:

1. **Source access:** use a separate repository when a collaborator must not read or modify backend or infrastructure source. A monorepo `appRoot`, build filter, or deployment directory is not an access boundary.
2. **Deployment authority:** grant the frontend publisher access only to the frontend repository. Keep hosting administration, edge routing, secrets, and emergency rollback with an operator.
3. **Browser authority:** record that self-merged same-origin HTML or JavaScript is trusted first-party production code. Repository separation protects backend source and cloud administration; it does not sandbox code running in users' browsers.

Do not claim that CORS, HttpOnly cookies, or static checks prevent hostile same-origin JavaScript from influencing backend behavior. Keep authentication, object authorization, CSRF, validation, and rate limits authoritative on the backend.

## 2. Inventory request-time coupling before choosing routes

Inspect the current public request path and list every behavior applied before or while serving a page:

- method and status behavior for root, clean paths, extension paths, trailing slashes, redirects, unknown paths, and traversal attempts;
- API, admin, fallback-form, webhook, health, and compatibility namespaces;
- page-view cookies, analytics writes, engagement calls, and exclusion rules;
- bot or scripted-client filtering;
- security and indexing headers;
- tracker inclusion and demo/preview exclusions;
- runtime asset rewriting and cache headers; and
- redirects that return from backend form posts to frontend pages.

Generate a protected route fixture across representative paths and `GET`, `HEAD`, `POST`, plus an unsupported method. Record status, `Location`, content type, and relevant headers. Implement and test the edge dispatcher against that fixture; do not replace observed behavior with a simplified blanket `404`, `405`, or SPA fallback.

Route exact reserved roots and their complete namespaces to the backend for every method—for example, exact `/api` plus `/api/*`, not only currently known endpoints. This prevents future or wrong-method requests from falling through to static hosting.

## 3. Make the static repository publish only an artifact directory

Keep policy and validation outside the hosted tree:

```text
AGENTS.md
.github/workflows/
checks/
contracts/
site/                 # only published artifact
```

Never publish the repository root; otherwise agent instructions, workflow files, and validation fixtures can become public assets.

Define an exact editable-path allowlist. Put network, form, analytics, tracker, preview, and security behavior in operator-protected paths. Split mixed JavaScript before delegation: editable files may own presentation and local DOM behavior, while protected files own network requests and integration contracts.

Use tamper-resistant repository path rules for protected workflows, fixtures, hosting configuration, and integration code. CODEOWNERS or a check implemented by files the same writer can modify is not equivalent. If the hosting model requires a private-repository plan that supports push path rules, make that a prerequisite rather than silently weakening the boundary.

Because HTML usually remains editable, protect embedded contracts structurally: immutable fixtures should require exact protected-script inclusions and approved form markup, and reject new forms, reserved-path content, remote scripts, network primitives, and unapproved destinations. State plainly that static analysis is a structural defense, not a semantic JavaScript sandbox.

## 4. Make previews and direct hosting origins safe

A preview on another hostname does not become safe merely because relative API requests fail. Use one protected runtime bootstrap loaded before editable scripts:

- allow production integrations only on an exact canonical-hostname allowlist;
- on every other hostname, display a preview notice, disable mutation controls, and suppress trackers, analytics, and engagement;
- make each protected network client independently require a canonical hostname; and
- never rewrite preview requests toward production.

Treat the hosting provider's default production URL as a bypass origin. Either restrict access or make it equivalent to a safe preview: noindex, tracker-free, analytics-free, and mutation-inert. Test it directly. If an edge proxy removes origin-level `noindex` for canonical production responses, keep that transformation operator-owned and retain noindex on preview/demo/error surfaces as required.

## 5. Preserve analytics without double counting

When page views were previously recorded by backend middleware, static delivery bypasses that middleware. If exact behavior must remain, use one narrow backend analytics bridge called by the operator-owned edge dispatcher for trackable requests whose final response is edge- or static-origin-owned.

Do **not** call the bridge for requests routed to the backend; existing middleware remains authoritative there, and calling both creates duplicate writes.

The bridge should accept only the original method/path, referrer/user-agent, and existing analytics cookies over an operator-authenticated interface. The backend retains path sanitization, filtering, cookie generation, and queueing. Copy returned analytics cookies only onto the edge/static response. Call once with no retry; make failure observable but fail open for site availability unless the product requires otherwise. This preserves no-JavaScript, redirect, and unknown-page observations that an HTML pixel cannot capture.

## 6. Use one cache and rollback rule

Avoid combining mutable URLs with long-lived immutable caching. Choose one policy:

- require revalidation for every mutable frontend asset; or
- require new content-addressed filenames whenever a cacheable asset changes.

Apply the same rule at the browser, hosting provider, and edge. Define cache purge and probes for normal deployment, hosting rollback, and complete routing rollback. Atomic host deployment does not by itself prevent clients or an edge cache from mixing old assets with new HTML.

Keep two rollback controls until stabilization finishes:

1. redeploy the last known-good static release; and
2. atomically route public traffic back to the preserved application-served frontend.

Test both before cutover, retain the matching old application image/frontend, and verify cache state after rollback. Keep production cutover separately attended from local implementation, remote repository setup, preview hosting, and non-production routing.

## 7. Bootstrap least-privilege hosting access

Use the account root identity only to secure the account and bootstrap a constrained operator; never create or configure root access keys. Prefer temporary browser-backed CLI credentials over long-lived IAM access keys.

For an operator that initially needs only hosting inventory:

1. Create a dedicated IAM user with console access and MFA, then place it in a purpose-specific group rather than attaching broad policies directly.
2. Attach a customer-managed policy containing only the hosting provider's required `Get*` and `List*` actions. Do not substitute account-wide `ReadOnlyAccess`, `PowerUserAccess`, or a service-branded administrator policy; those exceed inventory scope.
3. When using AWS CLI v2 console sign-in, attach `SignInLocalDevelopmentAccess` for the OAuth login flow. Authenticate with `aws login --profile <profile> --region <region>`; do not create an IAM access key.
4. Validate the IAM username and password against the account-specific IAM sign-in URL in a private browser before debugging the CLI. If authentication is rejected, verify the exact username, console-access status, account sign-in link, and reset the IAM-user password; the root email and root password are not IAM-user credentials.
5. Verify the resulting profile without printing account identifiers or credential material: check that the profile exists, `sts get-caller-identity` succeeds, the ARN resolves to the expected constrained principal, and one read-only service call succeeds. Report booleans, principal class, region, and resource counts rather than raw identity output.
6. Set and read back the intended profile region explicitly; a successful `aws login --region ...` invocation may authenticate without persisting the profile's default region.
7. Separate authentication from authorization when troubleshooting: a missing profile means the browser flow did not complete; a successful identity call followed by `AccessDenied` means the service policy is incomplete.
8. Add provisioning permissions only at the separately authorized creation gate, scoped to the exact services and resources. Do not promote the inventory identity to administrator merely to unblock setup.

## 8. Install a regional hosting GitHub App without widening access

Treat repository-app installation, hosting-resource creation, branch connection, and deployment as separate gates. When the hosting provider supports a direct GitHub installation URL, the repository grant can proceed through an authenticated GitHub web session even when the provider console or CLI is unavailable; do not infer that one authentication channel unlocks another gate.

For AWS Amplify Hosting, derive the official region-specific installation URL from the AWS-documented template:

```text
https://github.com/apps/aws-amplify-{{REGION}}/installations/new
```

Then:

1. Confirm the GitHub App name includes the intended AWS region and its developer is `aws-amplify-console`; reject lookalike apps.
2. Select the organization owner, never the operator's personal account when organization ownership is required.
3. Choose **Only select repositories** and select exactly the approved frontend repository. Never choose all repositories for convenience.
4. Install the app, then read it back under the organization's installed GitHub Apps settings and confirm the exact repository list. The successful installation response alone is not sufficient verification.
5. Do not add the app as a repository-ruleset bypass actor unless a separately reviewed design requires it.
6. Stop after installation when hosting-resource creation has not been separately authorized. Installing the app does not authorize creating an Amplify app, connecting a branch, enabling automatic builds, or deploying.

Later, after AWS access is restored, reconnect through the Amplify console and verify that the repository picker exposes only the expected authorized repository before provisioning.

## 9. Verification checklist

Require all of these before public cutover:

- repository permissions prove the frontend publisher cannot modify protected paths or access backend/infrastructure repositories;
- only the artifact directory is published;
- route fixtures pass across methods, redirects, URL variants, errors, and reserved namespaces;
- forms preserve JavaScript and no-JavaScript behavior without preview mutations;
- analytics matches representative page, redirect, unknown-page, exclusion, and engagement behavior without double counting;
- direct hosting origins are inert and non-indexable;
- canonical responses never leak the hosting-provider origin;
- tracker, SEO, demo, accessibility, visual, header, and asset checks pass;
- cache probes pass after deploy and both rollback modes; and
- external repository creation, access grants, cloud configuration, deployment, and cutover remain explicit human gates.
