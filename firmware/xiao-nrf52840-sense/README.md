# XIAO nRF52840 Sense firmware

This firmware reads the onboard LSM6DS3TR-C accelerometer and gyroscope and streams raw,
timestamped samples through a custom BLE GATT service. It intentionally leaves the microphone
disabled for the first experiments.

## Build

```bash
pio run
pio run --target upload
pio device monitor
```

The PlatformIO environment follows Seeed's official
[XIAO nRF52840 PlatformIO guide](https://wiki.seeedstudio.com/xiao_nrf52840_with_platform_io/)
and uses Seeed's board platform rather than the stock Nordic platform. The `board` value must be
`seeed-xiao-afruitnrf52-nrf52840-sense`. The non-Sense target
`seeed-xiao-afruitnrf52-nrf52840` can compile and upload, but it selects the wrong Arduino variant
for this project and caused the onboard IMU to appear unavailable during physical bring-up.

The board must be the **Sense** variant. Run the official IMU example and confirm `WHO_AM_I =
0x6A` before field use. See [`../../wiki/hardware/xiao-nrf52840-sense.md`](../../wiki/hardware/xiao-nrf52840-sense.md).

## Physical bring-up record

The first XIAO Sense desk test was completed on 2026-08-05 with the board advertised as
`GoatSensor-911806CBE88F40D2`.

Checks performed:

- flashed the firmware with PlatformIO 6.1.19 and the Sense board target;
- confirmed the onboard LSM6DS3TR-C produced acceleration and gyroscope values over USB serial;
- confirmed BLE capabilities reported `"imu":"LSM6DS3TR-C"` and rates `[13,26]`;
- confirmed BLE stream notifications delivered 20-byte packets with sequence, uptime,
  acceleration, and gyroscope values; and
- confirmed the Android app on an Infinix X6873 recorded and saved a 147-sample XIAO session at
  26 Hz.

If a future board reports `"imu":"unavailable"` or Android records zero samples, first verify
`platformio.ini` still uses the Sense target, rebuild, and reflash before suspecting soldering or
hardware damage. No soldering is required for USB flashing, serial IMU proof, BLE advertising, or
onboard IMU streaming.

## Control message

Write three little-endian bytes to `CONTROL`:

```text
byte 0: 0 = stop, 1 = stream
bytes 1-2: uint16 sample rate; supported values are 13 or 26 Hz
```

The 20-byte stream packet and board-ID handshake are documented in
[`../../protocol/ble-v2.md`](../../protocol/ble-v2.md).

The PlatformIO board platform is pinned to commit
`ee406566f0f12d07f135f6ae846b86a8f62628b0`, the Seeed LSM6DS3 library is pinned to
`2.0.7`, and the build flag is compile-time checked against protocol v2. Update these pins only
through a reviewed compatibility change with a firmware build and hardware regression test.
