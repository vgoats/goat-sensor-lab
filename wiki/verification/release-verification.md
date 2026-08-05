# Release Verification

This page records the verification boundary for the initial public release on **2026-08-01**.
It is evidence about the software build, not evidence that an animal behavior or welfare model is
accurate.

## Current Android release

The debug APK was built, installed, and opened explicitly on `emulator-5554` (Android SDK emulator,
`sdk_gphone64_arm64`). Visual checks covered the top, middle, and bottom of the scrollable UI:
status-bar icons remained dark on the light background, all fields and label heads scrolled into
view, and the Start/Stop and Export controls did not overlap content.

A controlled synthetic IMU session exercised changing acceleration and gyroscope inputs, three
simultaneous label heads, foreground-only finalization, and ZIP export. This was not a stationary
capture and is not animal data.

| Check | Observed result |
|---|---|
| Session | `20260801_170546_2d710871`; test identity `PHONE_TEST_001` |
| Synthetic sensor changes | Multiple acceleration and gyroscope vectors supplied through the emulator sensor console |
| Recorded rows | 575 canonical 25-column rows over 22.96 seconds |
| Requested / achieved rate | 25 Hz / 25.0 Hz |
| Gyroscope coverage | 575 rows with timestamp-bounded preceding gyroscope values |
| Live label transition | `FEEDING` + `ACTIVE_MOVEMENT` + `NORMAL`, retained in both event log and subsequent rows |
| Lifecycle | Pressing Home finalized `session.json` as `COMPLETED` with 575 rows |
| Export | ZIP contained `events.csv`, `samples.csv`, and `session.json` |
| Independent parser | `goat-sensor-analysis validate` accepted the exported CSV |

No additional stationary capture was created.

## Earlier physical-phone boundary

Before the 25-column contract was finalized, the recorder and Android share sheet were exercised
on a physical Infinix phone. That capture contained 587 samples at approximately 25.9 Hz and its
ZIP share flow completed. It used the former 24-column draft without `source_uptime_ms`; therefore
it is retained only as historical phone/acquisition proof and is not claimed as proof of the
current release schema. The physical phone was unavailable for the release pass, so the current
APK was verified on the emulator as described above.

## Firmware and automated checks

- 34 Android JVM tests passed; the debug APK assembled successfully. Recovery coverage includes
  torn quoted records, partial event rows, malformed headers, damaged metadata, quarantine, and
  export refusal for inconsistent sessions, including exact-width rows lacking a final terminator.
- 75 Python analysis tests and Ruff passed under the frozen `uv.lock` environment. Provenance
  coverage includes raw-export and annotation digest mismatches, schema/identity alignment,
  frozen-consensus interval joins, media/clock mapping, active revision and adjudication checks,
  recomputed multi-rater coverage/votes, expanded single-domain guards, and engineering-only
  isolation.
- The canonical schema verifier and its four tests passed.
- Seven JSON Schemas were meta-validated; the evidence and reference manifests validated against
  their schemas.
- Firmware built with PlatformIO 6.1.19, the pinned Seeed platform commit, and LSM6DS3 library
  2.0.7: 14,776 bytes RAM (6.2%) and 125,556 bytes flash (15.5%).

## 2026-08-05 physical XIAO Sense verification

The XIAO wearable path was physically tested after the original release boundary. This test used a
Seeed Studio XIAO nRF52840 Sense board and an Infinix X6873 physical Android phone.

| Check | Observed result |
|---|---|
| Board identity | `GoatSensor-911806CBE88F40D2` |
| Firmware target | `seeed-xiao-afruitnrf52-nrf52840-sense` |
| IMU proof | USB serial probe read live acceleration and gyroscope values from the onboard LSM6DS3TR-C |
| BLE capabilities | `protocol: 2`, `imu: LSM6DS3TR-C`, `rates_hz: [13,26]`, `packet_bytes: 20` |
| Direct BLE stream | 48 packets received in 3 seconds during a Mac-side stream check |
| Android device | Infinix X6873, Android SDK 36, app running under user/profile 10 |
| Android XIAO session | 26 Hz capture saved by the app with 147 samples |

The bring-up failure was a configuration mismatch: the firmware had been using the plain
`seeed-xiao-afruitnrf52-nrf52840` PlatformIO target. That target can build and upload, but it
selects the wrong Arduino variant for this Sense use case and made the onboard IMU appear
unavailable. The firmware now uses `seeed-xiao-afruitnrf52-nrf52840-sense`.

## Not yet physically verified

- export pulling from the Android work/profile-10 private app storage through ADB;
- battery operation on an actual board;
- mount/enclosure safety, calibration, wearability, or any goat/sheep trial; and
- animal-held-out, external-farm, prospective welfare, reproductive, or clinical performance.

These items remain mandatory gates in the [validation roadmap](../roadmap/validation-roadmap.md).
