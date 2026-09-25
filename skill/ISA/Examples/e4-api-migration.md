---
task: "Migrate the ApiBridge public API from REST to GraphQL"
slug: 20260112-091500_apibridge-rest-to-graphql-migration
project: ApiBridge
effort: E4
phase: execute
progress: 30/73
started: 2026-01-12T17:15:00Z
updated: 2026-04-22T03:48:00Z
---

<!-- Fictitious example. "ApiBridge" is a teaching project name; any resemblance to real products or organizations is coincidental. The example.org domain is RFC 2606 reserved. -->

## Problem

The ApiBridge public API at `api.apibridge.example.org` has accumulated 14 REST endpoints across 4 years of organic growth. Half of them are over-fetching (one read of `/orgs/:id` pulls 38 fields when the dashboard uses 6); the other half are under-fetching (rendering a single project page costs 6 sequential GETs because each related resource lives behind its own URL). External consumers — 47 known integrations across 12 partners — repeatedly hit the same N+1 patterns and route around them with caching that's now stale more often than fresh. Internally, every new product surface argues over which existing endpoint to bend versus which new one to add, and the answer is usually "add another," which makes the surface worse.

A GraphQL endpoint at `api.apibridge.example.org/graphql` lets clients ask for exactly the fields they need in one round trip. The migration is hard because the 47 integrations cannot break — partners will move at their own pace, and at least three of them publish quarterly release trains. The goal is not "GraphQL replaces REST tomorrow." The goal is "GraphQL is preferred, REST is supported for six months with clear deprecation telemetry, and at the end of the window every active consumer has either migrated or is opted into a paid extended-support track."

## Vision

A partner integration team opens our docs, sees a single GraphQL playground next to a dimmed REST reference labeled "deprecated April 2026 → October 2026," runs three example queries, and realizes their nightly sync that takes 14 round trips can become one. They migrate their staging environment in an afternoon. Six months later, our REST egress drops to under 2% of total API traffic, and the cutover ships without a single Sev-2.

## Out of Scope

- Internal service-to-service traffic. Internal callers continue using gRPC; this migration is for the public boundary only.
- GraphQL subscriptions. Pub/sub realtime is a separate roadmap item; v1 is queries and mutations only.
- Schema federation. We expose one monolithic GraphQL schema; we are not introducing Apollo Federation, schema stitching, or a gateway tier in this migration.
- Authentication redesign. Existing OAuth 2.0 bearer tokens are reused unchanged; no migration to mTLS, no new scopes, no re-issuing keys.
- Webhook redesign. Webhook payloads remain JSON-shaped per existing contracts; this migration does not touch outbound delivery.
- Self-service partner portal. Partners continue to be onboarded by the partnerships team; no portal changes ship as part of this work.

## Principles

- **Public APIs are contracts, not implementations.** A consumer cannot tell us "we'll fix it next quarter" and have us break their build before that quarter ends. Migration windows must respect external release cadence.
- **Deprecation is a product, not an event.** The deprecation experience — telemetry, sunset headers, dashboard, partner emails, escalation paths — is itself a feature with its own ISCs.
- **Every breaking change has a non-breaking adapter.** If GraphQL cannot serve a REST shape verbatim, we add a thin REST→GraphQL adapter rather than asking the partner to change shape immediately.
- **Performance is part of the contract.** GraphQL must not be slower than REST for equivalent queries at p95. Latency regressions are bugs.
- **Schema is owned by product, not by transport.** The shape of `Project`, `Organization`, `User` lives in one place and is consumed by both REST adapters and GraphQL resolvers; we do not duplicate types.

## Constraints

- The current REST API at `api.apibridge.example.org/v1/*` continues to return correct, byte-identical responses for the entire 6-month deprecation window (April 22, 2026 → October 22, 2026). No silent shape changes.
- GraphQL endpoint exposed at `api.apibridge.example.org/graphql` only. No `/v2`, no subdomain split, no separate hostname.
- Apollo Server v4+ on Node 20 LTS. We do not roll a custom GraphQL implementation. We do not pin to v3.
- Schema-first development with codegen. The SDL file at `schema/api.graphql` is the source of truth; resolvers are generated, not hand-written from scratch.
- Every breaking change ships behind a feature flag with a default-off rollout managed by the existing LaunchDarkly account.
- Sunset headers (`Sunset`, `Deprecation`, `Link`) are emitted on every REST response per RFC 8594 throughout the deprecation window. No exceptions.
- The migration ships in 4 increments (schema → resolvers → REST adapter layer → deprecation telemetry); no big-bang cutover.
- Documentation site at `docs.apibridge.example.org` must show GraphQL and REST side-by-side for the entire window; "REST docs deleted" is not an option until October 22, 2026.

## Goal

Ship the GraphQL endpoint at `api.apibridge.example.org/graphql` with full coverage of the 14 REST endpoints' read and write surface area, parity-tested under load, with a published 6-month deprecation runway for REST that emits RFC 8594 sunset headers, exposes per-partner deprecation telemetry on an internal dashboard, and lands the cutover without any external integration breaking before its partner-confirmed migration date.

## Criteria

- [x] ISC-1: `schema/api.graphql` exists, validates against `graphql-schema-linter`, and covers all 14 REST endpoint shapes.
- [x] ISC-2: GraphQL endpoint responds with `200` and a valid introspection result for `query { __schema { queryType { name } } }`.
- [x] ISC-3: All 14 REST endpoints have a corresponding query or mutation in the schema.
- [x] ISC-4: Schema codegen produces typed resolver stubs at `src/generated/resolvers.ts`.
- [x] ISC-5: 100% of read-side resolvers return data byte-identical to the matching REST endpoint for a 1,000-row golden fixture.
- [ ] ISC-6: 100% of write-side resolvers produce identical database side-effects to the matching REST mutation for the golden fixture.
- [ ] ISC-7: GraphQL p95 latency stays within its REST budget per query-shape tier.
  - [x] ISC-7.1: GraphQL p95 latency for the 5 most common query shapes is ≤ matching REST p95 + 10ms under 200 rps load.
  - [ ] ISC-7.2: GraphQL p95 latency for the 20 next-most-common query shapes is ≤ matching REST p95 + 25ms under 200 rps load.
- [ ] ISC-8: GraphQL p99 latency under 1000 rps load remains under 800ms.
- [x] ISC-9: REST responses include `Sunset: Wed, 22 Oct 2026 00:00:00 GMT` header.
- [x] ISC-10: REST responses include `Deprecation: true` header.
- [x] ISC-11: REST responses include `Link: <https://docs.apibridge.example.org/graphql>; rel="successor-version"`.
- [ ] ISC-12: Per-partner deprecation telemetry dashboard at `internal.apibridge.example.org/deprecation` shows REST request count, GraphQL request count, and migration percentage by partner ID.
- [ ] ISC-13: Dashboard shows the 5 most-called deprecated REST endpoints by partner.
- [ ] ISC-14: Dashboard alerts fire when any partner's REST traffic increases week-over-week after April 22, 2026.
- [x] ISC-15: All 47 known integrations are tagged with a `partner_id` in request logs.
- [ ] ISC-16: Migration emails sent to partner technical contacts at T-90, T-60, T-30, T-14, T-7, T-1 days from cutover.
- [x] ISC-17: GraphQL playground at `api.apibridge.example.org/graphql` loads in a browser with example queries pre-populated.
- [x] ISC-18: Documentation site shows GraphQL and REST side-by-side for every endpoint.
- [ ] ISC-19: Anti: REST endpoints return shape-changed responses during the deprecation window.
- [ ] ISC-20: Anti: GraphQL endpoint accepts queries deeper than 8 levels.
- [ ] ISC-21: Anti: GraphQL endpoint accepts queries with cost > 1000.
- [x] ISC-22: Anti: introspection is enabled in production.
- [ ] ISC-23: Anti: any partner is silently cut off.
- [x] ISC-24: Feature flag `graphql_endpoint_enabled` defaults to `false` and is explicitly enabled per environment.
- [x] ISC-25: Feature flag `rest_sunset_headers_enabled` defaults to `false` until April 22, 2026.
- [ ] ISC-26: Rollback runbook at `docs/runbooks/graphql-rollback.md` exists and has been dry-run executed in staging.
- [x] ISC-27: Schema changes go through PR review with at least one API-team approver.
- [x] ISC-28: Every resolver has a Datadog APM span tagged with `graphql.operation_name` and `graphql.field_name`.
- [ ] ISC-29: Authorization middleware enforces the same scopes on GraphQL fields as the matching REST endpoint requires.
- [ ] ISC-30: Rate limits applied per partner at the GraphQL layer match the REST layer.
- [ ] ISC-31: Error responses follow the structured GraphQL error spec with `extensions.code` set per error class.
- [x] ISC-32: REST request logs include `Accept-Migration` header value when partner sends it (used to track partners actively testing GraphQL).
- [ ] ISC-33: Partner status file `partner-status.json` lists every `partner_id` with fields `confirmed_migration_date`, `last_rest_request`, `first_graphql_request`, `migration_pct`.
- [ ] ISC-34: Status file is regenerated nightly from request logs.
- [ ] ISC-35: Partner support runbook at `docs/runbooks/partner-migration-support.md` covers the top 10 expected migration questions with copy-paste GraphQL equivalents.
- [ ] ISC-36: Public changelog entry posted at `docs.apibridge.example.org/changelog` announcing GraphQL availability with example queries.
- [ ] ISC-37: Public changelog entry posted announcing REST deprecation with sunset date.
- [x] ISC-38: GraphQL schema is published at `schema.apibridge.example.org/api.graphql` for tooling consumption.
- [ ] ISC-39: Schema diff CI gate fails the build if a breaking schema change is introduced without `BREAKING_CHANGE_APPROVED=true` env flag.
- [x] ISC-40: Resolvers reuse the existing data-access layer (no duplicate query logic between REST handlers and GraphQL resolvers).
- [ ] ISC-41: Load test simulating partner-realistic query patterns (mix of 60% reads, 30% writes, 10% complex nested queries) sustains 500 rps for 1 hour without error rate exceeding 0.5%.
- [x] ISC-42: GraphQL endpoint enforces request body size limit of 100KB.
- [x] ISC-43: GraphQL endpoint enforces query timeout of 10 seconds at the resolver layer.
- [ ] ISC-44: Anti: REST endpoint `/v1/orgs/:id/projects` returns 404 before October 22, 2026.
- [ ] ISC-45: Anti: any GraphQL field returns PII not present in the matching REST endpoint.
- [ ] ISC-46: Cutover dry-run executed at T-30 against staging with all 47 partner integrations simulated.
- [ ] ISC-47: Sentry release tag `graphql-cutover-v1` exists.
- [ ] ISC-48: PagerDuty escalation policy `graphql-launch` is on-call rotation for the 2 weeks following October 22, 2026.
- [x] ISC-49: GraphQL endpoint logs include `partner_id` extracted from the bearer token claim.
- [x] ISC-50: REST adapter layer at `src/rest/adapter.ts` translates REST routes to internal GraphQL execution (single resolver path, two transports).
- [ ] ISC-51: Adapter layer adds < 5ms p95 overhead vs. direct REST handler.
- [x] ISC-52: All 14 REST routes are now served by the adapter (legacy direct handlers deleted).
- [ ] ISC-53: Adapter is feature-flagged by `rest_via_adapter_enabled` and rolled out in 10% increments.
- [ ] ISC-54: Adapter rollout reaches 100% before deprecation telemetry begins (April 22, 2026).
- [ ] ISC-55: Migration retrospective document at `docs/retrospectives/graphql-migration.md` written by November 1, 2026.
- [x] ISC-56: GraphQL gateway has a circuit breaker that opens when downstream data layer error rate exceeds 5% over 60s.
- [ ] ISC-57: Circuit-breaker behavior documented in incident response runbook.
- [x] ISC-58: Persisted queries are supported via APQ (Automatic Persisted Queries) for partners that opt in.
- [ ] ISC-59: At least 3 partners using APQ in production by October 1, 2026.
- [ ] ISC-60: GraphQL access logs are retained for 90 days in the existing log retention bucket.
- [ ] ISC-61: Audit log for schema changes is queryable via `bun scripts/schema-history.ts`.
- [x] ISC-62: Anti: a single resolver makes more than 3 sequential database calls without batching via DataLoader.
- [x] ISC-63: DataLoader instances are created per-request, not per-process.
- [ ] ISC-64: Schema documentation generated from SDL comments and published to docs site.
- [ ] ISC-65: Partner-specific cost limits enforced (cost ≤ 500 for free tier, cost ≤ 2000 for paid tier, cost ≤ 5000 for enterprise tier).
- [x] ISC-66: GraphQL errors are scrubbed of internal stack traces in production responses.
- [ ] ISC-67: External health check at `api.apibridge.example.org/graphql/health` returns `200` with schema version.
- [ ] ISC-68: Anti: deprecation cutover proceeds with any partner still showing > 100 REST requests/day in the 7 days before cutover.
- [ ] ISC-69: Extended support contract template exists at `legal/extended-rest-support-template.md` for partners needing a paid runway past October 22, 2026.
- [ ] ISC-70: At most 3 partners are on extended support after October 22, 2026.
- [ ] ISC-71: Public status page at `status.apibridge.example.org` has a `graphql` component and a `rest` component, each with independent uptime SLOs.
- [ ] ISC-72: Final cutover postmortem published to docs site within 14 days of October 22, 2026.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: schema lint + REST shape coverage
  threshold: 0 lint errors, 14/14 shapes
  tool: graphql-schema-linter schema/api.graphql && node scripts/coverage-check.ts --shapes

- isc: ISC-2
  type: bash
  check: minimal introspection query
  threshold: 200 + queryType.name == "Query"
  tool: "curl -s -X POST https://api.apibridge.example.org/graphql -H \"Authorization: Bearer $ADMIN\" -d '{\"query\":\"{ __schema { queryType { name } } }\"}' | jq -r '.data.__schema.queryType.name'"

- isc: ISC-3
  type: bash
  check: every REST endpoint maps to a GraphQL field
  threshold: 14/14, exit 0
  tool: node scripts/coverage-check.ts

- isc: ISC-4
  type: bash
  check: codegen output is current
  threshold: file exists, empty git diff after regeneration
  tool: bun run codegen && git diff --exit-code src/generated/resolvers.ts

- isc: ISC-5
  type: parity-test
  check: GraphQL response body byte-equal to REST response for 1000 fixtures
  threshold: 1000/1000
  tool: bun test parity/read.test.ts

- isc: ISC-6
  type: parity-test
  check: DB side-effects of each mutation vs its REST twin on the golden fixture
  threshold: identical row diffs for every write
  tool: bun test parity/write.test.ts

- isc: ISC-7.1
  type: load
  check: GraphQL p95 vs REST p95 for top-5 query shapes
  threshold: GraphQL p95 ≤ REST p95 + 10ms at 200 rps
  tool: k6 run loadtests/p95-parity.js --env SHAPES=top5

- isc: ISC-7.2
  type: load
  check: GraphQL p95 vs REST p95 for shapes 6–25
  threshold: GraphQL p95 ≤ REST p95 + 25ms at 200 rps
  tool: k6 run loadtests/p95-parity.js --env SHAPES=next20

- isc: ISC-8
  type: load
  check: p99 at 1000 rps
  threshold: < 800ms
  tool: k6 run loadtests/p99-1000rps.js --summary-export=/tmp/p99.json && jq '.metrics.http_req_duration["p(99)"]' /tmp/p99.json

- isc: ISC-9
  type: bash
  check: Sunset header on every REST route
  threshold: 14/14 routes carry the exact value
  tool: bash scripts/rest-header-audit.sh Sunset 'Wed, 22 Oct 2026 00:00:00 GMT'

- isc: ISC-10
  type: bash
  check: Deprecation header on every REST route
  threshold: 14/14
  tool: bash scripts/rest-header-audit.sh Deprecation 'true'

- isc: ISC-11
  type: bash
  check: successor-version Link header on every REST route
  threshold: 14/14
  tool: bash scripts/rest-header-audit.sh Link '<https://docs.apibridge.example.org/graphql>; rel="successor-version"'

- isc: ISC-12
  type: screenshot
  check: dashboard per-partner table
  threshold: columns REST count, GraphQL count, migration % — one row per partner_id
  tool: screenshot of internal.apibridge.example.org/deprecation, viewed

- isc: ISC-13
  type: screenshot
  check: top-5 deprecated endpoints panel
  threshold: panel present with 5 rows for a sample partner
  tool: screenshot of the partner drill-down, viewed

- isc: ISC-14
  type: bash
  check: alert rule fires on synthetic week-over-week REST growth
  threshold: 1 alert in the test channel
  tool: bun scripts/replay-traffic.ts --partner test-p1 --rest-growth 20% --alert-dry-run

- isc: ISC-15
  type: bash
  check: request-log lines without partner_id over the last 24h
  threshold: "0"
  tool: logcli query '{app="api"} | json | partner_id=""' --since 24h --quiet | wc -l

- isc: ISC-16
  type: bash
  check: scheduled migration emails per partner
  threshold: 6 sends (T-90, -60, -30, -14, -7, -1) for each of 47 partners
  tool: bun scripts/email-schedule.ts --campaign graphql-migration --json | jq '[group_by(.partner_id)[] | length == 6] | all'

- isc: ISC-17
  type: screenshot
  check: playground with example queries
  threshold: editor shows the pre-populated example tabs
  tool: screenshot of api.apibridge.example.org/graphql, viewed

- isc: ISC-18
  type: bash
  check: docs pages with both GraphQL and REST samples
  threshold: 14/14
  tool: bun scripts/docs-audit.ts --require-tabs graphql,rest

- isc: ISC-19
  type: regression-probe
  check: REST shape diff vs frozen golden bodies
  threshold: zero diffs
  tool: bun test parity/rest-stability.test.ts   # daily cron

- isc: ISC-20
  type: bash
  check: depth-limit middleware blocks deep queries
  threshold: 400 on depth 9
  tool: |-
    curl -s -o /dev/null -w '%{http_code}' -X POST https://api.apibridge.example.org/graphql -H "Authorization: Bearer $PARTNER" --data @test/queries/depth9.json

- isc: ISC-21
  type: bash
  check: cost-analysis middleware blocks expensive queries
  threshold: 400 on cost 1001
  tool: |-
    curl -s -o /dev/null -w '%{http_code}' -X POST https://api.apibridge.example.org/graphql -H "Authorization: Bearer $PARTNER" --data @test/queries/cost1001.json

- isc: ISC-22
  type: bash
  check: introspection disabled in production
  threshold: 403 on __schema query with non-admin token
  tool: bun test security/introspection.test.ts

- isc: ISC-23
  type: bash
  check: cutover requires partner confirmation
  threshold: cutover.ts exits non-zero if any active partner_id lacks confirmed_migration_date
  tool: bun scripts/cutover.ts --dry-run --fixture test/fixtures/partner-status-missing-one.json; test $? -ne 0

- isc: ISC-24
  type: bash
  check: flag default and per-env overrides
  threshold: default false; enabled only in the envs listed
  tool: bun scripts/flags.ts show graphql_endpoint_enabled --json | jq '.default == false and (.overrides | length > 0)'

- isc: ISC-25
  type: bash
  check: sunset-header flag default
  threshold: "false"
  tool: bun scripts/flags.ts show rest_sunset_headers_enabled --json | jq '.default'

- isc: ISC-26
  type: bash
  check: runbook exists and staging dry-run is logged
  threshold: file exists + 1 dry-run record
  tool: |-
    test -f docs/runbooks/graphql-rollback.md && rg -c 'dry-run: staging' docs/runbooks/graphql-rollback.md

- isc: ISC-27
  type: bash
  check: CODEOWNERS entry for schema/
  threshold: 1 line
  tool: rg -c '^/?schema/\s+@api-team' .github/CODEOWNERS

- isc: ISC-28
  type: unit-test
  check: every resolver emits a span with both tags
  threshold: test passes for every field in the schema
  tool: bun test tracing/spans.test.ts

- isc: ISC-29
  type: parity-test
  check: required scopes per GraphQL field vs matching REST route
  threshold: identical for every pair
  tool: bun test auth/scope-parity.test.ts

- isc: ISC-30
  type: parity-test
  check: per-partner rate limits GraphQL vs REST
  threshold: identical limits for every tier
  tool: bun test rate-limit/parity.test.ts

- isc: ISC-31
  type: property
  property: "∀ error class e: a GraphQL error of class e has extensions.code == code(e)"
  generator: "one trigger per error class in src/errors.ts × random valid-looking inputs"
  runs: 500
  tool: bun test errors/codes.property.test.ts

- isc: ISC-32
  type: bash
  check: Accept-Migration echoed into the request log
  threshold: log line carries the sent value
  tool: "curl -s -H 'Accept-Migration: graphql-testing' https://api.apibridge.example.org/v1/orgs/test-org >/dev/null && logcli query '{app=\"api\"} |= \"graphql-testing\"' --since 1m --quiet | wc -l"

- isc: ISC-33
  type: bash
  check: every partner_id has all four fields
  threshold: jq prints true
  tool: jq '[.[] | has("confirmed_migration_date") and has("last_rest_request") and has("first_graphql_request") and has("migration_pct")] | all' partner-status.json

- isc: ISC-34
  type: bash
  check: age of partner-status.json
  threshold: < 26 hours
  tool: echo $(( ($(date +%s) - $(stat -c %Y partner-status.json)) / 3600 ))

- isc: ISC-35
  type: bash
  check: runbook question count with GraphQL snippets
  threshold: ≥ 10 `### Q` headings, each followed by a graphql code block
  tool: bun scripts/runbook-audit.ts docs/runbooks/partner-migration-support.md --min 10

- isc: ISC-36
  type: bash
  check: availability changelog entry with an example query
  threshold: entry present + ≥ 1 graphql code block
  tool: curl -s https://docs.apibridge.example.org/changelog | rg -c 'GraphQL (is )?available'

- isc: ISC-37
  type: bash
  check: deprecation changelog entry names the sunset date
  threshold: ≥ 1 match
  tool: curl -s https://docs.apibridge.example.org/changelog | rg -c 'October 22, 2026'

- isc: ISC-38
  type: bash
  check: published schema equals repo schema
  threshold: empty diff
  tool: diff <(curl -s https://schema.apibridge.example.org/api.graphql) schema/api.graphql

- isc: ISC-39
  type: bash
  check: CI gate on a branch with a breaking change
  threshold: job fails without the flag, passes with it
  tool: bash ci/test-schema-gate.sh

- isc: ISC-40
  type: bash
  check: SQL/query-builder calls inside resolvers
  threshold: zero matches (rg exits 1)
  tool: rg -n 'db\.(query|select|insert|update)\(' src/graphql/resolvers/

- isc: ISC-41
  type: load
  check: 1-hour soak at 500 rps, 60/30/10 read/write/nested mix
  threshold: error rate < 0.5%
  tool: k6 run loadtests/soak.js

- isc: ISC-42
  type: bash
  check: 101KB request body
  threshold: HTTP 413
  tool: head -c 103424 /dev/zero | tr '\0' 'a' | curl -s -o /dev/null -w '%{http_code}' -X POST --data-binary @- https://api.apibridge.example.org/graphql

- isc: ISC-43
  type: unit-test
  check: resolver that sleeps 11s
  threshold: aborted at 10s with TIMEOUT code
  tool: bun test resolvers/timeout.test.ts

- isc: ISC-44
  type: bash
  check: synthetic monitor status for /v1/orgs/:id/projects, last 7 days
  threshold: zero 404 results before 2026-10-22
  tool: bun scripts/monitor-history.ts rest-projects --since 7d --status 404 --count

- isc: ISC-45
  type: parity-test
  check: PII-tagged fields reachable via GraphQL vs REST per endpoint
  threshold: GraphQL set ⊆ REST set for every endpoint
  tool: bun test parity/pii-coverage.test.ts

- isc: ISC-46
  type: bash
  check: T-30 staging dry-run report
  threshold: 47/47 simulated partners pass
  tool: jq '.partners | map(select(.result=="pass")) | length' reports/cutover-dryrun-T30.json

- isc: ISC-47
  type: bash
  check: Sentry release exists
  threshold: exit 0
  tool: sentry-cli releases info graphql-cutover-v1

- isc: ISC-48
  type: bash
  check: on-call schedule window
  threshold: covers 2026-10-22 through 2026-11-05
  tool: pd schedule show graphql-launch --json | jq '.start <= "2026-10-22" and .end >= "2026-11-05"'

- isc: ISC-49
  type: bash
  check: partner_id in GraphQL access log matches token claim
  threshold: equal
  tool: bash scripts/log-claim-check.sh graphql

- isc: ISC-50
  type: bash
  check: REST routes resolved through the adapter
  threshold: 14/14 route registrations import src/rest/adapter.ts
  tool: rg -l "from '../rest/adapter'" src/rest/routes/ | wc -l

- isc: ISC-51
  type: load
  check: adapter overhead vs direct handler, same fixture
  threshold: p95 delta < 5ms
  tool: k6 run loadtests/adapter-overhead.js

- isc: ISC-52
  type: bash
  check: legacy direct handlers
  threshold: directory absent
  tool: test ! -d src/rest/handlers

- isc: ISC-53
  type: bash
  check: rollout steps recorded for rest_via_adapter_enabled
  threshold: steps are multiples of 10%
  tool: bun scripts/flags.ts history rest_via_adapter_enabled --json | jq '[.[].percent % 10 == 0] | all'

- isc: ISC-54
  type: bash
  check: date the adapter flag reached 100%
  threshold: before 2026-04-22
  tool: bun scripts/flags.ts history rest_via_adapter_enabled --json | jq -r 'map(select(.percent==100))[0].at'

- isc: ISC-55
  type: bash
  check: retrospective file and its first commit date
  threshold: exists, committed ≤ 2026-11-01
  tool: git log --diff-filter=A --format=%as -- docs/retrospectives/graphql-migration.md

- isc: ISC-56
  type: unit-test
  check: breaker opens at 5% errors over 60s
  threshold: open state after injected 6% error rate
  tool: bun test gateway/circuit-breaker.test.ts

- isc: ISC-57
  type: bash
  check: breaker section in the incident runbook
  threshold: ≥ 1 match
  tool: rg -c -i '^#+ .*circuit.breaker' docs/runbooks/incident-response.md

- isc: ISC-58
  type: bash
  check: APQ hash-only request after registration
  threshold: data returned, no PersistedQueryNotFound
  tool: bash scripts/apq-smoke.sh

- isc: ISC-59
  type: bash
  check: distinct partners sending APQ hashes in production
  threshold: ≥ 3 by 2026-10-01
  tool: logcli query '{app="api"} | json | apq="true"' --since 7d --quiet | jq -r .partner_id | sort -u | wc -l

- isc: ISC-60
  type: bash
  check: retention rule on the access-log bucket
  threshold: 90 days
  tool: aws s3api get-bucket-lifecycle-configuration --bucket apibridge-logs | jq '.Rules[] | select(.Filter.Prefix=="graphql/") | .Expiration.Days'

- isc: ISC-61
  type: bash
  check: schema-history script lists past changes
  threshold: exit 0 + ≥ 1 row
  tool: bun scripts/schema-history.ts --limit 1

- isc: ISC-62
  type: bash
  check: CI lint rule for sequential DB calls
  threshold: rule enabled + 0 violations
  tool: |-
    bunx eslint --rule 'apibridge/no-sequential-db-calls: error' src/graphql/

- isc: ISC-63
  type: unit-test
  check: two concurrent requests share no DataLoader cache
  threshold: test passes
  tool: bun test dataloader/scope.test.ts

- isc: ISC-64
  type: bash
  check: every SDL type documented on the docs site
  threshold: 0 undocumented types
  tool: bun scripts/docs-audit.ts --sdl schema/api.graphql --missing

- isc: ISC-65
  type: property
  property: "∀ tier t, ∀ query cost c: accepted ⇔ c ≤ limit(t), with limits free 500 / paid 2000 / enterprise 5000"
  generator: "tiers × costs around each limit (limit−1, limit, limit+1) plus random costs 0–10000"
  runs: 1000
  tool: bun test cost/tier-limits.property.test.ts

- isc: ISC-66
  type: bash
  check: forced resolver error in production mode
  threshold: response has no "at " stack frames
  tool: NODE_ENV=production bun test errors/scrub.test.ts

- isc: ISC-67
  type: bash
  check: external health check
  threshold: 200 + schema_version present
  tool: curl -s https://api.apibridge.example.org/graphql/health | jq -e '.schema_version'

- isc: ISC-68
  type: bash
  check: cutover with one partner above 100 REST req/day
  threshold: script exits non-zero
  tool: bun scripts/cutover.ts --dry-run --fixture test/fixtures/partner-high-rest.json; test $? -ne 0

- isc: ISC-69
  type: bash
  check: contract template exists
  threshold: exit 0
  tool: test -s legal/extended-rest-support-template.md

- isc: ISC-70
  type: bash
  check: partners with extended_support after cutover
  threshold: ≤ 3
  tool: jq '[.[] | select(.extended_support == true)] | length' partner-status.json

- isc: ISC-71
  type: bash
  check: status-page components and their SLOs
  threshold: graphql and rest components, each with its own SLO
  tool: curl -s https://status.apibridge.example.org/api/v2/components.json | jq '[.components[] | select(.name=="graphql" or .name=="rest") | .slo] | length'

- isc: ISC-72
  type: bash
  check: postmortem page and publish date
  threshold: live, dated ≤ 2026-11-05
  tool: curl -s https://docs.apibridge.example.org/postmortems/graphql-cutover | rg -o 'datetime="\K[0-9-]+'
```

## Features

```yaml
- name: SchemaAndCodegen
  description: Define `schema/api.graphql` covering all 14 endpoint shapes; wire up codegen for typed resolver stubs at `src/generated/resolvers.ts`.
  satisfies: [ISC-1, ISC-2, ISC-3, ISC-4, ISC-27, ISC-38, ISC-39, ISC-64]
  depends_on: []
  parallelizable: false

- name: ResolverImplementation
  description: Implement read and write resolvers backed by the existing data-access layer; ensure parity with REST responses; enforce auth scopes; per-request DataLoader.
  satisfies: [ISC-5, ISC-6, ISC-29, ISC-31, ISC-40, ISC-49, ISC-62, ISC-63, ISC-66]
  depends_on: [SchemaAndCodegen]
  parallelizable: true  # split by resource group: orgs/projects/users/billing/audit

- name: GatewayHardening
  description: Apollo Server config, depth limit, cost analysis, request size limit, query timeout, circuit breaker, persisted queries, error scrubbing, introspection lock-down.
  satisfies: [ISC-20, ISC-21, ISC-22, ISC-30, ISC-42, ISC-43, ISC-56, ISC-58, ISC-65]
  depends_on: [ResolverImplementation]
  parallelizable: true

- name: RestAdapter
  description: Build `src/rest/adapter.ts` so the 14 REST routes execute through GraphQL resolvers; flag-rolled to 100% before deprecation telemetry begins; preserves REST byte-shape.
  satisfies: [ISC-19, ISC-50, ISC-51, ISC-52, ISC-53, ISC-54]
  depends_on: [ResolverImplementation]
  parallelizable: false

- name: DeprecationTelemetry
  description: Sunset/Deprecation/Link headers, partner_id tagging, internal dashboard, weekly partner status emails, alerting on REST traffic regression, partner-status.json nightly regen.
  satisfies: [ISC-9, ISC-10, ISC-11, ISC-12, ISC-13, ISC-14, ISC-15, ISC-16, ISC-25, ISC-32, ISC-33, ISC-34]
  depends_on: [RestAdapter]
  parallelizable: true

- name: DocsAndPlayground
  description: GraphQL playground at the live endpoint with pre-populated examples; side-by-side REST/GraphQL docs; public changelog entries; published SDL.
  satisfies: [ISC-17, ISC-18, ISC-36, ISC-37]
  depends_on: [SchemaAndCodegen]
  parallelizable: true

- name: CutoverGovernance
  description: Per-partner confirmed_migration_date tracking, T-90/60/30/14/7/1 emails, dry-run at T-30, runbooks, status page components, postmortem.
  satisfies: [ISC-23, ISC-26, ISC-35, ISC-44, ISC-46, ISC-47, ISC-48, ISC-55, ISC-57, ISC-67, ISC-68, ISC-69, ISC-70, ISC-71, ISC-72]
  depends_on: [DeprecationTelemetry]
  parallelizable: false
```

## Decisions

- 2026-01-12 17:15: Apollo Server v4 over Yoga or a hand-rolled implementation. Existing team familiarity, mature plugin ecosystem, schema-first defaults. Yoga rejected because the persisted-query story is less mature for partners on legacy SDKs.
- 2026-01-19 22:00: Schema-first with codegen rather than code-first. The SDL is the contract the partners read; making it the source of truth means PR diffs on `schema/api.graphql` are reviewable as contract changes by people who don't read TypeScript.
- 2026-01-26 14:30: REST adapter layer (one resolver path, two transports) rather than maintaining REST handlers in parallel. Eliminates parity drift by construction. Cost: adapter overhead measured at ~3ms p95 in early prototype, well under the ISC-51 budget of 5ms.
- 2026-02-03 11:00: ❌ DEAD END: Tried Apollo Federation v2 to split the schema across 3 services owned by different product teams. Reverted after week-long spike — gateway introspection added 40ms p95 overhead and the team boundary was nominal (all 3 services share the same database). Single monolithic schema, owned by api-team, reviewed by product-team approvers per CODEOWNERS.
- 2026-02-10 09:45: 6-month deprecation window over 3 months. Partner survey (37 of 47 responded) showed 4 partners with quarterly release trains where a 3-month window would force an emergency rollout. Cost is real (longer parity guarantees, more telemetry overhead) but cheaper than 4 angry partners.
- 2026-02-18 16:20: refined: ISC-7 split into ISC-7.1 (top-5 query shapes, +10ms budget) and ISC-7.2 (next-20 shapes, +25ms budget); ISC-7 stays as their parent. The two budgets reflect that the top-5 are tightly optimized REST paths while the next-20 are over-fetching today and GraphQL will already be faster on those by virtue of asking for fewer fields.
- 2026-02-25 21:00: ❌ DEAD END: Considered exposing GraphQL at `api-v2.apibridge.example.org` so the cutover would be a DNS swap. Rejected — partner integrations using URL-based service discovery would have to change config rather than client library, and the URL change would have meant more breaking surface than the protocol change.
- 2026-03-04 10:00: APQ for partners that opt in, not mandatory. Mandatory APQ would force every partner to ship a registration step before going live; the migration cost is already non-trivial and APQ value is largest for the high-volume partners who will adopt it voluntarily.
- 2026-03-12 13:30: Cost limits per partner tier (500/2000/5000) calibrated against the most expensive REST endpoints' equivalent cost in the cost-analysis prototype; free-tier cap of 500 is ~2x the heaviest current REST call to leave migration headroom without leaving DoS surface.
- 2026-03-21 17:00: refined: added ISC-44 (synthetic monitor on deprecated endpoint pre-cutover) after partner-success team flagged that "deprecated" and "removed" had been conflated in two earlier migrations.
- 2026-04-08 09:30: Extended-support track capped at 3 partners (ISC-70). Operational cost of running parallel REST infrastructure past cutover scales worse than linearly; 3 is the threshold where a separate small REST cluster makes sense vs. ad-hoc bypass.
- 2026-04-15 22:15: refined: ISC-23 (anti: silent cutoff) hardened — the cutover script now reads `partner-status.json` and exits non-zero if any active partner_id is missing `confirmed_migration_date`. Earlier draft only logged a warning; partner-success caught a near-miss in dry-run where a newly added partner would have been cut off because the field was absent rather than false.

## Changelog

- 2026-02-18 conjectured: a single +10ms p95 budget would cover all GraphQL query shapes vs REST. / refuted by: prototype load test (k6, 200 rps) showed top-5 already at +8ms while shapes 6-25 ranged +12ms to +22ms — single budget would fail on hot paths and over-budget on long-tail. / learned: REST is irregularly optimized; the top-5 shapes have hand-tuned indexes, the rest don't. GraphQL inherits this asymmetry. / criterion now: ISC-7 → ISC-7.1 (top-5, +10ms) + ISC-7.2 (next-20, +25ms) — two budgets reflecting the underlying optimization asymmetry.

- 2026-02-25 conjectured: a `/v2` URL split would make cutover a clean DNS-level swap with no client code changes. / refuted by: partner survey identified 11 integrations using URL-based service discovery (env vars or config files); URL change would force config-file edits and re-deploy, while protocol change touches only the client library. / learned: URL stability is a stronger contract than transport stability for service-discovery-based partners. / criterion now: GraphQL co-located at `api.apibridge.example.org/graphql`; no `/v2`, no subdomain split — preserved as a Constraint.

- 2026-03-21 conjectured: the deprecation-window guarantee that "REST endpoints continue working" was sufficient. / refuted by: partner-success team review found that "endpoint working" had been ambiguously interpreted in two earlier minor-version cutovers — partners read it as "still routable," ops read it as "still serving the documented payload." / learned: the deprecation contract has to specify byte-shape stability AND endpoint reachability, separately, with separate probes. / criterion now: ISC-19 (Anti: REST shape changes) plus ISC-44 (Anti: REST endpoint returns 404 before cutover) — two probes, daily cadence, separate failure modes.

- 2026-04-15 conjectured: cutover script logging a warning when a partner_id was missing `confirmed_migration_date` was sufficient governance. / refuted by: dry-run revealed a newly onboarded partner whose record had been created without the field; warning was lost in normal log volume and the script proceeded. / learned: governance gates must hard-fail; partial enforcement of a binary anti-criterion is no enforcement. / criterion now: ISC-23 hardened — cutover script exits non-zero on missing field; partner-success owns the field-presence check in onboarding.

## Verification

- ISC-1: `graphql-schema-linter schema/api.graphql` exits 0; output `0 errors, 0 warnings`; `coverage-check --shapes` → `14/14`. Verified 2026-02-04.
- ISC-2: `curl -s -X POST api.apibridge.example.org/graphql -H "Authorization: Bearer $T" -d '{"query":"{ __schema { queryType { name } } }"}' | jq -r '.data.__schema.queryType.name'` returns `Query`. Verified 2026-02-12 (staging) and 2026-03-04 (production behind feature flag).
- ISC-3: `node scripts/coverage-check.ts` outputs `14/14 REST endpoints have a matching GraphQL field`. Verified 2026-02-15.
- ISC-4: `bun run codegen && git diff --exit-code src/generated/resolvers.ts` — exit 0. Verified 2026-02-15.
- ISC-5: `bun test parity/read.test.ts` reports `1000 passed, 0 failed`. Verified 2026-03-08.
- ISC-7.1: k6 run output for top-5 query shapes — REST p95: 87ms / GraphQL p95: 91ms (+4ms, well within +10ms budget). Verified 2026-03-22.
- ISC-9: `rest-header-audit.sh Sunset …` — `14/14 routes: Sunset: Wed, 22 Oct 2026 00:00:00 GMT`. Verified 2026-04-22.
- ISC-10: `rest-header-audit.sh Deprecation true` — `14/14`. Verified 2026-04-22.
- ISC-11: `rest-header-audit.sh Link …` — `14/14 routes: rel="successor-version"`. Verified 2026-04-22.
- ISC-15: `logcli query '{app="api"} | json | partner_id=""' --since 24h` — 0 lines. Verified 2026-03-01.
- ISC-17: screenshot `shots/playground-2026-03-04.png` viewed — three example tabs (`orgs`, `projects`, `createProject`) pre-populated. Verified 2026-03-04.
- ISC-18: `bun scripts/docs-audit.ts --require-tabs graphql,rest` — `14/14 pages OK`. Verified 2026-03-10.
- ISC-22: introspection probe with non-admin token returns `403 Forbidden` with body `{"errors":[{"message":"Introspection disabled in production","extensions":{"code":"INTROSPECTION_DISABLED"}}]}`. Verified 2026-03-04.
- ISC-24: `flags.ts show graphql_endpoint_enabled` — `default: false`, overrides `staging: true`, `production: true`. Verified 2026-03-04.
- ISC-25: `flags.ts show rest_sunset_headers_enabled` — `default: false`. Verified 2026-03-04.
- ISC-27: `rg '^/?schema/' .github/CODEOWNERS` — `/schema/  @api-team`. Verified 2026-02-02.
- ISC-28: `bun test tracing/spans.test.ts` — `52 passed` (one per schema field). Verified 2026-03-12.
- ISC-32: log query for `graphql-testing` after a tagged request — 1 line, `accept_migration="graphql-testing"`. Verified 2026-03-18.
- ISC-38: `diff <(curl -s https://schema.apibridge.example.org/api.graphql) schema/api.graphql` — empty. Verified 2026-03-04.
- ISC-40: `rg -n 'db\.(query|select|insert|update)\(' src/graphql/resolvers/` — no matches. Verified 2026-04-10.
- ISC-42: 101KB body → `413`. Verified 2026-03-04.
- ISC-43: `bun test resolvers/timeout.test.ts` — `1 passed` (aborted at 10.00s, code `TIMEOUT`). Verified 2026-03-04.
- ISC-49: `log-claim-check.sh graphql` — 500/500 sampled lines match the token claim. Verified 2026-03-18.
- ISC-50: `rg -l "from '../rest/adapter'" src/rest/routes/ | wc -l` — `14`. Verified 2026-04-10.
- ISC-52: `test ! -d src/rest/handlers` — exit 0 (final commit `9f3e2a1` deleted all 14 legacy handlers). Verified 2026-04-10.
- ISC-56: `bun test gateway/circuit-breaker.test.ts` — `3 passed` (open at 6% injected errors, half-open after 30s). Verified 2026-03-25.
- ISC-58: `apq-smoke.sh` — hash-only request returned data after registration, no `PersistedQueryNotFound`. Verified 2026-04-02.
- ISC-62: `eslint --rule 'apibridge/no-sequential-db-calls: error' src/graphql/` — 0 problems. Verified 2026-04-10.
- ISC-63: `bun test dataloader/scope.test.ts` — `2 passed`. Verified 2026-03-12.
- ISC-66: `NODE_ENV=production bun test errors/scrub.test.ts` — `4 passed`, no stack frames in any response. Verified 2026-03-12.
