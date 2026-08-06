# Ptah gateway deployment

Use this reference when a saved Ptah connection must become active on a gateway, custom hostname, or production viewer.

## Contents

- [Discover the real platform](#discover-the-real-platform)
- [Verify the saved connection](#verify-the-saved-connection)
- [Create durable map configuration](#create-durable-map-configuration)
- [Control deployment scope](#control-deployment-scope)
- [Attach and verify the hostname](#attach-and-verify-the-hostname)
- [Run live acceptance](#run-live-acceptance)
- [Record deployment evidence](#record-deployment-evidence)

## Discover the real platform

Do not assume a name containing `gateway` is an SSH host.

Resolve:

- the Ptah admin or gateway origin
- the source repository and its local instructions
- the hosting provider and project
- whether deployment uses Pages, Workers, containers, SSH, or another surface
- which deployment command touches only the requested surface and which command also publishes companion services

Read the gateway repository's `AGENTS.md`, runbook, hosting configuration, and applicable provider skill before making production changes.

## Verify the saved connection

Inspect Airtable and resolve the actual table and view names before building the connection payload. Test before save, then verify after save.

Post-save verification must include:

- saved connection id
- exact live provider endpoint returned or configured by the connection; do not infer its route from the hostname
- native timestamp strategy accepted by the gateway
- provider count equal to the intended published count
- unique provider ids
- category and subcategory mappings present
- one representative provider with expected name, website, description, category, and subcategory

Saving a connection is not proof that the live data adapter works.

## Create durable map configuration

Keep hostname-specific configuration in the canonical gateway source repository. At minimum, make explicit:

- stable map id and display name
- custom hostname and canonical hostname
- hosting project
- saved Airtable connection id
- admin and submission settings

Run the repository's manifest generator and focused routing/config tests. Verify the built manifest maps the hostname to the intended map and that the built config contains the intended connection id.

If permissions require an isolated snapshot, record its source commit and the exact pre-existing dirty state. Do not call the deployment durable until the configuration is merged or otherwise persisted in the canonical repository; a later normal release must not remove the map silently.

## Control deployment scope

Before deployment:

1. inspect `git status`
2. inventory unrelated modified and untracked files
3. inspect the deployment script for companion Workers, functions, databases, or other services
4. run focused map tests, the repository release gate, and the production build
5. compare the requested scope with the actual deployable snapshot

Prefer the narrowest supported production command. A Pages-only map change should not silently redeploy companion Workers when a supported Pages-only path exists.

If the deployable snapshot contains pre-existing unrelated changes, explain the blast radius and require explicit user approval before publishing it. If a deployment is rejected for excessive scope, do not work around the rejection through an indirect command; choose a materially narrower supported path or request explicit approval.

## Attach and verify the hostname

Plan domain changes before applying them. Avoid removals unless explicitly authorized.

Verify:

- the custom domain is attached to the intended hosting project
- provider-side domain, certificate, and validation status are active
- authoritative and public DNS resolve to the intended target
- the desired-domain plan has no unexpected removals

Domain attachment and application routing are separate checks.

## Run live acceptance

After deployment, verify both the immutable deployment URL and the final custom hostname.

Require:

- custom root returns HTTP 200
- custom-domain manifest maps the hostname to the intended map id
- manifest points to the intended config path
- config exposes the intended map id, name, hostname, and connection id
- provider endpoint returns the expected total and unique ids
- taxonomy counts and a representative record are plausible
- settings endpoint returns the expected JSON response
- an intentionally invalid submission returns a validation error without sending mail

Hosting aliases may update before custom-domain routing or caches converge. Direct access to the new config file is not sufficient. Re-read the custom-domain manifest until it contains the new hostname mapping, and compare response headers or the immutable deployment URL when diagnosing propagation.

After a row leaves a filtered Airtable view, a view-scoped `Updated At` query may no longer observe the change that removed it. For retirement or deletion maintenance:

1. call the gateway's update detector
2. read the exact live provider endpoint and verify the retired ids are absent
3. prefer an explicit cache-refresh mechanism when the endpoint is stale
4. only when no refresh hook exists, use a reversible update to one still-published signal record, restore it immediately, and verify unrelated fields before reading the provider endpoint again

Do not declare a removal live from Airtable state alone.

## Record deployment evidence

Write a compact JSON or Markdown artifact containing:

- hostname and production URL
- hosting project
- deployment id and immutable URL
- connection id
- provider count and unique-id count
- category count
- endpoint status results
- change-detection result and cache status after any filtered-view removals
- release checks passed
- whether companion services were deployed
- whether the deployed configuration is present in canonical source

Update the progress log only after live acceptance. If canonical-source persistence is still pending, record it as an open deployment risk rather than declaring the workflow fully complete.
