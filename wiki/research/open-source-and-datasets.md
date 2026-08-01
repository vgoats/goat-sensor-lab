# Open Source and Datasets

## Directly relevant resources

| Resource | Use | Reuse boundary |
|---|---|---|
| [ACT4Behav pipeline](https://github.com/smauny/pipeline-act4behav) | Closest public indoor-goat feature/preprocessing reference | Inspect and reproduce methods; verify repository license before copying code |
| [Indoor-goat dataset](https://doi.org/10.57745/LGZBM1) and [data paper](https://doi.org/10.1016/j.anopes.2025.100095) | Ear accelerometer plus behavior labels from eight indoor goats | Etalab Open License 2.0 dataset; map schema explicitly and preserve study/domain identity |
| [ACT4Behav archival release](https://doi.org/10.5281/zenodo.12624796) | Reproducible versioned research artifact | Reference exact release |
| [Tjøtta lambing data](https://doi.org/10.6084/m9.figshare.28815974.v1) | Raw 20 Hz ewe data and temperature around lambing | Sheep/parturition research only; do not convert directly into a goat product claim |
| [Tjøtta analysis code](https://doi.org/10.5281/zenodo.16902750) | Parturition feature/model reference | Re-run with grouped animal evaluation |
| [Goat kidding dataset](https://figshare.com/s/925215e8ea73da4b01f2) | Event-centered goat data | Inspect metadata, mount, cohort, and license before use |
| [RAMSMART](https://git.wur.nl/nlas-asg/ramsmart) | Open sheep wearable research design/code | Hardware and license review required |
| [CabriTrack data paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11953975/) | Goat behavior dataset methodology | Grazing labels/domain differ from stall feeding |
| [2025 Japanese goat inertial study](https://doi.org/10.11357/jsamfe.87.3_197) | Evidence that neck angular-velocity rhythms can help identify rumination | Reproduce on our hardware, placement, and unseen animals; reported accuracy is not portable |
| [2024 sheep ingestive-behavior study](https://doi.org/10.1016/j.compag.2024.108657) | Sampling-rate and Random-Forest comparison for feeding/rumination/other | Treat its low-rate summaries as a power-design clue, not a substitute for raw pilot capture |
| [CABRA paper](https://doi.org/10.3390/agriengineering8080301) and [IMUcabra repository](https://github.com/knklB/IMUcabra) | Open goat collar, ESP-NOW telemetry, video synchronization and embedded inference | Pasture/GPS transfer-only; animal-held-out macro-F1 0.31 is a warning about placement/domain shift, not indoor validation |
| [BORIS](https://github.com/olivierfriard/BORIS) and [methods paper](https://doi.org/10.1111/2041-210X.12584) | Independent video/audio event annotation | GPL tool/method reference; still require blinded raters, agreement, immutable tracks, and consensus provenance |

The annotation tools have distinct roles. Goat Sensor Lab uses BORIS as the default reference for
manual sensor-study behavior intervals. The Observer XT is retained only to describe and reproduce
the Mauny study method. CVAT and DeepLabCut labeling address camera tracks, spatial regions, or pose
keypoints and therefore fall under Herdlink when used for fixed-camera identity research. See
[Annotation tooling and responsibility boundary](../experiments/annotation-tooling.md).

## Engineering libraries

| Project | Intended use | License/status note |
|---|---|---|
| [Seeed Arduino LSM6DS3](https://github.com/Seeed-Studio/Seeed_Arduino_LSM6DS3) | XIAO IMU bring-up and firmware access | Official Seeed library; pin a tested release |
| [Nordic Kotlin BLE Library](https://github.com/NordicSemiconductor/Kotlin-BLE-Library) | Android BLE connection/GATT patterns | Prefer maintained stable release; verify license at integration time |
| [Android Scanner Compat](https://github.com/NordicSemiconductor/Android-Scanner-Compat-Library) | Consistent BLE scanning behavior | Useful if native scanner behavior becomes a support problem |
| [BLESSED Kotlin Coroutines](https://github.com/weliem/blessed-android-coroutines) | Alternative BLE client abstraction | Do not combine multiple BLE stacks without a clear reason |
| [LiteRT samples](https://github.com/google-ai-edge/litert-samples) | On-device model packaging/inference | General ML plumbing, not livestock behavior logic |
| [Edge Impulse Android inferencing](https://github.com/edgeimpulse/example-android-inferencing) | Phone-side prototype inference | Engineering reference |
| [Edge Impulse XIAO docs](https://docs.edgeimpulse.com/hardware/boards/seeed-xiao-nrf52840-sense) | Board data/model workflow | Hosted tooling option, not required architecture |
| [phyphox Android](https://github.com/phyphox/phyphox-android) | Mature phone sensor recording reference | GPL; study behavior, do not copy into an incompatible codebase |
| [AWARE Android](https://github.com/awareframework/aware-client) | Mobile sensing and study-management reference | General phone research framework |

## Model-use rules

- Human-activity repositories can teach windowing, feature extraction, and deployment, but their labels and body placement do not transfer to goats/sheep.
- Cattle models are references, not pretrained truth for small ruminants.
- Grazing datasets help test generalization methods but do not replace stall-fed data.
- Record the source, version, license, checksum, preprocessing, and excluded animals for every external dataset.
- Never mix windows from the same animal across training and test, even when an imported study originally used a random split.

## Reproducibility manifest

For each benchmark, capture: source URL/DOI, access date, license, exact files/checksums,
animals/species, environment, placement, sensor/rate/range, labels, split strategy, windowing,
metrics, and deviations from the paper. The current literature extraction is in
[`references/evidence-ledger.json`](../../references/evidence-ledger.json); local checkout pins and
license status are in [`references/manifest.json`](../../references/manifest.json). Keep downloaded
reference repositories outside the product repository; commit only our code, manifests, and lawful
derived metadata.
