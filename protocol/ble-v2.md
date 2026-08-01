# BLE Sensor Protocol v2

Protocol v2 carries raw XIAO nRF52840 Sense IMU observations into the same `SensorFrame`
used by the Android phone source. All multi-byte fields are little-endian.

The firmware advertises `GoatSensor-<16 hex digits>`. The suffix is derived from the
nRF52840 factory device ID. The Android app requires this ID before scanning, so it does
not silently connect to the first board in a multi-animal shed.

## GATT service

| Name | UUID suffix | Operation | Purpose |
|---|---|---|---|
| Service | `0001` | - | `7c1e0001-6b1b-4d4f-9d1a-c9986f217c10` |
| Capabilities | `0002` | Read | Protocol, device identity, firmware, IMU, rates, ranges, and read mode |
| Control | `0003` | Write with response | Start/stop and select sampling rate |
| Stream | `0004` | Notify | Raw 20-byte IMU observations |
| Status | `0005` | Read/notify | Active rate and dropped-sample count |
| Time anchor | `0006` | Read/notify | Map board uptime to phone clocks |

The UTF-8 capabilities JSON contains `protocol`, `firmware`, `device_id`, `imu`,
`rates_hz`, `accel_g`, `gyro_dps`, `packet_bytes`, and `sample_read`. Android archives the
observed JSON and does not substitute expected constants for research provenance.

## Start handshake

1. The phone scans for the configured `GoatSensor-<ID>` and connects only to that board.
2. It reads capabilities and fails closed unless the device identity, protocol, requested
   rate, packet size, ranges, and sample-read mode match the app contract.
3. It enables time-anchor, stream, and status notifications, then reads initial status.
4. It writes the 3-byte control command: `enabled:uint8`, `rate_hz:uint16`.
5. The board sends a fresh time anchor and status, and acknowledges the control write.
6. The app enters `Recording` only after the write, anchor, and active-rate status all agree.
   Earlier stream packets are ignored. A 15-second handshake timeout fails the session closed.

This avoids treating a queued GATT operation as a started experiment.

## Time-anchor packet: 12 bytes

| Bytes | Type | Field | Unit |
|---:|---|---|---|
| 0 | `uint8` | Protocol version | `2` |
| 1 | `uint8` | Flags | Reserved |
| 2-3 | `uint16` | Reserved | - |
| 4-7 | `uint32` | Next sample sequence | counter |
| 8-11 | `uint32` | Board uptime | ms |

The phone maps the fresh anchor to the midpoint between issuing the control request and
receiving the anchor, and stores half of that observed interval as synchronization uncertainty.
This is a bounded best-RTT estimate, not sub-millisecond clock synchronization. The anchor is not
periodically reset. Losing an unrelated BLE notification therefore cannot move future sample
timestamps backward.

## Stream packet: 20 bytes

| Bytes | Type | Field | Unit |
|---:|---|---|---|
| 0-3 | `uint32` | Sample sequence | Detect loss/reordering |
| 4-7 | `uint32` | Board uptime | ms |
| 8-13 | `int16[3]` | Acceleration x/y/z | milli-g |
| 14-19 | `int16[3]` | Gyroscope x/y/z | 0.01 degree/s |

The phone computes unsigned `sample_uptime - anchor_uptime`, which also handles one 32-bit
uptime wrap, and adds that delta to both phone anchor clocks. BLE notification-arrival time is
not used as sample time. Sequence gaps identify scheduler or notification loss.

## Status packet: 8 bytes

| Bytes | Type | Field | Unit |
|---:|---|---|---|
| 0 | `uint8` | Protocol version | `2` |
| 1 | `uint8` | Flags | bit 0 = streaming |
| 2-3 | `uint16` | Active sample rate | Hz |
| 4-7 | `uint32` | Dropped samples since boot | counter |

The app records the latest observed device counter separately from sequence gaps observed by
Android. The status counter includes firmware scheduler overruns and failed BLE notifications.
It is cumulative since boot, so experiments that require an exact per-session value must retain
both the initial and final observations. Firmware notifies status at stream start and every five
seconds while streaming. Android also persists its own final sequence-gap count as
`receiver_missing_samples`, including loss between the fresh anchor and first accepted packet.

## Measurement limitation

The current firmware reads the six axes sequentially through the vendor library. They are a
closely timed IMU observation, not a proven hardware-latched or FIFO-synchronized six-axis
sample. A later firmware revision can use data-ready/FIFO burst reads if experiments show that
the distinction affects classification.

## Canonical storage units

The Android decoder converts acceleration to `m/s²`, gyroscope to `rad/s`, and mapped monotonic
time to nanoseconds. Unit conversion does not establish traceable project calibration. It also
retains board uptime in `source_uptime_ms`. Phone and board rows use the canonical CSV schema in
[`../schema/samples-v1.schema.json`](../schema/samples-v1.schema.json); calibration status,
method, configuration, and coefficient-artifact provenance belong in the versioned
[`experiment-manifest-v1`](../schema/experiment-manifest-v1.schema.json). Preserve the untouched
SI-converted export when applying a later calibration transform to a derived dataset.
