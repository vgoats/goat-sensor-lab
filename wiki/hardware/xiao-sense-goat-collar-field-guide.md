# XIAO nRF52840 Sense: sensor inventory and goat collar experiment

Updated 7 October 2026. This guide covers the original XIAO nRF52840 **Sense** connected to Ravi's Mac, and separates hardware capability from readings actually captured. It is an experiment plan for indoor, stall-fed goats.

## Device observed on this Mac

macOS USB enumeration reports `Seeed XIAO nRF52840 Sense` on `/dev/cu.usbmodem1101` (USB vendor 0x2886, product 0x8045). This verifies that the board is connected and exposes a serial interface. A second Sense board was also connected and both subsequently streamed live IMU data over BLE. The repository records a separate successful USB/BLE desk test on 5 August 2026 in [the earlier board note](xiao-nrf52840-sense.md).

## What is physically on the board

| Part | Direct output or function | Boundary |
|---|---|---|
| ST LSM6DS3TR-C 3-axis accelerometer | Signed X/Y/Z acceleration, raw 16-bit counts or converted g | Measures board motion plus gravity; not walking distance by itself |
| ST LSM6DS3TR-C 3-axis gyroscope | Signed X/Y/Z angular rate, raw counts or degrees/second | Measures rotation rate; integrated heading drifts |
| IMU die temperature sensor | Raw temperature register or converted °C | Chip temperature, **not goat body temperature** |
| Digital PDM microphone | Audio waveform samples after PDM conversion; amplitude and spectral features can be computed | Acoustic signal is affected by enclosure, wind, other goats, power, and privacy |
| nRF52840 2.4 GHz radio | BLE advertising, connections, RSSI observed by receiver, custom GATT data; NFC capability | **No Wi-Fi**, cellular, GPS, or LoRa hardware; BLE RSSI is a rough link measurement, not location |
| Battery circuit and ADC | Battery voltage estimate and charge indication with a connected Li-ion battery | Battery is separate; voltage is not an accurate state-of-charge or fuel gauge by itself |
| 2 MB external flash | Local buffered records if firmware implements storage | Not continuous long-term audio storage |
| GPIO / ADC / I2C / SPI / UART | Read external pressure, contact vibration, temperature, or other sensors after wiring and firmware | These sensors are **not built in** |
| USB-C | Power, programming, serial data | USB enumeration does not prove live sensor output |

There is no onboard magnetometer, barometer, environmental temperature probe, RFID reader, heart-rate sensor, or direct rumen/jaw pressure sensor. The IMU has configurable ±2/4/8/16 g acceleration and ±125/250/500/1000/2000 °/s angular-rate ranges, a 4 KB FIFO, and embedded step/motion events. Those events are generic chip functions; a chip “step count” is not a validated goat step count. Sources: [Seeed board guide](https://wiki.seeedstudio.com/XIAO_BLE/), [ST device page](https://www.st.com/en/mems-and-sensors/lsm6ds3tr-c.html), [ST datasheet](https://www.st.com/resource/en/datasheet/lsm6ds3tr-c.pdf).

## Raw values to record

| Field | Unit | Why retain it |
|---|---|---|
| `sequence`, `board_uptime_ms`, host receive time | count, ms, timestamp | Detect dropped packets, clock drift, and align video; BLE arrival time is not sample time |
| `ax`, `ay`, `az` | raw counts **and/or** g | Motion intensity, tilt, head movement, vibration patterns |
| `gx`, `gy`, `gz` | raw counts **and/or** °/s | Head turns, rotations, movement transitions |
| `imu_temp` | °C | Device thermal diagnostics only |
| `battery_mv`, charging state | mV, boolean | Power and missing-data interpretation |
| `audio_samples` or short derived features | PCM samples or feature units | Optional jaw/chewing sound experiment; keep disabled in first IMU comparison |
| BLE RSSI, connection/disconnection and loss counts | dBm, events/count | Link quality and completeness, not animal behavior |
| mount, orientation, firmware, range, nominal/achieved rate | metadata | Reproducible calibration and analysis |

The current repository firmware is narrower than the hardware: it advertises 13 or 26 Hz, ±4 g, ±500 °/s, and sends a 20-byte BLE packet containing `sequence`, `boardUptimeMs`, three acceleration values in milli-g, and three gyro values in hundredths of a degree/second. It also exposes BLE capability, control, status, and time-anchor characteristics. It does **not** transmit microphone, IMU temperature, battery voltage, or raw IMU register counts. See [firmware source](../../firmware/xiao-nrf52840-sense/src/main.cpp). Six axes are read sequentially, so this is a practical motion stream rather than a perfectly simultaneous hardware snapshot.

At 26 samples/s, 20 payload bytes imply about 520 bytes/s or 45 MB/day before BLE, timestamps, metadata, and file overhead. Continuous audio is far more expensive: mono 16-bit PCM at 16 kHz is about 32 kB/s or 2.76 GB/day. These are calculated payload estimates, not measured battery or radio throughput.

## Sampling rate and battery planning

For a labeled animal trial, begin with 26 Hz accelerometer and gyroscope data to compare rumination, feeding, and other head movements. About 13 Hz accelerometer-only data is a reasonable starting point for broad activity and posture. If individual chew events are not resolved at 26 Hz, test a higher rate (for example 52 Hz) at a jaw-coupled mount before choosing a production rate. The cited 10-versus-20 Hz sheep/goat result used a **pressure noseband**, so it does not validate a rate for this IMU on a collar. Current repository firmware exposes only 13 and 26 Hz; higher rates require firmware changes.

In the 7 October 2026 two-board hand test, each board delivered 1,560 samples over 120 seconds at 13 Hz with zero sequence gaps. A preceding simultaneous 26 Hz trial lost many BLE packets. This is a transport observation, not evidence that 13 Hz can classify goat rumination. Record one board at 26 Hz or improve BLE transport before relying on paired 26 Hz recordings. The hand movements verify motion capture only.

Battery life depends on **capacity in mAh and measured average current**, not voltage alone. A common CR2032 round coin cell is 3 V with a 235 mAh *typical* rating at a light test load ([Energizer datasheet](https://data.energizer.com/pdfs/cr2032.pdf)). Its usable capacity decreases at higher loads and its voltage can sag during radio bursts ([Energizer discharge guide](https://data.energizer.com/pdfs/lithiumcoin_appman.pdf)). It is not a 5 V battery. Do not connect 5 V to the XIAO battery pads; follow the [Seeed battery wiring guide](https://wiki.seeedstudio.com/XIAO_BLE/).

| Assumed **whole-device** average current | Ideal CR2032 arithmetic: 235 mAh / current |
|---:|---:|
| 1 mA | 235 hours, about 9.8 days |
| 5 mA | 47 hours, about 2 days |
| 10 mA | 23.5 hours, about 1 day |

These are upper-level arithmetic examples, **not measured runtimes or predictions for this board**. High drain, BLE pulses, regulator losses, and cutoff voltage can shorten operation. For 30 days on 235 mAh, the whole device would need to average at most about 0.33 mA; for 90 days, about 0.11 mA, before derating. Continuous sampling and BLE streaming with today's firmware should not be assumed to meet those limits. The [ST IMU datasheet](https://www.st.com/resource/en/datasheet/lsm6ds3tr-c.pdf) lists chip-mode currents (for example 9 µA for low-power accelerometer operation and 0.29 mA for accelerometer plus gyro at 52 Hz), but these exclude the XIAO processor, radio, and board circuitry.

Measure the **complete board** at its battery input in 13 Hz accelerometer-only, 26 Hz six-axis sampling, and BLE streaming modes, including current peaks and average charge over a representative session. Then estimate runtime as usable battery mAh divided by measured average mA, and confirm with a discharge test on the selected cell. Months of runtime may require sleep, intermittent or event-triggered sensing, and infrequent batched transmissions; any such change must be validated again against labeled goat behavior.

## What behaviors can be inferred

| Outcome | Sensor evidence | Confidence before field validation |
|---|---|---|
| Stillness versus active movement; head turns | Neck/ear acceleration and gyro | Plausible research target |
| Standing versus lying | Gravity-relative orientation plus movement | Plausible, mount rotation and individual fit matter |
| Head near feeder / feeding activity | Head motion with video context | Plausible, eating and rumination can overlap in motion features |
| Rumination duration | Repetitive jaw movement or contact vibration, potentially audio | **Not directly measured by a loose neck collar**; needs labeled goat data |
| Individual chews, cud cycles | Jaw-coupled pressure/contact sensor preferred | Not established with this board alone on a loose collar |
| Disease, fever, pregnancy, estrus, exact feed intake | No direct measurement | Do not claim from these signals |

In an [indoor dairy-goat ear accelerometer study](https://doi.org/10.24072/pcjournal.545), rumination AUC fell to 0.644 when testing goats absent from training. That is a warning against reporting a good random-window score as performance on new goats. A [sheep/goat jaw-pressure study](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0285933) found useful feeding/rumination discrimination with a fitted noseband system, and 20 Hz improved performance over 10 Hz in that study. Its results do not transfer automatically to this IMU or to a loose neck collar.

## Placement comparison

1. **Side of neck, high and close to the jaw angle:** practical collar candidate. Place the sealed module on a consistent side and orientation where head/jaw motion couples to the enclosure, away from the throat and feeder impacts. Expect good activity/head-motion data; treat rumination as an open hypothesis.
2. **Under-jaw or cheek-adjacent strap on a fitted halter:** stronger mechanical coupling to jaw motion. The sensor must not rub the mouth, obstruct eating, create pressure sores, or snag. This is the best IMU placement to compare for chewing patterns, subject to veterinary-approved fit.
3. **Noseband pressure or jaw-side contact sensor wired to XIAO:** best direct jaw-motion candidate, but requires another sensor, careful fit and calibration. The cited JAM-R study used pressure-sensitive tubing; the XIAO does not contain this sensor.
4. **Ear mount:** useful comparison for head movement and practical attachment, but the indoor-goat study shows uncertain transfer to unseen animals for rumination.

For a first trial, compare **neck versus jaw-adjacent** on the same goats in counterbalanced sessions. Keep the board in a smooth, sealed, padded, strain-relieved, breakaway enclosure. Never attach bare electronics, loose wires, or an exposed battery directly to an animal. Stop immediately for rubbing, distress, entanglement, impaired feeding/drinking, or attachment failure. A veterinarian and site husbandry team should approve fit before animal use.

## First experiment

1. **Bench:** confirm Sense SKU, flash or inspect the Sense-target firmware, rotate all three axes, tap the enclosure, and check approximately 1 g vector magnitude at rest. Verify rate, packet sequence, gyro zero drift, BLE range in the actual shed, battery runtime, and the microphone only if it will be used.
2. **Mount pilot:** test fit briefly under supervision; document side, orientation, enclosure mass, strap tension, movement/slip, skin contact, feed access, and any mount changes. Use the same placement definition for every session.
3. **Capture:** record six axes at 26 Hz with board sequence/uptime and phone timestamps. Film an overhead view for posture and a feeder-side view that resolves muzzle/jaw movement. Synchronize with a visible tap/gesture at start and end. Capture feeding, post-feed rumination, standing, lying, walking, grooming, and handling in normal husbandry.
4. **Label:** independently annotate feeding, rumination, neither/unknown; separately label lying, standing, active movement/unknown. Flag occlusion, loose mount, handling, and packet loss. Use the repository [ethogram](../experiments/ethogram.md) and [video-sync procedure](../experiments/video-sync-and-annotation.md).
5. **Compare mounts:** quantify labeled minutes per behavior, valid data, packet loss, achieved rate, welfare issues, and false positives. Train simple features first: acceleration magnitude/variance, gravity orientation, gyro energy, periodicity, and short-window spectral power. Split by **animal before windowing**; report per-class precision/recall/F1 and animal-held-out results.
6. **Decision:** if neck IMU cannot reliably separate rumination from feeding/grooming on unseen goats, move to jaw-adjacent IMU or a pressure/contact sensor. Do not infer rumination just because rhythmic peaks appear in one animal.

The repository's fuller [pilot protocol](../experiments/pilot-protocol.md) contains staged sample sizes, welfare stops, prespecified evaluation, and external-validation steps. Its stage sizes are planning targets, not a powered study.

## SDK and starting points

- [Seeed XIAO nRF52840 board setup and pin map](https://wiki.seeedstudio.com/XIAO_BLE/)
- [Seeed IMU usage and serial example](https://wiki.seeedstudio.com/XIAO-BLE-Sense-IMU-Usage/)
- [Seeed LSM6DS3 Arduino driver](https://github.com/Seeed-Studio/Seeed_Arduino_LSM6DS3): `readRawAccelX/Y/Z`, `readRawGyroX/Y/Z`, float conversions, `readRawTemp`, `readTempC`
- [Seeed microphone usage](https://wiki.seeedstudio.com/XIAO-BLE-Sense-PDM-Usage/) and [microphone library](https://github.com/Seeed-Studio/Seeed_Arduino_Mic)
- [Existing XIAO firmware](../../firmware/xiao-nrf52840-sense/src/main.cpp) and [validation roadmap](../roadmap/validation-roadmap.md)

Use the Sense board target `seeed-xiao-afruitnrf52-nrf52840-sense`. The non-Sense target previously built but failed IMU initialization in this repository's desk test.
