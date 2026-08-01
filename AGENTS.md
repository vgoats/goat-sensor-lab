# Goat Sensor Lab Agent Guide

## Product boundary

This repository owns wearable-sensor experimentation for indoor, stall-fed goats and sheep.
It does not own grazing, GPS geofencing, camera identity tracking, or the Goat OS production app.

## Architecture rule

Every sensor source must emit the same `SensorFrame` domain model. The Android phone is the
reference source now; XIAO nRF52840 Sense BLE becomes another adapter, not a second data model.

## Evidence rule

- Cite primary papers or official hardware documentation for scientific and hardware claims.
- Mark Reddit, supplier messages, and marketplace listings as anecdotal or vendor claims.
- Report animal-independent validation separately from random row/window splits.
- Never claim the prototype diagnoses disease, pregnancy, or estrus. It produces research signals.

## Documentation tone rule

- Use neutral, professional headings that name the subject directly.
- Never characterize readers by presumed technical ability, sophistication, or intelligence.
- Present the material directly; do not describe how its complexity was adjusted for the audience.
- Make explanations precise and well structured without compromising technical accuracy.

## Verification

- Android: `./gradlew testDebugUnitTest assembleDebug`
- Device: install to the explicit physical ADB serial; when it is unavailable, use an explicit
  emulator serial and report that verification boundary.
- Analysis: `uv sync --directory analysis --extra dev --frozen && uv run --directory analysis pytest`
- Firmware: `uvx --from platformio==6.1.19 platformio run -d firmware/xiao-nrf52840-sense`.
