---
task: "Build BeanLine, a peer-to-peer green-coffee marketplace"
slug: 20260201-090000_beanline-v1
project: BeanLine
effort: E5
phase: execute
progress: 20/43
started: 2026-02-01T17:00:00Z
updated: 2026-04-25T03:14:00Z
stated_goal: "I want small roasters to sell 5–50kg green lots straight to verified buyers, with escrow, and all-in fees under 8%."
stated_goal_source: prompt
stated_goal_signal: 2
stated_goal_locked: 2026-02-01T17:00:00Z
context_sufficient: true
interview_invoked: false
interview_ran: 2026-02-01T17:20:00Z
current_state: "Small green-coffee lots sell at festivals once a year or get composted"
ideal_state: "Verified roasters list a lot and ship it to a verified buyer within a week"
---

<!-- Fictitious example. "BeanLine" is a teaching project name; any resemblance to real products or organizations is coincidental. The beanline.example.com domain is RFC 2606 reserved. -->

## Problem

Specialty-coffee roasters with small-batch lots (under 50kg) and home-roasting hobbyists with green-bean surplus have no good place to find each other. Existing marketplaces (eBay, Etsy, Reddit's r/coffee) either don't support food-safe shipping logistics, charge consumer-marketplace fees that eat the margin on a 5kg lot, or have zero buyer trust signals for "is this bean stored properly?" Most lots end up sold at coffee festivals (one weekend a year) or composted. The supply exists. The connective tissue does not.

## Vision

A small focused marketplace at `beanline.example.com` where a verified roaster lists a 5–50kg lot with origin, processing, harvest date, moisture content, and tasting notes; a verified buyer (home roaster or small cafe) browses by region and process, pays via escrow-Stripe, and the lot ships with a QR-coded handoff card the buyer scans on receipt to confirm condition. Delight: a roaster lists Colombia Geisha Wednesday and ships it to a third-wave cafe in Portland on Friday — no festival, no haggling, no Reddit DM dance.

## Out of Scope

- **No retail-bag pricing.** Minimum lot 5kg. Below that, the unit economics break for both sides.
- **No green-bean futures or pre-harvest contracts.** Existing physical lots only.
- **No roasted-bean retail.** Green coffee only; once it's roasted, the freshness window collides with shipping speed.
- **No multi-currency.** USD only in v1; international expansion requires a real customs and excise story we don't have.
- **No social-graph features.** No follow / friend / DM. Buyer-seller messaging is per-listing, not per-user-relationship.
- **No machine-only quality verification.** Listings carry seller-supplied data + buyer-confirmation handoff card; no third-party assay until v2.
- **No mobile native apps.** Web + PWA install. The buyer is at a desk pricing lots, not in line for boba.

## Principles

- Buyer trust beats catalog size. A verified-buyer + verified-seller marketplace with 200 lots beats an open marketplace with 20,000 lots and one fraud incident.
- The handoff card is the product, not the website. A clean post-shipment confirmation flow is what makes the next listing land.
- Roaster economics are non-negotiable: under 8% all-in fees or it doesn't beat festival sales.
- Defaults teach. If a buyer's first three searches return relevant lots, they convert; if the first three return junk, they leave.
- Editorial signals beat algorithmic personalization at this scale. Curation by humans (an in-house quality lead reviewing every new listing) is cheaper than building a recommendation engine.

## Constraints

- Edge SSR on Cloudflare Workers + D1 + R2. No third-party hosting in the user path.
- Auth via magic-link email only in v1. No password, no SSO. Verified-status (roaster vs buyer) gated by manual review of submitted business proof.
- Stripe Connect for escrow + split payments. No homegrown payment.
- All-in fees ≤ 8% (Stripe ~2.9% + 30¢ + BeanLine margin ≤ 5.1%).
- Bundle budget: ≤ 100KB JS gzipped on the listing page; ≤ 60KB CSS gzipped.
- p95 cold load on cellular ≤ 1s for browse pages, ≤ 1.5s for the listing detail page.
- Image storage in R2 with eager WebP transcoding; no original JPEGs ever served.
- Public read API rate-limited at 60 req/min/IP via Cloudflare WAF.
- All buyer-seller messaging logged for dispute resolution; retention 12 months minimum.
- HTTPS-only; HSTS preload-listed.

## Goal

"I want small roasters to sell 5–50kg green lots straight to verified buyers, with escrow, and all-in fees under 8%." Concretely: a Cloudflare-hosted marketplace at `beanline.example.com` where verified roasters list lots and verified buyers pay through Stripe escrow released by a QR handoff scan, with BeanLine's own margin ≤ 5.1%. Browse pages render in ≤ 1s p95 on cellular, and the in-house quality lead approves a new listing in ≤ 10 minutes per lot.

## Criteria

### Build & Deploy

- [x] ISC-1: `bun run deploy` exits 0 against production wrangler env.
- [x] ISC-2: TypeScript strict-mode build emits 0 errors.
- [x] ISC-3: `beanline.example.com` returns HTTP 200 with `text/html`.
- [x] ISC-4: Deployed version string in HTML head matches local git short-sha.

### Listing Lifecycle

- [x] ISC-5: A roaster can submit a listing with every required lot field and ≥ 1 photo.
- [x] ISC-6: Submitted listings enter `pending_review` and are invisible to anonymous visitors.
- [ ] ISC-7: Quality lead approves or rejects a pending listing in ≤ 10 minutes at p95.
- [x] ISC-8: An approved listing is live at `/lots/<slug>` within 60 seconds.
- [ ] ISC-9: A sold-out listing leaves the browse page within 60 seconds of the last sale.

### Browse and Search

- [x] ISC-10: `/browse` paginates available lots, 20 per page, newest first.
- [x] ISC-11: `/browse?region=<region>` returns only lots from that origin region.
- [x] ISC-12: `/browse?process=<process>` returns only lots with that processing method.
- [x] ISC-13: Browse page p95 cold load on simulated 4G is ≤ 1000ms.
- [ ] ISC-14: Listing detail page p95 cold load is ≤ 1500ms.
- [ ] ISC-15: `?q=<term>` matches origin, process, and tasting notes, case-insensitive substring.

### Auth and Verification

- [x] ISC-16: `/auth/magic-link` emails a single-use link that expires after 15 minutes.
- [x] ISC-17: Magic-link callback sets a session cookie with `HttpOnly; Secure; SameSite=Lax`.
- [x] ISC-18: New users start as `buyer_unverified` until the quality lead approves business proof.
- [ ] ISC-19: `POST /listings` from any role except `roaster_verified` returns 403.
- [ ] ISC-20: `POST /checkout` from `buyer_unverified` returns 403 "verification required".

### Payments and Escrow

- [x] ISC-21: `roaster_verified` users reach Stripe Connect onboarding at `/account/payouts`.
- [x] ISC-22: Checkout creates an escrow charge whose funds stay held until handoff.
- [ ] ISC-23: Fees stay inside the roaster-economics ceiling.
  - [ ] ISC-23.1: BeanLine's platform fee is ≤ 5.1% of lot price.
  - [ ] ISC-23.2: All-in fees (BeanLine + Stripe) are ≤ 8% of lot price.
- [ ] ISC-24: Payment success starts the shipment.
  - [ ] ISC-24.1: Webhook `payment_intent.succeeded` flips the listing to `in_transit`.
  - [ ] ISC-24.2: The roaster receives a printable handoff-card email after payment succeeds.
- [ ] ISC-25: Buyer's QR handoff scan closes the sale.
  - [ ] ISC-25.1: A QR handoff scan flips the listing status to `delivered`.
  - [ ] ISC-25.2: A QR handoff scan releases escrow funds to the roaster.
  - [ ] ISC-25.3: A QR handoff scan emails the buyer a receipt.
- [ ] ISC-26: Unconfirmed escrow auto-releases on day 8 after carrier delivery, with an audit entry.

### Messaging and Disputes

- [ ] ISC-27: Buyer-roaster messages are scoped to a single listing, never cross-listing.
- [ ] ISC-28: Messages are retained for at least 12 months.
- [ ] ISC-29: "Open dispute" after purchase creates an `open` dispute row and notifies both parties.

### RBAC / Visibility

- [x] ISC-30: Anonymous requests to purchase or message endpoints return 401.
- [ ] ISC-31: Roasters see all their own listings, never another roaster's pending ones.
- [ ] ISC-32: Non-admin requests to `/admin/*` routes return 403.

### Performance and Operational

- [ ] ISC-33: The health endpoint is fast and informative.
  - [ ] ISC-33.1: `/health` returns JSON with `status`, `version`, `last_deploy_at`.
  - [ ] ISC-33.2: `/health` responds in ≤ 50ms at p95.
- [ ] ISC-34: Every `/img/...` URL is served as `image/webp` by the transform Worker.
- [ ] ISC-35: The 61st `/api/lots` request from one IP within 60s returns 429.

### Anti-criteria

- [x] ISC-36: Anti: out of scope — follow, DM, and other social-graph endpoints return 404.
- [x] ISC-37: Anti: privacy — raw camera JPEG originals are never served from R2.
- [x] ISC-38: Anti: regression — first browse load makes zero third-party network requests.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "derived: the marketplace is live on Cloudflare"
  type: bash
  check: production deploy
  threshold: exit 0
  tool: bun run deploy

- isc: ISC-2
  anchors_to: "derived: the marketplace is live on Cloudflare"
  type: bash
  check: strict-mode type check
  threshold: exit 0, 0 errors
  tool: bunx tsc --noEmit --strict

- isc: ISC-3
  anchors_to: "derived: the marketplace is live on Cloudflare"
  type: bash
  check: HTTP status + content-type
  threshold: 200 + text/html
  tool: |-
    curl -sI https://beanline.example.com | rg -i '^(HTTP/2 200|content-type: text/html)'

- isc: ISC-4
  anchors_to: "derived: the marketplace is live on Cloudflare"
  type: bash
  check: deployed version meta vs local HEAD
  threshold: strings equal
  tool: test "$(curl -s https://beanline.example.com | rg -o 'name="version" content="\K[0-9a-f]+')" = "$(git rev-parse --short HEAD)"

- isc: ISC-5
  anchors_to: literal
  type: unit-test
  check: listing form submission with every required field and one photo
  threshold: response has an id and status pending_review
  tool: bun test test/listings.test.ts -t "submit listing"

- isc: ISC-6
  anchors_to: "derived: buyer trust — only reviewed lots are public"
  type: bash
  check: anonymous fetch of a pending listing
  threshold: HTTP 404
  tool: curl -s -o /dev/null -w '%{http_code}' https://beanline.example.com/listings/$PENDING_ID

- isc: ISC-7
  anchors_to: "derived: quality lead approves a lot in ≤ 10 minutes"
  type: bash
  check: quality-lead approval time per lot, last 7 days
  threshold: p95 ≤ 600s
  tool: wrangler d1 execute beanline --command "SELECT p95 FROM review_timing_7d" --json | jq '.[0].results[0].p95'

- isc: ISC-8
  anchors_to: literal
  type: bash
  check: public URL after approval
  threshold: HTTP 200 within 60s
  tool: bun run scripts/approve-and-poll.ts --sandbox --timeout=60

- isc: ISC-9
  anchors_to: "derived: buyers never see lots they can't buy"
  type: bash
  check: sold-out lot disappears from /browse
  threshold: absent within 60s
  tool: bun run scripts/sellout-and-poll.ts --sandbox --timeout=60

- isc: ISC-10
  anchors_to: "derived: buyers can find lots"
  type: bash
  check: articles on page 1 and their order
  threshold: 20 articles, listed_at descending
  tool: bun test test/browse.test.ts -t "pagination"

- isc: ISC-11
  anchors_to: "derived: buyers can find lots"
  type: property
  property: "∀ region r: every lot in /browse?region=r has origin_region == r"
  generator: "fc.constantFrom('africa','americas','asia-pacific') × fixture catalogs of 0–200 lots"
  runs: 200
  tool: bun test test/browse.property.test.ts -t "region filter"

- isc: ISC-12
  anchors_to: "derived: buyers can find lots"
  type: property
  property: "∀ process p: every lot in /browse?process=p has process == p"
  generator: "fc.constantFrom('washed','natural','honey','anaerobic') × fixture catalogs of 0–200 lots"
  runs: 200
  tool: bun test test/browse.property.test.ts -t "process filter"

- isc: ISC-13
  anchors_to: "derived: browse ≤ 1s p95 on cellular"
  type: performance
  check: browse-page p95 cold load on simulated 4G
  threshold: ≤ 1000ms
  tool: lighthouse --preset=mobile --only-categories=performance --url=https://beanline.example.com/browse

- isc: ISC-14
  anchors_to: "derived: browse ≤ 1s p95 on cellular"
  type: performance
  check: listing-detail p95 cold load on simulated 4G
  threshold: ≤ 1500ms
  tool: lighthouse --preset=mobile --only-categories=performance --url=https://beanline.example.com/lots/colombia-geisha-2026-q1

- isc: ISC-15
  anchors_to: "derived: buyers can find lots"
  type: property
  property: "lot ∈ search(q) ⇔ lower(q) is a substring of lower(origin + process + tasting_notes)"
  generator: "random fixture lots × query terms drawn from their own fields, mixed case, plus random non-matching terms"
  runs: 1000
  tool: bun test test/search.property.test.ts

- isc: ISC-16
  anchors_to: "derived: verified accounts need sign-in"
  type: unit-test
  check: magic link is single-use and expires
  threshold: second use → 401; use after 15 min → 401
  tool: bun test test/auth.test.ts -t "magic link"

- isc: ISC-17
  anchors_to: "derived: verified accounts need sign-in"
  type: bash
  check: Set-Cookie flags on callback
  threshold: HttpOnly, Secure, SameSite=Lax all present
  tool: curl -si "https://beanline.example.com/auth/callback?token=$TEST_TOKEN" | rg -i '^set-cookie:.*HttpOnly.*Secure.*SameSite=Lax'

- isc: ISC-18
  anchors_to: literal
  type: unit-test
  check: role of a fresh account, before and after quality-lead approval
  threshold: buyer_unverified → buyer_verified only via the approval action
  tool: bun test test/roles.test.ts -t "verification gate"

- isc: ISC-19
  anchors_to: literal
  type: property
  property: "∀ role ≠ roaster_verified: POST /listings → 403"
  generator: "fc.constantFrom(every role in the enum except roaster_verified) × valid listing bodies"
  runs: 200
  tool: bun test test/rbac.property.test.ts -t "listings"

- isc: ISC-20
  anchors_to: literal
  type: bash
  check: checkout as an unverified buyer
  threshold: 403 + body contains "verification required"
  tool: curl -s -w '\n%{http_code}' -X POST -b "session=$UNVERIFIED" https://beanline.example.com/checkout | rg -c 'verification required|^403$'

- isc: ISC-21
  anchors_to: literal
  type: bash
  check: payouts page for a verified roaster
  threshold: HTTP 200 + a connect.stripe.com onboarding link
  tool: curl -s -b "session=$ROASTER" https://beanline.example.com/account/payouts | rg -c 'connect\.stripe\.com'

- isc: ISC-22
  anchors_to: literal
  type: bash
  check: payment intent created at checkout
  threshold: capture_method manual (funds held)
  tool: bun run scripts/checkout-test.ts --sandbox --lot-price=25000 | jq -r '.payment_intent.capture_method'

- isc: ISC-23.1
  anchors_to: literal
  type: property
  property: "∀ lot price p ∈ [5kg × $4, 50kg × $40]: platform_fee(p) ≤ 0.051 × p"
  generator: "fc.integer over lot prices in cents across the 5–50kg range"
  runs: 10000
  tool: bun test test/fees.property.test.ts -t "platform fee"

- isc: ISC-23.2
  anchors_to: literal
  type: property
  property: "∀ lot price p: platform_fee(p) + stripe_fee(p) ≤ 0.08 × p"
  generator: "same price domain as ISC-23.1 — the fixed 30¢ Stripe fee makes the smallest lots the edge"
  runs: 10000
  tool: bun test test/fees.property.test.ts -t "all-in fee"

- isc: ISC-24.1
  anchors_to: literal
  type: bash
  check: listing status after a replayed payment_intent.succeeded
  threshold: in_transit
  tool: stripe trigger payment_intent.succeeded --override payment_intent:metadata.listing=$LOT && bun run scripts/lot-status.ts $LOT

- isc: ISC-24.2
  anchors_to: literal
  type: bash
  check: handoff-card email in the roaster test inbox
  threshold: 1 message with a PDF attachment
  tool: bun run scripts/mailbox.ts --to roaster@test --subject 'Handoff card' --json | jq '[.[] | select(.attachments[]?.type=="application/pdf")] | length'

- isc: ISC-25.1
  anchors_to: literal
  type: unit-test
  check: status after QR scan
  threshold: delivered
  tool: bun test test/handoff.test.ts -t "status"

- isc: ISC-25.2
  anchors_to: literal
  type: bash
  check: QR handoff scan releases escrow
  threshold: a transfer.created event for the lot
  tool: bun run scripts/handoff-test.ts --sandbox | jq -e '.events[] | select(.type=="transfer.created")'

- isc: ISC-25.3
  anchors_to: literal
  type: bash
  check: receipt email in the buyer test inbox
  threshold: 1 message
  tool: bun run scripts/mailbox.ts --to buyer@test --subject 'Receipt' --json | jq length

- isc: ISC-26
  anchors_to: literal
  type: bash
  check: auto-release on day 8
  threshold: transfer fires within 60s of the day-8 cron + 1 audit row
  tool: bun run scripts/auto-release-test.ts --simulate-day=8

- isc: ISC-27
  anchors_to: "derived: Out of Scope — messaging is per-listing, no social graph"
  type: unit-test
  check: reading a thread with a different listing id
  threshold: 404
  tool: bun test test/messages.test.ts -t "listing scope"

- isc: ISC-28
  anchors_to: "derived: Constraints — 12-month message retention"
  type: bash
  check: retention window configured on the messages table
  threshold: ≥ 365 days
  tool: wrangler d1 execute beanline --command "SELECT retention_days FROM retention_policy WHERE tbl='messages'" --json | jq '.[0].results[0].retention_days'

- isc: ISC-29
  anchors_to: "derived: buyer trust — disputes have a path"
  type: unit-test
  check: dispute row + two notifications
  threshold: status open, 2 emails queued
  tool: bun test test/disputes.test.ts -t "open dispute"

- isc: ISC-30
  anchors_to: "derived: buyer trust — only verified accounts transact"
  type: bash
  check: protected endpoints without a session
  threshold: every one returns 401
  tool: for p in /checkout /messages /listings; do curl -s -o /dev/null -w '%{http_code}\n' -X POST https://beanline.example.com$p; done | sort -u

- isc: ISC-31
  anchors_to: "derived: buyer trust — pending lots stay private"
  type: unit-test
  check: /account/listings for roaster A with roaster B's pending lot in the fixture
  threshold: all of A's lots listed, none of B's
  tool: bun test test/rbac.test.ts -t "own listings only"

- isc: ISC-32
  anchors_to: "derived: admin tooling is gated"
  type: property
  property: "∀ role ≠ admin, ∀ path under /admin: request → 403"
  generator: "non-admin roles × every route registered under /admin"
  runs: 500
  tool: bun test test/rbac.property.test.ts -t "admin"

- isc: ISC-33.1
  anchors_to: "derived: the marketplace is live on Cloudflare"
  type: bash
  check: health payload keys
  threshold: jq exits 0
  tool: curl -s https://beanline.example.com/health | jq -e 'has("status") and has("version") and has("last_deploy_at")'

- isc: ISC-33.2
  anchors_to: "derived: the marketplace is live on Cloudflare"
  type: bash
  check: health latency over 100 requests
  threshold: p95 ≤ 50ms
  tool: hey -n 100 -c 5 https://beanline.example.com/health | rg '95% in'

- isc: ISC-34
  anchors_to: "derived: Constraints — WebP only"
  type: bash
  check: content type of every image URL on the sitemap
  threshold: every line is image/webp
  tool: bash scripts/image-format-audit.sh | sort -u

- isc: ISC-35
  anchors_to: "derived: Constraints — public API rate limit"
  type: bash
  check: status of the 61st request in one minute
  threshold: "429"
  tool: for i in $(seq 61); do curl -s -o /dev/null -w '%{http_code}\n' https://beanline.example.com/api/lots; done | tail -1

- isc: ISC-36
  anchors_to: "derived: Out of Scope — no social graph"
  type: bash
  check: social-graph endpoints don't exist
  threshold: every one returns 404
  tool: for p in follow dm friends; do curl -s -o /dev/null -w '%{http_code}\n' https://beanline.example.com/api/$p; done | sort -u

- isc: ISC-37
  anchors_to: "derived: Constraints — no original JPEGs served"
  type: property
  property: "∀ uploaded image: every public URL for it answers Content-Type image/webp, never image/jpeg"
  generator: "fixture uploads: JPEG with EXIF GPS, PNG, HEIC, 1px–8000px"
  runs: 100
  tool: bun test test/images.property.test.ts

- isc: ISC-38
  anchors_to: "derived: Principles — no third-party tracking in the user path"
  type: bash
  check: third-party hosts requested on first /browse load
  threshold: "0"
  tool: bunx playwright test e2e/third-party.spec.ts --reporter=json | jq '.stats.unexpected'
```

## Features

```yaml
- name: ListingPipeline
  description: Submit → pending review → approved → public; quality-lead admin tooling
  satisfies: [ISC-5, ISC-6, ISC-7, ISC-8, ISC-9, ISC-31]
  depends_on: []
  parallelizable: false  # every other slice needs a live listing to exercise

- name: BrowseAndSearch
  description: Paginated browse, region/process filters, substring search, performance budget
  satisfies: [ISC-10, ISC-11, ISC-12, ISC-13, ISC-14, ISC-15]
  depends_on: [ListingPipeline]
  parallelizable: false  # all browse views share layout primitives

- name: AuthAndVerification
  description: Magic-link sign-in, role gating (buyer/roaster/admin), verification queue
  satisfies: [ISC-16, ISC-17, ISC-18, ISC-19, ISC-20, ISC-30, ISC-32]
  depends_on: []
  parallelizable: true  # parallel to listings

- name: PaymentsEscrow
  description: Stripe Connect onboarding, escrow checkout, handoff release, auto-release timer
  satisfies: [ISC-21, ISC-22, ISC-23.1, ISC-23.2, ISC-24.1, ISC-24.2, ISC-25.1, ISC-25.2, ISC-25.3, ISC-26]
  depends_on: [AuthAndVerification, ListingPipeline]
  parallelizable: false  # checkout flow is end-to-end sequential

- name: MessagingAndDisputes
  description: Per-listing buyer-roaster messaging, retention, dispute open
  satisfies: [ISC-27, ISC-28, ISC-29]
  depends_on: [AuthAndVerification, ListingPipeline]
  parallelizable: true

- name: ImageEdge
  description: R2 image storage + WebP transform Worker
  satisfies: [ISC-34, ISC-37]
  depends_on: []
  parallelizable: true

- name: HealthAndRateLimit
  description: /health endpoint, public-API rate limiting via WAF
  satisfies: [ISC-33.1, ISC-33.2, ISC-35]
  depends_on: [ListingPipeline]
  parallelizable: true
```

## Decisions

- 2026-02-01 17:00: Cloudflare-only stack chosen over a Vercel/Postgres path because edge-co-location wins at the cellular-load budget, D1's row-flat shape fits the listing schema, and the platform-fee math only works with low compute cost.
- 2026-02-01 17:20: Interview ran before BUILD (7 questions). Answers set the 5kg lot minimum, the 8% all-in ceiling, and USD-only; all three are now Constraints or Out of Scope.
- 2026-02-08 11:30: Magic-link auth chosen over password+OAuth because v1's user base is small and known; password-reset flow would be the highest-cost auth surface for the verification-team load.
- 2026-02-22 14:00: ❌ DEAD END: Tried buyer-self-attested verification (upload a business license image, accept on submission). Three of the first eight attestations were retail bag-shop owners trying to source for resale, not the wholesale-buyer profile. Reverted to manual quality-lead review of every verification. Don't retry without an automated business-database cross-check.
- 2026-03-04 09:00: refined: ISC-7 sharpened from "quality lead can approve listings quickly" to "≤ 10 minutes per lot at p95" — the first phrasing was unfalsifiable; the second became a staffing-model input.
- 2026-03-15 22:00: ❌ DEAD END: Tried open-graph + Twitter-card image generation for listings. Pulled in 40KB JS for the meta-tag generator, broke the bundle budget. Reverted to server-rendered static OG meta. Don't retry the dynamic generator path.
- 2026-04-01 10:00: refined: ISC-23 split into ISC-23.1 (BeanLine fee ≤ 5.1%) and ISC-23.2 (all-in ≤ 8%); ISC-23 stays as their parent. The original compound ISC let the all-in pass while BeanLine's slice silently crept past the principle's 5.1% ceiling.
- 2026-04-12 16:30: refined: ISC-26 added the auto-release timer (day-8) after the first three deliveries had buyers who never scanned the handoff QR — escrow sat indefinitely. The timer + audit log is the safety net.
- 2026-04-22 22:00: refined: Goal sharpened — added the explicit "p95 ≤ 1s on cellular" and "all-in fees ≤ 8%" — the original Goal was domain-correct but operationally fuzzy.
- 2026-04-25 03:00: refined: Splitting Test pass — ISC-24, ISC-25 and ISC-33 each joined claims that fail independently (a status flip can land while the email doesn't); split into leaves, parents kept.
- 2026-04-25 03:10: ISC-7 and ISC-9 have no property form — both depend on a human reviewer and live traffic. Example-based probes only.

## Changelog

- 2026-02-22 | conjectured: Buyer self-attestation will scale verification at low ops cost
  refuted by: 3 of 8 attestations turned out to be the wrong buyer profile (retail, not wholesale)
  learned: verification is the load-bearing trust signal; attestation without ops review degrades the buyer-pool quality, which kills roaster trust, which kills supply
  criterion now: ISC-18 now names the quality-lead manual review explicitly; "buyer_verified" role is gated on it

- 2026-03-15 | conjectured: Dynamic OG/Twitter card generation will improve social sharing CTR
  refuted by: bundle exceeded the 100KB JS budget (ISC-13/14 broke); social CTR uplift was undetectable in A/B
  learned: bundle-budget Constraints outrank social-meta features; static OG is good enough at this scale
  criterion now: ISC-13 unchanged but Decisions logs the dead end as a bundle-creep canary

- 2026-04-12 | conjectured: Buyers will reliably scan the handoff QR; escrow release flows from buyer action
  refuted by: 3 of the first deliveries had buyers who never scanned (busy shop, lost card); escrow sat
  learned: shipment-confirmation must have a buyer-action AND a timeout fallback; relying on either alone breaks the merchant cash-flow story
  criterion now: ISC-26 added (auto-release on day 8 with audit entry)

- 2026-04-22 | conjectured: Vague performance Goals ("fast on cellular") are operational enough
  refuted by: bundle creep of 8KB went undetected for two sprints; nothing failed an ISC because no ISC named a number
  learned: every Constraint that maps to a budget needs a numeric ISC, not a vibe; Goal sharpening propagates down to ISCs
  criterion now: Goal explicitly states "p95 ≤ 1s on cellular" and "all-in fees ≤ 8%"; ISC-13 enforces the first, ISC-23.2 enforces the second

## Verification

- ISC-1: `bun run deploy` — `Deployed beanline (route: beanline.example.com/*)`
- ISC-2: `bunx tsc --noEmit --strict` — exit 0, no output
- ISC-3: `curl -i https://beanline.example.com` — `HTTP/2 200 / content-type: text/html; charset=utf-8`
- ISC-4: HTML head shows `<meta name="version" content="a3b4c5d">` matching `git rev-parse --short HEAD` output `a3b4c5d`
- ISC-5: Listing form integration test 2026-04-22 — submitted listing returned `id: lst_TestXXXX` + status `pending_review`
- ISC-6: `curl … /listings/lst_TestPend01` (anonymous) — `404`
- ISC-8: `curl -i https://beanline.example.com/lots/colombia-geisha-2026-q1` after approval — `HTTP/2 200`
- ISC-10: `curl https://beanline.example.com/browse | rg "<article" | wc -l` — `20`
- ISC-11: `bun test test/browse.property.test.ts -t "region filter"` — 200 runs, 0 failures
- ISC-12: `bun test test/browse.property.test.ts -t "process filter"` — 200 runs, 0 failures
- ISC-13: Lighthouse mobile run 2026-04-25 — `Performance 92 / FCP 624ms / LCP 891ms` on `/browse`
- ISC-16: `bun test test/auth.test.ts -t "magic link"` — 4 pass (reuse → 401, 15m01s → 401)
- ISC-17: callback `Set-Cookie: session=…; HttpOnly; Secure; SameSite=Lax; Path=/`
- ISC-18: `bun test test/roles.test.ts -t "verification gate"` — 3 pass
- ISC-21: `/account/payouts` as roaster — `200`, 1 `connect.stripe.com` link
- ISC-22: Stripe-sandbox checkout test 2026-04-15 — `payment_intent_TestXXXX` created with `transfer_group: lst_TestYYY`
- ISC-30: `curl -i https://beanline.example.com/checkout` (no session) — `HTTP/2 401`
- ISC-36: `curl -i https://beanline.example.com/api/follow` — `HTTP/2 404`
- ISC-37: Image-format audit 2026-04-22 — 100% of 247 image URLs returned `Content-Type: image/webp`
- ISC-38: devtools network panel at `/browse` 2026-04-25 — 0 third-party requests on initial load

<!--
Canonical showpiece. Marketplace pattern (auth + Stripe escrow + RBAC + listings + search + reviews + messaging) at E5 scale. Every section a standalone ISA can have is populated (all but Dependencies and Bridge Criteria, which need a hierarchy). It shows the verbatim `stated_goal` quoted as the Goal's first sentence, with every Test Strategy entry anchored to it (`literal`) or to a named derived claim, real-feeling Decisions with two ❌ DEAD ENDs and five refinements, four-piece C/R/L Changelog entries spanning the 4-month build. Anti-criteria (ISC-36, 37, 38) cover scope, privacy, and regression. Antecedents (none) — the goal is verifiable, not experiential, so antecedents aren't required at this gate. The delight prediction in Vision is falsifiable by the user but not gated as an ISC because the marketplace's success is measured by transactions completed, not by any single user's reaction.
-->
