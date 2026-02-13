---
name: app-store-connect-api
description: Reference and query the App Store Connect API from a bundled OpenAPI artifact. Use when implementing or reviewing App Store Connect endpoints, request/response payloads, query params, relationships, or operation coverage, and when translating API requirements into client code changes.
---

# App Store Connect API

Use this skill to work against the local App Store Connect OpenAPI definition in `references/openapi.oas.json`.

## Workflow

1. Start with a fast API overview.
Run:
`python skills/app-store-connect-api/scripts/query_spec.py summary`

2. Find candidate operations by feature keyword.
Run:
`python skills/app-store-connect-api/scripts/query_spec.py search "subscriptions" --limit 20`

3. Inspect one operation in detail before coding.
Run:
`python skills/app-store-connect-api/scripts/query_spec.py show GET /v1/apps`

4. Generate a compact operation index when repeated lookups are needed.
Run:
`python skills/app-store-connect-api/scripts/build_operation_index.py`

## Rules

- Prefer the scripts above instead of loading the full OpenAPI file into context.
- Resolve ambiguity by checking `operationId`, path, method, required params, request body, and response codes.
- When proposing code changes, cite the exact method and path used from the spec lookup.

## Resources

- OpenAPI source: `skills/app-store-connect-api/references/openapi.oas.json`
- Query helper: `skills/app-store-connect-api/scripts/query_spec.py`
- Index builder: `skills/app-store-connect-api/scripts/build_operation_index.py`
- Generated index (optional): `skills/app-store-connect-api/references/operation-index.json`
