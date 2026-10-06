---
status: "acked 2026-01-12 #7e3f9639"
effort: E4
---

<!-- Fictitious example ("ApiBridge" is a teaching name; example.org is RFC 2606 reserved), the spec behind Examples/e4-api-migration.md. -->

# ApiBridge: REST to GraphQL

## Problem

The public API has 14 REST endpoints that over-fetch or under-fetch; 47 partner integrations route around them with stale caches, and they can't break: three partners ship quarterly.

## Goal

GraphQL at `api.apibridge.example.org/graphql` covers the read and write surface of the 14 REST endpoints, while REST keeps working byte for byte through a 6-month deprecation window, and no integration breaks before its confirmed migration date.
Said:
- move the public API to GraphQL without breaking the partners
Assumed:
- six months, 2026-04-22 to 2026-10-22, is long enough (a partner survey backs it).
- queries and mutations only; subscriptions are a separate item.

## Out of scope

Internal gRPC traffic, subscriptions, schema federation, an auth redesign.

## Constraints

- REST at `/v1/*` returns byte-identical responses until 2026-10-22.
- Apollo Server v4 or later; schema-first, with `schema/api.graphql` as the source of truth.

## Approaches

1. Schema-first, with REST served through the GraphQL resolvers by a thin adapter (chosen): one resolver path, two transports, so they can't drift apart.
2. REST handlers kept beside new resolvers: twice the code, and parity drifts. Rejected.

## S1 — Schema and resolvers

The SDL covering every REST shape, and resolvers over the existing data-access layer.
Accepted when:
- `schema/api.graphql` passes `graphql-schema-linter` and maps each of the 14 endpoints
- read resolvers return data byte-identical to REST for the 1,000-row golden fixture
- queries deeper than 8 levels, or costing over 1000, are refused

## S2 — REST adapter and deprecation

The 14 REST routes executed through the resolvers, with the sunset headers.
Accepted when:
- the REST contract tests pass unchanged through the adapter
- every REST response carries `Sunset: Wed, 22 Oct 2026 00:00:00 GMT`
- the cutover script exits non-zero while any partner lacks a `confirmed_migration_date`

## Decisions

- 2026-01-12: Apollo Server v4 over Yoga: the team knows it, and its persisted queries suit old SDKs.

## Open questions
