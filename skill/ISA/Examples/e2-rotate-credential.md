---
task: "Rotate the production deploy credential in the CI pipeline"
slug: 20260208-103000_rotate-deploy-credential
effort: E2
phase: execute
progress: 0/16
started: 2026-02-08T18:30:00Z
updated: 2026-02-08T18:30:00Z
---

<!-- Fictitious example. The CI pipeline and credential surfaces here are teaching placeholders. -->

## Problem

The production deploy credential (a long-lived API token stored in CI as `DEPLOY_API_TOKEN`) was provisioned 14 months ago, has never been rotated, and grants broad write scope on the deploy target. Per the org's quarterly rotation policy this is overdue. We need to rotate it without breaking the next deploy and without leaving the old token live longer than necessary.

## Goal

Rotate `DEPLOY_API_TOKEN` end-to-end: provision a new token with the same scope, update the CI secret, run a verification deploy on a non-production branch, then revoke the old token. The next production deploy after this rotation must succeed, and the old token must be inactive within four hours of the new one going live.

## Criteria

### Pre-rotation

- [ ] ISC-1: New token's scope list is exactly `["deploy:write"]`.
- [ ] ISC-2: New token's `expires_at` is at most 90 days after issue.
- [ ] ISC-3: New token's `created_by` is the rotation runbook service account.

### CI update

- [ ] ISC-4: CI secret `DEPLOY_API_TOKEN` shows an `updated_at` within the rotation window.
- [ ] ISC-5: The new token value appears in no CI run log.

### Verification

- [ ] ISC-6: A `rotation-test` branch deploy using the new token exits 0.
- [ ] ISC-7: The verification deploy registers an artifact tagged `rotation-test-<timestamp>`.
- [ ] ISC-8: The test artifact returns 404 within 60 minutes of verify.

### Old token revocation

- [ ] ISC-9: Old token shows `revoked_at` ≤ 4 hours after new-token activation.
- [ ] ISC-10: A deploy attempt with the old token returns HTTP 401.
- [ ] ISC-11: Auth audit log holds a `token_revoked` event with actor, time, reason.

### Documentation

- [ ] ISC-12: The rotation runbook records the new token ID and rotation date.
- [ ] ISC-13: A next-rotation reminder is scheduled 76 days after this rotation.

### Anti-criteria

- [ ] ISC-14: Anti: privacy — neither token value appears in any commit, PR, or artifact.
- [ ] ISC-15: Anti: scope creep — new token holds no `admin:*` or `users:*` scope.
- [ ] ISC-16: Anti: rollback safety — old token is revoked no sooner than 30 minutes after activation.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: new token's scope list
  threshold: output is exactly deploy:write
  tool: |-
    curl -s -H "Authorization: Bearer $NEW_TOKEN" https://deploy.example.org/v1/me | jq -r '.scopes | sort | join(",")'

- isc: ISC-2
  type: bash
  check: seconds between issue and expiry
  threshold: ≤ 7776000 (90 days)
  tool: |-
    curl -s -H "Authorization: Bearer $ADMIN_TOKEN" https://deploy.example.org/v1/tokens/$NEW_ID | jq '(.expires_at|fromdate) - (.created_at|fromdate)'

- isc: ISC-3
  type: bash
  check: token creator
  threshold: svc-credential-rotation
  tool: |-
    curl -s -H "Authorization: Bearer $ADMIN_TOKEN" https://deploy.example.org/v1/tokens/$NEW_ID | jq -r '.created_by'

- isc: ISC-4
  type: bash
  check: secret updated_at is after the rotation start
  threshold: jq prints true
  tool: gh api repos/$REPO/actions/secrets/DEPLOY_API_TOKEN | jq --arg t "$ROTATION_START" '.updated_at >= $t'

- isc: ISC-5
  type: bash
  check: new token prefix in the verify run's log
  threshold: zero matches (rg exits 1)
  tool: gh run view $RUN_ID --log | rg -F "${NEW_TOKEN:0:8}"

- isc: ISC-6
  type: bash
  check: test deploy with new token succeeds
  threshold: run conclusion == success
  tool: gh workflow run deploy.yml --ref rotation-test && gh run watch --exit-status $(gh run list -w deploy.yml -b rotation-test -L1 --json databaseId -q '.[0].databaseId')

- isc: ISC-7
  type: bash
  check: tagged verification artifact exists
  threshold: count ≥ 1
  tool: |-
    curl -s -H "Authorization: Bearer $NEW_TOKEN" 'https://deploy.example.org/v1/artifacts?tag=rotation-test' | jq 'length'

- isc: ISC-8
  type: bash
  check: test artifact removed after cleanup
  threshold: HTTP 404
  tool: |-
    curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $NEW_TOKEN" https://deploy.example.org/v1/artifacts/$TEST_ARTIFACT_ID

- isc: ISC-9
  type: bash
  check: seconds from new-token activation to old-token revocation
  threshold: ≤ 14400
  tool: jq '(.revoked|fromdate) - (.activated|fromdate)' rotation-log.json

- isc: ISC-10
  type: bash
  check: old token is rejected
  threshold: HTTP 401
  tool: |-
    curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $OLD_TOKEN" -X POST https://deploy.example.org/v1/deploys

- isc: ISC-11
  type: bash
  check: revocation event in the audit log
  threshold: 1 event with non-empty actor, timestamp, reason
  tool: siem query 'event=token_revoked token_id=$OLD_ID earliest=-1h' --json | jq '[.[] | select(.actor and .timestamp and .reason)] | length'

- isc: ISC-12
  type: bash
  check: runbook names the new token ID and today's date
  threshold: both greps exit 0
  tool: grep -q "$NEW_ID" docs/runbooks/credential-rotation.md && grep -q "$(date +%F)" docs/runbooks/credential-rotation.md

- isc: ISC-13
  type: manual
  check: team calendar shows the reminder (90 days minus a 14-day early warning)
  threshold: event exists on the date printed by `date -d '+76 days' +%F`
  tool: open the team calendar at that date

- isc: ISC-14
  type: bash
  check: neither token's first 8 chars in git history, PR bodies, or build artifacts
  threshold: script exits 0 (it exits 1 on any match)
  tool: bash scripts/credential-leak-audit.sh "${NEW_TOKEN:0:8}" "${OLD_TOKEN:0:8}"

- isc: ISC-15
  type: bash
  check: forbidden scopes on the new token
  threshold: 0
  tool: |-
    curl -s -H "Authorization: Bearer $NEW_TOKEN" https://deploy.example.org/v1/me | jq '[.scopes[] | select(test("^(admin|users):"))] | length'

- isc: ISC-16
  type: bash
  check: gap between new-token activation and old-token revocation
  threshold: ≥ 1800s
  tool: jq '(.revoked|fromdate) - (.activated|fromdate)' rotation-log.json
```

<!--
E2 ops ISA. Required sections: Problem, Goal, Criteria, Test Strategy.
Demonstrates the ISA primitive applied to an ops/runbook task — the same shape as a code task. Anti-criteria (ISC-14, 15, 16) cover privacy, scope, and rollback safety — typical ops-task regression-prevention concerns. Every probe here is deterministic (`bash`) except the calendar reminder: the task touches secrets and auth, so the blast-radius rule forbids `manual` probes on those ISCs. Note ISC-16 explicitly preserves a safety window — a real-world lesson learned from prior bungled rotations.
-->
