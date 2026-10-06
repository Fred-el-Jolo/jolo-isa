---
status: acked 2026-01-12 #d24cd520
effort: E4
plan: docs/plan/2026-01-12-apibridge-graphql.md
---

<!-- Fictitious example, the spec behind Examples/e4-api-migration.md ("ApiBridge" is a teaching name; example.org is RFC 2606 reserved). Its project path would be docs/spec/2026-01-12-apibridge-graphql.md, with its plan in e4-api-migration.plan.md. S1 shows the marks `isa close` writes: P1's ISA proved both bullets. -->

# ApiBridge: REST to GraphQL

## Problem
The public API has 14 REST endpoints that over-fetch (one read of `/orgs/:id` returns 38 fields, the dashboard uses 6) or under-fetch (a project page costs 6 sequential GETs). 47 partner integrations route around it with caches that are stale more often than fresh, and they can't break: three partners ship quarterly.

## Goal
GraphQL at `api.apibridge.example.org/graphql` covers the read and write surface of the 14 REST endpoints, while REST keeps working, byte for byte, through a 6-month deprecation window with sunset headers and per-partner telemetry, and no integration breaks before its confirmed migration date.
Said:
- move the public API to GraphQL without breaking the partners
Assumed:
- six months, 2026-04-22 to 2026-10-22, is long enough (a partner survey backs it).
- queries and mutations only; subscriptions are a separate item.
- the existing OAuth 2.0 tokens and scopes are reused unchanged.

## Out of scope
Internal gRPC traffic, subscriptions, schema federation, an auth redesign, webhook payloads, the partner portal.

## Constraints
- REST at `/v1/*` returns byte-identical responses until 2026-10-22.
- GraphQL only at `api.apibridge.example.org/graphql`: no `/v2`, no new hostname.
- Apollo Server v4 or later on Node 20 LTS; schema-first, with `schema/api.graphql` as the source of truth.
- Every breaking change ships behind a default-off feature flag.
- Four increments (schema, resolvers, REST adapter, deprecation) and no big-bang cutover.

## Approaches
1. Schema-first, with REST served through the GraphQL resolvers by a thin adapter (chosen): one resolver path, two transports, so REST and GraphQL can't drift apart.
2. REST handlers kept beside new resolvers: twice the code, and parity drifts. Rejected.
3. A separate `api-v2` hostname, so the cutover is a DNS swap: partners that find services by URL would break. Rejected.

## S1 — Schema and codegen
Done: 2026-02-02 — 2/2 accepted (ISAs 20260119-100000_graphql-schema)
The SDL covering every REST shape, and the typed resolver stubs generated from it.
Accepted when:
- [x] A1: `schema/api.graphql` passes `graphql-schema-linter` and has a query or mutation for each of the 14 REST endpoints  (2026-02-02, ISA 20260119-100000_graphql-schema)
- [x] A2: codegen writes typed resolver stubs to `src/generated/resolvers.ts`, with no diff on a second run  (2026-02-02, ISA 20260119-100000_graphql-schema)

## S2 — Resolvers
Read and write resolvers over the existing data-access layer, enforcing the REST scopes.
Accepted when:
- [ ] A1: read resolvers return data byte-identical to REST for the 1,000-row golden fixture
- [ ] A2: write resolvers produce the same database side effects as the matching REST mutations
- [ ] A3: GraphQL p99 stays under 800 ms at 1,000 rps
- [ ] A4: queries deeper than 8 levels, or with a cost over 1000, are refused

## S3 — REST adapter
The 14 REST routes executed through the GraphQL resolvers, in `src/rest/adapter.ts`.
Accepted when:
- [ ] A1: the REST contract tests pass unchanged through the adapter
- [ ] A2: the adapter adds under 5 ms p95 over the direct handler
- [ ] A3: the rollout behind `rest_via_adapter_enabled` reaches 100% before 2026-04-22

## S4 — Deprecation and cutover
The sunset headers, the partner telemetry and the cutover guard.
Accepted when:
- [ ] A1: every REST response carries `Sunset: Wed, 22 Oct 2026 00:00:00 GMT`, `Deprecation: true` and a `Link` to the GraphQL docs
- [ ] A2: the dashboard at `internal.apibridge.example.org/deprecation` shows REST and GraphQL request counts per `partner_id`
- [ ] A3: the cutover script exits non-zero while any active partner has no `confirmed_migration_date`

## Decisions
- 2026-01-12: Apollo Server v4 over Yoga or a hand-rolled server: the team knows it, and its persisted-query support suits partners on old SDKs.
- 2026-01-12: a six-month window over three: four partners have quarterly release trains.
- second-look: the API team's lead read the spec before the ack; S2:A4 (depth and cost limits) and S4:A3 (the cutover guard) came from that review.

## Open questions
