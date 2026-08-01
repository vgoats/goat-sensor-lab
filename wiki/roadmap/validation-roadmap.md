# Validation Roadmap

## Stage gates

| Stage | Deliverable | Exit evidence |
|---|---|---|
| 0. Recorder engineering | Phone IMU capture, independent labels, monotonic timing, export | Repeatable stationary/motion captures; schema and rate checks; no animal claim |
| 1. XIAO bench | Raw six-axis BLE stream using the canonical contract | Firmware build; six-axis rotation/tap tests; packet-loss and clock-drift report |
| 2. Safe mount | Ear and/or neck enclosure prototypes | Veterinary/welfare review; mass/balance/heat/ingress/attachment tests; removal criteria |
| 3. Small animal engineering | 6–8 animals/species | Reliable capture, synchronized video, mount tolerance, label agreement, failure log |
| 4. Behavior pilot | At least 24 animals/species across days | Grouped-by-animal feeding/rumination/posture metrics with confidence intervals |
| 5. Robustness | More animals, pens, devices, sizes, days | Stable performance by subgroup, mount, device, operator, and drift conditions |
| 6. Individual-baseline alerts | Longitudinal normal data plus naturally occurring reviewed events | Prospective alert sensitivity, false-alert burden, lead time, and human workflow |
| 7. External validation | New shed/farm and unseen team | Pre-registered prospective metrics and reproducible deployment |
| 8. Productization | Custom PCB/enclosure/gateway/backend | Battery, reliability, security, manufacturing, support, and compliance evidence |

## Outcome order

1. Sensor quality and mount state.
2. Lying, standing, and active movement.
3. Feeding/head-in-feeder and rumination.
4. Daily durations, bouts, and individual-baseline deviations.
5. Welfare review alerts.
6. Separate, specifically designed estrus or parturition studies.

Pregnancy and disease diagnosis are not implied endpoints. Add them only through a distinct clinical study with an accepted reference standard, qualified investigators, and prospective external validation.

## Metrics and release checklist

- animal-grouped train/validation/test partitions are immutable and published in the experiment manifest;
- macro-F1 and balanced accuracy plus per-class precision/recall/F1 and confusion matrix;
- confidence intervals bootstrapped at animal level;
- calibration and abstention/unknown performance;
- achieved rate, packet loss, invalid duration, synchronization error, and battery consumption;
- label prevalence, annotator agreement, adjudication count, and missingness;
- errors stratified by species, breed/size, mount, pen, day, device, and farm;
- model card, data sheet, firmware/app versions, and reproducible scripts;
- explicit claim text approved against the evidence and welfare policy.

## Research risks to retire early

| Risk | Test |
|---|---|
| Phone-to-board domain shift | Compare synchronized phone and XIAO bench motions, then train only on animal-mounted XIAO data |
| Ear versus neck mismatch | Run a paired mount sub-study; do not pool without placement features/evidence |
| BLE loss in metal/occupied sheds | Map packet loss and RSSI with animals, partitions, gates, moisture, and receiver positions |
| Collar rotation / ear orientation drift | Capture orientation landmarks and test robustness/quality detection |
| Label ambiguity | Multi-head ethogram, double annotation, agreement threshold, adjudication |
| Animal leakage | Split by animal before windows and verify IDs in CI |
| Battery promises | Measure current by mode and model duty cycle with derating |
| Alert fatigue | Prospective false alerts per animal-day and documented disposition |

The end state is not “a model with a high random-split score.” It is a traceable sensor-to-alert system whose performance, limits, welfare impact, and operational workload remain credible on animals and sheds that were not used to train it.
