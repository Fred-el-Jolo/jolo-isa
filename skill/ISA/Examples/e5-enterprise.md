---
task: "Build the Beacon Health multi-region HIPAA patient portal"
slug: 20260108-070000_beaconhealth-portal-v1
project: BeaconHealthPortal
effort: E5
phase: execute
progress: 47/68
started: 2026-01-08T15:00:00Z
updated: 2026-04-28T20:30:00Z
context_sufficient: true
interview_ran: 2026-01-08T16:00:00Z
---

<!-- Fictitious example. "Beacon Health Alliance" is a teaching project name; any resemblance to real products or organizations is coincidental. The portal.beaconhealth.example.org domain is RFC 2606 reserved. -->

## Problem

Beacon Health Alliance — a 50-hospital regional health system spanning the Pacific Northwest, Mountain, and Midwest census regions, with approximately 11,400 employed clinicians, 38,000 affiliated providers, and a covered patient population of ~3.2 million — currently operates a patient portal forked from a 2014 vendor codebase that is end-of-life on 2027-06-30. The legacy portal is a single-region monolith hosted on a tier-2 colo with no documented disaster recovery RTO better than 14 hours; auth is a homegrown OAuth 1.0a implementation with documented session-fixation issues; the audit log writes to a local Postgres instance with 90-day retention (HIPAA mandates a defensible 6-year retention floor in this organization's compliance posture); and the appointment-scheduling subsystem cannot honor the 2025 acquisition of the 14-hospital Cascade Care Group, whose existing records live in a MEDITECH instance that the legacy portal has no integration path to. Patients today see only their primary-region records; clinicians moving between regions cannot view a unified longitudinal chart; auditors run quarterly reports that require manual reconciliation against the source EHR because the portal's audit trail is not authoritative. The replacement is a 2026 Q1–Q4 strategic program with executive sponsorship, a Q1 2027 cutover deadline driven by the legacy vendor's hard end-of-life date, and a budget gate at the end of Q1 2026 that requires Phase 1 (identity + read-only chart access) live in a production canary by 2026-04-30.

## Vision

A unified patient portal at `portal.beaconhealth.example.org` serving all 50 hospitals across three regions, where a patient logs in with SSO + step-up MFA, sees their complete longitudinal chart regardless of which hospital generated which record, books an appointment with any in-network clinician in any region, messages their care team through a HIPAA-conformant inbox, views lab results within 4 hours of resulting (CMS Cures Act minimum), receives e-prescriptions handed off to their preferred pharmacy without a portal-side copy of PHI persisted beyond the handoff window, and never sees a "your records from <other region> are unavailable" error. Clinicians see a single chart view independent of source EHR. Auditors see an immutable, queryable, 6-year-retained audit log that is authoritative for compliance attestation. Delight: a patient who moved from the Pacific Northwest region to the Midwest region in 2025, got admitted at a Cascade Care hospital in 2026, and saw her unified chart on day one without having to fax records — and her primary care physician at the originating hospital saw the encounter note within 20 minutes of discharge.

## Out of Scope

- **No native iOS or Android applications in v1.** Mobile experience is via responsive web (PWA install on iOS 17+ and Android 14+); native apps are a separate program scoped for FY28.
- **No telehealth video integration.** The portal links out to the existing telehealth vendor; in-portal video is not part of v1.
- **No patient self-pay billing UI.** Statements and receipts are read-only; payment processing remains in the existing patient-financial-services platform until v2.
- **No third-party API marketplace.** SMART-on-FHIR app launches are deferred to v1.1; no developer-portal, no app store, no third-party app reviews in v1.
- **No multi-language UI in v1.** English only at launch; Spanish ships in v1.1 (2027 Q3); additional locales evaluated in 2028.
- **No employer / wellness-program integrations.** Employer dashboards and population-health analytics are different products owned by the population-health line.
- **No research-cohort enrollment flows.** Research-data deidentification and export is a separate downstream system; the portal does not initiate research workflows in v1.
- **No coverage of skilled-nursing or behavioral-health subsidiaries.** Those EHRs are out of scope for v1; their patients use a legacy portal until v1.2.
- **No PHI persisted in the e-prescription handoff path.** Prescription objects are signed, transmitted to Surescripts, and the portal-side copy is purged within the handoff TTL window. The portal is not a long-term store for prescription content.

## Principles

- Compliance is not a layer; it is a property of the system. Every architectural choice is judged against whether it makes HIPAA, HITRUST, and state-level health-data laws easier or harder to attest to.
- The audit log is authoritative. If an action is not in the audit log it did not happen; if it is in the audit log it cannot be edited. Authoritativeness beats convenience every time.
- Zero-trust between subsystems. Inter-service auth uses short-lived SPIFFE-style identities; no service trusts another service because of network position.
- The patient is the principal. RBAC starts from "the patient owns their record"; clinicians and admins have access by virtue of relationship + role + business justification, not by virtue of being employees.
- Multi-region is a load-balancing concern AND a compliance concern. Data-residency rules, BAA boundaries, and cross-region failover semantics are part of the architecture, not an operational afterthought.
- Operability is a first-class deliverable. A feature is not done when it works; it is done when on-call can diagnose its failures from the dashboards and runbooks.
- Vendor consolidation is not a goal. Best-of-breed where the cost of integration is paid back; "single pane of glass" is a marketing phrase, not an architectural principle.

## Constraints

- **Hosting:** AWS three-region active-active (us-west-2, us-east-1, us-east-2) with primary read traffic served from the closest region; writes go to a regional primary with synchronous replication for compliance-relevant tables and asynchronous replication for the rest.
- **Data residency:** All PHI persists exclusively within US-region AWS accounts under signed BAAs; no PHI in any non-US region, edge cache, or non-BAA service.
- **Identity:** Enterprise SSO via the existing Okta tenant federated to Azure AD for Beacon employees; patient identity uses Auth0 with passwordless email + step-up MFA (TOTP or WebAuthn); no patient passwords in the system.
- **EHR integration:** FHIR R4 against Epic (40 hospitals), MEDITECH Expanse (10 hospitals from the Cascade acquisition), and Cerner (legacy contracts on the affiliated network). HL7 v2 only as a fallback when FHIR R4 is not yet stood up at a particular site.
- **Audit log:** Append-only, 6-year minimum retention, queryable for compliance reporting, hash-chained for tamper evidence, replicated to immutable S3 with object-lock in compliance mode.
- **Session management:** 15-minute idle timeout for clinician/admin/auditor roles (HIPAA minimum-implementation guidance); 30-minute idle timeout for patient role; absolute session lifetime 12 hours for any role.
- **Encryption:** TLS 1.3 in transit; AES-256-GCM at rest; PHI fields envelope-encrypted with KMS keys scoped per data domain (clinical, demographic, financial); rotated quarterly.
- **BAAs:** No vendor in the PHI data path operates without a signed BAA on file with corporate compliance. Vendor onboarding requires a documented BAA SHA reference in the architecture log.
- **Performance:** Patient-facing pages p95 ≤ 1.2s on 4G; clinician chart view p95 ≤ 1.8s on hospital LAN; appointment-search autocomplete p95 ≤ 250ms.
- **Accessibility:** WCAG 2.2 AA across all patient-facing surfaces; clinician surfaces meet WCAG 2.1 AA minimum.
- **Code base:** TypeScript on the application tier (Node 22); FHIR adapters in TypeScript with a Rust shim where parsing throughput dominates; infrastructure as Terraform; secrets via AWS Secrets Manager; no roll-your-own crypto.

## Goal

Deliver a multi-region active-active patient portal at `portal.beaconhealth.example.org` that replaces the legacy 2014 forked codebase before the 2027-06-30 vendor end-of-life, unifies records across all 50 hospitals (Epic, MEDITECH, Cerner) into a single longitudinal view, supports patient/clinician/admin/auditor roles with HIPAA-conformant audit logging at 6-year retention, exposes appointment scheduling and secure messaging across all regions, provides authoritative read-only chart access plus e-prescription handoff to Surescripts, and stays inside the data-residency, BAA, encryption, and session-management constraints across both standard operations and regional failover.

## Criteria

### Identity and Authentication

- [x] ISC-1: Patient login at `/auth/patient` accepts an email, sends a 10-minute-expiry magic link, and creates a session on callback.
- [x] ISC-2: Patient step-up MFA is required before any chart-data action; MFA factor is TOTP, WebAuthn, or SMS (SMS only as fallback for patients without smartphones).
- [x] ISC-3: Clinician login at `/auth/clinician` redirects to Okta SAML, returns with a clinician-role session bound to the clinician's NPI.
- [x] ISC-4: Admin and auditor logins use Okta with a separate role-claim mapping; admin and auditor sessions cannot be promoted to clinician without a fresh login.
- [x] ISC-5: Session cookies are `HttpOnly; Secure; SameSite=Lax`; refresh tokens are stored server-side keyed on a session ID, never in the cookie.
- [x] ISC-6: Idle timeout is 15 minutes for clinician/admin/auditor and 30 minutes for patient; absolute session lifetime is 12 hours.
- [x] ISC-7: Failed authentication attempts are rate-limited per identifier (10 / 5min for patient email; 5 / 5min for SSO subject).
- [x] ISC-8: A logout invalidates the session in the session store within 1 second; the cookie is cleared client-side.

### RBAC and Authorization

- [x] ISC-9: Patient role can read only their own chart; queries scoped to `patient_id = session.subject`.
- [x] ISC-10: Clinician role can read a patient chart only when a documented clinician-patient relationship exists in the relationship service (encounter, scheduled appointment, referral, or break-glass with audit).
- [x] ISC-11: Admin role gates `/admin/*` routes; non-admin sessions receive HTTP 403.
- [x] ISC-12: Auditor role can read audit log queries via `/audit/*` but cannot read PHI directly.
- [x] ISC-13: Break-glass access (clinician without prior relationship) requires a one-line stated reason and writes a high-priority audit event flagged for compliance review.
- [ ] ISC-14: Role transitions in a session require re-authentication; a clinician who is also an admin must log in twice to use both surfaces in one day.

### Identity-Linkage and Patient Matching

- [x] ISC-15: Patient identity at the portal level resolves to a single longitudinal patient record across all 50 hospitals via the enterprise master patient index (eMPI).
- [x] ISC-16: When eMPI returns a probable-match below confidence threshold 0.95, the portal does NOT auto-merge; it surfaces a "we need to verify your identity" flow.
- [ ] ISC-17: Patient-initiated record-linking offers a verifiable challenge (DOB + last 4 SSN + DL number, or insurance card + verified phone) before merging across regions.

### Appointment Scheduling

- [x] ISC-18: Appointment search autocomplete returns ≥ 10 candidates in p95 ≤ 250ms across all 50 hospitals.
- [x] ISC-19: Booking an appointment writes to the source EHR via FHIR R4 `Appointment.create` and returns a confirmation with the EHR-issued appointment ID.
- [x] ISC-20: A booking failure (EHR rejection, slot taken) shows a recoverable error and offers the next 3 alternatives.
- [ ] ISC-21: Cancellation propagates back to the source EHR within 60 seconds; the patient sees the canceled state immediately.
- [ ] ISC-22: Multi-region availability: a patient in the Pacific Northwest can book at any of the 14 Cascade Care (Midwest) hospitals; cross-region booking carries a "this appointment is at <region>" disclosure.

### Lab Results and Chart Access

- [x] ISC-23: Lab results visible in the portal within 4 hours of EHR resulting (CMS Cures Act floor; the org's internal SLA is 1 hour).
- [x] ISC-24: Critical-flag results show an in-app banner and trigger a notification to the patient's preferred channel (push or email; never SMS for content).
- [ ] ISC-25: Chart view aggregates encounters across all source EHRs into a single timeline ordered by clinical-effective date.
- [ ] ISC-26: Patients can download a Continuity of Care Document (CCD/C-CDA) covering the last 5 years in p95 ≤ 8 seconds.

### Secure Messaging

- [x] ISC-27: Patient-initiated messages route to the addressed care team's shared inbox in the source EHR within 30 seconds.
- [x] ISC-28: Clinician replies appear in the patient's portal inbox within 60 seconds of EHR send.
- [x] ISC-29: Messages are end-to-end encrypted in transit and at rest; the portal stores ciphertext keyed to the patient session and the EHR thread ID.
- [ ] ISC-30: Messages older than 7 years are purged from the portal store; the EHR remains the long-term system of record for clinical communication.

### E-Prescription Handoff

- [ ] ISC-31: Prescription objects are signed by the prescribing clinician, transmitted to Surescripts, and the portal-side copy is purged within 24 hours of handoff.
- [ ] ISC-32: A patient can view their active prescriptions (read-only summary, sourced live from the EHR pharmacy module — not from a portal copy).
- [ ] ISC-33: Refill-request flow returns the patient to the EHR's pharmacy queue within 60 seconds of submission.

### Audit Logging

- [x] ISC-34: Every read of PHI by any role writes an audit event with `(timestamp, actor_id, actor_role, action, patient_id, data_class, justification, request_id)`.
- [x] ISC-35: Audit events are hash-chained; a tampered event breaks the chain and is detected by the integrity-check job within 1 hour.
- [x] ISC-36: Audit log retention is ≥ 6 years; daily snapshots replicate to S3 with object-lock in compliance mode (cannot be deleted before retention).
- [x] ISC-37: Auditor role can query audit events by patient, by actor, or by time window; query results render p95 ≤ 5 seconds for 30-day windows.
- [ ] ISC-38: Compliance attestation report (monthly) is generated automatically and stored at a defensible retrieval path with cryptographic signature.

### Multi-Region Failover

- [x] ISC-39: Synthetic regional-failure drill quarterly: a single-region outage in us-west-2 drains traffic to us-east-1 within 5 minutes with zero clinical-data loss for committed writes.
- [ ] ISC-40: Read traffic during single-region outage maintains p95 latency within 1.5× of steady-state (no full SLO collapse).
- [ ] ISC-41: Cross-region replication lag p99 ≤ 60 seconds for compliance-relevant tables (audit, identity, RBAC); ≤ 5 minutes for non-compliance tables.
- [ ] ISC-42: A two-region simultaneous outage degrades to read-only mode in the surviving region; writes return HTTP 503 with a "service degraded" page; no PHI loss.

### Observability

- [x] ISC-43: Every request carries a correlation ID propagated to the EHR adapter and surfaced in support tooling.
- [x] ISC-44: Dashboards exist for: identity (login/MFA success/failure rates), authorization (403 / break-glass rates), EHR latency (per-source p50/p95/p99), audit log volume + integrity, regional health.
- [x] ISC-45: On-call runbooks cover the top 12 alerting scenarios with explicit "this is a false positive when …" notes.
- [ ] ISC-46: SLO dashboards visible to the patient ombudsman office show monthly availability against the 99.95% target with breach narratives.

### Build, Deploy, Release

- [x] ISC-47: Infrastructure provisioned exclusively via Terraform; click-ops in the AWS console is alarmed and reverted.
- [x] ISC-48: All deploys are blue/green per region; rollback completes in ≤ 90 seconds.
- [x] ISC-49: A failed canary in any region rolls back automatically and pages on-call within 60 seconds.
- [x] ISC-50: Production secrets live in AWS Secrets Manager; no secrets in env vars baked into images, no secrets in Terraform state.
- [ ] ISC-51: Release notes for every production deploy are auto-generated from PR descriptions and posted to the change-management ticket.

### Phase 1 Canary (2026-04-30 budget gate)

- [x] ISC-52: Phase 1 scope shipped to canary at `portal.beaconhealth.example.org/canary`: identity + RBAC + read-only chart from Epic for 1 hospital + audit log + observability.
- [x] ISC-53: Phase 1 canary serves ≥ 200 enrolled real-patient testers without P1 incident over a 14-day soak.
- [x] ISC-54: Phase 1 canary passes a third-party HIPAA risk-assessment audit (HITRUST validated assessor) with zero open high-severity findings.

### Phase 2 Cutover from Legacy MEDITECH (Q3 2026)

- [ ] ISC-55: 14 Cascade Care hospitals (MEDITECH Expanse) integrated via FHIR R4; chart unification across Epic + MEDITECH live for ≥ 1,000 enrolled patients.
- [ ] ISC-56: Phase 2 cutover plan signed off by Cascade Care CMIO and Beacon CMIO with explicit rollback criteria.
- [ ] ISC-57: Legacy MEDITECH portal entry points redirect to the new portal with no patient action required; redirect uptime ≥ 99.95% for 90 days.

### Phase 3 (Q4 2026)

- [ ] ISC-58: 100% of patient population has access; legacy portal is decommissioned and the legacy database is sealed for archival retention.
- [ ] ISC-59: Q4 audit by external HITRUST assessor returns "Certified" rating with no MRSAs (Major Required Supplemental Assessor) findings.

### Anti-criteria

- [x] ISC-60: Anti: PHI in URL — PHI never appears in URL query strings logged by the edge proxy or the WAF.
- [x] ISC-61: Anti: audit log retention floor — audit log retention never falls below 6 years; the daily integrity-check job verifies the oldest retained event is ≥ 6y - 7d (alarm fires before retention is lost).
- [x] ISC-62: Anti: BAA gap — no vendor in the PHI data path operates without a signed BAA; the architecture log enumerates every vendor with their BAA SHA reference and the reconciliation job alerts on any unrecognized vendor in the data path.
- [x] ISC-63: Anti: session timeout — session idle timeout never exceeds 15 minutes for clinician/admin/auditor roles; a config drift that exceeds 15 fails the deploy preflight.
- [x] ISC-64: Anti: PHI in non-US region — no PHI persists in any non-US AWS region, edge cache, or non-BAA service.
- [x] ISC-65: Anti: cross-region transit without BAA — PHI in transit between regions traverses only AWS-internal (BAA-covered) network paths; no public internet hops.
- [x] ISC-66: Anti: patient password — no patient password is ever stored, hashed or otherwise; passwordless-only is enforced at the auth layer with a deploy-time test that asserts the password column does not exist.
- [x] ISC-67: Anti: silent role escalation — no code path elevates a session role without re-authentication; a static analysis rule blocks any in-process role mutation.
- [x] ISC-68: Anti: audit-log writability — audit events are never updated or deleted by application code; only the retention-compliance job (running under a separate IAM role) can prune events that have exceeded the 6-year window, and only by writing a tombstone, never by deletion.

## Test Strategy

```yaml
- isc: ISC-1
  type: unit-test
  check: magic-link issue, 10-minute expiry, session on callback
  threshold: link works at 9m59s, fails at 10m01s; callback sets a session
  tool: bun run scripts/auth-magic-link.ts

- isc: ISC-2
  type: property
  property: "∀ chart-data action a, ∀ patient session s without a fresh MFA step: a → 401 mfa_required"
  generator: "every chart-data route × sessions with no MFA, stale MFA, and each factor type"
  runs: 1000
  tool: bun test test/auth/step-up.property.test.ts

- isc: ISC-3
  type: bash
  check: clinician SSO round-trip against the Okta test tenant
  threshold: session role clinician, npi claim equals the test user's NPI
  tool: bun run scripts/saml-roundtrip.ts --role clinician --expect-npi 1234567893

- isc: ISC-4
  type: unit-test
  check: admin/auditor session asking for a clinician route
  threshold: 401 reauth_required; no in-place promotion
  tool: bun test test/auth/role-separation.test.ts

- isc: ISC-5
  type: bash
  check: cookie flags and cookie contents
  threshold: HttpOnly, Secure, SameSite=Lax; no refresh token in any cookie
  tool: bun run scripts/cookie-audit.ts --all-roles

- isc: ISC-6
  type: bash
  check: idle timeouts per role + absolute lifetime
  threshold: clinician 401 at minute 16; patient 401 at minute 31; any role 401 at 12h01m
  tool: bun run scripts/session-idle-timeout.ts --role all --fake-clock

- isc: ISC-7
  type: bash
  check: request number that gets 429
  threshold: 11th patient-email attempt and 6th SSO-subject attempt within 5 minutes
  tool: bun run scripts/auth-rate-limit.ts

- isc: ISC-8
  type: bash
  check: session store and cookie after logout
  threshold: session row gone ≤ 1s; Set-Cookie clears the cookie
  tool: bun run scripts/logout-probe.ts

- isc: ISC-9
  type: property
  property: "∀ patients p ≠ q: a session for p reading any chart route for q → 403"
  generator: "random patient pairs from the synthetic population × every chart read route"
  runs: 5000
  tool: bun test test/rbac/patient-scope.property.test.ts

- isc: ISC-10
  type: property
  property: "clinician c reads chart p ⇔ relationship(c, p) ∈ {encounter, appointment, referral} or a break-glass event exists"
  generator: "random clinician × patient pairs with random relationship sets, incl. expired ones"
  runs: 5000
  tool: bun test test/rbac/clinician-relationship.property.test.ts

- isc: ISC-11
  type: property
  property: "∀ role ≠ admin, ∀ route under /admin: → 403"
  generator: "non-admin roles × every registered /admin route"
  runs: 1000
  tool: bun test test/rbac/admin.property.test.ts

- isc: ISC-12
  type: property
  property: "auditor sessions → 200 on /audit/*, 403 on every PHI route"
  generator: "every /audit route and every PHI route"
  runs: 500
  tool: bun test test/rbac/auditor.property.test.ts

- isc: ISC-13
  type: unit-test
  check: break-glass with and without a reason
  threshold: no reason → 400; with reason → access + audit event priority=high, review=true
  tool: bun test test/rbac/break-glass.test.ts

- isc: ISC-14
  type: unit-test
  check: clinician+admin user switching surfaces in one session
  threshold: 401 reauth_required on the second surface
  tool: bun test test/auth/role-switch.test.ts

- isc: ISC-15
  type: bash
  check: fixture patients resolve to one longitudinal id across regions
  threshold: 12/12 single ids, 0 false merges
  tool: bun run scripts/empi-cross-region-probe.ts --test-fixture mrn-set-A

- isc: ISC-16
  type: property
  property: "eMPI confidence < 0.95 ⇒ no merge row written and the verify-identity flow is returned"
  generator: "match candidates with confidence drawn from [0, 1], weighted around 0.95"
  runs: 5000
  tool: bun test test/identity/merge-threshold.property.test.ts

- isc: ISC-17
  type: unit-test
  check: cross-region link without, with partial, and with full challenge
  threshold: merge only after a complete challenge set
  tool: bun test test/identity/link-challenge.test.ts

- isc: ISC-18
  type: load
  check: autocomplete p95 and candidate count
  threshold: p95 ≤ 250ms; ≥ 10 candidates
  tool: k6 run load/appointment-autocomplete.js --vus 200 --duration 5m

- isc: ISC-19
  type: bash
  check: booking against the Epic sandbox
  threshold: 201 + confirmation id equal to the EHR Appointment.id
  tool: bun run scripts/fhir-book.ts --sandbox epic

- isc: ISC-20
  type: unit-test
  check: booking with EHR rejection and with slot-taken responses
  threshold: recoverable error + 3 alternative slots in both cases
  tool: bun test test/scheduling/booking-failure.test.ts

- isc: ISC-21
  type: bash
  check: cancellation propagation to the EHR sandbox
  threshold: EHR status cancelled ≤ 60s; portal shows cancelled on the next render
  tool: bun run scripts/fhir-cancel.ts --sandbox epic --timeout 60

- isc: ISC-22
  type: unit-test
  check: PNW patient booking at a Cascade Care hospital
  threshold: booking allowed + region disclosure rendered
  tool: bun test test/scheduling/cross-region.test.ts

- isc: ISC-23
  type: bash
  check: EHR-resulted → portal-visible latency over 7 days
  threshold: p95 ≤ 4h (internal SLA ≤ 1h)
  tool: bun run scripts/lab-latency-audit.ts --window 7d

- isc: ISC-24
  type: property
  property: "critical result ⇒ banner + notification on the preferred channel; the channel is never SMS when content is included"
  generator: "random results with critical flags × patient channel prefs (push, email, sms)"
  runs: 2000
  tool: bun test test/labs/critical.property.test.ts

- isc: ISC-25
  type: property
  property: "timeline(p) is the union of all source-EHR encounters for p, sorted by clinical-effective date"
  generator: "synthetic patients with encounters split across 1–3 EHRs, clashing timestamps and time zones"
  runs: 1000
  tool: bun test test/chart/timeline.property.test.ts

- isc: ISC-26
  type: load
  check: 5-year CCD download
  threshold: p95 ≤ 8s; document validates against C-CDA R2.1
  tool: k6 run load/ccd-download.js && bun run scripts/ccda-validate.ts /tmp/ccd-sample.xml

- isc: ISC-27
  type: bash
  check: patient message → EHR inbox latency
  threshold: ≤ 30s
  tool: bun run scripts/message-roundtrip.ts --direction to-ehr

- isc: ISC-28
  type: bash
  check: clinician reply → portal inbox latency
  threshold: ≤ 60s
  tool: bun run scripts/message-roundtrip.ts --direction to-portal

- isc: ISC-29
  type: bash
  check: stored message bodies + TLS on every hop
  threshold: 0 plaintext bodies in the store; TLS 1.2+ on all hops
  tool: bun run scripts/message-at-rest-audit.ts && bun run scripts/tls-hop-audit.ts messaging

- isc: ISC-30
  type: bash
  check: messages older than 7 years in the portal store
  threshold: "0"
  tool: psql "$PORTAL_DB" -Atc "SELECT count(*) FROM messages WHERE created_at < now() - interval '7 years'"

- isc: ISC-31
  type: bash
  check: signed transmission to the Surescripts sandbox + portal copy after 24h
  threshold: signature verifies; 0 portal rows older than 24h
  tool: bun run scripts/erx-handoff.ts --sandbox && psql "$PORTAL_DB" -Atc "SELECT count(*) FROM rx_handoff WHERE sent_at < now() - interval '24 hours'"

- isc: ISC-32
  type: unit-test
  check: prescription view data source
  threshold: served from the EHR pharmacy API; no portal prescription table read
  tool: bun test test/rx/live-source.test.ts

- isc: ISC-33
  type: bash
  check: refill request → EHR pharmacy queue latency
  threshold: ≤ 60s
  tool: bun run scripts/refill-roundtrip.ts --sandbox epic

- isc: ISC-34
  type: bash
  check: PHI reads vs audit events per 1-minute bucket, 24h
  threshold: '|reads| == |audit_events| in every bucket'
  tool: psql "$AUDIT_DB" -f sql/audit-completeness.sql

- isc: ISC-35
  type: bash
  check: hash chain over 30 days + injected tamper
  threshold: 0 breaks on clean data; tamper detected ≤ 1h
  tool: bun run scripts/audit-chain-verify.ts --window 30d && bun run scripts/audit-tamper-drill.ts

- isc: ISC-36
  type: bash
  check: object-lock mode and retain-until on today's snapshot
  threshold: COMPLIANCE, ≥ 6 years out
  tool: aws s3api get-object-retention --bucket audit-logs --key $(date +%F).parquet

- isc: ISC-37
  type: load
  check: auditor queries by patient, actor, time window (30 days)
  threshold: p95 ≤ 5s for each query type
  tool: k6 run load/audit-queries.js

- isc: ISC-38
  type: bash
  check: last month's attestation report + signature
  threshold: file exists at the retrieval path; signature verifies
  tool: cosign verify-blob --key kms://audit-attest --signature reports/$(date -d 'last month' +%Y-%m).sig reports/$(date -d 'last month' +%Y-%m).pdf

- isc: ISC-39
  type: bash
  check: single-region drill
  threshold: drain ≤ 5 min; 0 committed writes lost
  tool: bun run scripts/regional-outage-drill.ts --target us-west-2

- isc: ISC-40
  type: load
  check: read p95 during the drill vs steady state
  threshold: ≤ 1.5×
  tool: k6 run load/read-mix.js --during-drill us-west-2

- isc: ISC-41
  type: bash
  check: replication lag p99 per table class, 7 days
  threshold: compliance tables ≤ 60s; others ≤ 300s
  tool: bun run scripts/replication-lag.ts --window 7d --by-class

- isc: ISC-42
  type: bash
  check: two-region outage drill
  threshold: writes → 503 + degraded page; reads OK; 0 PHI rows lost
  tool: bun run scripts/regional-outage-drill.ts --target us-west-2,us-east-1 --staging

- isc: ISC-43
  type: bash
  check: correlation id end to end
  threshold: same id in edge log, app log, EHR adapter log, support tool
  tool: bun run scripts/trace-correlation.ts --sample 100

- isc: ISC-44
  type: bash
  check: dashboards by tag
  threshold: 5 dashboards (identity, authz, ehr-latency, audit, regional)
  tool: bun run scripts/dashboards.ts --tag portal --names

- isc: ISC-45
  type: bash
  check: runbooks with a false-positive section
  threshold: 12 alert runbooks, each with a "false positive when" heading
  tool: rg -l -i '^#+ .*false positive when' docs/runbooks/alerts/ | wc -l

- isc: ISC-46
  type: bash
  check: ombudsman dashboard panels
  threshold: monthly availability vs 99.95% + a breach-narrative panel; ombudsman group has view
  tool: bun run scripts/dashboards.ts --name slo-ombudsman --panels --acl

- isc: ISC-47
  type: bash
  check: Terraform drift + console-change alarm
  threshold: plan shows no changes; alarm rule enabled
  tool: terraform plan -detailed-exitcode && aws events describe-rule --name console-change-revert | jq -r .State

- isc: ISC-48
  type: bash
  check: blue/green rollback drill per region
  threshold: ≤ 90s in every region
  tool: bun run scripts/rollback-drill.ts --all-regions

- isc: ISC-49
  type: bash
  check: injected canary failure
  threshold: auto-rollback + page ≤ 60s
  tool: bun run scripts/canary-failure-injection.ts

- isc: ISC-50
  type: bash
  check: secret-looking values in image env, task defs and Terraform state
  threshold: zero matches
  tool: bash scripts/secret-surface-scan.sh images taskdefs tfstate

- isc: ISC-51
  type: bash
  check: last 10 deploys each have generated notes on their change ticket
  threshold: 10/10
  tool: bun run scripts/change-ticket-audit.ts --last 10

- isc: ISC-52
  type: bash
  check: canary URL and its enabled scope
  threshold: 200; feature set = identity, rbac, chart-read (1 hospital), audit, observability
  tool: curl -s https://portal.beaconhealth.example.org/canary/_features | jq -r '.enabled | sort | join(",")'

- isc: ISC-53
  type: bash
  check: soak window incidents + enrolled testers
  threshold: 0 P1 in 14 days; ≥ 200 testers
  tool: bun run scripts/soak-report.ts --from 2026-04-08 --to 2026-04-22

- isc: ISC-54
  type: bash
  check: assessor findings export
  threshold: 0 open high-severity findings
  tool: jq '[.findings[] | select(.severity=="high" and .status=="open")] | length' compliance/hitrust-2026-04.json

- isc: ISC-55
  type: bash
  check: MEDITECH-sourced chart entries for enrolled patients
  threshold: 14 hospitals live; ≥ 1,000 patients with both Epic and MEDITECH entries
  tool: psql "$PORTAL_DB" -f sql/phase2-unification.sql

- isc: ISC-56
  type: manual
  check: signed cutover plan
  threshold: both CMIO signatures + a rollback-criteria section
  tool: open compliance/phase2-cutover-plan.pdf

- isc: ISC-57
  type: bash
  check: legacy entry-point redirects + 90-day redirect uptime
  threshold: every legacy URL → 301 to the new portal; uptime ≥ 99.95%
  tool: bash scripts/legacy-redirects.sh && bun run scripts/uptime.ts legacy-redirects --days 90

- isc: ISC-58
  type: bash
  check: access coverage + legacy DB state
  threshold: 100% of active patients enrolled; legacy DB read-only and snapshotted
  tool: psql "$PORTAL_DB" -Atc "SELECT round(100.0*enrolled/total,1) FROM coverage" && bash scripts/legacy-db-sealed.sh

- isc: ISC-59
  type: bash
  check: Q4 assessor result
  threshold: status Certified; 0 MRSA findings
  tool: jq '.status, ([.findings[] | select(.type=="MRSA")] | length)' compliance/hitrust-2026-q4.json

- isc: ISC-60
  type: bash
  check: PHI-shaped query parameters in edge and WAF logs, 7 days
  threshold: zero matches (rg exits 1)
  tool: rg "patient_id=|mrn=|dob=|ssn=" /var/log/cloudflare-edge/*.log /var/log/waf/*.log

- isc: ISC-61
  type: bash
  check: oldest retained audit event
  threshold: ≥ 6 years − 7 days old (or the archive predates that window)
  tool: psql "$AUDIT_DB" -Atc "SELECT MIN(timestamp) <= now() - interval '6 years' + interval '7 days' OR MIN(timestamp) = (SELECT go_live FROM meta) FROM audit_log_archive"

- isc: ISC-62
  type: bash
  check: vendors in data path vs vendors with a BAA
  threshold: '|vendors_in_data_path| == |vendors_with_baa_sha|, 0 unrecognized'
  tool: bun run scripts/baa-reconciliation.ts

- isc: ISC-63
  type: property
  property: "preflight(config) fails ⇔ idle_timeout(role) > 15 min for any of clinician/admin/auditor"
  generator: "random configs with per-role idle timeouts 1–120 min"
  runs: 1000
  tool: bun test test/preflight/idle-timeout.property.test.ts

- isc: ISC-64
  type: bash
  check: PHI-tagged resources outside US regions and non-BAA services
  threshold: "0"
  tool: bun run scripts/phi-residency-scan.ts --count

- isc: ISC-65
  type: bash
  check: inter-region PHI flows over public hops, from VPC flow logs
  threshold: "0"
  tool: bun run scripts/flowlog-public-hops.ts --tag phi --window 7d --count

- isc: ISC-66
  type: bash
  check: password columns in the patient-identity DB
  threshold: 0 rows
  tool: psql "$IDENTITY_DB" -Atc "SELECT column_name FROM information_schema.columns WHERE column_name ~ 'password'"

- isc: ISC-67
  type: bash
  check: static-analysis rule for in-process role mutation
  threshold: rule enabled; 0 violations
  tool: |-
    bunx eslint --rule 'beacon/no-role-mutation: error' src/

- isc: ISC-68
  type: bash
  check: UPDATE/DELETE on audit_log by the app role, 30 days
  threshold: 0 rows
  tool: psql "$AUDIT_DB" -Atc "SELECT count(*) FROM pg_stat_statements WHERE query ~ '(UPDATE|DELETE).+audit_log' AND userid = 'app_role'::regrole"
```

## Features

```yaml
- name: IdentityPatient
  description: Patient passwordless auth with magic link + step-up MFA (TOTP, WebAuthn, SMS-fallback)
  satisfies: [ISC-1, ISC-2, ISC-5, ISC-6, ISC-7, ISC-8, ISC-66]
  depends_on: []
  parallelizable: true

- name: IdentitySSO
  description: Okta SAML for clinician / admin / auditor with role-claim mapping
  satisfies: [ISC-3, ISC-4, ISC-6, ISC-7, ISC-8]
  depends_on: []
  parallelizable: true

- name: RBACAndRelationships
  description: Patient/clinician/admin/auditor RBAC with relationship-based access + break-glass
  satisfies: [ISC-9, ISC-10, ISC-11, ISC-12, ISC-13, ISC-14, ISC-67]
  depends_on: [IdentityPatient, IdentitySSO]
  parallelizable: false

- name: PatientMatchingEMPI
  description: eMPI-driven longitudinal record resolution across 50 hospitals
  satisfies: [ISC-15, ISC-16, ISC-17]
  depends_on: []
  parallelizable: true

- name: AppointmentScheduling
  description: Cross-region scheduling with FHIR R4 booking + cancellation
  satisfies: [ISC-18, ISC-19, ISC-20, ISC-21, ISC-22]
  depends_on: [PatientMatchingEMPI, RBACAndRelationships]
  parallelizable: true

- name: ChartAndLabs
  description: Unified chart timeline + lab results + CCD/C-CDA export
  satisfies: [ISC-23, ISC-24, ISC-25, ISC-26]
  depends_on: [PatientMatchingEMPI, RBACAndRelationships]
  parallelizable: true

- name: SecureMessaging
  description: Patient-care-team messaging with E2E encryption + EHR thread linkage
  satisfies: [ISC-27, ISC-28, ISC-29, ISC-30]
  depends_on: [RBACAndRelationships]
  parallelizable: true

- name: EPrescriptionHandoff
  description: Surescripts handoff with TTL-bounded portal-side state
  satisfies: [ISC-31, ISC-32, ISC-33]
  depends_on: [RBACAndRelationships]
  parallelizable: false

- name: AuditLogPlatform
  description: Hash-chained, 6-year-retained, S3-object-locked audit log
  satisfies: [ISC-34, ISC-35, ISC-36, ISC-37, ISC-38, ISC-61, ISC-68]
  depends_on: []
  parallelizable: false

- name: MultiRegionInfra
  description: Active-active 3-region AWS with documented failover and data-residency boundaries
  satisfies: [ISC-39, ISC-40, ISC-41, ISC-42, ISC-64, ISC-65]
  depends_on: []
  parallelizable: false

- name: Observability
  description: Correlation IDs + dashboards + runbooks + ombudsman SLO view
  satisfies: [ISC-43, ISC-44, ISC-45, ISC-46]
  depends_on: []
  parallelizable: true

- name: ReleasePipeline
  description: Terraform-only infra + blue/green per region + auto-rollback + secrets in Secrets Manager
  satisfies: [ISC-47, ISC-48, ISC-49, ISC-50, ISC-51, ISC-63]
  depends_on: []
  parallelizable: true

- name: ComplianceProgram
  description: BAA reconciliation + HITRUST audit prep + monthly attestation
  satisfies: [ISC-38, ISC-54, ISC-59, ISC-60, ISC-62]
  depends_on: [AuditLogPlatform, MultiRegionInfra]
  parallelizable: true

- name: Phase1Canary
  description: Phase 1 read-only chart canary live by 2026-04-30 budget gate
  satisfies: [ISC-52, ISC-53, ISC-54]
  depends_on: [IdentityPatient, IdentitySSO, RBACAndRelationships, ChartAndLabs, AuditLogPlatform, Observability]
  parallelizable: false

- name: Phase2MEDITECHCutover
  description: Cascade Care 14-hospital MEDITECH integration in Q3 2026
  satisfies: [ISC-55, ISC-56, ISC-57]
  depends_on: [Phase1Canary, AppointmentScheduling, ChartAndLabs]
  parallelizable: false

- name: Phase3Decommission
  description: Legacy decommission + HITRUST certification in Q4 2026
  satisfies: [ISC-58, ISC-59]
  depends_on: [Phase2MEDITECHCutover, ComplianceProgram]
  parallelizable: false
```

## Decisions

- 2026-01-08 15:00: Three-region active-active over two-region active-active because the SLO target (99.95%) and the 2027-Q1 cutover deadline both require a topology that survives single-region failure without manual intervention. Cost delta is ~22% over two-region; the program steering committee approved the delta on 2026-01-15.
- 2026-01-08 16:00: Interview ran before BUILD (12 questions across CMIO, CISO, and compliance). It produced the three-phase rollout, the 15-minute clinician idle timeout, and the BAA-reconciliation requirement (ISC-62).
- 2026-01-15 11:30: Auth0 for patient identity over building on the corporate Okta tenant because patient identity carries different lifecycle / opt-in semantics than employee identity, and mixing them would create role-elevation paths that are hard to audit. Two identity providers, separate trust boundaries, single portal.
- 2026-01-22 14:00: FHIR R4 as the EHR integration contract; HL7 v2 as fallback only. The 10-hospital MEDITECH Expanse cohort (Cascade Care) ships FHIR R4 in their 2026 release; the affiliated Cerner sites are on FHIR R4 already; Epic across the 40 home hospitals already exposes R4. Building on R4 avoids carrying HL7 v2 mappings as a permanent surface.
- 2026-02-04 09:30: ❌ DEAD END: Tried using DynamoDB as the audit-log store because of the active-active multi-region story. Hash-chain verification across regions had eventual-consistency windows that broke ISC-35's 1-hour detection target during synthetic chaos tests; the chain detected as broken when it was just stale. Reverted to per-region Aurora Postgres with cross-region read replicas + S3 object-lock as the immutable archive. Don't retry DynamoDB for hash-chain workloads.
- 2026-02-12 16:00: refined: ISC-23 sharpened from "lab results visible promptly" to "p95 ≤ 4h with internal SLA p95 ≤ 1h." Compliance asked for the floor (Cures Act); the org's clinical leadership asked for the SLA. Both are now ISC fields.
- 2026-02-18 10:00: Break-glass design — clinician without a documented relationship can read a chart with a one-line stated reason; the read writes a high-priority audit event flagged for compliance review within 24h. The alternative (no break-glass) was rejected because emergency-department workflows require it; the alternative (silent override) was rejected because it defeats the audit log.
- 2026-02-26 13:00: ❌ DEAD END: Tried storing patient-uploaded documents (insurance cards, prior records) in a portal-side S3 bucket with a 30-day retention. Two problems: (1) it created a PHI store outside the EHR's audit perimeter, and (2) compliance review on 2026-02-25 flagged that the 30-day window left orphaned PHI without a defensible retention policy. Reverted: patient-uploaded documents go to the EHR's document-management subsystem via FHIR `DocumentReference.create`; no portal-side store. Don't retry portal-side document storage.
- 2026-03-04 15:00: refined: ISC-31 sharpened — e-prescription portal-side state has a 24-hour TTL, not the original "transient." Surescripts handoff sometimes returns asynchronously and the TTL must be long enough to survive the handoff round-trip without losing the receipt-confirmation surface.
- 2026-03-11 09:00: Vendor decision: Surescripts as the e-prescription handoff partner over rolling our own pharmacy-network integrations. The "no roll-your-own" principle for compliance-relevant integrations applies; Surescripts has a signed BAA on file (SHA recorded in architecture log).
- 2026-03-18 14:30: refined: ISC-39 quarterly drill cadence formalized after the inaugural drill on 2026-03-15 succeeded but exposed a 47-second gap in correlation-ID propagation during region-drain. Drill cadence is now in the operations runbook with assigned owners.
- 2026-03-25 11:00: ❌ DEAD END: Tried using a session JWT containing role + relationship claims to skip a per-request relationship check. Pen-test team demonstrated a stale-relationship attack: a clinician's relationship was revoked at t=0 but the JWT carried valid claims until t+15min. Reverted to per-request relationship check against the relationship service; cached locally with a 60-second TTL. Don't retry stateless RBAC for relationship-bound clinical access.
- 2026-04-02 10:30: refined: ISC-60 sharpened — original anti-criterion was "PHI not in URLs"; sharpened to "PHI never appears in URL query strings logged by the edge proxy or the WAF" with a probe over a 7-day rolling window. The original was not testable; the sharpened version is.
- 2026-04-08 16:00: Phase 1 canary scope finalized: identity + RBAC + read-only chart from Epic for 1 hospital + audit log + observability. The original scope included messaging; messaging deferred to Phase 1.5 because the EHR-thread-linkage integration was not ready by 2026-04-30.
- 2026-04-15 13:00: refined: ISC-22 added cross-region disclosure requirement after a UX research session showed patients were confused when booking at a Midwest hospital from a Pacific Northwest profile. The disclosure is a one-line "this appointment is at <region>" text with the address.
- 2026-04-22 09:00: Phase 1 canary opened to 200 enrolled real-patient testers; HITRUST validated assessor scheduled for 2026-04-26 through 2026-04-29. Budget gate review with steering committee 2026-04-30.
- 2026-04-26 17:00: refined: ISC-65 added explicit requirement that cross-region transit traverses AWS-internal paths only (no public internet hops). The architecture review board found that the original constraint was implicit; making it explicit lets the network-engineering team alarm on any cross-region traffic that exits AWS.

## Changelog

- 2026-02-04 | conjectured: A multi-region active-active audit log on DynamoDB will simplify the cross-region story by relying on eventually-consistent global tables
  refuted by: synthetic chaos testing showed hash-chain verification flapping between "valid" and "broken" during the eventual-consistency window; the 1-hour detection target was unhittable
  learned: hash-chain integrity demands strong consistency at the chain-write boundary; eventual consistency turns "broken chain" into a noisy false signal that compliance cannot use
  criterion now: ISC-35 unchanged in text but the implementation pivoted to per-region Aurora Postgres with strong consistency at write, plus S3 object-lock for the immutable archive; Decisions logs the dead end

- 2026-02-26 | conjectured: Patient-uploaded documents can live in a portal-side S3 with a 30-day retention to avoid pushing every upload into the EHR
  refuted by: compliance review flagged that a portal-side PHI store outside the EHR audit perimeter creates a parallel system of record with no defensible retention policy beyond 30 days
  learned: PHI storage outside the EHR's audit perimeter is a recurring temptation that compliance will (correctly) reject every time; the EHR is the system of record for clinical content
  criterion now: no ISC change in text; implementation pivoted to FHIR `DocumentReference.create` against the EHR; Decisions logs the dead end

- 2026-03-25 | conjectured: A session JWT with role + relationship claims can skip per-request relationship checks and improve clinician-chart latency
  refuted by: pen-test team demonstrated that a clinician whose relationship was revoked at t=0 retained access until JWT expiry at t+15min — a 15-minute window of unauthorized access that the audit log captured but the access-control layer did not prevent
  learned: relationship-bound RBAC requires per-request authority checks; caching can shorten the check, but stateless trust over a 15-minute window is incompatible with the principle that revocation is immediate
  criterion now: ISC-10 unchanged in text but implementation now performs a per-request check against the relationship service with a 60-second local cache TTL; the cache invalidates on relationship-revocation events

- 2026-04-02 | conjectured: An anti-criterion that says "PHI not in URLs" is sufficient as written
  refuted by: a security review found that "in URLs" was ambiguous (does it mean path? query? fragment? Referer header? edge log?); the security team and the platform team interpreted it differently
  learned: anti-criteria need a single nameable probe; "PHI not in URLs" is a guideline, not a criterion
  criterion now: ISC-60 sharpened to "PHI never appears in URL query strings logged by the edge proxy or the WAF" with a 7-day rolling-window probe

- 2026-04-15 | conjectured: Cross-region appointment booking is just an appointment booking with a different region attribute
  refuted by: UX research session showed patients booking at a Cascade Care (Midwest) hospital from a Pacific Northwest profile did not realize they had selected a different region until they saw the confirmation; one tester said "I would not have driven 1,800 miles for this"
  learned: cross-region context is a UX surface, not just a backend attribute; the patient must see the region context before confirming, not after
  criterion now: ISC-22 sharpened — cross-region booking carries a one-line "this appointment is at <region>" disclosure shown before confirmation

## Verification

- ISC-1: Auth integration test 2026-04-25 — magic-link arrives p95 ≤ 28s, callback creates session within 1.4s; link rejected at 10m01s
- ISC-2: `bun test test/auth/step-up.property.test.ts` — 1000 runs, 0 failures
- ISC-3: `saml-roundtrip.ts --role clinician` — role `clinician`, `npi=1234567893`
- ISC-4: `bun test test/auth/role-separation.test.ts` — 4 passed
- ISC-5: `cookie-audit.ts --all-roles` — 4 roles, flags OK, 0 refresh tokens in cookies
- ISC-6: Session idle-timeout drill 2026-04-26 — clinician role: 16th-minute request returned `401 session-expired`; patient role: 31st-minute request returned `401 session-expired`; 12h01m absolute → `401`
- ISC-7: `auth-rate-limit.ts` — `429` on patient attempt 11 and SSO attempt 6
- ISC-8: `logout-probe.ts` — session row deleted in 0.3s; `Set-Cookie: session=; Max-Age=0`
- ISC-9: `bun test test/rbac/patient-scope.property.test.ts` — 5000 runs, 0 failures
- ISC-10: `bun test test/rbac/clinician-relationship.property.test.ts` — 5000 runs, 0 failures
- ISC-11: `bun test test/rbac/admin.property.test.ts` — 1000 runs, 0 failures
- ISC-12: `bun test test/rbac/auditor.property.test.ts` — 500 runs, 0 failures
- ISC-13: `bun test test/rbac/break-glass.test.ts` — 3 passed
- ISC-15: eMPI cross-region probe 2026-04-24 — 12 fixture patients each resolved to one longitudinal ID across 3 hospitals; zero false-merges
- ISC-16: `bun test test/identity/merge-threshold.property.test.ts` — 5000 runs, 0 failures
- ISC-18: k6 run 2026-04-27 — 200 vus / 5min — autocomplete p95 218ms across 50-hospital corpus, min 12 candidates
- ISC-19: `fhir-book.ts --sandbox epic` — `201`, confirmation `appt-8841207` = EHR `Appointment.id`
- ISC-20: `bun test test/scheduling/booking-failure.test.ts` — 2 passed
- ISC-23: lab-latency-audit 2026-04-25 (7-day window) — p95 1h 47m, internal SLA met
- ISC-24: `bun test test/labs/critical.property.test.ts` — 2000 runs, 0 failures
- ISC-27: `message-roundtrip.ts --direction to-ehr` — 11s
- ISC-28: `message-roundtrip.ts --direction to-portal` — 23s
- ISC-29: at-rest audit — 0 plaintext bodies in 48,112 rows; TLS audit — TLS 1.3 on all 4 hops
- ISC-34: audit-completeness check 2026-04-26 — `phi_reads = audit_events` per 1-min bucket over 24h, zero gaps
- ISC-35: audit-chain-verify 2026-04-27 — 30-day window, zero chain breaks across all three regions; tamper drill detected at +38 min
- ISC-36: `aws s3api get-object-retention --bucket audit-logs --key 2026-04-27.parquet` — `Mode: COMPLIANCE, RetainUntilDate: 2032-04-27T00:00:00Z`
- ISC-37: `k6 run load/audit-queries.js` — p95 by patient 1.9s, by actor 2.4s, by window 3.8s
- ISC-39: regional outage drill 2026-03-15 — drain time 4m 12s; data-loss events: 0
- ISC-43: `trace-correlation.ts --sample 100` — 100/100 ids present in all four places
- ISC-44: `dashboards.ts --tag portal --names` — `identity`, `authz`, `ehr-latency`, `audit`, `regional`
- ISC-45: `rg -l -i … docs/runbooks/alerts/ | wc -l` — 12
- ISC-47: `terraform plan -detailed-exitcode` — exit 0 (no changes); `console-change-revert` rule `ENABLED`
- ISC-48: `rollback-drill.ts --all-regions` — 58s / 64s / 71s
- ISC-49: canary-failure-injection 2026-04-23 — rollback completed in 71s; pager fired at +43s
- ISC-50: `secret-surface-scan.sh images taskdefs tfstate` — 0 matches
- ISC-52: Phase 1 canary live 2026-04-22 at `portal.beaconhealth.example.org/canary` — `_features` = `audit,chart-read,identity,observability,rbac`
- ISC-53: Phase 1 14-day soak 2026-04-08 to 2026-04-22 — 0 P1 incidents, 211 enrolled testers
- ISC-54: HITRUST validated-assessor report received 2026-04-29 — 0 high-severity findings, 2 medium with mitigation plans accepted
- ISC-60: `rg "patient_id=|mrn=|dob=|ssn=" /var/log/cloudflare-edge/*.log /var/log/waf/*.log` 7-day rolling window 2026-04-21 through 2026-04-28 — 0 matches
- ISC-61: oldest-retained check — `t` (archive begins at go-live 2026-04-22; alarm armed for the 6y − 7d mark)
- ISC-62: `baa-reconciliation.ts` — 9 vendors in data path, 9 with BAA SHA, 0 unrecognized
- ISC-63: `bun test test/preflight/idle-timeout.property.test.ts` — 1000 runs, 0 failures
- ISC-64: `phi-residency-scan.ts --count` — 0
- ISC-65: `flowlog-public-hops.ts --tag phi --window 7d --count` — 0
- ISC-66: `SELECT column_name FROM information_schema.columns WHERE column_name ~ 'password'` against patient-identity DB — 0 rows
- ISC-67: `eslint --rule 'beacon/no-role-mutation: error' src/` — 0 problems
- ISC-68: `SELECT count(*) FROM pg_stat_statements WHERE query ~ '(UPDATE|DELETE).+audit_log' AND userid = app_role` — 0 over 30-day window
