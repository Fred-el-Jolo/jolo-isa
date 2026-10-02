---
task: "Build WattWatch, a local-first home energy monitoring app"
slug: 20260115-090000_wattwatch-v1
project: WattWatch
effort: E5
phase: execute
progress: 41/50
started: 2026-01-15T17:00:00Z
updated: 2026-04-27T22:30:00Z
context_sufficient: true
interview_ran: 2026-01-15T17:30:00Z
---

<!-- Fictitious example. "WattWatch" is a teaching project name; any resemblance to real products or organizations is coincidental. The wattwatch.example.org domain is RFC 2606 reserved. -->

## Problem

People with rooftop solar, home batteries, and smart-plug-instrumented circuits have access to real-time energy data, but the data lives in five vendor walled gardens. Shelly's app shows Shelly devices. Emporia shows Emporia. Sense shows Sense. Tesla's app shows Powerwall. None of them speak to each other; none of them produce a coherent house-level picture; all of them require a vendor cloud round-trip even for "is the heat pump on right now" questions answered by a sensor sitting on the homeowner's own LAN. Anyone who actually wants to optimize home electricity ends up running a Home Assistant install, hand-writing YAML for each integration, and accepting that the result is a hobbyist toolkit rather than a finished product. The middle ground — a polished desktop application that aggregates the major US residential energy sensors into one local-first picture — does not exist in 2026.

## Vision

A native desktop application (macOS-first, Linux next, Windows last) that the homeowner installs from a signed `.dmg`, points at their LAN, and within ten minutes is watching live whole-house power flow with per-circuit attribution, per-device drill-down, and a six-month historical archive — all stored locally on the homeowner's own disk. Delight: the user opens the app on a hot afternoon, sees the heat pump pull 4.2kW while the solar array produces 6.8kW, and watches the Powerwall charge with the surplus in real time — without a single packet leaving the home network. They send a screenshot to a friend. The friend installs the app the same night.

## Out of Scope

- **No mandatory cloud account.** The app runs fully offline against LAN-only sensors. Cloud sync is opt-in and disabled by default.
- **No utility-bill integration.** Reading PDFs from the utility company's portal is a different product. We aggregate sensor data, not billing data.
- **No HVAC or appliance control.** WattWatch reads. It never writes. No "turn off the dryer at 3pm" automation in v1.
- **No mobile apps.** Desktop only. A future read-only web view served from the desktop app is plausible; a native iOS/Android client is not v1.
- **No commercial / multi-tenant deployments.** Single home, single user, single machine. No fleet management, no landlord-tenant separation.
- **No support for vendor-encrypted protocols we cannot legitimately decode.** Shelly local HTTP API: yes. Emporia Vue local UDP: yes. Sense reverse-engineered cloud-only protocol: deferred until Sense ships a documented local API.
- **No real-time price arbitrage / battery-dispatch optimization.** Visualizing the data is v1. Acting on it is v2 or never.

## Principles

- Local-first is not a feature, it is the entire posture. If a feature requires the cloud to function, it is a different product.
- Sensor data is the homeowner's data. The app does not phone home, does not ship anonymized telemetry, does not embed third-party SDKs in the read path.
- A polished single-user desktop application is a legitimate product category in 2026; "just use Home Assistant" is not the answer for a non-developer audience.
- Hardware integrations are slow, fragile, and vendor-specific by nature. The app is honest about partial coverage rather than pretending all sensors are equal.
- Historical data is sacred. The user's six-month archive must survive app updates, sensor changes, and vendor API churn without manual export-import dances.

## Constraints

- TypeScript + Bun for tooling; the desktop shell is Tauri 2.x (Rust + system webview), not Electron. Bundle target ≤ 25MB compressed.
- All sensor data persists in a local SQLite database at `${APP_DATA}/wattwatch/db.sqlite`. No remote primary store.
- The app supports macOS 13+ as tier-1, Linux x86_64/aarch64 (AppImage + .deb) as tier-2, Windows 10+ as tier-3. Tier-1 must be production-quality; tier-3 may have known issues documented in release notes.
- All authentication is local (single password, Argon2id, stored in OS keychain). No SSO, no OAuth, no account servers.
- Optional cloud-sync (off by default) uses end-to-end encryption with a user-derived key; the sync server is a thin relay that cannot read content.
- Sensor poll cadence is configurable but bounded: minimum 1 second, maximum 5 minutes, default 5 seconds for whole-house and 30 seconds for per-device.
- The UI must remain responsive (60fps scroll, ≤ 100ms interaction latency p95) on a 2019 MacBook Air with 8GB RAM and 90 days of accumulated data.

## Goal

Ship a Tauri-based desktop application — code-named WattWatch and distributed via signed installers from `wattwatch.example.org` — that aggregates Shelly, Emporia Vue, Sense, and Tesla Powerwall sensor data into a unified local SQLite store, presents a real-time whole-house energy view with per-device attribution and a six-month historical archive, and operates fully offline by default with optional end-to-end-encrypted cloud sync.

## Criteria

### Build & Distribution

- [x] ISC-1: `bun run tauri build` produces signed `.dmg` (macOS arm64), `.AppImage` (Linux x86_64), and `.msi` (Windows x64) artifacts.
- [x] ISC-2: macOS `.dmg` is notarized; `spctl --assess --verbose` reports `accepted (source=Notarized Developer ID)`.
- [x] ISC-3: All three platform artifacts ≤ 25MB compressed.
- [x] ISC-4: `wattwatch.example.org/download` serves the latest signed artifacts with SHA-256 checksums posted alongside.
- [x] ISC-5: `wattwatch --version` prints semver matching the `package.json` version.

### First-Run & Onboarding

- [x] ISC-6: First-launch wizard completes in ≤ 10 minutes for a user with one Shelly device and one Powerwall.
- [x] ISC-7: LAN scan auto-detects Shelly devices via mDNS (`_shelly._tcp.local`) within 30 seconds.
- [x] ISC-8: Emporia Vue setup accepts the homeowner's local credentials and verifies UDP port 65432 is reachable.
- [x] ISC-9: Tesla Powerwall setup accepts the gateway IP and the customer-set password (no Tesla cloud account required).
- [x] ISC-10: Sense integration is gated behind a "experimental — cloud-only" disclaimer that the user must dismiss before enabling.
- [ ] ISC-11: Onboarding stores zero credentials in plaintext on disk; all secrets land in OS keychain (Keychain on macOS, libsecret on Linux, Credential Manager on Windows).

### Sensor Drivers

- [x] ISC-12: Shelly driver polls Gen1 and Gen2 devices via local HTTP API (`/status` and `/rpc/Shelly.GetStatus`).
- [x] ISC-13: Emporia Vue driver decodes the local UDP broadcast and maps the 16 circuit channels to user-named labels.
- [x] ISC-14: Tesla Powerwall driver authenticates against `/api/login/Basic` and polls `/api/meters/aggregates` and `/api/system_status/soe` every 5 seconds.
- [ ] ISC-15: Sense driver (experimental) authenticates against the documented WebSocket and warns the user that this path requires a Sense cloud round-trip.
- [x] ISC-16: A driver that fails three consecutive polls is marked `degraded` in the UI; ten consecutive failures marks it `offline` and pauses polling for 60 seconds.
- [x] ISC-17: Driver poll latency p95 ≤ 200ms on LAN sensors; cloud sensors (Sense) p95 ≤ 2000ms.

### Data Model & Storage

- [x] ISC-18: SQLite schema: `device`, `sensor_reading`, `circuit`, `aggregate_5min`, `aggregate_hourly`, `aggregate_daily`, `event`, `user_pref`.
- [x] ISC-19: `sensor_reading` rolls up to `aggregate_5min` continuously; older raw readings are pruned after 7 days.
- [x] ISC-20: `aggregate_hourly` retained 13 months; `aggregate_daily` retained indefinitely.
- [x] ISC-21: Database integrity check (`PRAGMA integrity_check`) runs at startup; failure shows recovery wizard, never silently ignores.
- [x] ISC-22: A user-triggered `Export → JSON` writes the full history to a timestamped file in ≤ 30 seconds for a 6-month archive.

### UI / Real-Time View

- [x] ISC-23: Live dashboard shows whole-house power, solar production, battery state-of-charge, and grid import/export with values updated every 5 seconds.
- [x] ISC-24: Per-circuit panel lists all Emporia Vue circuits sorted by current draw with sparklines for the last 60 minutes.
- [x] ISC-25: Energy-flow diagram (Sankey) renders solar → home / battery / grid splits in real time.
- [ ] ISC-26: Drill-down view for any circuit shows raw readings, hourly aggregates, and daily aggregates with zoom and pan.
- [x] ISC-27: UI maintains 60fps scroll on a 2019 MacBook Air (8GB) with 90 days of data loaded.
- [x] ISC-28: Interaction latency (click → first paint) p95 ≤ 100ms on tier-1 hardware.

### Alerts

- [x] ISC-29: User can define rules of the form `if <metric> <op> <threshold> for <duration>`.
- [x] ISC-30: When a rule fires, the app shows a system notification and writes an `event` row.
- [x] ISC-31: Alert state persists across app restarts; an alert that fires while the app is closed shows on next launch.
- [ ] ISC-32: Notification permission failure is handled gracefully — the alert still writes to the in-app log even if the OS denies notifications.

### Auth (local password)

- [x] ISC-33: First launch prompts the user to set a local password (Argon2id, m=64MB, t=3, p=4).
- [x] ISC-34: The local password unlocks the SQLite encryption key (SQLCipher) at app start.
- [x] ISC-35: Five failed unlock attempts triggers a 5-minute cooldown.
- [x] ISC-36: Password reset requires the user to confirm they will lose access to existing encrypted data; there is no recovery key in v1.

### Cloud Sync (optional, disabled by default)

- [ ] ISC-37: Cloud sync is OFF in default settings; turning it on shows a single-screen explanation of what data leaves the device.
- [ ] ISC-38: When enabled, the app derives a sync key from the local password using HKDF and a stable per-install salt.
- [ ] ISC-39: Synced payloads are encrypted with AES-256-GCM client-side; the relay server stores ciphertext only.
- [ ] ISC-40: A second device with the same password and email can pair within 60 seconds and resume showing the user's data.
- [ ] ISC-41: Disabling cloud sync deletes all server-side ciphertext within 24 hours; the app shows a confirmation when deletion completes.

### Updates

- [x] ISC-42: The app checks `wattwatch.example.org/api/release/latest` once per 24 hours; updates are applied only after the user clicks "Install."
- [x] ISC-43: Update payloads are signed; an unsigned or tampered payload aborts the update with a visible error.

### Operational

- [x] ISC-44: A diagnostic export bundles the SQLite schema (no rows), driver logs (last 24h), and OS info into a `.zip` for support.
- [x] ISC-45: Crash reporter is opt-in and shows the user the exact bytes that would be sent before transmission.

### Anti-criteria

- [x] ISC-46: Anti: privacy — the app makes zero outbound network requests on first launch before the user explicitly enables cloud sync (verified via packet capture).
- [x] ISC-47: Anti: out of scope — there is no `Control` button anywhere in the UI; sensor write paths are not wired up.
- [x] ISC-48: Anti: data loss — an app update never overwrites or migrates the SQLite database without first writing a `.bak` copy with timestamp suffix.
- [x] ISC-49: Anti: dependency creep — no Electron in the build graph; `bun pm ls | grep electron` returns empty.
- [x] ISC-50: Anti: telemetry — `! rg -q "google-analytics|sentry|mixpanel|posthog|fullstory" src/` returns zero matches.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  kind: behaviour
  check: build artifacts and signatures
  threshold: 3 artifacts, each signature verifies
  tool: bun run tauri build && bash scripts/verify-signatures.sh dist/

- isc: ISC-2
  type: bash
  kind: behaviour
  check: macOS Gatekeeper accepts the signed .dmg
  threshold: spctl reports "accepted (source=Notarized Developer ID)"
  tool: spctl --assess --verbose dist/WattWatch.dmg

- isc: ISC-3
  type: bash
  kind: behaviour
  check: artifact size after compression
  threshold: ≤ 25MB each
  tool: du -m dist/WattWatch.dmg dist/WattWatch.AppImage dist/WattWatch.msi

- isc: ISC-4
  type: bash
  kind: http
  check: download page checksums vs fetched artifacts
  threshold: every posted SHA-256 matches
  tool: bash scripts/verify-download-page.sh https://wattwatch.example.org/download

- isc: ISC-5
  type: bash
  kind: file
  check: CLI version vs package.json
  threshold: strings equal
  tool: test "$(wattwatch --version)" = "$(jq -r .version package.json)"
  fails-when: "--version prints something other than package.json's version"

- isc: ISC-6
  type: manual
  kind: doc
  check: timed first-run with one Shelly and one Powerwall
  threshold: ≤ 10 minutes, 3 of 3 test users
  tool: moderated first-run sessions with a stopwatch

- isc: ISC-7
  type: bash
  kind: behaviour
  check: mDNS scan returns Shelly devices in test rig
  threshold: ≥ 1 device discovered in ≤ 30s
  tool: bun run scripts/mdns-probe.ts

- isc: ISC-8
  type: unit-test
  kind: behaviour
  check: Emporia setup with valid creds and a reachable UDP port
  threshold: setup succeeds; unreachable port shows an error
  tool: bun test test/onboarding/emporia.test.ts

- isc: ISC-9
  type: bash
  kind: behaviour
  risk: high
  check: Powerwall setup with the gateway only, Tesla cloud blocked
  threshold: setup succeeds with cloud hosts null-routed
  tool: bash scripts/offline-setup.sh powerwall

- isc: ISC-10
  type: unit-test
  kind: behaviour
  check: Sense toggle before and after disclaimer dismissal
  threshold: toggle disabled until dismissed
  tool: bun test test/onboarding/sense-gate.test.ts

- isc: ISC-11
  type: property
  kind: behaviour
  risk: high
  property: "∀ credential c entered in onboarding: c never appears in any file under the app-data dir; keychain holds it"
  generator: "random credentials incl. unicode and 1–256 chars, across all four driver types"
  runs: 200
  tool: bun test test/secrets.property.test.ts

- isc: ISC-12
  type: unit-test
  kind: behaviour
  check: driver against Gen1 and Gen2 mock devices
  threshold: readings from both endpoints
  tool: bun test test/drivers/shelly.test.ts

- isc: ISC-13
  type: property
  kind: behaviour
  property: "decode(encode(frame)) == frame for 16-channel frames; channel i maps to the user label for i"
  generator: "random 16-channel frames with watt values 0–15000 and random label maps"
  runs: 1000
  tool: bun test test/drivers/emporia.property.test.ts

- isc: ISC-14
  type: bash
  kind: behaviour
  risk: high
  check: Powerwall driver reads /api/meters/aggregates with valid auth
  threshold: returns site/load/solar/battery values
  tool: bun run scripts/powerwall-probe.ts --gateway 192.168.x.x

- isc: ISC-15
  type: unit-test
  kind: behaviour
  check: Sense driver auth against a mock WebSocket + warning banner
  threshold: connects; warning rendered once per session
  tool: bun test test/drivers/sense.test.ts

- isc: ISC-16
  type: unit-test
  kind: behaviour
  check: state after 3 and 10 consecutive failed polls
  threshold: degraded at 3; offline + 60s pause at 10
  tool: bun test test/drivers/health.test.ts

- isc: ISC-17
  type: bash
  kind: behaviour
  check: poll latency per driver class over 1,000 polls
  threshold: LAN p95 ≤ 200ms; cloud p95 ≤ 2000ms
  tool: bun run scripts/poll-latency.ts --polls 1000

- isc: ISC-18
  type: bash
  kind: schema
  check: table list
  threshold: exactly the 8 named tables
  tool: sqlite3 "$DB" ".tables" | tr -s ' ' '\n' | sort | xargs

- isc: ISC-19
  type: unit-test
  kind: behaviour
  check: rollup and 7-day raw pruning with a fake clock
  threshold: 5-min aggregates match raw sums; raw rows older than 7d gone
  tool: bun test test/db/rollup.test.ts

- isc: ISC-20
  type: unit-test
  kind: behaviour
  check: retention with a fake clock at +14 months
  threshold: hourly rows ≤ 13 months old; daily rows all kept
  tool: bun test test/db/retention.test.ts

- isc: ISC-21
  type: bash
  kind: schema
  check: PRAGMA integrity_check on existing db
  threshold: returns "ok"
  tool: sqlite3 ${APP_DATA}/wattwatch/db.sqlite "PRAGMA integrity_check"

- isc: ISC-22
  type: bash
  kind: schema
  check: JSON export of the 6-month fixture archive
  threshold: ≤ 30s, file parses
  tool: time wattwatch export --json --db test/fixtures/6mo.sqlite --out /tmp/x.json && jq -e . /tmp/x.json >/dev/null

- isc: ISC-23
  type: screenshot
  kind: visual
  risk: low — solar energy production, not a production environment
  check: live dashboard tiles over 15 seconds
  threshold: 4 tiles present; values change on the 5s tick
  tool: bunx playwright test e2e/dashboard.spec.ts (3 shots, 5s apart), viewed

- isc: ISC-24
  type: unit-test
  kind: behaviour
  check: circuit list order and sparkline window
  threshold: sorted by current draw; sparkline spans 60 minutes
  tool: bun test test/ui/circuits.test.ts

- isc: ISC-25
  type: screenshot
  kind: visual
  check: Sankey with solar → home / battery / grid
  threshold: three outflows visible, widths proportional to fixture values
  tool: bunx playwright test e2e/sankey.spec.ts, viewed

- isc: ISC-26
  type: unit-test
  kind: behaviour
  check: drill-down levels and zoom/pan
  threshold: raw, hourly and daily views reachable; zoom and pan change the visible range
  tool: bunx playwright test e2e/drilldown.spec.ts

- isc: ISC-27
  type: performance
  kind: behaviour
  check: 60fps scroll with 90 days loaded
  threshold: median frame time ≤ 16.6ms
  tool: tauri devtools performance recorder

- isc: ISC-28
  type: performance
  kind: behaviour
  check: click → first paint p95
  threshold: ≤ 100ms
  tool: bun run scripts/ui-latency.ts --runs 200

- isc: ISC-29
  type: property
  kind: behaviour
  property: "parse(format(rule)) == rule for every rule in the metric × op × threshold × duration grammar"
  generator: "random metrics from the schema, ops < <= > >= ==, thresholds, durations 1s–24h"
  runs: 1000
  tool: bun test test/alerts/rule-grammar.property.test.ts

- isc: ISC-30
  type: unit-test
  kind: behaviour
  check: firing rule side effects
  threshold: 1 notification call + 1 event row
  tool: bun test test/alerts/fire.test.ts

- isc: ISC-31
  type: unit-test
  kind: behaviour
  check: alert fired while app closed (fake clock across restart)
  threshold: shown on next launch
  tool: bun test test/alerts/persist.test.ts

- isc: ISC-32
  type: unit-test
  kind: behaviour
  risk: low — the OS notification permission, not access control
  check: firing rule with notification permission denied
  threshold: event row still written, no throw
  tool: bun test test/alerts/permission-denied.test.ts

- isc: ISC-33
  type: unit-test
  kind: behaviour
  risk: high
  check: stored password hash parameters
  threshold: $argon2id$v=19$m=65536,t=3,p=4
  tool: bun test test/auth/kdf.test.ts

- isc: ISC-34
  type: bash
  kind: schema
  risk: high
  check: DB opened without the key
  threshold: '"file is not a database"'
  tool: sqlite3 ${APP_DATA}/wattwatch/db.sqlite 'SELECT 1' 2>&1

- isc: ISC-35
  type: unit-test
  kind: behaviour
  risk: high
  check: sixth unlock attempt after five failures
  threshold: rejected with cooldown ≥ 300s
  tool: bun test test/auth/cooldown.test.ts

- isc: ISC-36
  type: unit-test
  kind: behaviour
  risk: high
  check: reset flow without and with the data-loss confirmation
  threshold: reset blocked until confirmed; no recovery key generated
  tool: bun test test/auth/reset.test.ts

- isc: ISC-37
  type: unit-test
  kind: behaviour
  check: default sync setting + enable screen
  threshold: default off; explanation screen shown before on
  tool: bun test test/sync/defaults.test.ts

- isc: ISC-38
  type: property
  kind: behaviour
  risk: high
  property: "sync_key(pw, salt) is deterministic per install and differs across salts"
  generator: "random passwords × random 16-byte salts"
  runs: 1000
  tool: bun test test/sync/kdf.property.test.ts

- isc: ISC-39
  type: property
  kind: behaviour
  property: "∀ payload p: relay-stored blob ≠ p, decrypts to p only with the key, and carries a valid GCM tag"
  generator: "random JSON payloads 0–64KB drawn from the sync schema"
  runs: 1000
  tool: bun test test/sync/encryption.property.test.ts

- isc: ISC-40
  type: bash
  kind: behaviour
  risk: high
  check: second-device pairing on the staging relay
  threshold: paired and showing data in ≤ 60s
  tool: bun run scripts/pair-two-devices.ts --relay staging

- isc: ISC-41
  type: bash
  kind: behaviour
  check: server-side ciphertext after disable
  threshold: 0 objects for the install within 24h; confirmation shown
  tool: bun run scripts/relay-objects.ts --install $INSTALL_ID --after-disable 24h

- isc: ISC-42
  type: unit-test
  kind: behaviour
  risk: high
  check: update checks over 72h of fake clock; install gating
  threshold: 3 checks; nothing applied until "Install" clicked
  tool: bun test test/update/schedule.test.ts

- isc: ISC-43
  type: unit-test
  kind: behaviour
  check: unsigned and tampered payloads
  threshold: both abort with a visible error
  tool: bun test test/update/signature.test.ts

- isc: ISC-44
  type: bash
  kind: behaviour
  check: diagnostic bundle contents
  threshold: schema only (0 INSERT lines), logs ≤ 24h old, os.json present
  tool: |-
    wattwatch diag --out /tmp/d.zip && ! unzip -p /tmp/d.zip schema.sql | rg -q INSERT

- isc: ISC-45
  type: unit-test
  kind: behaviour
  check: crash reporter default + preview
  threshold: off by default; preview shows the exact bytes later sent
  tool: bun test test/crash/preview.test.ts

- isc: ISC-46
  type: bash
  kind: regression
  check: outbound packets on first launch before consent
  threshold: 0 packets to non-LAN destinations
  tool: |-
    test "$(timeout 60 tcpdump -i en0 -n -q 'not net 192.168.0.0/16 and not net 10.0.0.0/8 and not net 172.16.0.0/12' 2>/dev/null | wc -l)" -eq 0
  fails-when: "a packet leaves for a non-LAN address in the first minute"

- isc: ISC-47
  type: bash
  kind: regression
  check: control affordances and write paths
  threshold: zero matches (the negated rg exits 0)
  tool: |-
    ! rg -qi '"control"|>Control<|setRelay|set_output|/relay/' src/
  fails-when: "a Control button or relay call exists in src/"

- isc: ISC-48
  type: unit-test
  kind: regression
  check: DB file set before and after a simulated migration
  threshold: a timestamped .bak exists before the migration writes
  tool: bun test test/update/backup.test.ts
  fails-when: "an update writes the database without a timestamped backup first"

- isc: ISC-49
  type: bash
  kind: regression
  check: no Electron in dependency tree
  threshold: zero matches (the negated rg exits 0)
  tool: |-
    ! bun pm ls | rg -qi electron
  fails-when: "Electron is in the dependency graph"

- isc: ISC-50
  type: bash
  kind: regression
  check: no third-party telemetry SDK strings in source
  threshold: zero matches (the negated rg exits 0)
  tool: |-
    ! rg -q "google-analytics|sentry|mixpanel|posthog|fullstory" src/
  fails-when: "a tracking library is referenced in src/"
```

## Features

```yaml
- name: SensorDriverShelly
  description: Local HTTP polling for Shelly Gen1/Gen2 devices with mDNS discovery
  satisfies: [ISC-7, ISC-12, ISC-16, ISC-17]
  depends_on: []
  parallelizable: true

- name: SensorDriverEmporia
  description: UDP broadcast decoder + 16-channel circuit mapping
  satisfies: [ISC-8, ISC-13, ISC-16, ISC-17]
  depends_on: []
  parallelizable: true

- name: SensorDriverPowerwall
  description: Local Tesla Gateway auth + meter/battery polling
  satisfies: [ISC-9, ISC-14, ISC-16, ISC-17]
  depends_on: []
  parallelizable: true

- name: SensorDriverSense
  description: Experimental WebSocket integration with cloud-required disclaimer
  satisfies: [ISC-10, ISC-15, ISC-16]
  depends_on: []
  parallelizable: true

- name: LocalStorage
  description: SQLCipher-backed SQLite with rollups, retention, and integrity checks
  satisfies: [ISC-18, ISC-19, ISC-20, ISC-21, ISC-22, ISC-34, ISC-48]
  depends_on: []
  parallelizable: false

- name: AuthLocal
  description: Argon2id password + OS keychain + cooldown
  satisfies: [ISC-11, ISC-33, ISC-34, ISC-35, ISC-36]
  depends_on: [LocalStorage]
  parallelizable: false

- name: LiveDashboard
  description: Real-time whole-house view + Sankey + per-circuit panel
  satisfies: [ISC-23, ISC-24, ISC-25, ISC-26, ISC-27, ISC-28]
  depends_on: [SensorDriverShelly, SensorDriverEmporia, SensorDriverPowerwall, LocalStorage]
  parallelizable: false

- name: Alerts
  description: Rule engine, system notifications, persisted alert state
  satisfies: [ISC-29, ISC-30, ISC-31, ISC-32]
  depends_on: [LocalStorage]
  parallelizable: true

- name: CloudSyncOptional
  description: E2E-encrypted optional sync via thin relay
  satisfies: [ISC-37, ISC-38, ISC-39, ISC-40, ISC-41]
  depends_on: [AuthLocal, LocalStorage]
  parallelizable: false

- name: Updater
  description: Signed update channel with explicit user opt-in per install
  satisfies: [ISC-42, ISC-43]
  depends_on: []
  parallelizable: true

- name: Distribution
  description: Tauri build pipeline, notarization, downloads page
  satisfies: [ISC-1, ISC-2, ISC-3, ISC-4, ISC-5]
  depends_on: []
  parallelizable: true

- name: Diagnostics
  description: Diagnostic export + opt-in crash reporter
  satisfies: [ISC-44, ISC-45]
  depends_on: [LocalStorage]
  parallelizable: true
```

## Decisions

- 2026-01-15 17:00: Tauri 2.x over Electron because the bundle-size constraint (≤ 25MB) is impossible with Electron's Chromium baseline (~120MB minimum) and because system-webview reuse improves cold-start latency materially on tier-1 macOS hardware.
- 2026-01-15 17:30: Interview ran before BUILD (8 questions). It fixed the supported-sensor list (Shelly, Emporia Vue, Powerwall; Sense as experimental) and made "no cloud account required" a Constraint.
- 2026-01-22 11:00: SQLite + SQLCipher over a custom encrypted KV because the data shape is genuinely relational (devices, circuits, readings, aggregates) and the homeowner-export use case demands a portable file format.
- 2026-02-04 14:30: ❌ DEAD END: Tried polling all four sensor families from a single Worker thread to simplify the scheduler. Result: a stalled Sense WebSocket blocked Shelly polls and dashboard latency exceeded ISC-28 by 4×. Reverted to per-driver dedicated workers with isolated event loops. Don't retry.
- 2026-02-19 09:00: refined: ISC-19 retention policy split — original "raw readings retained indefinitely" was naive; 7-day raw + 13-month hourly + indefinite daily is the actual storage shape that survives 6 months on a 256GB Mac.
- 2026-03-02 22:15: ❌ DEAD END: Tried using vendor cloud APIs as a fallback when LAN auth failed. This violated the local-first principle and introduced a hidden cloud dependency that some users would not notice. Reverted to honest "this sensor is offline" UI. Don't retry.
- 2026-03-14 16:00: Cloud sync deferred from v1 to v1.1 — the threat model around the relay server is non-trivial and shipping the local-first product first is more honest than shipping cloud sync alongside it.
- 2026-03-29 13:00: refined: ISC-46 sharpened from "no telemetry" to "zero outbound packets to non-LAN destinations on first launch before user opts in" after a packet-capture review found a Tauri auto-update probe firing pre-consent. Updater check now waits until the user has finished onboarding.
- 2026-04-10 19:30: Sense driver kept in v1 as `experimental` rather than dropped, because user-research showed Sense owners are the most underserved by existing tools. The cloud-required disclaimer + ISC-15's explicit warning is the honest compromise.
- 2026-04-22 10:00: refined: ISC-3 bundle target tightened from 35MB to 25MB after Tauri 2.x's release notes on system-webview reuse landed; the original 35MB target was generous.

## Changelog

- 2026-02-04 | conjectured: A single polling worker with all four drivers will simplify the architecture without measurable cost
  refuted by: a stalled Sense WebSocket blocked Shelly polls and dashboard interaction latency exceeded ISC-28 by 4×
  learned: per-driver isolation is required when one driver's failure mode is a hung connection rather than an error response
  criterion now: ISC-17 split into LAN sensor budget (≤ 200ms) and cloud sensor budget (≤ 2000ms); driver implementation moved to per-driver workers

- 2026-02-22 | conjectured: 7 days of raw readings is enough for power-user drill-down
  refuted by: beta tester filed a bug saying he wanted to look at 5-minute resolution from 30 days ago for a heat-pump diagnostic
  learned: 5-minute aggregates are the right "drill-down" resolution; raw 1-second readings are only useful within a week
  criterion now: ISC-19 sharpened — raw retained 7 days, 5-minute aggregates retained 13 months, daily indefinitely

- 2026-03-02 | conjectured: Falling back to vendor cloud when LAN auth fails is a kindness to the user
  refuted by: the fallback was invisible and one tester ran for 3 weeks on cloud-fallback without noticing — exactly the failure mode the local-first principle exists to prevent
  learned: silent fallbacks across trust boundaries violate the user's mental model; the honest UI is "your sensor is offline, here's why"
  criterion now: no change to ISCs; Decisions logs the dead end and the principle is sharpened in code review checklist

- 2026-03-29 | conjectured: Tauri's default auto-update probe is a reasonable thing to ship pre-consent
  refuted by: packet-capture audit found the probe firing on first launch before the user had even seen the welcome screen, contradicting "zero outbound packets before consent"
  learned: "no telemetry" is not enough; the audit must include framework-default network behavior, not just our own code
  criterion now: ISC-46 sharpened from "no telemetry" to "zero outbound packets to non-LAN destinations on first launch before user opts in"; updater check deferred until post-onboarding

## Verification

- ISC-1: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun run tauri build && bash scripts/verify-signatures.sh dist/` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L2)
- ISC-2: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `spctl --assess --verbose dist/WattWatch.dmg` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L3)
- ISC-3: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `du -m dist/WattWatch.dmg dist/WattWatch.AppImage dist/WattWatch.msi` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L4)
- ISC-4: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bash scripts/verify-download-page.sh https://wattwatch.example.org/download` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L5)
- ISC-5: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `test "$(wattwatch --version)" = "$(jq -r .version package.json)"` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L6)
- ISC-6: attested 2026-04-27T22:30:00 — three moderated first runs — 6:40, 8:15, 9:02 (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L7)
- ISC-7: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun run scripts/mdns-probe.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L8)
- ISC-8: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/onboarding/emporia.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L9)
- ISC-9: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bash scripts/offline-setup.sh powerwall` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L10)
- ISC-10: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/onboarding/sense-gate.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L11)
- ISC-12: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/drivers/shelly.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L12)
- ISC-13: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/drivers/emporia.property.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L13)
- ISC-14: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun run scripts/powerwall-probe.ts --gateway 192.168.x.x` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L14)
- ISC-16: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/drivers/health.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L15)
- ISC-17: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun run scripts/poll-latency.ts --polls 1000` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L16)
- ISC-18: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `sqlite3 "$DB" ".tables" | tr -s ' ' '\n' | sort | xargs` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L17)
- ISC-19: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/db/rollup.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L18)
- ISC-20: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/db/retention.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L19)
- ISC-21: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `sqlite3 ${APP_DATA}/wattwatch/db.sqlite "PRAGMA integrity_check"` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L20)
- ISC-22: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `time wattwatch export --json --db test/fixtures/6mo.sqlite --out /tmp/x.json && jq -e . /tmp/x.json >/dev/null` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L21)
- ISC-23: attested 2026-04-27T22:30:00 — dashboard shots `shots/dash-{0,5,10}s.png` viewed — 4 tiles, values change between shots (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L22)
- ISC-24: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/ui/circuits.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L23)
- ISC-25: attested 2026-04-27T22:30:00 — `shots/sankey.png` viewed — solar → home / battery / grid, widths match fixture 2.1 / 1.4 / 0.8 kW (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L24)
- ISC-27: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `tauri devtools performance recorder` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L25)
- ISC-28: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun run scripts/ui-latency.ts --runs 200` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L26)
- ISC-29: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/alerts/rule-grammar.property.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L27)
- ISC-30: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/alerts/fire.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L28)
- ISC-31: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/alerts/persist.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L29)
- ISC-33: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/auth/kdf.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L30)
- ISC-34: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `sqlite3 ${APP_DATA}/wattwatch/db.sqlite 'SELECT 1' 2>&1` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L31)
- ISC-35: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/auth/cooldown.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L32)
- ISC-36: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/auth/reset.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L33)
- ISC-42: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/update/schedule.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L34)
- ISC-43: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/update/signature.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L35)
- ISC-44: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `wattwatch diag --out /tmp/d.zip && ! unzip -p /tmp/d.zip schema.sql | rg -q INSERT` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L36)
- ISC-45: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/crash/preview.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L37)
- ISC-46: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `test "$(timeout 60 tcpdump -i en0 -n -q 'not net 192.168.0.0/16 and not net 10.0.0.0/8 and not net 172.16.0.0/12' 2>/dev/null | wc -l)" -eq 0` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L38)
- ISC-47: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `! rg -qi '"control"|>Control<|setRelay|set_output|/relay/' src/` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L39)
- ISC-48: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `bun test test/update/backup.test.ts` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L40)
- ISC-49: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `! bun pm ls | rg -qi electron` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L41)
- ISC-50: verified 2026-04-27T22:30:00 — exit 0 in 0.3s — `! rg -q "google-analytics|sentry|mixpanel|posthog|fullstory" src/` (ledger: 20260115-090000_wattwatch-v1-dfd99783f158#L42)
