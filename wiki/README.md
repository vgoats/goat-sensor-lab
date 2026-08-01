# Goat Sensor Lab Wiki

This wiki defines a research system for **indoor, stall-fed goats and sheep**. The immediate goal is to collect synchronized wearable-sensor and observation data, then validate models for feeding, rumination, posture, and activity. GPS grazing, virtual fencing, and aversive cues are outside scope.

## Evidence labels

- **Independent evidence**: peer-reviewed paper, public dataset, standards body, or regulatory filing.
- **Official specification**: manufacturer documentation for a component.
- **Vendor claim**: supplier or product statement not independently reproduced for our animals and sheds.
- **Inference**: engineering conclusion drawn from cited evidence; it still requires testing.
- **Unknown**: information not established by a credible public source.

No current product is independently validated across every requested outcome for indoor goats and sheep. This project must not claim to diagnose sickness or pregnancy, or to determine estrus, kidding, or lambing, until each specific outcome is prospectively validated on unseen animals and farms. Initial health outputs are research signals and alerts for human review.

## System and data

- [System architecture](architecture/system.md)
- [Data contract](data/data-contract.md)
- [XIAO nRF52840 Sense](hardware/xiao-nrf52840-sense.md)
- [Power and production](hardware/power-and-production.md)

## Experiments

- [Ethogram](experiments/ethogram.md)
- [Pilot protocol](experiments/pilot-protocol.md)
- [Video synchronization and annotation](experiments/video-sync-and-annotation.md)

## Research

- [Evidence matrix](research/evidence-matrix.md)
- [Literature search method](research/literature-search-method.md)
- [Halter and IP landscape](research/halter-and-ip-landscape.md)
- [Commercial landscape](research/commercial-landscape.md)
- [Open source and datasets](research/open-source-and-datasets.md)

## Governance

- [Ethics and claims](welfare/ethics-and-claims.md)
- [Validation roadmap](roadmap/validation-roadmap.md)
- [Release verification and physical-device boundary](verification/release-verification.md)

## Non-negotiable research rules

1. The Android phone is an **engineering sensor source only**. It tests recording, timestamps, labels, and export; it is not a substitute for animal-mounted XIAO data.
2. The XIAO nRF52840 Sense is the final research source for wearable experiments. A model trained only on phone data is not an animal-behavior model.
3. Preserve raw accelerometer and gyroscope samples, monotonic timing, placement, device identity, animal identity, and label provenance.
4. Split training and evaluation by animal. Randomly splitting overlapping windows from the same animal gives misleading results.
5. Keep ingestive behavior, posture/activity, welfare observation, and invalid-data status as separate label heads.
6. Human care, visual checks, rectal clinical temperature where required, and veterinary assessment remain authoritative.
