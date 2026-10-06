---
status: acked 2026-01-12 #5e11e8ca
spec: docs/spec/2026-01-12-apibridge-graphql.md
---

<!-- Fictitious example, the plan of e4-api-migration.spec.md. Its project path would be docs/plan/2026-01-12-apibridge-graphql.md. P1 is done: its ISA's close ticked it and S1's bullets. -->

# Plan — ApiBridge: REST to GraphQL

Goal: GraphQL for all 14 REST endpoints, with REST served through it and deprecated over six months.
Approach: The schema first, so every later step builds on the generated types. Then the resolvers, then the REST adapter over them, and the deprecation headers, telemetry and cutover guard only once REST runs through the adapter.
Files:
- `schema/api.graphql` — the SDL, source of truth for both transports
- `src/generated/resolvers.ts` — the generated stubs, never edited by hand
- `src/resolvers/` — the resolvers over the existing data-access layer
- `src/rest/adapter.ts` — the REST routes executed through the resolvers
- `src/rest/sunset.ts` — the RFC 8594 headers
- `scripts/cutover.ts` — the cutover guard
Review focus:
- a token whose scopes allow a REST endpoint but not every field of the matching query → P2
- a GraphQL field returning personal data the matching REST endpoint does not → P2
- a REST client relying on `ETag` / `If-None-Match` caching through the adapter → P3

- [x] P1 — Schema and codegen · E2 · covers S1 · Done: 2026-02-02
  Files: `schema/api.graphql` (create), `codegen.yml` (create), `src/generated/resolvers.ts` (generated)
  Interfaces: produces the `Resolvers` type in `src/generated/resolvers.ts`
  Done when:
  - `graphql-schema-linter schema/api.graphql` passes, and each of the 14 endpoints maps to a query or mutation;
  - `npm run codegen` writes `src/generated/resolvers.ts`, and a second run leaves no diff.
- [ ] P2 — Resolvers · E3 · covers S2 · after P1
  Files: `src/resolvers/` (create), `src/server.ts` (change)
  Interfaces: consumes `Resolvers` from P1; produces `createLoaders(req) -> Loaders`, one set per request
  Done when:
  - reads byte-identical to REST on the 1,000-row golden fixture, writes with the same side effects;
  - p99 under 800 ms at 1,000 rps; a depth over 8 or a cost over 1000 refused.
- [ ] P3 — REST adapter · E3 · covers S3 · after P2
  Files: `src/rest/adapter.ts` (create), `src/rest/routes.ts` (change)
  Interfaces: consumes the executable schema of P2; produces `restRoute(method, path) -> Handler`
  Done when:
  - the REST contract tests pass unchanged, with under 5 ms p95 added;
  - `rest_via_adapter_enabled` rolled out in 10% steps to 100% before 2026-04-22.
- [ ] P4 — Deprecation and cutover · E3 · covers S4 · after P3
  Files: `src/rest/sunset.ts` (create), `scripts/cutover.ts` (create), `dashboards/deprecation.json` (create)
  Interfaces: consumes `restRoute` from P3; produces `partner-status.json`, regenerated nightly
  Done when:
  - the three headers on every REST response, with the values of S4:A1;
  - the dashboard counts per `partner_id`; `scripts/cutover.ts` exits non-zero while a partner lacks `confirmed_migration_date`.
