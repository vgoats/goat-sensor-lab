# Open-Source Reference Index

These upstream repositories were inspected as **references**, not copied into Goat Sensor Lab.
Their code remains under each upstream project's license. Local checkouts used during research live
outside this repository under `/Users/ravi/mesha/reference-repos/goat-sensor-lab/` and are not part
of the product or its MIT license.

[`manifest.json`](manifest.json), validated by
[`reference-manifest-v1.schema.json`](../schema/reference-manifest-v1.schema.json), is the portable
manifest template and current inventory: upstream URL, exact commit/tag, retrieval/verification
date, checkout state, license review, purpose, and reuse boundary. Update the manifest in the same
change whenever a checkout is added or advanced. Commit SHAs pin clean Git content; do not describe
a dirty or incomplete working tree as reproducible.

| Upstream project | What we inspect | How it informs this project |
|---|---|---|
| [pipeline-act4behav](https://github.com/smauny/pipeline-act4behav) | Indoor-goat accelerometer preprocessing and behavior-classification pipeline | Goat-specific evidence for labeling, windows, features, and animal-held-out validation |
| [Nordic Android Scanner Compat Library](https://github.com/NordicSemiconductor/Android-Scanner-Compat-Library) | Android BLE scanning compatibility | Reference for robust scanning across Android releases |
| [Nordic Kotlin BLE Library](https://github.com/NordicSemiconductor/Kotlin-BLE-Library) | Structured BLE GATT operations | Reference for production connection/state handling |
| [BLESSED Android Coroutines](https://github.com/weliem/blessed-android-coroutines) | Coroutine-oriented BLE client patterns | Alternative reference for connection lifecycle and errors |
| [Seeed OSHW XIAO Series](https://github.com/Seeed-Studio/OSHW-XIAO-Series) | Board schematics and hardware files | Verifies XIAO nRF52840 Sense hardware boundaries |
| [Seeed LSM6DS3 library](https://github.com/Seeed-Studio/Seeed_Arduino_LSM6DS3) | IMU driver and sensor configuration | Reference for accelerometer/gyroscope acquisition on the board |
| [Edge Impulse Android inferencing example](https://github.com/edgeimpulse/example-android-inferencing) | On-device model integration | Future deployment reference after valid animal data exists |
| [Edge Impulse mobile client](https://github.com/edgeimpulse/mobile-client) | Mobile sensor collection and inferencing | Reference for phone-based engineering collection workflows |
| [Google LiteRT samples](https://github.com/google-ai-edge/litert-samples) | Android edge-model execution | Future model runtime reference, not a behavior model |
| [phyphox Android](https://github.com/phyphox/phyphox-android) | High-rate phone sensor recording | Reference for sensor timing and export ergonomics |
| [AWARE Android client](https://github.com/awareframework/aware-client) | Mobile sensing architecture | Reference only; clean Git LFS-aware checkout, not animal-behavior evidence |
| [BORIS](https://github.com/olivierfriard/BORIS) | Video/audio behavior coding and event export | Annotation-method reference; GPL-3.0, with exact version recorded in every experiment |
| [IMUcabra](https://github.com/knklB/IMUcabra) | Open goat collar, ESP-NOW telemetry, synchronization, and embedded inference | Pasture/GPS transfer reference only; not indoor validation |

The active AWARE checkout is now a clean Git LFS-aware shallow clone at the pinned commit. The
ACT4Behav checkout is clean, but no root license was found; inspect and reproduce the published
method, and do not copy its code unless upstream licensing is resolved.

Human-activity-recognition repositories and cattle/wildlife projects are transfer references only.
They do not establish accuracy for indoor goats or sheep. Papers and datasets with direct
small-ruminant evidence are catalogued in the [evidence matrix](../wiki/research/evidence-matrix.md)
and [open-source and datasets guide](../wiki/research/open-source-and-datasets.md).
