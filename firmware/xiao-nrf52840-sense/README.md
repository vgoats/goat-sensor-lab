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
and uses Seeed's board platform rather than the stock Nordic platform.

The board must be the **Sense** variant. Run the official IMU example and confirm `WHO_AM_I =
0x6A` before field use. See [`../../wiki/hardware/xiao-nrf52840-sense.md`](../../wiki/hardware/xiao-nrf52840-sense.md).

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
