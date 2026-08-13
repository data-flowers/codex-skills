# Credential sourcing

Use this reference when a model API, Airtable PAT, deployment token, or other
secret is needed.

## Authorized source order

Use credentials only from:

1. the current process environment
2. the active working area's ignored `.env`
3. one explicitly named local project or secret source supplied by the user

A generic instruction such as “use the PAT” does not identify a source when
multiple unrelated projects contain tokens. Ask the user to name the source or
configure the active `.env`. Do not enumerate, copy, or test unrelated project
credentials to discover which one works.

## Handling rules

- Report only presence, variable name, and authorized source label or path.
- Never print, log, commit, or record secret values.
- When the user explicitly names another local project, copy only the requested
  variable into the active ignored `.env`; keep the current target ids
  authoritative.
- Record credential status and source provenance separately, for example
  `"pat": "present"` and `"credentialSource": "active-workspace-env"`.
- Treat authentication failure as an access finding, not permission to try other
  credentials.
- Never use browser cookies, local storage, password stores, or session files as
  a substitute for an API token.

Use an authenticated browser directly when the user asks for their signed-in
session or when UI-only setup is required. That authorizes interaction with the
visible service, not extraction of its credentials for API use.
