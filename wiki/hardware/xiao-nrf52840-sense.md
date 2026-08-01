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
3. Flash a simple official IMU example and verify all six axes.
4. Flash the repository BLE firmware and verify capabilities, control, stream, status, and time-anchor characteristics.
5. Compare sequence continuity, achieved rate, axes at rest, rotations, and known taps against the phone recorder.
6. Add a battery only after USB behavior is stable. A permanent battery connection normally requires soldering or a purpose-built carrier/connector.
7. Do not place the development board directly on an animal; first build a rounded, sealed, strain-relieved, breakaway prototype.

Seeed documents TensorFlow Lite/TinyML examples for the board, but that means the board can run a trained model; it does not provide a goat/sheep model. See [Seeed's TinyML guide](https://wiki.seeedstudio.com/XIAO-BLE-Sense-TFLite-Getting-Started/) and [Edge Impulse's board documentation](https://docs.edgeimpulse.com/hardware/boards/seeed-xiao-nrf52840-sense).
