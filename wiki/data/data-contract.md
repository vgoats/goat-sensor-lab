# Data Contract

Sample schema version `1` stores sensor samples, capture-session metadata, and live observer events
separately. Canonical storage uses SI units so phone and XIAO values do not silently mix units.
It does **not** make their sensor distributions interchangeable. Independent research annotations,
derived consensus, clinical outcomes, and experiment metadata use separate versioned contracts.

## `samples.csv`

| Field | Type / unit | Meaning |
|---|---|---|
| `schema_version` | integer | Contract version |
| `session_id` | string | Immutable recording-session identifier |
| `animal_id` | string | Pseudonymous study identity; map to farm RFID outside exported research data |
| `species` | enum | `GOAT` or `SHEEP` |
| `placement` | enum | `PHONE_HANDHELD_TEST`, `NECK_COLLAR`, `EAR_MOUNT`, or `BODY_HARNESS` |
| `source` | enum | `ANDROID_PHONE` or `XIAO_NRF52840_SENSE` |
| `device_id` | string | Phone sensor identity or board/BLE identity |
| `sequence` | integer | Monotonic per-source sequence; detects missing or reordered packets |
| `wall_time_epoch_ms` | integer ms | Human-readable time; may jump if the system clock changes |
| `monotonic_time_ns` | integer ns | Primary acceleration sample clock for synchronization and intervals |
| `source_uptime_ms` | integer ms or null | Source-native uptime retained for packet-loss and clock-anchor audits; blank for phone frames without a separate source clock |
| `gyro_monotonic_time_ns` | integer ns or null | Gyroscope sample time when independently available |
| `acc_x_m_s2`, `acc_y_m_s2`, `acc_z_m_s2` | float `m/s²` | Raw sensor acceleration converted to SI units, including gravity; project calibration is not implied |
| `gyro_x_rad_s`, `gyro_y_rad_s`, `gyro_z_rad_s` | float `rad/s` or null | Raw angular velocity |
| `temperature_c` | float or null | Device/IMU/contact proxy only; not automatically core body temperature |
| `battery_percent` | integer or null | Source-reported estimate, not available without suitable power measurement |
| `rssi_dbm` | integer or null | BLE received signal strength at receiver |
| behavior columns | enums | Current live-observer state copied onto each row for field operation and QA; not adjudicated research ground truth |
| `invalid_data` | boolean | Sensor/mount/visibility failure; separate from unknown behavior |

## `events.csv`

Events contain wall and monotonic timestamps, session ID, event type, and the full current state of
the live label heads. Required event types are `session_start`, `label_change`, and `session_stop`.
Future events such as synchronization taps, battery changes, mount adjustments, treatment, and
feed delivery must use explicit event names rather than overloaded notes. `events.csv` is an
operator trace; it has no independent-rater, media-clock, revision, or adjudication provenance and
must not be promoted directly to frozen research ground truth.

## `session.json`

The current app capture file includes schema version, session and animal IDs, species, placement,
requested and achieved sample rates, notes, start/end wall times, and sample count. This is a
capture summary, not the complete reproducibility record. Bind every curated session to an
[`experiment-manifest-v1`](../../schema/experiment-manifest-v1.schema.json) containing protocol and
registration, farm/site/pen, animal characteristics, hardware/software versions, placement and
enclosure, observed rates/ranges, calibration provenance, cameras and clocks, annotators,
husbandry, study allocation, and missingness explanations. The Android app does not yet emit this
manifest automatically.

## Independent annotations and consensus

Live labels in `samples.csv` and `events.csv` are useful contemporaneous observer notes. They are
not independent multi-rater truth. Research annotation uses:

1. [`annotations-v1.csv`](../../schema/annotations-v1.schema.json), an append-only table with rater,
   head, onset/offset, media position and clock mapping, ethogram version, confidence, visibility,
   revision/supersedes, and adjudication provenance;
2. the immutable raw rater tracks and their input digest; and
3. a separate [`annotation-consensus-v1`](../../schema/annotation-consensus-v1.schema.json)
   materialization that cites every contributing annotation ID and a versioned resolution method.

Corrections append records; they never rewrite a published rater row. Consensus is regenerated
when its inputs or rules change, assigned a new materialization ID, and never replaces the rater
table. Only a frozen consensus artifact may be selected as a model target, and its animal/session
partition must be fixed before window generation. Research training resolves active revision
chains, verifies immutable media and clock-mapping references, recomputes multi-rater coverage,
requires the registered blinding/coverage gate, and rematerializes unanimous or majority votes;
adjudicated segments require two independent source raters and a distinct adjudicator record.

## Clinical outcomes

Clinical confirmation is not a live welfare label, behavior annotation, or consensus label. A
registered clinical study records it in
[`clinical-outcomes-v1.csv`](../../schema/clinical-outcomes-v1.schema.json), including qualified
assessor role, reference-standard version and result, blinded status, pseudonymous source-record
key, clinical onset/assessment times, and the pre-specified prediction window. Identifying medical
records remain in the approved clinical system. The IMU model cannot populate this artifact.

## Label heads

| Head | Values | Rule |
|---|---|---|
| Ingestive | `UNKNOWN`, `FEEDING`, `RUMINATION`, `NEITHER` | Rumination means regurgitating and re-chewing cud; it is not ordinary feed chewing |
| Posture/activity | `UNKNOWN`, `LYING`, `STANDING`, `ACTIVE_MOVEMENT` | Posture may coexist with ingestive behavior |
| Welfare observation | `UNKNOWN`, `NORMAL`, `SUSPECTED_ABNORMAL_INACTIVITY` | Observable review signal only; clinical outcomes are separate |
| Data validity | `true` / `false` | Mark occlusion, loose mount, sensor failure, handling, or unreliable sync |

`UNKNOWN` means the behavior cannot be determined. `invalid_data=true` means the measurement or
annotation interval is unreliable. They must not be merged.

## Measurement and calibration provenance

The raw exports contain device readings converted into the stated SI units. Unit conversion does
not establish traceable project calibration. Until calibration is performed, the experiment
manifest must use `UNCALIBRATED`, `FACTORY_SPECIFICATION_ONLY`, or `UNKNOWN` and
`applied_to_raw_export=false`.

A project calibration release must include a calibration ID, device ID and configuration, date and
operator, method/version, six-position accelerometer bias/scale results, stationary gyroscope
bias/noise, achieved-rate and clock checks, saturation checks, test temperature, coefficients,
and a digest of the coefficient artifact. Apply corrections only to a derived dataset unless the
raw-export contract is versioned explicitly; preserve the untouched SI-converted source export.

## Timing and quality invariants

- Sort and segment by `monotonic_time_ns`, not wall time.
- Reject duplicate `(session_id, source, device_id, sequence)` rows.
- Record gaps and achieved rate; never interpolate before preserving the original rows.
- Do not merge phone and XIAO sessions as if they were the same sensor distribution.
- Window only within one session, animal, source, placement, and continuous valid interval.
- Split model development by animal before generating overlapping windows.
- Preserve raw exports read-only; create derived datasets with versioned code and manifests.
- Never train from live label columns as if they were independently adjudicated truth.
- Never pool sources, placements, species, farms, calibration states, or protocol versions without
  an explicit, registered domain-generalization analysis.

The XIAO wire format and time-anchor rules are specified in [`protocol/ble-v2.md`](../../protocol/ble-v2.md).
