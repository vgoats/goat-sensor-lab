# Evidence Matrix

This matrix prioritizes indoor or directly transferable goat/sheep evidence. Performance values are not comparable unless animal split, placement, labels, and environment are also comparable. Search and extraction follow the [literature search method](literature-search-method.md); machine-readable provenance is in the [evidence ledger](../../references/evidence-ledger.json), last reconciled 2026-08-02.

| Source | Animals / setting | Sensor and labels | Strongest finding | Limitation / status |
|---|---|---|---|---|
| [Mauny et al., 2025](https://doi.org/10.24072/pcjournal.545) | 8 indoor Alpine goats | Ear 3-axis accelerometer, 5 Hz; one human coded synchronized overhead video in Observer XT 16; four CatBoost binary classifiers used engineered accelerometer windows, not video pixels | Tuned models reached AUC 0.800–0.829; held-out-goat AUC fell to 0.644–0.749 | **Independent evidence**; closest direct study, but small, accelerometer-only, and single-observer ground truth |
| [Mauny data](https://doi.org/10.57745/LGZBM1) and [pipeline](https://github.com/smauny/pipeline-act4behav) | Same study | Raw data, labels, feature/preprocessing pipeline | Reproducible starting point for feature/window experiments | **Independent/open research**; repository license must be checked before reuse |
| [Mauny data paper, 2025](https://doi.org/10.1016/j.anopes.2025.100095) | 8 indoor Alpine dairy goats | Ear 3-axis accelerometer at 5 Hz; 24 h capture; approximately 11 h/goat manually coded by one human from synchronized video using Observer XT 16 | Establishes the dataset provenance and human-annotation design behind ACT4Behav; it does not validate video AI | **Direct indoor-goat evidence**; single observer, small cohort, accelerometer-only |
| [Méndez et al., 2025](https://doi.org/10.1016/j.compag.2025.110701) | 15 indoor goats | Neck LIS3DH 10 Hz; eating, walking, inactive | Supports neck-accelerometer indoor classification and animal-independent evaluation | **Independent evidence**; validate details from full paper and replicate on our IMU/mount |
| [Sugi et al., 2025](https://doi.org/10.11357/jsamfe.87.3_197) | Goats; neck inertial sensor | Rumination, foraging, resting, other; acceleration plus angular velocity | Reported 81.9% four-class accuracy and periodic rumination patterns in pitch/yaw angular velocity | **Independent goat evidence**; cohort/split details and Japanese full text require careful replication |
| [Amorim et al., 2024](https://doi.org/10.1016/j.compag.2024.108657) | 18 sheep | Triaxial ADXL345; feeding, rumination, other; multiple low-rate summaries | Random Forest reported 85.2–88.6% accuracy and tested energy-saving sampling intervals | **Independent sheep evidence**; summary/epoch rate is not equivalent to our raw IMU sampling design |
| [Schneidewind et al., 2026](https://doi.org/10.3390/s26041169) | Indoor sheep | Halter/jaw 3-axis accelerometer 10 Hz; eating, rumination, resting | Reported useful rumination/resting performance | **Independent evidence**; small prototype and jaw mount differ from ear/neck IMU |
| [Silva et al., 2026](https://doi.org/10.3390/s26041150) | 20 ewes, indoor/pasture | Cattle collar; feeding and rumination | Feeding agreed more strongly than rumination | **Independent evidence**; cattle device and collar rotation limit transfer |
| [Sheep rumination systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10740880/) | 17 publications reviewed | Accelerometer, pressure, acoustic systems | All included wearable systems used accelerometry; generalization remains a key problem | **Independent synthesis** |
| [RumiWatch validation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10194855/) | Sheep and goats | Pressure noseband plus motion; feeding/rumination | Strong research benchmark for jaw-based sensing | **Independent evidence**; intrusive research halter, not our hardware |
| [Tjøtta lambing study](https://doi.org/10.1038/s41597-026-06660-2) and [data](https://doi.org/10.6084/m9.figshare.28815974.v1) | 61 indoor ewes, 113 births | Raw 20 Hz collar acceleration and device temperature, BLE gateway, synchronized video | Valuable open indoor parturition dataset and directly relevant acquisition architecture | **Independent/open data**; not proof of goat kidding or production performance |
| [Goats on the Move](https://doi.org/10.3390/ani14131977) | Goats, primarily outdoor/grazing | Accelerometer behavior classification | Leave-one-goat-out performance was materially below random splits | **Transfer evidence**; behavior/environment mismatch to stall feeding |
| [Indoor sheep stress proof-of-concept](https://pmc.ncbi.nlm.nih.gov/articles/PMC12944225/) | Small sheep cohort | Custom 3-axis accelerometer 10 Hz | Rumination/resting changed after relocation; classifier performance reported | **Independent early evidence**; small cohort, stress alert still requires larger validation |
| [Morgan-Davies et al., 2024](https://doi.org/10.1016/j.animal.2024.101233) | Goat/sheep welfare synthesis and stakeholder workshops | Multiple PLF technologies and welfare indicators | Supports risk-management alerts while showing limited technology readiness | **Synthesis**, not validation of this device/model |
| [Wang et al., 2025](https://doi.org/10.1016/j.compag.2025.110050) | Sheep monitoring review | Wearable and non-wearable sensing | Current map of technologies, challenges, and adoption gaps | **Synthesis**; heterogeneous settings and no Goat Sensor Lab accuracy claim |
| [CABRA, 2026](https://doi.org/10.3390/agriengineering8080301) and [repository](https://github.com/knklB/IMUcabra) | Pasture dairy-goat hardware proof of concept | ~60 g collar, 6-axis IMU/GPS/ESP32, ESP-NOW, 20 Hz | Window-level F1 >0.99 fell to animal-held-out macro-F1 0.31 | **Transfer-only pasture/open-hardware evidence**; strong domain-shift warning, not indoor validation |
| [Ferreira et al., 2026](https://doi.org/10.3390/agriculture16020259) | 28 Charnequeira goats around kidding | Collar acceleration/temperature at 20 Hz with collar/edge inference | Demonstrates a two-stage architecture for its registered reproductive endpoint | **Transfer-only endpoint evidence**; does not validate pregnancy, disease, or core behavior claims |

## Outcome status

| Requested outcome | Current evidence position | Allowed project wording |
|---|---|---|
| Feeding/head-in-feeder | Direct indoor goat evidence exists | “Research model under animal-independent validation” |
| Rumination | Direct goat/sheep evidence exists; generalization is difficult | “Estimated rumination behavior” after validation |
| Lying/standing/activity | Direct evidence exists | “Estimated posture/activity” after validation |
| Abnormal inactivity/not eating | Behavior change can be an alert feature | “Deviation requiring review,” never “sick” |
| Estrus/breeding time | Evidence exists for some proprietary/cattle-derived systems, with variable transfer | Research endpoint only until prospective goat/sheep validation |
| Pregnancy | IMU behavior is not a pregnancy test | No pregnancy claim |
| Lambing/kidding | Research datasets/studies exist | Research prediction only; no unattended management claim |
| Disease diagnosis | Behavior may change with disease/challenge | No diagnosis; veterinary confirmation required |

No paper establishes one wearable and one model as independently validated for every row above across indoor goats and sheep.
