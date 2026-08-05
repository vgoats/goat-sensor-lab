# XIAO nRF52840 Sense

## Confirmed hardware

**Official specification:** the **Sense** variant contains an nRF52840 microcontroller with Bluetooth Low Energy/NFC, an LSM6DS3TR-C 6-axis IMU (3-axis accelerometer plus 3-axis gyroscope), a PDM microphone, 2 MB onboard flash, exposed GPIO/I2C/SPI/UART pads, USB-C, and onboard lithium-battery charging. See [Seeed's board guide](https://wiki.seeedstudio.com/XIAO_BLE/), [IMU guide](https://wiki.seeedstudio.com/XIAO-BLE-Sense-IMU-Usage/), [schematic](https://files.seeedstudio.com/wiki/XIAO-BLE/Seeed_Studio_XIAO_nRF52840_PDF.pdf), and [ST's LSM6DS3TR-C documentation](https://www.st.com/en/mems-and-sensors/lsm6ds3tr-c.html).

The non-Sense XIAO nRF52840 does **not** contain the IMU or microphone. Marketplace photos often show the same top side, so the order line must explicitly say `XIAO nRF52840 Sense` and `6-axis IMU`.

## What it gives the project

- raw acceleration `x/y/z` for gravity-relative orientation and motion;
- raw angular velocity `x/y/z` for head/ear rotation patterns;
- configurable sampling suitable for supervised behavior experiments;
- BLE for live phone or programmable-gateway transfer;
- enough compute for later feature extraction or TinyML inference;
- flash for firmware and limited buffering, subject to endurance and capacity design.

The microphone is optional. **Inference:** jaw/neck vibration and chewing sounds may help distinguish feeding and rumination, but continuous audio increases power, storage, privacy, enclosure, and validation complexity. Keep it disabled in the first IMU study.

## What it does not give

- no battery is included;
- no Wi-Fi, 4G, GPS, LoRa, or cellular modem;
- no reliable core-body-temperature sensor;
- no production enclosure, strap, breakaway, charging connector, or fuel gauge;
- no ready-made behavior classifier;
- no guarantee that a third-party BLE gateway understands our custom service.

The IMU's embedded temperature reading is principally a sensor/device temperature. It can be studied as a trend, but it is not equivalent to rectal core temperature.

## Phone versus board

The phone and XIAO both expose 3-axis acceleration and 3-axis gyroscope data, so the phone can prove the software pipeline. They are not measurement-equivalent: sensor model, range, filtering, clock, orientation, enclosure coupling, and attachment location differ. The production research model must be trained and evaluated using XIAO data from the intended ear or neck mount.

## First-board bring-up

1. Verify the received board is the Sense variant.
2. Connect USB-C; no soldering is required for USB firmware and serial IMU tests.
3. Confirm the firmware build uses the PlatformIO board target
   `seeed-xiao-afruitnrf52-nrf52840-sense`. Do not use the plain
   `seeed-xiao-afruitnrf52-nrf52840` target for Sense firmware.
4. Flash a simple official IMU example and verify all six axes.
5. Flash the repository BLE firmware and verify capabilities, control, stream, status, and time-anchor characteristics.
6. Compare sequence continuity, achieved rate, axes at rest, rotations, and known taps against the phone recorder.
7. Add a battery only after USB behavior is stable. A permanent battery connection normally requires soldering or a purpose-built carrier/connector.
8. Do not place the development board directly on an animal; first build a rounded, sealed, strain-relieved, breakaway prototype.

## 2026-08-05 desk proof

A physical Seeed Studio XIAO nRF52840 Sense board, SKU `102010469`, was tested over USB-C and BLE.
The visible board silkscreen read `XIAO nRF52840`, while the package label identified the Sense
SKU. This is expected enough that verification should rely on the order/package identity and IMU
proof, not top-side silkscreen alone.

Observed results:

- PlatformIO Sense board target:
  `seeed-xiao-afruitnrf52-nrf52840-sense`.
- USB serial IMU proof showed stable acceleration near gravity and non-zero gyroscope readings.
- BLE advertised as `GoatSensor-911806CBE88F40D2`.
- BLE capabilities included `"imu":"LSM6DS3TR-C"`, `"rates_hz":[13,26]`,
  `"accel_g":4`, `"gyro_dps":500`, and `"packet_bytes":20`.
- A direct BLE stream check received 48 packets in 3 seconds.
- The Infinix X6873 Android app recorded a 26 Hz XIAO session and saved 147 samples.

Failure mode found during bring-up: using the plain non-Sense PlatformIO board target allowed the
firmware to compile and upload, but the IMU initialization failed and the board reported
`"imu":"unavailable"`. The fix is the Sense board target; no soldering is required for the onboard
IMU.

Seeed documents TensorFlow Lite/TinyML examples for the board, but that means the board can run a trained model; it does not provide a goat/sheep model. See [Seeed's TinyML guide](https://wiki.seeedstudio.com/XIAO-BLE-Sense-TFLite-Getting-Started/) and [Edge Impulse's board documentation](https://docs.edgeimpulse.com/hardware/boards/seeed-xiao-nrf52840-sense).
