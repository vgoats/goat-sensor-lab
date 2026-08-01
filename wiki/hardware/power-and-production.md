# Power and Production

## The central trade-off

Continuous raw IMU sampling and BLE transmission are research-friendly but battery-expensive. Multi-year life requires sleeping most of the time, transmitting compact summaries, or using short triggered bursts.

For a nominal 600 mAh battery, the average-current budgets are approximately:

| Target life | Ideal average current before derating |
|---|---:|
| 1 year | 68 µA |
| 2 years | 34 µA |
| 3 years | 23 µA |

Real capacity, self-discharge, temperature, radio retries, regulators, and aging reduce these budgets. A XIAO development board streaming six raw axes continuously should not be promised 2–3 years without measured current profiles and a redesigned production PCB.

## Research prototype strategy

| Phase | Sampling and transfer | Power approach |
|---|---|---|
| Bench bring-up | Continuous 25 Hz IMU over USB/BLE | USB power |
| Supervised animal trials | Continuous 25/26 Hz IMU for bounded sessions | Rechargeable cell; recharge between sessions |
| Extended validation | Buffered raw bursts plus low-rate summaries | Larger replaceable/rechargeable collar battery |
| Production research | Always-on low-power acceleration; gyro/microphone only on triggers | Custom PCB, measured sleep states, battery gauge |

Use a neck collar for early prototypes if it safely carries more battery and a robust enclosure. “The entire collar is battery” is not literal: cells must be discrete, protected, flexible only through wiring, isolated from bite/impact, and balanced so the electronics do not rotate. Ear mounting requires a much smaller mass and therefore a tighter energy budget.

## Production design requirements

- low-quiescent-current regulator and power-path design;
- protected cell, charger matched to chemistry, and accessible replacement/charging workflow;
- measured current in sleep, sensing, processing, BLE advertising, connection, and retry modes;
- battery voltage or fuel gauge in telemetry;
- watchdog, brownout recovery, safe OTA/firmware recovery, and local packet-loss counters;
- rounded IP67/IP68 enclosure with pressure management where needed;
- breakaway attachment, anti-rotation geometry, strain relief, and chew/impact resistance;
- unique device identity, traceability, calibration record, and firmware version;
- serviceable manufacturing test points and a jig;
- radio, battery transport, materials, and market certifications reviewed before scale-up.

## Data policy for battery life

**Inference:** a practical product can keep a low-power accelerometer active, compute orientation/activity features locally, wake the gyro for ambiguous/high-motion periods, and upload summaries plus selected evidence windows. Raw continuous data remains essential during model development and audits, but it need not be transmitted continuously in the final product.

The microphone should remain off until IMU-only accuracy is measured. Wi-Fi on every wearable is usually a poor fit for battery life. A fixed powered gateway can use Wi-Fi/4G while the wearable uses BLE or another low-power link.

## Claims that remain unknown

- exact battery life for the repository firmware;
- safe maximum battery mass for each goat/sheep breed and mount;
- radio reliability through animals, metal pens, wet surfaces, and partitions;
- enclosure ingress protection and impact life;
- recharge/replacement labor at 2,000 to 1,000,000 devices.

Resolve these with instrumented current measurements, veterinary/animal-welfare review, and staged field trials before a production claim.
