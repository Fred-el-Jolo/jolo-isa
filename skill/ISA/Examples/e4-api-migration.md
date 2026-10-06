---
task: "ApiBridge: REST to GraphQL"
slug: 20260112-091500_apibridge-graphql
effort: E4
phase: build
progress: 3/8
started: 2026-01-12T09:15:00
updated: 2026-02-03T18:00:00
root: /home/me/dev/apibridge
spec: specs/e4-api-migration.spec.md
spec_hash: 7e3f9639
acked: "2026-01-13 #3ce526ed"
asks: ["without breaking the partners"]
---

<!-- Fictitious example ("ApiBridge" is a teaching name). E4: four levels of criteria, mid-build — the schema proven, the resolvers half way. -->

## Problem

14 REST endpoints over-fetch or under-fetch; 47 partner integrations route around them, and none of them may break.

## Vision

A partner runs three example queries in the playground, sees that its nightly 14-call sync becomes one query, and migrates its staging environment in an afternoon.

## Out of Scope

Internal gRPC traffic, subscriptions, schema federation, an auth redesign.

## Principles

- A public API is a contract: a partner's build never breaks before its own migration date.
- One resolver path, two transports: REST and GraphQL can't drift if they share the code.

## Constraints

- REST at `/v1/*` returns byte-identical responses until 2026-10-22.
- Apollo Server v4 or later; schema-first, with `schema/api.graphql` as the source of truth.

## Goal

GraphQL at `api.apibridge.example.org/graphql` covers the read and write surface of the 14 REST endpoints, while REST keeps working byte for byte through a 6-month deprecation window, and no integration breaks before its confirmed migration date.

## Criteria

- [1/2] ISC-1: GraphQL serves every REST resource.
  - [x] ISC-1.1: The schema covers the 14 endpoints.
    - [x] ISC-1.1.1: The SDL is the source of truth.
      - [x] ISC-1.1.1.1: `schema/api.graphql` passes `graphql-schema-linter`.
      - [x] ISC-1.1.1.2: Each of the 14 endpoints maps to a query or a mutation.
  - [0/2] ISC-1.2: The resolvers answer like REST, and safely.
    - [1/2] ISC-1.2.1: Reads match REST.
      - [x] ISC-1.2.1.1: Reads are byte-identical to REST on the golden fixture.
      - [ ] ISC-1.2.1.2: Anti: a list query issues one SQL query per item.
    - [0/1] ISC-1.2.2: Expensive queries are refused.
      - [ ] ISC-1.2.2.1: A depth over 8, or a cost over 1000, is refused.
- [0/2] ISC-2: REST keeps working until the cutover.
  - [0/2] ISC-2.1: The adapter serves REST through the resolvers.
    - [ ] ISC-2.1.1: The REST contract tests pass unchanged.
    - [ ] ISC-2.1.2: Every REST response carries the sunset header.
  - [0/1] ISC-2.2: The cutover can't strand a partner.
    - [ ] ISC-2.2.1: The cutover script fails while a partner lacks a migration date.

## Test Strategy

```yaml
- isc: ISC-1.1.1.1
  anchors_to: S1
  kind: behaviour
  tool: npx graphql-schema-linter schema/api.graphql
- isc: ISC-1.1.1.2
  anchors_to: S1
  kind: behaviour
  tool: npm test -- --grep "every REST endpoint maps"
- isc: ISC-1.2.1.1
  anchors_to: S1
  kind: behaviour
  tool: npm test -- --grep "golden fixture parity"
- isc: ISC-1.2.1.2
  anchors_to: S1
  kind: regression
  tool: npm test -- --grep "one SQL query per list"
  fails-when: "a list of 100 items issues more than one SQL query"
- isc: ISC-1.2.2.1
  anchors_to: S1
  kind: behaviour
  tool: npm test -- --grep "depth and cost limits"
- isc: ISC-2.1.1
  anchors_to: S2
  kind: regression
  tool: npm run test:rest-contract
  fails-when: "a REST response differs from its recorded contract"
- isc: ISC-2.1.2
  anchors_to: S2
  kind: behaviour
  tool: 'curl -sI https://staging.apibridge.example.org/v1/orgs/1 | grep -q "^Sunset: Wed, 22 Oct 2026 00:00:00 GMT"'
- isc: ISC-2.2.1
  anchors_to: S2
  kind: behaviour
  tool: '! ./scripts/cutover.ts --dry-run --partners test/fixtures/partner-missing-date.json'
```

## Decisions

- 2026-01-19 10:00: schema-first with codegen: the SDL is what the partners read, so it is the source of truth.
- 2026-02-03 11:00: dead end — Apollo Federation across three services: gateway introspection was too slow; one schema instead.

## Verification

- ISC-1.1.1.1: red 2026-01-19 09:40 exit 1 — `npx graphql-schema-linter schema/api.graphql`
- ISC-1.1.1.1: verified 2026-01-26 16:02 exit 0 — `npx graphql-schema-linter schema/api.graphql`
- ISC-1.1.1.2: red 2026-01-19 09:40 exit 1 — `npm test -- --grep "every REST endpoint maps"`
- ISC-1.1.1.2: verified 2026-01-26 16:03 exit 0 — `npm test -- --grep "every REST endpoint maps"`
- ISC-1.2.1.1: red 2026-01-27 09:00 exit 1 — `npm test -- --grep "golden fixture parity"`
- ISC-1.2.1.1: verified 2026-02-03 17:45 exit 0 — `npm test -- --grep "golden fixture parity"`
- ISC-1.2.1.2: failed 2026-02-03 17:46 exit 1 — `npm test -- --grep "one SQL query per list"`
